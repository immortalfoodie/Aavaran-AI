/**
 * Food safety gates and hazard interlocks in TypeScript.
 * Ported from engine/models/safety.py and verified against golden_models.json.
 */

export const RULE_BOTULINUM = 'SAFE-BOT-01'
export const RULE_FRESH_CUT = 'SAFE-FRESHCUT-01'
export const RULE_HISTAMINE = 'SAFE-HISTAMINE-01'
export const RULE_LIGHT_POTATO = 'SAFE-LIGHT-POTATO-01'

export const SCOMBROID_SPECIES = [
  'tuna',
  'mackerel',
  'mahi_mahi',
  'mahimahi',
  'bonito',
  'sardine',
  'anchovy',
]

export interface SafetyVerdict {
  status: 'PASS' | 'WARN' | 'BLOCK'
  ruleId: string
  rule_id?: string
  messageKey: string
  isOverridable: boolean
}

export function botulinumGate(params: {
  waterActivity?: number
  ph?: number
  o2Fraction?: number
  maxTemperatureC?: number
}): SafetyVerdict {
  const aw = params.waterActivity ?? 0.95
  const ph = params.ph ?? 6.0
  const o2 = params.o2Fraction ?? 0.209
  const temp = params.maxTemperatureC ?? 20.0

  if (aw > 0.92 && ph > 4.6 && o2 < 0.02 && temp > 5.0) {
    return {
      status: 'BLOCK',
      ruleId: RULE_BOTULINUM,
      messageKey:
        'This combination is unsafe. Either guarantee <=5 °C throughout, or do not remove oxygen. (aw > 0.92, pH > 4.6, O2 < 2%, T > 5 °C presents a lethal Clostridium botulinum hazard).',
      isOverridable: false,
    }
  }

  return {
    status: 'PASS',
    ruleId: RULE_BOTULINUM,
    messageKey: 'botulinum_gate_passed',
    isOverridable: true,
  }
}

export function histamineGate(params: {
  commodityId?: string
  maxTemperatureC?: number
}): SafetyVerdict {
  const cid = (params.commodityId || '').toLowerCase()
  const temp = params.maxTemperatureC ?? 20.0
  const isScombroid = SCOMBROID_SPECIES.some((s) => cid.includes(s))

  if (isScombroid && temp > 5.0) {
    return {
      status: 'BLOCK',
      ruleId: RULE_HISTAMINE,
      messageKey:
        'Scombroid-prone fish exposed to journey temperature > 5 °C. Permits rapid bacterial histidine decarboxylation and toxic histamine formation.',
      isOverridable: false,
    }
  }

  return {
    status: 'PASS',
    ruleId: RULE_HISTAMINE,
    messageKey: 'histamine_gate_passed',
    isOverridable: true,
  }
}

export function freshCutGate(params: {
  stateModifiers?: Record<string, unknown>
  maxTemperatureC?: number
  o2Fraction?: number
}): SafetyVerdict {
  const isCut = Boolean(params.stateModifiers?.cut || params.stateModifiers?.sliced || params.stateModifiers?.peeled)
  const temp = params.maxTemperatureC ?? 20.0
  const o2 = params.o2Fraction ?? 0.209

  if (isCut && temp > 5.0 && o2 < 0.20) {
    return {
      status: 'BLOCK',
      ruleId: RULE_FRESH_CUT,
      messageKey:
        'Fresh-cut produce stored at ambient temperature (> 5 °C) must never be sealed in reduced oxygen packaging due to anaerobic pathogen growth and fermentation.',
      isOverridable: false,
    }
  }

  return {
    status: 'PASS',
    ruleId: RULE_FRESH_CUT,
    messageKey: 'fresh_cut_gate_passed',
    isOverridable: true,
  }
}
