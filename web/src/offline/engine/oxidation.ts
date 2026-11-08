/**
 * Oxidation-limited shelf life and OTR requirement models in TypeScript.
 * Ported from engine/models/oxidation.py and verified against golden_models.json.
 */

export const O2_DENSITY_MG_PER_CC = 1.43
export const DEFAULT_AIR_O2_FRACTION = 0.209

export interface OxidationShelfLifeParams {
  otr?: number
  packAreaM2?: number
  productMassKg?: number
  qBudgetMgPerKg?: number
  headspaceVolumeCc?: number
  headspaceO2Fraction?: number
  deltaPAtm?: number
}

export interface OxidationShelfLifeResult {
  shelfLifeDays: number
  totalBudgetMg: number
  headspaceO2Mg: number
  ingressRateMgPerDay: number
  nitrogenFlushRecommended: boolean
}

export function shelfLifeOxidationLimited(params: OxidationShelfLifeParams): OxidationShelfLifeResult {
  const qBudgetMgPerKg = params.qBudgetMgPerKg ?? 15.0
  const productMassKg = params.productMassKg ?? 0.20
  const headspaceVolumeCc = params.headspaceVolumeCc ?? 50.0
  const headspaceO2Fraction = params.headspaceO2Fraction ?? DEFAULT_AIR_O2_FRACTION
  const otr = params.otr ?? 2.0
  const packAreaM2 = params.packAreaM2 ?? 0.055
  const deltaPAtm = params.deltaPAtm ?? DEFAULT_AIR_O2_FRACTION

  const totalBudgetMg = qBudgetMgPerKg * productMassKg
  const headspaceO2Mg = headspaceVolumeCc * headspaceO2Fraction * O2_DENSITY_MG_PER_CC

  const nitrogenFlushRecommended = headspaceO2Mg >= totalBudgetMg * 0.5

  if (otr <= 0) {
    if (headspaceO2Mg >= totalBudgetMg) {
      return {
        shelfLifeDays: 0.0,
        totalBudgetMg,
        headspaceO2Mg,
        ingressRateMgPerDay: 0.0,
        nitrogenFlushRecommended: true,
      }
    }
    return {
      shelfLifeDays: Infinity,
      totalBudgetMg,
      headspaceO2Mg,
      ingressRateMgPerDay: 0.0,
      nitrogenFlushRecommended,
    }
  }

  const remainingBudgetMg = totalBudgetMg - headspaceO2Mg
  if (remainingBudgetMg <= 0) {
    return {
      shelfLifeDays: 0.0,
      totalBudgetMg,
      headspaceO2Mg,
      ingressRateMgPerDay: otr * packAreaM2 * deltaPAtm * O2_DENSITY_MG_PER_CC,
      nitrogenFlushRecommended: true,
    }
  }

  const ingressRateMgPerDay = otr * packAreaM2 * deltaPAtm * O2_DENSITY_MG_PER_CC
  const shelfLifeDays = remainingBudgetMg / ingressRateMgPerDay

  return {
    shelfLifeDays,
    totalBudgetMg,
    headspaceO2Mg,
    ingressRateMgPerDay,
    nitrogenFlushRecommended,
  }
}
