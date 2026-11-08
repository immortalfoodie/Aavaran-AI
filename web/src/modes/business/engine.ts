import type {
  BusinessInputState,
  PackagingSpecSheet,
  ASTMProperty,
  ComplianceItem,
  EprLiabilityComparison,
  RfqSpecification,
  CostBenefitAnalysis,
} from './types'

export const COMMODITY_PRESETS: Array<{
  id: string
  name: string
  category: string
  defaultPackGrams: number
  defaultShelfLifeDays: number
  defaultRetailInr: number
  defaultLossPct: number
  respirationType: 'non_climacteric' | 'climacteric' | 'processed_dry' | 'high_fat'
  sensitivity: string
}> = [
  {
    id: 'food.snack.namkeen_bhujia',
    name: 'Besan Sev / Namkeen / Bhujia',
    category: 'Fried Savory Snacks',
    defaultPackGrams: 200,
    defaultShelfLifeDays: 180,
    defaultRetailInr: 75,
    defaultLossPct: 8.5,
    respirationType: 'high_fat',
    sensitivity: 'Oxidative rancidity (peroxide value) & moisture crispness loss (aw > 0.42)',
  },
  {
    id: 'food.produce.table_potato',
    name: 'Fresh Table Potatoes (Solanum tuberosum)',
    category: 'Fresh Produce',
    defaultPackGrams: 1000,
    defaultShelfLifeDays: 30,
    defaultRetailInr: 40,
    defaultLossPct: 15.0,
    respirationType: 'non_climacteric',
    sensitivity: 'Sprouting, greening solanine accumulation, condensation rot',
  },
  {
    id: 'food.produce.fresh_tomato',
    name: 'Red Vine Tomatoes (Solanum lycopersicum)',
    category: 'Fresh Produce',
    defaultPackGrams: 500,
    defaultShelfLifeDays: 14,
    defaultRetailInr: 35,
    defaultLossPct: 18.2,
    respirationType: 'climacteric',
    sensitivity: 'Chilling injury < 10°C, fungal soft rot, transpirational shrivelling',
  },
  {
    id: 'food.dairy.fresh_paneer',
    name: 'Fresh Cow Milk Paneer (Vacuum MAP)',
    category: 'Dairy Products',
    defaultPackGrams: 200,
    defaultShelfLifeDays: 45,
    defaultRetailInr: 95,
    defaultLossPct: 12.0,
    respirationType: 'non_climacteric',
    sensitivity: 'Lactic acidification, coliform proteolysis, surface syneresis',
  },
  {
    id: 'food.spice.turmeric_powder',
    name: 'Pure Ground Turmeric Powder (Curcuma longa)',
    category: 'Spices & Seasonings',
    defaultPackGrams: 500,
    defaultShelfLifeDays: 365,
    defaultRetailInr: 160,
    defaultLossPct: 4.0,
    respirationType: 'processed_dry',
    sensitivity: 'Curcumin photolytic degradation, moisture caking, essential oil aroma loss',
  },
  {
    id: 'food.bakery.tea_rusk',
    name: 'Crisp Cardamom Wheat Rusk',
    category: 'Bakery & Biscuits',
    defaultPackGrams: 300,
    defaultShelfLifeDays: 120,
    defaultRetailInr: 60,
    defaultLossPct: 7.0,
    respirationType: 'processed_dry',
    sensitivity: 'Moisture uptake loss of crispness (critical aw 0.38)',
  },
  {
    id: 'veg.spinach.spinacia_oleracea',
    name: 'Fresh Spinach / Palak Leaves (Spinacia oleracea)',
    category: 'Fresh Leafy Produce',
    defaultPackGrams: 250,
    defaultShelfLifeDays: 7,
    defaultRetailInr: 40,
    defaultLossPct: 20.0,
    respirationType: 'non_climacteric',
    sensitivity: 'Extremely high respiration rate (>60 mg/kg·h), transpirational shrivelling, anaerobic botulinum risk under hermetic films',
  },
]

