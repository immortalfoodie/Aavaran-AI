import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

import { LinearIsotherm, GABIsotherm, shelfLifeMoistureLimited, requiredWvtr } from './moisture'
import { shelfLifeOxidationLimited } from './oxidation'
import { rateAtTemperature } from './respiration'
import { perforationDesign } from './mapDesign'
import { ratkowskyGrowthRate } from './microbial'
import { botulinumGate, histamineGate, freshCutGate } from './safety'
import { recommendOffline } from './index'

describe('Shared Golden Models Benchmark parity test (TypeScript vs Python)', () => {
  const goldenPath = path.resolve(__dirname, '../../../../tests/golden/golden_models.json')
  const golden = JSON.parse(fs.readFileSync(goldenPath, 'utf-8'))

  it('verifies moisture models match golden benchmark', () => {
    const iso = new LinearIsotherm(0.45, 0.01)
    const m1 = shelfLifeMoistureLimited({
      wvtr: 1.2,
      packAreaM2: 0.05,
      drySolidsKg: 0.2,
      temperatureC: 30.0,
      relativeHumidityPct: 75.0,
      awInitial: 0.20,
      awCrit: 0.45,
      isotherm: iso,
    })
    expect(m1.shelfLifeDays).toBeCloseTo(golden.moisture.shelf_life_days, 1)

    const m2 = requiredWvtr({
      targetDays: 180.0,
      packArea: 0.05,
      drySolids: 0.2,
      temperatureC: 30.0,
      relativeHumidityPct: 75.0,
      awInitial: 0.20,
      awCrit: 0.45,
      isothermSlopeB: 7.0,
    })
    expect(m2.requiredWvtr).toBeCloseTo(golden.moisture.required_wvtr, 1)

    const gab = new GABIsotherm(0.04, 15.0, 0.85)
    expect(gab.moistureAtAw(0.4)).toBeCloseTo(golden.moisture.gab_moisture_at_aw_0_4, 3)
  })

  it('verifies oxidation models match golden benchmark', () => {
    const ox = shelfLifeOxidationLimited({
      otr: 2.0,
      packAreaM2: 0.05,
      productMassKg: 0.25,
      qBudgetMgPerKg: 15.0,
      headspaceVolumeCc: 50.0,
      headspaceO2Fraction: 0.02,
      deltaPAtm: 0.209,
    })
    expect(ox.shelfLifeDays).toBeCloseTo(golden.oxidation.shelf_life_days, 1)
  })

  it('verifies respiration models match golden benchmark', () => {
    const rArr = rateAtTemperature({
      rateRef: 12.0,
      tempRefC: 5.0,
      tempTargetC: 25.0,
      eaKjMol: 55.0,
    })
    expect(rArr.rate).toBeCloseTo(golden.respiration.arrhenius_rate, 1)

    const rQ10 = rateAtTemperature({
      rateRef: 12.0,
      tempRefC: 5.0,
      tempTargetC: 25.0,
      q10: 2.5,
    })
    expect(rQ10.rate).toBeCloseTo(golden.respiration.q10_rate, 1)
  })

  it('verifies MAP perforation sizing matches golden benchmark', () => {
    const perf = perforationDesign({
      respirationO2: 45.0,
      mass: 1.0,
      filmThicknessUm: 30.0,
      holeDiameterUm: 100.0,
      yOut: 0.209,
      yIn: 0.05,
      temperatureC: 20.0,
    })
    expect(perf.holeCount).toBe(golden.map.hole_count)
  })

  it('verifies microbial growth rate matches golden benchmark', () => {
    const growth = ratkowskyGrowthRate({
      organism: 'pseudomonas',
      temperatureC: 25.0,
      waterActivity: 0.98,
      ph: 6.5,
      o2Fraction: 0.209,
    })
    expect(growth.muMaxPerDay).toBeCloseTo(golden.microbial.mu_max_per_day, 1)
  })

  it('verifies safety gates match golden benchmark', () => {
    const bGate = botulinumGate({
      waterActivity: 0.98,
      ph: 6.1,
      o2Fraction: 0.01,
      maxTemperatureC: 30.0,
    })
    expect(bGate.status === 'BLOCK').toBe(golden.safety.botulinum_blocked)

    const hGate = histamineGate({
      commodityId: 'fish.tuna.albacore',
      maxTemperatureC: 18.0,
    })
    expect(hGate.status === 'BLOCK').toBe(golden.safety.histamine_blocked)

    const fcGate = freshCutGate({
      stateModifiers: { cut: true },
      maxTemperatureC: 30.0,
      o2Fraction: 0.01,
    })
    expect(fcGate.status === 'BLOCK').toBe(golden.safety.fresh_cut_blocked)
  })

  it('verifies offline orchestrator refusal path for cut potato at 30 C', () => {
    const result = recommendOffline({
      commodityId: 'veg.potato.solanum_tuberosum',
      state: { cut: true, hoursSinceCut: 48 },
      temperatureC: 30.0,
    })
    expect(result.verdict).toBe('NOT_A_PACKAGING_PROBLEM')
    expect(result.safety?.status).toBe('BLOCK')
    expect(result.guidance.length).toBeGreaterThanOrEqual(3)
  })

  it('verifies offline orchestrator recommendation path for tomato', () => {
    const result = recommendOffline({
      commodityId: 'veg.tomato.solanum_lycopersicum',
      state: { cut: false },
      storage: 'shed',
      district: 'Nashik',
    })
    expect(result.verdict).toBe('RECOMMENDED')
    expect(result.recommendedPackage).toBeDefined()
    expect(result.shelfLifeDaysP50).toBeGreaterThan(0)
    expect(result.whereToBuyDistrict).toBe('Nashik')
  })
})
