/**
 * Respiration kinetics and state modifier models in TypeScript.
 * Ported from engine/models/respiration.py and verified against golden_models.json.
 */

export const R_G_KJ_PER_MOL_K = 8.314462618e-3

export const STATE_MODIFIER_RANGES: Record<string, [number, number]> = {
  cut: [3.0, 7.0],
  sliced: [3.0, 7.0],
  peeled: [3.0, 7.0],
  bruised: [1.3, 2.0],
  mechanically_damaged: [1.3, 2.0],
  washed: [1.0, 1.0],
  cured: [0.6, 0.9],
  blanched: [0.0, 0.0],
}

export interface RespirationRateParams {
  rateRef: number
  tempRefC: number
  tempTargetC?: number
  eaKjMol?: number
  q10?: number
}

export interface RespirationRateResult {
  rate: number
  equationId: string
  modelUsed: 'arrhenius' | 'q10_fallback'
}

export function rateAtTemperature(params: RespirationRateParams): RespirationRateResult {
  const rateRef = params.rateRef
  const tempRefC = params.tempRefC
  const tempTargetC = params.tempTargetC ?? 20.0

  const tRefK = tempRefC + 273.15
  const tTargetK = tempTargetC + 273.15

  if (params.eaKjMol !== undefined && params.eaKjMol > 0) {
    const exponent = (params.eaKjMol / R_G_KJ_PER_MOL_K) * (1.0 / tRefK - 1.0 / tTargetK)
    const scaledRate = rateRef * Math.exp(exponent)
    return {
      rate: scaledRate,
      equationId: 'RESP-01',
      modelUsed: 'arrhenius',
    }
  }

  const q10Val = params.q10 ?? 2.5
  const deltaT = tempTargetC - tempRefC
  const scaledRate = rateRef * Math.pow(q10Val, deltaT / 10.0)

  return {
    rate: scaledRate,
    equationId: 'RESP-02',
    modelUsed: 'q10_fallback',
  }
}
