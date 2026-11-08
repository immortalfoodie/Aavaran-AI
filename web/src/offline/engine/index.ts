/**
 * Offline Decision Support Engine for Aavaran Client-side execution.
 * Full TypeScript port verified against Python backend.
 */

import { rateAtTemperature } from './respiration'
import { timeToSpoilage } from './microbial'
import type { SafetyVerdict } from './safety'

export const SAFETY_FACTOR_SHELF_LIFE = 0.75

export interface OfflineInput {
  commodityId?: string
  rawText?: string
  state?: {
    cut?: boolean
    washed?: boolean
    bruised?: boolean
    damaged?: boolean
    cured?: boolean
    hoursSinceHarvest?: number
    hoursSinceCut?: number
  }
  storage?: 'shed' | 'cold_room' | 'ice'
  temperatureC?: number
  relativeHumidityPct?: number
  district?: string
}

export interface StructuredGuidance {
  action: 'CHILL' | 'PROCESS' | 'SELL_IMMEDIATELY' | 'VENTILATE'
  headline: string
  detail: string
  priority: number
}

export interface OfflineCandidate {
  id: string
  name: string
  structureType: 'perforated_pouch' | 'ventilated_crate' | 'mesh_sack' | 'barrier_pouch'
  image: string
  costPerPack: string
  costUnit: string
  eprCategory: string
  instructionKey: string
  doNotItems: Array<{ icon: string; textKey: string }>
}

export interface OfflineRecommendationResult {
  resultId: string
  isOffline: boolean
  verdict: 'RECOMMENDED' | 'NOT_A_PACKAGING_PROBLEM'
  commodityId: string
  commodityName: string
  safety?: SafetyVerdict
  shelfLifeDaysP50: number
  limitingMechanism: string
  guidance: StructuredGuidance[]
  recommendedPackage?: OfflineCandidate
  alternativePackages: OfflineCandidate[]
  indicativePrice: string
  whereToBuyDistrict: string
  computedAt: string
  resolved?: {
    commodity?: {
      id?: string
      name?: string
      display_name?: string
      local_name?: string
    }
  }
  recommendation?: {
    packaging_name?: string
    packaging_description?: string
    kisan_instruction?: string
    key_action?: string
  }
  candidates?: Array<{
    structure_name?: string
  }>
}

const COMMODITY_PROFILES: Record<string, {
  name: string
  waterActivity: number
  ph: number
  respirationRefRate: number
  respirationRefTC: number
  respirationEa: number
  defaultStorageDays: number
  isProduce: boolean
}> = {
  'veg.potato.solanum_tuberosum': {
    name: 'Potato',
    waterActivity: 0.98,
    ph: 6.1,
    respirationRefRate: 3.5,
    respirationRefTC: 5.0,
    respirationEa: 58.0,
    defaultStorageDays: 30,
    isProduce: true,
  },
  'veg.tomato.solanum_lycopersicum': {
    name: 'Tomato',
    waterActivity: 0.99,
    ph: 4.4,
    respirationRefRate: 8.0,
    respirationRefTC: 5.0,
    respirationEa: 52.0,
    defaultStorageDays: 7,
    isProduce: true,
  },
  'veg.onion.allium_cepa': {
    name: 'Onion',
    waterActivity: 0.97,
    ph: 5.6,
    respirationRefRate: 3.0,
    respirationRefTC: 5.0,
    respirationEa: 48.0,
    defaultStorageDays: 45,
    isProduce: true,
  },
  'fruit.banana.musa_acuminata': {
    name: 'Banana',
    waterActivity: 0.98,
    ph: 5.0,
    respirationRefRate: 15.0,
    respirationRefTC: 13.0,
    respirationEa: 62.0,
    defaultStorageDays: 6,
    isProduce: true,
  },
  'fruit.mango.mangifera_indica': {
    name: 'Mango',
    waterActivity: 0.98,
    ph: 4.8,
    respirationRefRate: 18.0,
    respirationRefTC: 12.0,
    respirationEa: 65.0,
    defaultStorageDays: 8,
    isProduce: true,
  },
  'veg.okra.abelmoschus_esculentus': {
    name: 'Okra',
    waterActivity: 0.98,
    ph: 6.2,
    respirationRefRate: 35.0,
    respirationRefTC: 10.0,
    respirationEa: 50.0,
    defaultStorageDays: 5,
    isProduce: true,
  },
  'veg.spinach.spinacia_oleracea': {
    name: 'Spinach',
    waterActivity: 0.99,
    ph: 6.5,
    respirationRefRate: 45.0,
    respirationRefTC: 5.0,
    respirationEa: 55.0,
    defaultStorageDays: 3,
    isProduce: true,
  },
  'veg.green_chilli.capsicum_annuum': {
    name: 'Green Chilli',
    waterActivity: 0.97,
    ph: 5.3,
    respirationRefRate: 12.0,
    respirationRefTC: 10.0,
    respirationEa: 52.0,
    defaultStorageDays: 10,
    isProduce: true,
  },
}

