/** Plain-language pouch descriptions for shop owners (no film jargon on the main screen). */

export type PouchKind = 'foil' | 'metal' | 'breathable' | 'clear_strong' | 'clear'

export function pouchKind(layers: string[]): PouchKind {
  const l = layers.join(' ').toUpperCase()
  if (/ALU|FOIL/.test(l)) return 'foil'
  if (/VM|METAL/.test(l)) return 'metal'
  if (/PERF|MESH/.test(l)) return 'breathable'
  if (/PET|BOPA|PA\b|EVOH|ALOX/.test(l)) return 'clear_strong'
  return 'clear'
}

/** "20u BOPP / 18u VMBOPP / 40u CPP" -> "20 micron BOPP / 18 micron VMBOPP / 40 micron CPP" */
export function sellerSpec(name: string | null | undefined, layers: string[]): string {
  const raw = name || layers.join(' / ')
  return raw.replace(/(\d+(?:\.\d+)?)\s*u\b/g, '$1 micron')
}


/**
 * The KB's indicative ₹/pack is for a ~200 g snack pouch (~0.058 m² of film; ₹/m² × area ≈ that
 * price). Bigger packs need more film: for the same pouch shape, area grows with weight^(2/3).
 * Must stay identical to `scaled_pack_cost` in api/voice/dialogue.py so voice and screen agree.
 */
export const REFERENCE_PACK_G = 200

export function scaledPackCost(costPerReferencePack: number, packSizeG: number): number {
  const factor = Math.pow(Math.max(packSizeG, 1) / REFERENCE_PACK_G, 2 / 3)
  return Math.round(costPerReferencePack * factor * 100) / 100
}
