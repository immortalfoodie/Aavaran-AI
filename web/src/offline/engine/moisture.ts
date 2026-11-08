/**
 * Moisture-limited shelf life and WVTR requirement models in TypeScript.
 * Ported from engine/models/moisture.py and verified against golden_models.json.
 */

export class LinearIsotherm {
  readonly b: number
  readonly c: number

  constructor(b: number, c = 0.0) {
    if (b <= 0) {
      throw new Error(`Linear isotherm slope b must be positive, got ${b}`)
    }
    this.b = b
    this.c = c
  }

  moistureAtAw(aw: number): number {
    if (aw < 0) throw new Error(`Water activity cannot be negative, got ${aw}`)
    return this.b * aw + this.c
  }

  awAtMoisture(m: number): number {
    const aw = (m - this.c) / this.b
    return Math.max(0, aw)
  }
}

export class GABIsotherm {
  readonly m0: number
  readonly cG: number
  readonly k: number

  constructor(m0: number, cG: number, k: number) {
    if (m0 <= 0) throw new Error(`m0 must be positive, got ${m0}`)
    if (cG <= 0) throw new Error(`cG must be positive, got ${cG}`)
    if (k <= 0 || k > 1.5) throw new Error(`k must be in (0, 1.5], got ${k}`)
    this.m0 = m0
    this.cG = cG
    this.k = k
  }

  moistureAtAw(aw: number): number {
    if (aw < 0) throw new Error(`Water activity cannot be negative, got ${aw}`)
    if (aw === 0) return 0
    const x = this.k * aw
    if (x >= 1.0) return Infinity
    const denom = (1.0 - x) * (1.0 + (this.cG - 1.0) * x)
    if (denom <= 0) return Infinity
    return (this.m0 * this.cG * x) / denom
  }
}

/**
 * Saturation vapor pressure p0 in kPa at temperature T in °C.
 * Uses the Tetens equation (same as Python engine).
 */
export function saturationVaporPressureKpa(tempC: number): number {
  return 0.61078 * Math.exp((17.27 * tempC) / (tempC + 237.3))
}

/**
 * ASTM F1249 test driving force: 38 °C, 90 % RH.
 * Δp_test = 0.90 * p0(38 °C) [kPa]
 */
export function astmF1249TestDrivingForceKpa(): number {
  const p0_38 = saturationVaporPressureKpa(38.0)
  return 0.90 * p0_38
}

export interface MoistureShelfLifeParams {
  wvtr?: number
  packAreaM2?: number
  drySolidsKg?: number
  temperatureC?: number
  relativeHumidityPct?: number
  awInitial?: number
  awCrit?: number
  isotherm?: LinearIsotherm | GABIsotherm
}

export interface MoistureShelfLifeResult {
  shelfLifeDays: number
  isothermUsed: string
  allowablePermeance: number
}

export function shelfLifeMoistureLimited(params: MoistureShelfLifeParams): MoistureShelfLifeResult {
  const wvtr = params.wvtr ?? 1.0
  const packAreaM2 = params.packAreaM2 ?? 0.055
  const drySolidsKg = params.drySolidsKg ?? 0.1
  const temperatureC = params.temperatureC ?? 30.0
  const rhPct = params.relativeHumidityPct ?? 75.0
  const awInitial = params.awInitial ?? 0.22
  const awCrit = params.awCrit ?? 0.45
  const awOut = rhPct / 100.0

  if (awInitial >= awCrit) {
    return { shelfLifeDays: 0, isothermUsed: 'none', allowablePermeance: 0 }
  }
  if (awOut <= awCrit) {
    return { shelfLifeDays: Infinity, isothermUsed: 'none', allowablePermeance: 0 }
  }
  if (wvtr <= 0) {
    return { shelfLifeDays: Infinity, isothermUsed: 'none', allowablePermeance: 0 }
  }

  const deltaPTestKpa = astmF1249TestDrivingForceKpa()
  const permeanceMag = wvtr / deltaPTestKpa // g / (m² · day · kPa)
  const p0Kpa = saturationVaporPressureKpa(temperatureC)
  const wsG = drySolidsKg * 1000.0

  const bSlope = params.isotherm instanceof LinearIsotherm ? params.isotherm.b : 7.0
  const ratio = (awOut - awInitial) / (awOut - awCrit)
  const lnTerm = Math.log(ratio)

  const timeDays = (wsG * bSlope) / (permeanceMag * packAreaM2 * p0Kpa) * lnTerm

  return {
    shelfLifeDays: timeDays,
    isothermUsed: 'linear',
    allowablePermeance: permeanceMag,
  }
}

export interface RequiredWvtrParams {
  targetDays?: number
  packArea?: number
  drySolids?: number
  temperatureC?: number
  relativeHumidityPct?: number
  awInitial?: number
  awCrit?: number
  isothermSlopeB?: number
}

export function requiredWvtr(params: RequiredWvtrParams): { allowablePermeance: number; requiredWvtr: number } {
  const targetDays = params.targetDays ?? 180.0
  const packArea = params.packArea ?? 0.055
  const drySolids = params.drySolids ?? 0.1
  const temperatureC = params.temperatureC ?? 30.0
  const rhPct = params.relativeHumidityPct ?? 75.0
  const awInitial = params.awInitial ?? 0.20
  const awCrit = params.awCrit ?? 0.45
  const bSlope = params.isothermSlopeB ?? 7.0
  const awOut = rhPct / 100.0

  const wsG = drySolids * 1000.0
  const p0Kpa = saturationVaporPressureKpa(temperatureC)
  const ratio = (awOut - awInitial) / (awOut - awCrit)
  const lnTerm = Math.log(ratio)

  const allowablePermeance = (wsG * bSlope) / (targetDays * packArea * p0Kpa) * lnTerm
  const deltaPTestKpa = astmF1249TestDrivingForceKpa()
  const reqWvtr = allowablePermeance * deltaPTestKpa

  return { allowablePermeance, requiredWvtr: reqWvtr }
}