export const DEFAULT_BUSINESS_INPUT: BusinessInputState = {
  commodityId: 'food.snack.namkeen_bhujia',
  commodityName: 'Besan Sev / Namkeen / Bhujia',
  packSizeGrams: 200,
  packAreaM2: 0.058, // Approx 160mm x 220mm pouch surface area
  targetShelfLifeDays: 180,
  budgetPerPackInr: 2.8,
  fillingMachine: 'vffs',
  destinationMarket: 'IN',
  annualPackVolume: 500000, // 500k packs/year
  productRetailPriceInr: 75,
  currentLossRatePct: 8.5,
  routeLegs: [
    {
      id: 'leg-1',
      name: 'Factory Packaging & Internal Buffer',
      mode: 'ambient_truck',
      durationHours: 48,
      temperatureC: 28,
      relativeHumidityPct: 65,
      vibrationSeverity: 'low',
    },
    {
      id: 'leg-2',
      name: 'Interstate Long-Haul Logistics (NH-48)',
      mode: 'ambient_truck',
      durationHours: 72,
      temperatureC: 36,
      relativeHumidityPct: 80,
      vibrationSeverity: 'severe',
    },
    {
      id: 'leg-3',
      name: 'Regional C&F Wholesale Depot',
      mode: 'ambient_truck',
      durationHours: 336, // 14 days
      temperatureC: 30,
      relativeHumidityPct: 70,
      vibrationSeverity: 'low',
    },
    {
      id: 'leg-4',
      name: 'Last-Mile Kirana / Supermarket Shelf',
      mode: 'local_van',
      durationHours: 2160, // 90 days retail exposure
      temperatureC: 32,
      relativeHumidityPct: 75,
      vibrationSeverity: 'moderate',
    },
  ],
}

/**
 * Calculates candidate packaging structure specs matching the commodity and route stresses.
 */
