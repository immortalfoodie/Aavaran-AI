/**
 * Predictive microbiology and Ratkowsky growth rate models in TypeScript.
 * Ported from engine/models/microbial.py and verified against golden_models.json.
 */

export interface OrganismParams {
  name: string
  b: number
  tMinC: number
  awMin: number
  phMin: number
  phMax: number
  co2Sensitivity: number
  requiresO2: boolean
}

export const ORGANISMS: Record<string, OrganismParams> = {
  pseudomonas: {
    name: 'Pseudomonas spp.',
    b: 0.165,
    tMinC: -3.0,
    awMin: 0.96,
    phMin: 5.0,
    phMax: 8.5,
    co2Sensitivity: 0.70,
    requiresO2: true,
  },
  lactic_acid_bacteria: {
    name: 'Lactic acid bacteria',
    b: 0.130,
    tMinC: -1.0,
    awMin: 0.93,
    phMin: 4.2,
    phMax: 8.5,
    co2Sensitivity: 0.15,
    requiresO2: false,
  },
}

export interface MicrobialGrowthParams {
  organism: string | OrganismParams
  temperatureC: number
  waterActivity: number
  ph: number
  co2Fraction?: number
  o2Fraction?: number
}

export function ratkowskyGrowthRate(params: MicrobialGrowthParams): { muMaxPerDay: number } {
  const org: OrganismParams =
    typeof params.organism === 'string'
      ? ORGANISMS[params.organism] || ORGANISMS.pseudomonas
      : params.organism

  const tC = params.temperatureC
  const aw = Math.max(0, Math.min(1, params.waterActivity))
  const ph = params.ph
  const co2Fraction = Math.max(0, Math.min(1, params.co2Fraction ?? 0.0))
  const o2Fraction = Math.max(0, Math.min(1, params.o2Fraction ?? 0.209))

  if (tC <= org.tMinC) return { muMaxPerDay: 0 }
  const tempTerm = org.b * (tC - org.tMinC)

  if (aw <= org.awMin) return { muMaxPerDay: 0 }
  const awTerm = Math.sqrt((aw - org.awMin) / (1.0 - org.awMin))

  if (ph <= org.phMin || ph >= org.phMax) return { muMaxPerDay: 0 }
  const phDelta = org.phMin - ph
  const phTerm = Math.sqrt(Math.max(0, 1.0 - Math.pow(10, phDelta)))

  const co2InhibitionRaw = 1.0 - org.co2Sensitivity * co2Fraction
  const co2Term = Math.max(0, Math.min(1, co2InhibitionRaw))

  let o2Term = 1.0
  if (org.requiresO2 && o2Fraction < 0.01) {
    o2Term = 0.0
  }

  const sqrtMuMax = tempTerm * awTerm * phTerm * co2Term * o2Term
  const muMaxPerDay = Math.pow(sqrtMuMax, 2)

  return { muMaxPerDay }
}

export function timeToSpoilage(
  temperatureC: number,
  waterActivity: number,
  ph: number,
  organism = 'pseudomonas',
): number {
  const { muMaxPerDay } = ratkowskyGrowthRate({
    organism,
    temperatureC,
    waterActivity,
    ph,
  })

  if (muMaxPerDay <= 0.0001) return 999.0

  const logN0 = 3.0 // 10^3 CFU/g
  const logNSpoil = 7.0 // 10^7 CFU/g
  const muLn10 = muMaxPerDay / Math.LN10
  const lagPhaseDays = 0.2

  const tDays = (logNSpoil - logN0) / muLn10 + lagPhaseDays
  return Math.max(0.1, tDays)
}
