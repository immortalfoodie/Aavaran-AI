/**
 * Modified Atmosphere Packaging (MAP) perforation design in TypeScript.
 * Ported from engine/models/map_design.py and verified against golden_models.json.
 */

export const DEFAULT_AIR_O2_FRACTION = 0.209
export const MIN_EQUILIBRIUM_O2_FLOOR = 0.02
export const DIFFUSIVITY_O2_AIR_CM2_S = 0.205
export const R_GAS_J_PER_MOL_K = 8.314462618

export interface PerforationDesignParams {
  respirationO2: number // mL O2 / (kg · h)
  mass: number // kg
  filmThicknessUm: number // um
  holeDiameterUm?: number // um
  holeCount?: number
  yOut?: number
  yIn?: number
  temperatureC?: number
  pressureAtm?: number
}

export interface PerforationResult {
  holeCount: number
  holeDiameterUm: number
  porePermeanceO2MlDayAtm: number
}

export function perforationDesign(params: PerforationDesignParams): PerforationResult {
  const yIn = params.yIn ?? 0.03
  const yOut = params.yOut ?? DEFAULT_AIR_O2_FRACTION
  const temperatureC = params.temperatureC ?? 20.0
  const pressureAtm = params.pressureAtm ?? 1.0

  if (yIn < MIN_EQUILIBRIUM_O2_FLOOR) {
    throw new Error(`Target internal O2 (${yIn}) cannot be below 2.0% safety floor.`)
  }

  const tK = temperatureC + 273.15
  const pPa = pressureAtm * 101325.0
  const lFilmM = params.filmThicknessUm * 1e-6
  const dO2M2S = DIFFUSIVITY_O2_AIR_CM2_S * 1e-4

  const deltaY = yOut - yIn
  const deltaC = (deltaY * pPa) / (R_GAS_J_PER_MOL_K * tK)

  const vMolMl = ((R_GAS_J_PER_MOL_K * tK) / pPa) * 1e6
  const rTotalMlH = params.respirationO2 * params.mass
  const rTotalMolS = rTotalMlH / 3600.0 / vMolMl

  const holeDiameterUm = params.holeDiameterUm ?? 100.0
  const dM = holeDiameterUm * 1e-6
  const rM = dM / 2.0
  const aHoleM2 = (Math.PI * Math.pow(dM, 2)) / 4.0
  const lEffM = lFilmM + 1.18 * rM

  const nExact = (rTotalMolS * lEffM) / (dO2M2S * aHoleM2 * deltaC)
  const holeCount = Math.ceil(nExact)

  const qSingleHoleMolS = (dO2M2S * aHoleM2 * deltaC) / lEffM
  const qSingleHoleMlDayAtm = ((qSingleHoleMolS * vMolMl * 86400.0) / deltaY) * pressureAtm
  const porePermeanceO2MlDayAtm = holeCount * qSingleHoleMlDayAtm

  return {
    holeCount,
    holeDiameterUm,
    porePermeanceO2MlDayAtm,
  }
}
