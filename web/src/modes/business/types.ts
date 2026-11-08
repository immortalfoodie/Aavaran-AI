export type FillingMachineType =
  | 'vffs'
  | 'hffs'
  | 'premade_pouch'
  | 'thermoforming'
  | 'manual_sealer'

export type DestinationMarket = 'IN' | 'EU' | 'US' | 'GLOBAL'

export type TransportMode =
  | 'refrigerated_truck'
  | 'ambient_truck'
  | 'air_freight'
  | 'rail_container'
  | 'local_van'

export interface RouteLeg {
  id: string
  name: string
  mode: TransportMode
  durationHours: number
  temperatureC: number
  relativeHumidityPct: number
  vibrationSeverity: 'low' | 'moderate' | 'severe'
}

export interface BusinessInputState {
  commodityId: string
  commodityName: string
  packSizeGrams: number
  packAreaM2: number
  targetShelfLifeDays: number
  budgetPerPackInr: number
  fillingMachine: FillingMachineType
  destinationMarket: DestinationMarket
  annualPackVolume: number
  productRetailPriceInr: number
  currentLossRatePct: number
  routeLegs: RouteLeg[]
  state?: string
  storageType?: 'ambient' | 'chilled' | 'frozen'
  hoursSinceHarvestOrProduction?: number
}

export interface ASTMProperty {
  propertyName: string
  testMethod: string
  value: string
  unit: string
  specificationNote: string
}

export interface PackagingSpecSheet {
  structureId: string
  name: string
  rank: 1 | 2 | 3
  rankLabel: 'RECOMMENDED PRIMARY' | 'COST-OPTIMIZED' | 'CIRCULAR MONO-MATERIAL'
  layerStackDisplay: string
  layers: Array<{ material: string; gaugeUm: number; colorClass: string }>
  compositeThicknessUm: number
  costPerPackInr: number
  eprCategory: 'Cat I' | 'Cat II' | 'Cat III' | 'Cat IV'
  recyclabilityStatus: string
  isMonoMaterial: boolean
  isMetallisedOrFoil: boolean
  properties: ASTMProperty[]
  cofStatic: number
  cofDynamic: number
  machineRunnabilityScore: number // 1 to 10
  predictedShelfLifeDaysP10: number
  predictedShelfLifeDaysP50: number
  predictedShelfLifeDaysP90: number
  limitingMechanism: string
  wvtrGPerM2Day?: number
  otrCcPerM2Day?: number
  isMoistureSensitive?: boolean
}

export interface ComplianceItem {
  id: string
  standard: string
  clause: string
  title: string
  status: 'COMPLIANT' | 'ACTION_REQUIRED' | 'EXEMPT'
  requiredDocumentName: string
  documentStatus: 'VERIFIED' | 'PENDING_UPLOAD' | 'CONVERTER_ACTION'
  details: string
}

export interface EprLiabilityComparison {
  category: string
  currentAnnualVolume: number
  packWeightGrams: number
  totalPlasticTonnagePerYear: number
  recyclingTargetPct: number
  recycledContentTargetPct: number
  creditRateInrPerTonne: number
  indicativeAnnualLiabilityInr: number
  indicativeCostPerPackInr: number
  monoAlternative: {
    category: string
    name: string
    indicativeAnnualLiabilityInr: number
    indicativeCostPerPackInr: number
    annualRupeeSavings: number
    circularityScorePct: number
  }
}

export interface RfqSpecification {
  rfqId: string
  createdAt: string
  brandName: string
  converterName: string
  contactEmail: string
  targetOrderQuantity: number
  orderType: 'premade_pouches' | 'roll_film'
  pouchDimensionsMm?: { width: number; height: number; bottomGusset?: number }
  rollDimensionsMm?: { width: number; repeatLength: number; coreDiameter: number; maxRollOd: number }
  structure: PackagingSpecSheet
  nominalGaugesWithTolerances: Array<{ layer: string; nominalUm: number; tolerancePct: number }>
  testMethodsAndAcceptance: Array<{ property: string; standard: string; acceptanceCriteria: string }>
  defectTolerancesAql: { critical: number; major: number; minor: number }
  commercialTerms: string[]
}

export interface CostBenefitAnalysis {
  costPerPackInr: number
  productRetailValueInr: number
  packagingCostRatioPct: number
  breakEvenLossRatePct: number
  currentAnnualLossInr: number
  predictedAnnualLossInr: number
  netAnnualMarginProtectedInr: number
  roiMultiple: number
}