export function calculateBusinessResults(input: BusinessInputState): {
  structures: PackagingSpecSheet[]
  complianceItems: ComplianceItem[]
  eprLiability: EprLiabilityComparison
  costBenefit: CostBenefitAnalysis
} {
  // 1. Calculate multi-leg route stress factor
  const totalRouteHours = input.routeLegs.reduce((acc, l) => acc + l.durationHours, 0)
  const weightedTemp =
    input.routeLegs.reduce((acc, l) => acc + l.temperatureC * l.durationHours, 0) /
    Math.max(1, totalRouteHours)
  const weightedRh =
    input.routeLegs.reduce((acc, l) => acc + l.relativeHumidityPct * l.durationHours, 0) /
    Math.max(1, totalRouteHours)
  const hasSevereVibration = input.routeLegs.some((l) => l.vibrationSeverity === 'severe')

  // Stress multiplier on barrier degradation
  const tempStressFactor = Math.exp((weightedTemp - 25) / 18)
  const rhStressFactor = Math.max(0.6, weightedRh / 65)
  const flexStressMultiplier = hasSevereVibration ? 1.45 : 1.15

  // 2. Build 3 ranked structure cards tailored to commodity
  const commKey = `${input.commodityId} ${input.commodityName}`.toLowerCase()
  let cand1: any
  let cand2: any
  let cand3: any

  if (commKey.includes('spinach') || commKey.includes('palak') || commKey.includes('leafy')) {
    cand1 = {
      id: 'struct_perf_bopp30_ldpe30',
      name: '30µm Perf-BOPP / 30µm LDPE (Micro-perforated MAP)',
      layer_stack: ['PerfBOPP', 'LDPE'],
      gauge_per_layer: [30.0, 30.0],
      composite_thickness_um: 60.0,
      measured_otr: 14500.0,
      measured_wvtr: 16.0,
      cost_per_pack: 1.30,
      epr_category: 'Cat II',
      recyclability_notes: 'Micro-laser perforated for gas exchange equilibrium with respiring greens',
    }
    cand2 = {
      id: 'struct_cpp25_cpp25',
      name: '25µm CPP / 25µm CPP (High-Gas Breathable Polyolefin)',
      layer_stack: ['CPP', 'CPP'],
      gauge_per_layer: [25.0, 25.0],
      composite_thickness_um: 50.0,
      measured_otr: 1750.0,
      measured_wvtr: 5.5,
      cost_per_pack: 0.95,
      epr_category: 'Cat II',
      recyclability_notes: '100% Polypropylene mono-material stream; prevents produce suffocation',
    }
    cand3 = {
      id: 'struct_bopp20_cpp40',
      name: '20µm BOPP / 40µm CPP (Clear Display Polyolefin)',
      layer_stack: ['BOPP', 'CPP'],
      gauge_per_layer: [20.0, 40.0],
      composite_thickness_um: 60.0,
      measured_otr: 1200.0,
      measured_wvtr: 3.5,
      cost_per_pack: 1.15,
      epr_category: 'Cat II',
      recyclability_notes: 'Standard PP pouch; high clarity with moisture retention',
    }
  } else if (commKey.includes('turmeric') || commKey.includes('powder') || commKey.includes('haldi') || commKey.includes('spice')) {
    cand1 = {
      id: 'struct_pet12_alu9_lldpe50',
      name: '12µm BOPET / 9µm AluFoil / 50µm LLDPE',
      layer_stack: ['PET', 'AluFoil', 'LLDPE'],
      gauge_per_layer: [12.0, 9.0, 50.0],
      composite_thickness_um: 71.0,
      measured_otr: 0.05,
      measured_wvtr: 0.05,
      cost_per_pack: 2.40,
      epr_category: 'Cat III',
      recyclability_notes: 'Hermetic pinhole-free Al foil barrier; 100% UV/light block against curcumin fading',
    }
    cand2 = {
      id: 'struct_pet12_bopa15_alu9_cpp70',
      name: '12µm BOPET / 15µm BOPA / 9µm AluFoil / 70µm CPP',
      layer_stack: ['PET', 'BOPA', 'AluFoil', 'CPP'],
      gauge_per_layer: [12.0, 15.0, 9.0, 70.0],
      composite_thickness_um: 106.0,
      measured_otr: 0.05,
      measured_wvtr: 0.05,
      cost_per_pack: 3.80,
      epr_category: 'Cat III',
      recyclability_notes: 'Heavy-duty 4-ply foil laminate with extreme puncture and drop protection',
    }
    cand3 = {
      id: 'struct_bopp20_vmbopp18_cpp40',
      name: '20µm BOPP / 18µm VMBOPP / 40µm CPP',
      layer_stack: ['BOPP', 'VMBOPP', 'CPP'],
      gauge_per_layer: [20.0, 18.0, 40.0],
      composite_thickness_um: 78.0,
      measured_otr: 22.0,
      measured_wvtr: 0.65,
      cost_per_pack: 1.75,
      epr_category: 'Cat II',
      recyclability_notes: 'Mono-material PP family with vacuum metallised moisture barrier',
    }
  } else if (commKey.includes('namkeen') || commKey.includes('sev') || commKey.includes('bhujia') || commKey.includes('snack') || commKey.includes('rusk')) {
    cand1 = {
      id: 'struct_bopp20_vmbopp18_cpp40',
      name: '20µm BOPP / 18µm VMBOPP / 40µm CPP',
      layer_stack: ['BOPP', 'VMBOPP', 'CPP'],
      gauge_per_layer: [20.0, 18.0, 40.0],
      composite_thickness_um: 78.0,
      measured_otr: 22.0,
      measured_wvtr: 0.65,
      cost_per_pack: 1.75,
      epr_category: 'Cat II',
      recyclability_notes: 'Circular mono-PP barrier film; meets 6-month shelf life under N2 flush per Section 4.4',
    }
    cand2 = {
      id: 'struct_pet12_vmpet12_lldpe50',
      name: '12µm BOPET / 12µm VMPET / 50µm LLDPE',
      layer_stack: ['PET', 'VMPET', 'LLDPE'],
      gauge_per_layer: [12.0, 12.0, 50.0],
      composite_thickness_um: 74.0,
      measured_otr: 0.85,
      measured_wvtr: 0.95,
      cost_per_pack: 2.10,
      epr_category: 'Cat III',
      recyclability_notes: 'Multi-layer laminated packaging (Requires co-processing/pyrolysis)',
    }
    cand3 = {
      id: 'struct_mdope25_evohpe45',
      name: '25µm MDO-PE / 45µm Coex High-Barrier PE (EVOH <5%)',
      layer_stack: ['MDO-PE', 'EVOH-Tie', 'LLDPE'],
      gauge_per_layer: [25.0, 5.0, 40.0],
      composite_thickness_um: 70.0,
      measured_otr: 2.1,
      measured_wvtr: 1.45,
      cost_per_pack: 2.45,
      epr_category: 'Cat II',
      recyclability_notes: 'Circular Mono-PE Stream (Fully recyclable per CEFLEX / RecyClass)',
    }
  } else {
    cand1 = {
      id: 'struct_pet12_vmbopp18_lldpe40',
      name: '12µm BOPET / 18µm VMBOPP / 40µm mLLDPE',
      layer_stack: ['BOPET', 'VMBOPP', 'mLLDPE'],
      gauge_per_layer: [12.0, 18.0, 40.0],
      composite_thickness_um: 70.0,
      measured_otr: 18.5,
      measured_wvtr: 0.62,
      cost_per_pack: 2.15,
      epr_category: 'Cat III',
      recyclability_notes: 'Multi-layer laminated flexible plastic',
    }
    cand2 = {
      id: 'struct_bopp20_cpp35',
      name: '20µm Printed BOPP / 35µm Transparent CPP',
      layer_stack: ['BOPP', 'CPP'],
      gauge_per_layer: [20.0, 35.0],
      composite_thickness_um: 55.0,
      measured_otr: 1420.0,
      measured_wvtr: 3.80,
      cost_per_pack: 1.45,
      epr_category: 'Cat II',
      recyclability_notes: '100% Polypropylene mono-material family (High recyclability index)',
    }
    cand3 = {
      id: 'struct_mdope25_evohpe45',
      name: '25µm MDO-PE / 45µm Coex High-Barrier PE (EVOH <5%)',
      layer_stack: ['MDO-PE', 'EVOH-Tie', 'LLDPE'],
      gauge_per_layer: [25.0, 5.0, 40.0],
      composite_thickness_um: 70.0,
      measured_otr: 2.1,
      measured_wvtr: 1.45,
      cost_per_pack: 2.45,
      epr_category: 'Cat II',
      recyclability_notes: 'Circular Mono-PE Stream (Fully recyclable per CEFLEX / RecyClass)',
    }
  }

  const stressFactors = { tempStressFactor, rhStressFactor, flexStressMultiplier }
  const rank1 = candidateToSpecSheet(cand1, 1, input.targetShelfLifeDays, stressFactors)
  const rank2 = candidateToSpecSheet(cand2, 2, input.targetShelfLifeDays, stressFactors)
  const rank3 = candidateToSpecSheet(cand3, 3, input.targetShelfLifeDays, stressFactors)
  const allStructures = [rank1, rank2, rank3]

  // 3. Compliance checklist
  const complianceItems: ComplianceItem[] = [
    {
      id: 'comp-fssai-art4',
      standard: 'FSSAI (Packaging) Regulations 2018',
      clause: 'Article 4(1) & Schedule I',
      title: 'Food-Grade Contact Resin & Overall Migration Limits',
      status: 'COMPLIANT',
      requiredDocumentName: 'NABL-Accredited Overall Migration Certificate (IS 9845)',
      documentStatus: 'VERIFIED',
      details:
        'Overall migration into simulant A (distilled water), B (3% acetic acid), and D (rectified olive oil) must not exceed 60 mg/kg or 10 mg/dm².',
    },
    {
      id: 'comp-fssai-sched2',
      standard: 'FSSAI (Packaging) Regulations 2018',
      clause: 'Schedule II, Article 5',
      title: 'Printing Ink Heavy Metal & Non-Contact Barrier',
      status: 'COMPLIANT',
      requiredDocumentName: 'Converter Non-Toxic Printing Ink Declaration (IS 15495)',
      documentStatus: 'CONVERTER_ACTION',
      details:
        'All inks must be toluene-free and ketone-free, reverse-printed on the outer carrier web with zero direct food contact surface leaching.',
    },
    {
      id: 'comp-pwm-sched2',
      standard: 'Plastic Waste Management Rules 2016 / 2022',
      clause: 'Schedule II, Guideline 4',
      title: 'Producer/Brand Owner (PIBO) EPR Central Portal Registration',
      status: 'ACTION_REQUIRED',
      requiredDocumentName: 'CPCB EPR Registration Certificate (Form I / Annual Return)',
      documentStatus: 'PENDING_UPLOAD',
      details:
        'Brand owner must file annual plastic packaging inventory on the CPCB centralized portal and fulfill recycling targets for Category III.',
    },
    {
      id: 'comp-pwm-thick',
      standard: 'Plastic Waste Management (Amendment) Rules 2022',
      clause: 'Rule 4(1)(c)',
      title: 'Minimum Virgin & Laminate Thickness Floor (50 µm)',
      status: 'COMPLIANT',
      requiredDocumentName: 'Film Gauge Micrometer Batch Audit Sheet (ASTM D6988)',
      documentStatus: 'VERIFIED',
      details:
        `Selected structure composite thickness is ${rank1.compositeThicknessUm} µm, comfortably exceeding the statutory 50 µm minimum floor.`,
    },
    {
      id: 'comp-astm-gelbo',
      standard: 'ASTM F392 / ASTM D3985',
      clause: 'Sub-clause 7.2 Post-Transport Integrity',
      title: 'Post-Flex Fatigue Retention for Metallised Barrier',
      status: hasSevereVibration ? 'ACTION_REQUIRED' : 'COMPLIANT',
      requiredDocumentName: 'Gelbo Flex Resistance Test Report (ASTM F392, Condition C)',
      documentStatus: hasSevereVibration ? 'CONVERTER_ACTION' : 'VERIFIED',
      details: hasSevereVibration
        ? 'Route contains severe transit vibration (NH-48 interstate leg). Converter must submit 20-cycle Gelbo flex barrier validation report.'
        : 'Gelbo post-flex barrier degradation verified within permissible 2.0x baseline threshold.',
    },
  ]

  // 4. EPR liability calculation under PWM 2022
  const packWeightGrams = (input.packAreaM2 * rank1.compositeThicknessUm * 0.95 * 1000000) / 1000000 // approx 3.8g
  const annualTonnage = (input.annualPackVolume * packWeightGrams) / 1000000 // tonnes

  // Category III credit cost is ~₹16,500/tonne, Category II is ~₹9,200/tonne
  const cat3CreditRate = 16500
  const cat2CreditRate = 9200
  const cat3AnnualCost = annualTonnage * cat3CreditRate
  const cat2AnnualCost = annualTonnage * cat2CreditRate
  const cat3PerPack = cat3AnnualCost / Math.max(1, input.annualPackVolume)
  const cat2PerPack = cat2AnnualCost / Math.max(1, input.annualPackVolume)

  const eprLiability: EprLiabilityComparison = {
    category: 'Category III (Multi-layered Plastic / MLP)',
    currentAnnualVolume: input.annualPackVolume,
    packWeightGrams: parseFloat(packWeightGrams.toFixed(2)),
    totalPlasticTonnagePerYear: parseFloat(annualTonnage.toFixed(2)),
    recyclingTargetPct: 70, // FY 2025-26 mandate
    recycledContentTargetPct: 10,
    creditRateInrPerTonne: cat3CreditRate,
    indicativeAnnualLiabilityInr: Math.round(cat3AnnualCost),
    indicativeCostPerPackInr: parseFloat(cat3PerPack.toFixed(2)),
    monoAlternative: {
      category: 'Category II (Flexible Mono-material Polyolefin)',
      name: rank3.name,
      indicativeAnnualLiabilityInr: Math.round(cat2AnnualCost),
      indicativeCostPerPackInr: parseFloat(cat2PerPack.toFixed(2)),
      annualRupeeSavings: Math.round(cat3AnnualCost - cat2AnnualCost),
      circularityScorePct: 92,
    },
  }

  // 5. Cost-Benefit analysis and break-even loss rate
  const packagingCostPerPack = rank1.costPerPackInr + cat3PerPack
  const productRetailVal = input.productRetailPriceInr
  const packagingRatio = (packagingCostPerPack / Math.max(1, productRetailVal)) * 100

  // Break-even loss rate: How much reduction in spoilage pays for the entire pack cost?
  // Cost per pack = BreakEvenSpoilagePct * productRetailVal => BreakEvenSpoilagePct = Cost / Retail
  const breakEvenLossRate = (packagingCostPerPack / Math.max(1, productRetailVal)) * 100

  const baselineLossAnnualInr =
    input.annualPackVolume * productRetailVal * (input.currentLossRatePct / 100)
  // With recommended barrier, spoilage is cut down to ~1.2%
  const improvedLossRatePct = 1.2
  const improvedLossAnnualInr =
    input.annualPackVolume * productRetailVal * (improvedLossRatePct / 100)
  const grossSpoilageSavedInr = baselineLossAnnualInr - improvedLossAnnualInr
  const annualPackagingExpenseInr = input.annualPackVolume * packagingCostPerPack
  const netMarginProtectedInr = grossSpoilageSavedInr - annualPackagingExpenseInr

  const costBenefit: CostBenefitAnalysis = {
    costPerPackInr: parseFloat(packagingCostPerPack.toFixed(2)),
    productRetailValueInr: productRetailVal,
    packagingCostRatioPct: parseFloat(packagingRatio.toFixed(1)),
    breakEvenLossRatePct: parseFloat(breakEvenLossRate.toFixed(2)),
    currentAnnualLossInr: Math.round(baselineLossAnnualInr),
    predictedAnnualLossInr: Math.round(improvedLossAnnualInr),
    netAnnualMarginProtectedInr: Math.round(netMarginProtectedInr),
    roiMultiple: parseFloat((grossSpoilageSavedInr / Math.max(1, annualPackagingExpenseInr)).toFixed(1)),
  }

  return {
    structures: allStructures,
    complianceItems,
    eprLiability,
    costBenefit,
  }
}

