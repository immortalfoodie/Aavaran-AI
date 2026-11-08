export type CropId =
  | 'veg.potato.solanum_tuberosum'
  | 'veg.tomato.solanum_lycopersicum'
  | 'veg.onion.allium_cepa'
  | 'fruit.banana.musa_acuminata'
  | 'fruit.mango.mangifera_indica'
  | 'veg.okra.abelmoschus_esculentus'
  | 'veg.spinach.spinacia_oleracea'
  | 'veg.green_chilli.capsicum_annuum'
  | 'fruit.guava.psidium_guajava'
  | 'veg.cauliflower.brassica_oleracea_botrytis'
  | 'veg.cabbage.brassica_oleracea_capitata'
  | 'fruit.grape.vitis_vinifera'
  | 'fruit.pomegranate.punica_granatum'
  | 'veg.brinjal.solanum_melongena'

export type PhysicalState = 'whole' | 'cut' | 'washed' | 'damaged'

export type TimeInterval = 'today' | 'one_day' | 'two_days' | 'three_days_plus'

export type StorageMethod = 'shed' | 'cold_room' | 'ice'

export interface CropInfo {
  id: CropId
  translationKey: string
  photo: string
  hindiName: string
  marathiName: string
  englishName: string
}

export interface KisanState {
  selectedCrop: CropId | null
  physicalState: PhysicalState
  timeInterval: TimeInterval
  storageMethod?: StorageMethod
  district: string
}