export function recommendOffline(input: OfflineInput): OfflineRecommendationResult {
  const resultId = `offline_res_${Math.random().toString(36).substring(2, 11)}`
  const computedAt = new Date().toISOString()
  const district = input.district || 'Nashik'

  // 1. Identify Commodity
  let cid = input.commodityId || 'veg.potato.solanum_tuberosum'
  if (input.rawText) {
    const t = input.rawText.toLowerCase()
    if (t.includes('aloo') || t.includes('potato') || t.includes('batata')) {
      cid = 'veg.potato.solanum_tuberosum'
    } else if (t.includes('tamatar') || t.includes('tomato')) {
      cid = 'veg.tomato.solanum_lycopersicum'
    } else if (t.includes('pyaaz') || t.includes('onion') || t.includes('kanda')) {
      cid = 'veg.onion.allium_cepa'
    } else if (t.includes('kela') || t.includes('banana')) {
      cid = 'fruit.banana.musa_acuminata'
    } else if (t.includes('aam') || t.includes('mango')) {
      cid = 'fruit.mango.mangifera_indica'
    } else if (t.includes('bhindi') || t.includes('okra')) {
      cid = 'veg.okra.abelmoschus_esculentus'
    } else if (t.includes('palak') || t.includes('spinach')) {
      cid = 'veg.spinach.spinacia_oleracea'
    } else if (t.includes('mirchi') || t.includes('chilli')) {
      cid = 'veg.green_chilli.capsicum_annuum'
    }
  }

  const profile = COMMODITY_PROFILES[cid] || COMMODITY_PROFILES['veg.potato.solanum_tuberosum']
  const state = input.state || {}
  const isCut = Boolean(state.cut)
  const isDamaged = Boolean(state.bruised || state.damaged)
  const isWashed = Boolean(state.washed)
  const hoursCut = state.hoursSinceCut || state.hoursSinceHarvest || (isCut ? 48 : 0)

  // 2. Storage Environment
  let tempC = input.temperatureC ?? 28.0
  let rhPct = input.relativeHumidityPct ?? 75.0
  if (input.storage === 'cold_room') {
    tempC = 4.0
    rhPct = 90.0
  } else if (input.storage === 'ice') {
    tempC = 1.0
    rhPct = 95.0
  }
  // Store effective RH factor
  const rhFactor = rhPct > 85 ? 0.95 : 1.0

  // 3. Safety Check: Botulinum / Fresh-cut / Histamine
  const isFreshCutAmbient = isCut && tempC > 5.0
  const isExpiredCutProduce = isCut && hoursCut > 6 && tempC > 15.0

  if (isFreshCutAmbient && (isExpiredCutProduce || isCut || cid.includes('potato'))) {
    // HARD REFUSAL INTERLOCK
    const botVerdict: SafetyVerdict = {
      status: 'BLOCK',
      ruleId: 'SAFE-BOT-01',
      rule_id: 'FSSAI-SEC-16 / BOT-01',
      messageKey:
        'Cut {commodity_name} kept in heat presents rapid bacterial soft rot and lethal Clostridium botulinum hazards. Packaging cannot prevent toxin formation.',
      isOverridable: false,
    }

    const guidance: StructuredGuidance[] = [
      {
        action: 'CHILL',
        headline: 'guidance_chill_headline',
        detail: 'guidance_chill_detail',
        priority: 1,
      },
      {
        action: 'PROCESS',
        headline: 'guidance_process_headline',
        detail: 'guidance_process_detail',
        priority: 2,
      },
      {
        action: 'SELL_IMMEDIATELY',
        headline: 'guidance_sell_headline',
        detail: 'guidance_sell_detail',
        priority: 3,
      },
    ]

    return {
      resultId,
      isOffline: true,
      verdict: 'NOT_A_PACKAGING_PROBLEM',
      commodityId: cid,
      commodityName: profile.name,
      resolved: {
        commodity: {
          id: cid,
          name: profile.name,
          display_name: profile.name.toLowerCase(),
          local_name: undefined,
        },
      },
      safety: botVerdict,
      shelfLifeDaysP50: 0.4,
      limitingMechanism: 'microbial_spoilage',
      guidance,
      alternativePackages: [],
      indicativePrice: '₹0',
      whereToBuyDistrict: district,
      computedAt,
    }
  }

  // 4. Calculate Shelf-Life across failure modes with 0.75 safety factor
  let p50ShelfLifeDays = profile.defaultStorageDays

  if (profile.isProduce) {
    // Respiration scaling
    const resp = rateAtTemperature({
      rateRef: profile.respirationRefRate,
      tempRefC: profile.respirationRefTC,
      tempTargetC: tempC,
      eaKjMol: profile.respirationEa,
    })

    const respMultiplier = isCut ? 4.0 : isDamaged ? 1.5 : 1.0
    const finalRespRate = resp.rate * respMultiplier

    // Microbial spoilage
    const spoilDays = timeToSpoilage(tempC, profile.waterActivity, profile.ph)

    // Baseline shelf-life calculation (inversely proportional to accelerated respiration)
    const respFactor = profile.respirationRefRate / Math.max(1.0, finalRespRate)
    const produceFactor = Math.max(1.0, (30.0 / tempC) * respFactor)
    let calculatedDays = Math.min(spoilDays * 1.5, profile.defaultStorageDays * (produceFactor / 3.0)) * rhFactor
    if (isCut) calculatedDays = Math.min(calculatedDays, 2.0)
    if (isDamaged) calculatedDays *= 0.65
    if (isWashed) calculatedDays *= 0.9

    p50ShelfLifeDays = Math.max(1, Math.round(calculatedDays * SAFETY_FACTOR_SHELF_LIFE))
  }

  // 5. Select Packaging Recommendation
  let recommendedPackage: OfflineCandidate
  let indicativePrice = '₹1.40 / bag'

  if (cid.includes('onion') || (cid.includes('potato') && !isCut)) {
    recommendedPackage = {
      id: 'pkg_mesh_sack_5kg',
      name: 'Ventilated Leno Mesh Sack (5 kg)',
      structureType: 'mesh_sack',
      image: '/images/packaging/mesh_sack.svg',
      costPerPack: '₹2.80',
      costUnit: 'per 5kg bag',
      eprCategory: 'Cat II (Recyclable)',
      instructionKey: 'instruction_mesh_sack',
      doNotItems: [
        { icon: '🚫', textKey: 'donot_direct_sun' },
        { icon: '🚫', textKey: 'donot_water_spray' },
        { icon: '🚫', textKey: 'donot_seal_airtight' },
      ],
    }
    indicativePrice = '₹2.80 / bag'
  } else if (cid.includes('tomato') || cid.includes('mango') || cid.includes('banana')) {
    recommendedPackage = {
      id: 'pkg_vent_crate_cfb',
      name: 'Ventilated Corrugated Crate with Soft EPE Liner',
      structureType: 'ventilated_crate',
      image: '/images/packaging/ventilated_crate.svg',
      costPerPack: '₹32.00',
      costUnit: 'per crate',
      eprCategory: 'Paper/Cardboard (Recyclable)',
      instructionKey: 'instruction_vent_crate',
      doNotItems: [
        { icon: '🚫', textKey: 'donot_overstack' },
        { icon: '🚫', textKey: 'donot_direct_sun' },
        { icon: '🚫', textKey: 'donot_drop' },
      ],
    }
    indicativePrice = '₹32.00 / crate'
  } else {
    recommendedPackage = {
      id: 'pkg_laser_perf_ldpe',
      name: 'Laser Micro-perforated Anti-fog LDPE Pouch',
      structureType: 'perforated_pouch',
      image: '/images/packaging/perforated_pouch.svg',
      costPerPack: '₹1.30',
      costUnit: 'per bag',
      eprCategory: 'Cat II (Recyclable mono-PE)',
      instructionKey: 'instruction_perforated_pouch',
      doNotItems: [
        { icon: '🚫', textKey: 'donot_seal_airtight' },
        { icon: '🚫', textKey: 'donot_wet_pack' },
        { icon: '🚫', textKey: 'donot_direct_sun' },
      ],
    }
    indicativePrice = '₹1.30 / bag'
  }

  return {
    resultId,
    isOffline: true,
    verdict: 'RECOMMENDED',
    commodityId: cid,
    commodityName: profile.name,
    safety: {
      status: 'PASS',
      ruleId: 'SAFE-FRESHCUT-01',
      messageKey: 'safety_passed',
      isOverridable: true,
    },
    shelfLifeDaysP50: p50ShelfLifeDays,
    limitingMechanism: 'respiration_and_transpiration',
    guidance: [],
    recommendedPackage,
    alternativePackages: [],
    indicativePrice,
    whereToBuyDistrict: district,
    computedAt,
    resolved: {
      commodity: {
        id: cid,
        name: profile.name,
        display_name: profile.name,
      },
    },
    recommendation: {
      packaging_name: recommendedPackage.name,
      packaging_description: recommendedPackage.name,
      kisan_instruction: `Stack gently in ${recommendedPackage.name.toLowerCase()} and maintain proper ventilation.`,
      key_action: 'maintain proper ventilation',
    },
    candidates: [
      {
        structure_name: recommendedPackage.name,
      },
    ],
  }
}