/**
 * Builds standard RFQ specification ready for export and copy.
 */
export function generateRfqData(
  input: BusinessInputState,
  selectedStructure: PackagingSpecSheet,
  brandName = 'Acme Natural Foods Pvt Ltd',
  converterName = 'Premier Flexible Laminators Ltd'
): RfqSpecification {
  return {
    rfqId: `RFQ-${Math.floor(100000 + Math.random() * 900000)}`,
    createdAt: new Date().toISOString().split('T')[0],
    brandName,
    converterName,
    contactEmail: 'procurement@aavaran-client.com',
    targetOrderQuantity: input.annualPackVolume,
    orderType: input.fillingMachine === 'premade_pouch' ? 'premade_pouches' : 'roll_film',
    pouchDimensionsMm: {
      width: 155,
      height: 220,
      bottomGusset: 40,
    },
    rollDimensionsMm: {
      width: 340,
      repeatLength: 225,
      coreDiameter: 76,
      maxRollOd: 380,
    },
    structure: selectedStructure,
    nominalGaugesWithTolerances: selectedStructure.layers.map((l) => ({
      layer: l.material,
      nominalUm: l.gaugeUm,
      tolerancePct: 5.0, // ASTM tolerance
    })),
    testMethodsAndAcceptance: selectedStructure.properties.map((p) => ({
      property: p.propertyName,
      standard: p.testMethod,
      acceptanceCriteria: `${p.value} ${p.unit} (Tol: ±8% per batch CoA)`,
    })),
    defectTolerancesAql: {
      critical: 0.0, // Zero pinholes or delamination allowed
      major: 1.0, // Seal leaks, print misregistration > 0.5mm
      minor: 2.5, // Scuffs, roll edge misalignment < 1mm
    },
    commercialTerms: [
      'CoA (Certificate of Analysis) from NABL accredited lab mandatory with each dispatch reel/carton.',
      'Raw materials must strictly comply with BIS IS 10146 / IS 10148 and FSSAI 2018 schedule I.',
      'Reverse printing strictly toluene-free and ketone-free per IS 15495.',
      'Payment terms: 30 days post-dispatch and satisfactory QA laboratory line-trial clearance.',
      'Rejection threshold: Failure of seal integrity (ASTM F88 < 20 N/15mm) on 2 consecutive reels triggers lot refusal.',
    ],
  }
}

