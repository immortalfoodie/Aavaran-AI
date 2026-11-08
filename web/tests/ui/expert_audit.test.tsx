import React from 'react'
import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ModelInspector, renderSubstitutedFormula } from '../../src/modes/expert/components/ModelInspector'
import { SensitivityTornadoChart } from '../../src/modes/expert/components/SensitivityTornadoChart'
import { MonteCarloDistribution } from '../../src/modes/expert/components/MonteCarloDistribution'
import { ComplianceRuleTrace } from '../../src/modes/expert/components/ComplianceRuleTrace'
import { ExpertMode } from '../../src/modes/expert/ExpertMode'
import type { EquationItem, SealedResult, SensitivityItem } from '../../src/modes/expert/types'

describe('Expert Mode Data Audit & Live Engine Output (Steps 1–7)', () => {
  const sampleEquations: EquationItem[] = [
    {
      equation_id: 'M-03',
      name: 'Fickian Moisture Barrier Permeance Integral',
      formula_template: 'permeance_max = ({W_s} × {b}) / ({A} × {p0} × {t}) × ln[({m_e} − {m_i}) / ({m_e} − {m_c})]',
      inputs: {
        W_s: { value: 0.18, unit: 'kg', source: 'Pack Spec' },
        b: { value: 0.042, unit: '', source: 'GAB Isotherm' },
        A: { value: 0.055, unit: 'm²', source: 'Geometry' },
        p0: { value: 4.24, unit: 'kPa', source: 'Antoine' },
        t: { value: 180, unit: 'd', source: 'Requirement' },
        m_e: { value: 0.75, unit: '', source: 'Storage RH' },
        m_i: { value: 0.038, unit: '', source: 'AOAC 925.10' },
        m_c: { value: 0.065, unit: '', source: 'Labuza Table' },
      },
      output: { value: 0.58, unit: 'g/m²·day' },
      citation: 'Labuza, T.P. (1984). Moisture Sorption Practical Aspects.',
    },
    {
      equation_id: 'MIC-01',
      name: 'Modified Gompertz Microbial Growth Model',
      formula_template: 'N(t) = {N_0} + {A_max} × exp(-exp({mu_max} × exp(1) / {A_max} × ({lambda} - t) + 1))',
      inputs: {
        N_0: { value: 2.3, unit: 'log CFU/g', source: 'Baseline' },
        A_max: { value: 7.0, unit: 'log CFU/g', source: 'Threshold' },
        mu_max: { value: 0.45, unit: '1/d', source: 'ComBase' },
        lambda: { value: 1.5, unit: 'd', source: 'Lag Phase' },
      },
      output: { value: 999.0, unit: 'days' },
      citation: 'Zwietering, M.H. et al. (1990). Modeling Bacterial Growth.',
    },
  ]

  const sampleSensitivity: SensitivityItem[] = [
    { parameter: 'storage_temperature', variance_reduction_pct: 39.0, direction: 'negative' },
    { parameter: 'initial_moisture', variance_reduction_pct: 26.0, direction: 'negative' },
    { parameter: 'storage_rh', variance_reduction_pct: 21.0, direction: 'negative' },
    { parameter: 'pack_area', variance_reduction_pct: 14.0, direction: 'negative' },
  ]

  const sampleSealedResult: SealedResult = {
    result_id: 'res_test_expert_123',
    engine_version: '1.0.0',
    kb_version: '1.0.0',
    ruleset_version: '1.0.0',
    verdict: 'RECOMMENDED',
    computed_at: '2026-09-23T12:00:00Z',
    assumptions: [
      { field: 'moisture_pct', value: 0.038, unit: 'g/g', source_type: 'LAB_MEASURED', source_id: 'AOAC-925.10', note: 'Initial moisture' },
      { field: 'water_activity', value: 0.42, unit: 'aw', source_type: 'ISOTHERM_DERIVED', source_id: 'GAB-FIT', note: 'Water activity' },
      { field: 'storage_temperature', value: 30.0, unit: '°C', source_type: 'CLIMATOLOGY', source_id: 'IMD-MUMBAI', note: 'Storage temp' },
      { field: 'storage_rh', value: 65.0, unit: '%', source_type: 'CLIMATOLOGY', source_id: 'IMD-MUMBAI', note: 'Storage RH' },
      { field: 'respiration_rate_or_na', value: 0.0, unit: 'mg/kg·h', source_type: 'COMMODITY_DB', source_id: 'USDA-66', note: 'Non-respiring' },
      { field: 'pack_area', value: 0.055, unit: 'm²', source_type: 'USER_INPUT', source_id: 'PACK-GEOM', note: 'Pack surface area' },
    ],
    candidates: [
      {
        material_id: 'mat_bopp_metcpp_35',
        name: 'BOPP 20 / Metallized CPP 15',
        score: 0.92,
        cost_per_pack: 2.80,
        recyclability_score: 0.45,
        layer_stack: ['BOPP 20µm', 'Met-CPP 15µm'],
      },
    ],
    shelf_life: {
      days_p10: 101.2,
      days_p50: 135.0,
      days_p90: 175.5,
      limiting_mechanism: 'lipid_oxidation',
      mechanism: 'lipid_oxidation',
      confidence: 0.88,
    },
    equations: sampleEquations,
    sensitivity: sampleSensitivity,
    compliance: {
      is_compliant: true,
      destination_market: 'IN',
      rules_evaluated: [
        {
          rule_id: 'IN-FSSAI-2018-R4',
          instrument: 'Food Safety and Standards (Packaging) Regulations, 2018',
          clause: 'Regulation 4',
          status: 'PASS',
          effect: 'Food-grade virgin packaging polymer verification',
        },
        {
          rule_id: 'IN-FSSAI-2018-SCH3',
          instrument: 'Food Safety and Standards (Packaging) Regulations, 2018',
          clause: 'Schedule III',
          status: 'PASS',
          effect: 'Conformity with BIS IS standards for plastic in food contact',
        },
        {
          rule_id: 'IN-PWM-2022-CAT',
          instrument: 'Plastic Waste Management Rules, 2022',
          clause: 'Schedule II, Guideline 4',
          status: 'WARN',
          effect: 'Category III Multi-layered plastic EPR recycling target apply',
        },
        {
          rule_id: 'IN-LAB-2020-DATE',
          instrument: 'Food Safety and Standards (Labelling) Regulations, 2020',
          clause: 'Regulation 5(7)',
          status: 'PASS',
          effect: 'Mandatory Date of Manufacture and Use-by date labelling',
        },
      ],
    },
    citations: [],
  }

  const cleanHtml = (str: string) => str.replace(/<!-- -->/g, '')

  // --- Step 2: Model Inspector Equations ---
  it('Step 2: renders equation with real numbers substituted rather than generic symbols', () => {
    const renderedStr = renderSubstitutedFormula(sampleEquations[0])
    expect(renderedStr).toContain('0.18 kg')
    expect(renderedStr).toContain('0.055 m²')
    expect(renderedStr).toContain('4.24 kPa')
    expect(renderedStr).toContain('180 d')
    expect(renderedStr).toContain('= 0.58 g/m²·day')

    const html = cleanHtml(renderToString(<ModelInspector equations={sampleEquations} />))
    expect(html).toContain('02 · Model Inspector (Real Inputs Substituted)')
    expect(html).toContain('2 DERIVED EQUATIONS WITH LIVE INPUTS')
    expect(html).toContain('M-03')
    expect(html).toContain('MIC-01')
    expect(html).toContain('REAL NUMBERS')
    expect(html).toContain('0.58 g/m²·day')
  })

  // --- Step 3: Sensitivity Tornado Chart ---
  it('Step 3: renders sensitivity tornado chart with real percentages summing to 100%', () => {
    const html = cleanHtml(renderToString(<SensitivityTornadoChart items={sampleSensitivity} />))
    expect(html).toContain('03 · Sensitivity Tornado Chart')
    expect(html).toContain('TOTAL EXPLAINED VARIANCE: 100%')
    expect(html).toContain('Ambient Storage Temperature')
    expect(html).toContain('39.0%')
    expect(html).toContain('Initial Product Moisture')
    expect(html).toContain('26.0%')
    expect(html).toContain('Ambient Relative Humidity')
    expect(html).toContain('21.0%')
    expect(html).toContain('Exposed Pack Surface Area')
    expect(html).toContain('14.0%')
  })

  it('Step 3: renders empty state when sensitivity items are empty or null', () => {
    const htmlEmpty = renderToString(<SensitivityTornadoChart items={[]} />)
    expect(htmlEmpty).toContain('Run a recommendation to see sensitivity data.')
  })

  // --- Step 4: Monte Carlo Distribution ---
  it('Step 4: renders real P10/P50/P90, limiting mechanism badge, confidence, and triangular simulation', () => {
    const html = cleanHtml(renderToString(<MonteCarloDistribution shelfLife={sampleSealedResult.shelf_life} />))
    expect(html).toContain('04 · Monte Carlo Shelf Life Distribution')
    expect(html).toContain('TRIANGULAR STOCHASTIC SIMULATION')
    expect(html).toContain('LIMITING MECHANISM: lipid_oxidation')
    expect(html).toContain('88% CONFIDENCE')
    expect(html).toContain('P10: 101.2d')
    expect(html).toContain('P50: 135d')
    expect(html).toContain('P90: 175.5d')
  })

  it('Step 4: renders empty state when shelf life is missing', () => {
    const htmlEmpty = renderToString(<MonteCarloDistribution shelfLife={null} />)
    expect(htmlEmpty).toContain('Run a recommendation to see shelf life probability distribution.')
  })

  // --- Step 5: Compliance Rule Trace ---
  it('Step 5: renders compliance rule trace with 4 statutory minimum rules and status badges', () => {
    const html = cleanHtml(renderToString(<ComplianceRuleTrace compliance={sampleSealedResult.compliance} />))
    expect(html).toContain('07 · Compliance Rule Trace Log')
    expect(html).toContain('IN-FSSAI-2018-R4')
    expect(html).toContain('IN-FSSAI-2018-SCH3')
    expect(html).toContain('IN-PWM-2022-CAT')
    expect(html).toContain('IN-LAB-2020-DATE')
    expect(html).toContain('PASS')
    expect(html).toContain('WARN')
    expect(html).toContain('PASS: 3')
    expect(html).toContain('WARN: 1')
  })

  // --- Step 7: Data Freshness Indicator & ExpertMode integration ---
  it('Step 7: ExpertMode renders live data freshness banner and populated subcomponents', () => {
    const html = cleanHtml(renderToString(<ExpertMode result={sampleSealedResult} />))
    // Freshness banner
    expect(html).toContain('LIVE ENGINE DATA')
    expect(html).toContain('Result computed')
    expect(html).toMatch(/Engine v.*1\.0\.0/)
    expect(html).toMatch(/KB v.*1\.0\.0/)
    expect(html).toMatch(/Rules v.*1\.0\.0/)

    // Model Inspector with real equations
    expect(html).toContain('M-03')
    expect(html).toContain('0.58 g/m²·day')

    // Sensitivity
    expect(html).toContain('39.0%')

    // Monte Carlo
    expect(html).toContain('LIMITING MECHANISM: lipid_oxidation')
    expect(html).toContain('88% CONFIDENCE')

    // Compliance
    expect(html).toContain('IN-FSSAI-2018-R4')
  })

  it('Step 8: ExpertMode does not show fetching banner when data is already present', () => {
    const html = cleanHtml(renderToString(<ExpertMode result={sampleSealedResult} />))
    expect(html).not.toContain('FETCHING LIVE ENGINE RECOMMENDATION')
  })
})
