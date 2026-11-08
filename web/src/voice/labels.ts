import type { TFunction } from 'i18next'
import type { SaathiLang } from './voiceApi'

/** Kisan crop ids -> i18n keys under `crops.*`. */
const KISAN_CROP_KEYS: Record<string, string> = {
  'veg.potato.solanum_tuberosum': 'potato',
  'veg.tomato.solanum_lycopersicum': 'tomato',
  'veg.onion.allium_cepa': 'onion',
  'fruit.banana.musa_acuminata': 'banana',
  'fruit.mango.mangifera_indica': 'mango',
  'veg.okra.abelmoschus_esculentus': 'okra',
  'veg.spinach.spinacia_oleracea': 'spinach',
  'veg.green_chilli.capsicum_annuum': 'green_chilli',
  'fruit.guava.psidium_guajava': 'guava',
  'veg.cauliflower.brassica_oleracea_botrytis': 'cauliflower',
  'veg.cabbage.brassica_oleracea_capitata': 'cabbage',
  'fruit.grape.vitis_vinifera': 'grape',
  'fruit.pomegranate.punica_granatum': 'pomegranate',
  'veg.brinjal.solanum_melongena': 'brinjal',
}

const BUSINESS_NAMES: Record<string, { en: string; hi: string; mr: string }> = {
  'processed.besan_namkeen.fried_snack': { en: 'Namkeen', hi: 'नमकीन', mr: 'फरसाण' },
  'dairy.milk_powder.whole': { en: 'Milk powder', hi: 'दूध पाउडर', mr: 'दूध पावडर' },
  'dairy.paneer.cottage_cheese': { en: 'Paneer', hi: 'पनीर', mr: 'पनीर' },
  'spice.turmeric_powder.curcuma_longa': { en: 'Turmeric powder', hi: 'हल्दी', mr: 'हळद' },
  'cereal.wheat_atta.triticum_aestivum': { en: 'Wheat atta', hi: 'आटा', mr: 'कणिक' },
  'pulse.toor_dal.cajanus_cajan': { en: 'Toor dal', hi: 'तूर दाल', mr: 'तूर डाळ' },
}

export function commodityLabel(id: string, lang: SaathiLang, t: TFunction): string {
  const cropKey = KISAN_CROP_KEYS[id]
  if (cropKey) return t(`crops.${cropKey}`, { defaultValue: cropKey })
  const names = BUSINESS_NAMES[id]
  if (names) return lang === 'mr-IN' ? names.mr : lang === 'hi-IN' ? names.hi : names.en
  return id.split('.')[1]?.replace(/_/g, ' ') ?? id
}

/** Business-mode form presets (web/src/modes/business/engine.ts) matching backend commodity ids. */
export const BUSINESS_PRESET_FOR: Record<string, string> = {
  'processed.besan_namkeen.fried_snack': 'food.snack.namkeen_bhujia',
  'dairy.paneer.cottage_cheese': 'food.dairy.fresh_paneer',
  'spice.turmeric_powder.curcuma_longa': 'food.spice.turmeric_powder',
  'veg.potato.solanum_tuberosum': 'food.produce.table_potato',
  'veg.tomato.solanum_lycopersicum': 'food.produce.fresh_tomato',
  'veg.spinach.spinacia_oleracea': 'veg.spinach.spinacia_oleracea',
}

export function businessDisplayName(id: string): string {
  return BUSINESS_NAMES[id]?.en ?? (id.split('.')[1]?.replace(/_/g, ' ') || id)
}