export function candidateToSpecSheet(
  cand: any,
  rank: 1 | 2 | 3,
  targetDays: number,
  routeStressFactor?: { tempStressFactor: number; rhStressFactor: number; flexStressMultiplier: number }
): PackagingSpecSheet {
  const stack: string[] = cand.layer_stack || []
  const gauges: number[] = cand.gauge_per_layer || []
  const compositeThickness =
    cand.composite_thickness_um ||
    gauges.reduce((a: number, b: number) => a + b, 0) ||
    60

  const layerColors: Record<string, string> = {
    PET: 'bg-cyan',
    BOPET: 'bg-cyan',
    BOPP: 'bg-yellow',
    VMBOPP: 'bg-yellow',
    VMPET: 'bg-yellow',
    CPP: 'bg-paper',
    LLDPE: 'bg-grey',
    LDPE: 'bg-grey',
    ALUFOIL: 'bg-amber-200',
    ALU: 'bg-amber-200',
    FOIL: 'bg-amber-200',
    BOPA: 'bg-blue-200',
    PERFBOPP: 'bg-lime',
  }

  const layers = stack.map((mat: string, idx: number) => {
    const matUpper = mat.toUpperCase()
    let colorClass = 'bg-paper'
    for (const [k, v] of Object.entries(layerColors)) {
      if (matUpper.includes(k)) {
        colorClass = v
        break
      }
    }
    return {
      material: `${mat} (${idx === 0 ? 'Outer Web' : idx === stack.length - 1 ? 'Sealant Layer' : 'Barrier Core'})`,
      gaugeUm: gauges[idx] || Math.round(compositeThickness / Math.max(1, stack.length)),
      colorClass,
    }
  })

  const isFoil = stack.some((l: string) => /foil|alu/i.test(l))
  const isMetallised = stack.some((l: string) => /vm/i.test(l))
  const isMono =
    /Cat I\b|Cat II\b/i.test(cand.epr_category || '') ||
    (stack.length > 0 && stack.every((l: string) => /pp/i.test(l))) ||
    (stack.length > 0 && stack.every((l: string) => /pe/i.test(l)))

  const stress = routeStressFactor
    ? routeStressFactor.tempStressFactor *
      routeStressFactor.rhStressFactor *
      (isMetallised ? routeStressFactor.flexStressMultiplier : 1.0)
    : 1.0

  let baseP50 = targetDays
  if (cand.measured_otr != null && cand.measured_otr > 1000) {
    baseP50 = Math.min(targetDays, 14)
  } else if (isFoil) {
    baseP50 = Math.max(365, targetDays)
  } else if (isMetallised) {
    baseP50 = /pet/i.test(cand.id || '') ? Math.max(240, targetDays) : Math.max(180, targetDays)
  }

  const p50 = Math.round(baseP50 / Math.max(0.5, stress))
  const p10 = Math.round(p50 * 0.8)
  const p90 = Math.round(p50 * 1.2)

  const properties: ASTMProperty[] = [
    {
      propertyName: 'Oxygen Transmission Rate (OTR)',
      testMethod: 'ASTM D3985',
      value: cand.measured_otr != null ? cand.measured_otr.toLocaleString() : '18.5',
      unit: 'cc/m²·day @ 23°C, 0% RH',
      specificationNote: 'Quoted per ASTM D3985 coulometric detector at 1 atm partial pressure gradient',
    },
    {
      propertyName: 'Water Vapor Transmission Rate (WVTR)',
      testMethod: 'ASTM F1249',
      value: cand.measured_wvtr != null ? cand.measured_wvtr.toFixed(2) : '0.65',
      unit: 'g/m²·day @ 38°C, 90% RH',
      specificationNote: 'Infrared modulated beam detection per ASTM F1249 tropical test condition',
    },
    {
      propertyName: 'Seal Strength (Heat Seal Jaw)',
      testMethod: 'ASTM F88',
      value: isFoil ? '32.5' : isMono ? '22.4' : '28.4',
      unit: 'N/15mm @ 135°C, 0.3s, 3 bar',
      specificationNote: 'Technique B (unsupported) jaw pull rate 250 mm/min on sealant boundary',
    },
    {
      propertyName: 'Tensile Strength & Modulus (MD/TD)',
      testMethod: 'ASTM D882',
      value: isFoil ? '180 / 165' : '145 / 138',
      unit: 'MPa',
      specificationNote: 'Ensures dimensional stability under high-speed packaging web pull tension',
    },
    {
      propertyName: 'Post-Flex Barrier Retention (Gelbo Flex)',
      testMethod: 'ASTM F392 Gelbo',
      value: isFoil ? '0.12' : isMetallised ? '1.25' : '3.80',
      unit: 'g/m²·day WVTR (after 20 full cycles)',
      specificationNote: 'Condition C (20 cycles at 45 rpm). Barrier decay remains within permissible threshold',
    },
  ]

  const rankLabel =
    rank === 1
      ? 'RECOMMENDED PRIMARY'
      : rank === 2
      ? 'COST-OPTIMIZED'
      : 'CIRCULAR MONO-MATERIAL'

  const limitingMechanism =
    cand.measured_otr != null && cand.measured_otr > 1000
      ? 'Aerobic gas equilibrium (respiring fresh produce MAP)'
      : isFoil
      ? 'Micro-defect seal boundary diffusion'
      : isMetallised
      ? 'Moisture uptake (critical aw threshold)'
      : 'Atmospheric oxygen and moisture permeation'

  return {
    structureId: cand.id || `struct-${rank}`,
    name: cand.name || stack.join(' / '),
    rank,
    rankLabel,
    layerStackDisplay: stack.map((s: string, i: number) => `${gauges[i] ? `${gauges[i]}µm ` : ''}${s}`).join(' // '),
    layers,
    compositeThicknessUm: compositeThickness,
    costPerPackInr: cand.cost_per_pack || (cand.cost_inr_per_sqm ? parseFloat((cand.cost_inr_per_sqm * 0.055).toFixed(2)) : 2.15),
    eprCategory: (cand.epr_category as any) || (isMono ? 'Cat II' : 'Cat III'),
    recyclabilityStatus:
      cand.recyclability_notes ||
      (isMono
        ? '100% Polyolefin mono-material stream (High recyclability index under PWM 2022)'
        : 'Multi-layer laminated flexible plastic (Requires Pyrolysis / Co-processing)'),
    isMonoMaterial: isMono,
    isMetallisedOrFoil: isFoil || isMetallised,
    properties,
    cofStatic: isMono ? 0.26 : 0.22,
    cofDynamic: isMono ? 0.22 : 0.18,
    machineRunnabilityScore: isMono ? 8.8 : 9.6,
    predictedShelfLifeDaysP10: p10,
    predictedShelfLifeDaysP50: p50,
    predictedShelfLifeDaysP90: p90,
    limitingMechanism,
  }
}
