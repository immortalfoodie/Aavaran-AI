export interface LedgerParameter {
  id: string
  category: 'commodity' | 'environment' | 'geometry' | 'microbial'
  name: string
  symbol: string
  defaultValue: number
  currentValue: number
  unit: string
  description: string
  provenance: string
  citation: {
    source: string
    title: string
    clause?: string
    year?: number
  }
  confidence: number // 1 to 10
  isOverridden: boolean
  minAllowed: number
  maxAllowed: number
  step: number
}

export interface EquationInput {
  value: number | string
  unit: string
  source: string
}

export interface EquationOutput {
  value: number | string
  unit: string
}

export interface EquationItem {
  equation_id: string
  name: string
  formula_template: string
  inputs: Record<string, EquationInput>
  output: EquationOutput
  citation?: string
}

export interface SensitivityItem {
  parameter: string
  variance_reduction_pct: number
  direction: string
}

export interface EvaluatedRule {
  rule_id: string
  instrument: string
  clause: string
  status: 'PASS' | 'WARN' | 'BLOCK'
  effect: string
  message?: string
}

export interface ComplianceSummary {
  is_compliant: boolean
  destination_market: string
  rules_evaluated: EvaluatedRule[]
}

export interface SealedShelfLife {
  days_p10: number
  days_p50: number
  days_p90: number
  limiting_mechanism?: string
  mechanism?: string
  confidence: number
  distribution_samples?: number[]
}

export interface SealedProvenance {
  field?: string
  value: any
  unit?: string
  source_id?: string
  source_type?: string
  confidence?: number
  note?: string
}

export interface SealedResult {
  result_id: string
  engine_version: string
  kb_version: string
  ruleset_version: string
  verdict: string
  computed_at: string
  resolved?: any
  assumptions: SealedProvenance[]
  requirements?: any
  candidates: any[]
  shelf_life: SealedShelfLife
  safety?: any
  guidance?: any[]
  value_of_information?: {
    field: string
    variance_reduction: number
    description: string
  }
  equations: EquationItem[]
  sensitivity: SensitivityItem[]
  compliance: ComplianceSummary
  citations: string[]
}

export interface MonteCarloHistogramBin {
  daysStart: number
  daysEnd: number
  count: number
  frequencyPct: number
  isP10Bin?: boolean
  isP50Bin?: boolean
  isP90Bin?: boolean
}

export interface MonteCarloResult {
  totalIterations: number
  p10Days: number
  p50Days: number
  p90Days: number
  meanDays: number
  standardDeviationDays: number
  bins: MonteCarloHistogramBin[]
}

export interface CandidateStructurePoint {
  id: string
  name: string
  layerStack: string
  costPerPackInr: number
  shelfLifeDays: number
  recyclabilityScorePct: number
  eprCategory: 'Cat I' | 'Cat II' | 'Cat III' | 'Cat IV'
  isParetoOptimal: boolean
  compositeThicknessUm: number
}

export interface SavedScenario {
  id: string
  label: string
  timestamp: string
  structureName: string
  layerStack: string
  costPerPackInr: number
  shelfLifeP10: number
  shelfLifeP50: number
  shelfLifeP90: number
  annualEprLiabilityInr: number
  recyclabilityScorePct: number
  limitingMechanism: string
  overriddenParameterCount: number
}

// Backwards-compatible aliases
export type RuleTraceItem = EvaluatedRule
export type ExpertSealedResultJson = SealedResult
