import React, { useState, useRef } from 'react'
import type { BusinessInputState, RouteLeg, TransportMode, FillingMachineType, DestinationMarket } from '../types'
import { COMMODITY_PRESETS } from '../engine'

interface ProgressiveFormProps {
  input: BusinessInputState
  onChange: (updated: BusinessInputState) => void
  onCalculate: (payload?: any) => void
}

export const ProgressiveForm: React.FC<ProgressiveFormProps> = ({
  input,
  onChange,
  onCalculate,
}) => {
  const [activeTab, setActiveTab] = useState<'product' | 'shelf_life' | 'route' | 'machine'>('product')
  const formRef = useRef(input)
  formRef.current = input

  const handleSelectPreset = (presetId: string) => {
    const preset = COMMODITY_PRESETS.find((p) => p.id === presetId)
    if (!preset) return
    onChange({
      ...input,
      commodityId: preset.id,
      commodityName: preset.name,
      packSizeGrams: preset.defaultPackGrams,
      targetShelfLifeDays: preset.defaultShelfLifeDays,
      productRetailPriceInr: preset.defaultRetailInr,
      currentLossRatePct: preset.defaultLossPct,
    })
  }

  const handleAddLeg = () => {
    const newLeg: RouteLeg = {
      id: `leg-${Date.now()}`,
      name: `Transit Leg ${input.routeLegs.length + 1}`,
      mode: 'ambient_truck',
      durationHours: 48,
      temperatureC: 32,
      relativeHumidityPct: 70,
      vibrationSeverity: 'moderate',
    }
    onChange({
      ...input,
      routeLegs: [...input.routeLegs, newLeg],
    })
  }

  const handleRemoveLeg = (id: string) => {
    if (input.routeLegs.length <= 1) return
    onChange({
      ...input,
      routeLegs: input.routeLegs.filter((l) => l.id !== id),
    })
  }

  const handleUpdateLeg = (id: string, updates: Partial<RouteLeg>) => {
    onChange({
      ...input,
      routeLegs: input.routeLegs.map((l) => (l.id === id ? { ...l, ...updates } : l)),
    })
  }

  const handleGenerateClick = () => {
    const cur = formRef.current

    const isChilled =
      cur.storageType === 'chilled' ||
      cur.routeLegs.some((l) => l.mode === 'refrigerated_truck' || l.temperatureC <= 10)
    const storage_type = cur.storageType || (isChilled ? 'chilled' : 'ambient')

    let stateVal = cur.state || 'fresh'
    const nameLower = (cur.commodityName || cur.commodityId || '').toLowerCase()
    if (
      nameLower.includes('namkeen') ||
      nameLower.includes('sev') ||
      nameLower.includes('bhujia') ||
      nameLower.includes('snack') ||
      nameLower.includes('fried')
    ) {
      stateVal = 'fried'
    } else if (
      nameLower.includes('turmeric') ||
      nameLower.includes('powder') ||
      nameLower.includes('haldi') ||
      nameLower.includes('spice')
    ) {
      stateVal = 'powder'
    } else if (nameLower.includes('spinach') || nameLower.includes('palak')) {
      stateVal = 'fresh'
    }

    const payload = {
      commodity_id: cur.commodityId || cur.commodityName,
      commodity_name: cur.commodityName,
      state: stateVal,
      hours_since_harvest: cur.hoursSinceHarvestOrProduction || 24,
      hours_since_production: cur.hoursSinceHarvestOrProduction || 24,
      hours_since: cur.hoursSinceHarvestOrProduction || 24,
      storage_type: storage_type,
      target_shelf_life_days: cur.targetShelfLifeDays,
      pack_size_g: cur.packSizeGrams,
      pack_area_m2: cur.packAreaM2,
      machine_type: cur.fillingMachine,
      destination_market:
        cur.destinationMarket === 'IN'
          ? 'india'
          : cur.destinationMarket === 'EU'
          ? 'export_eu'
          : cur.destinationMarket === 'US'
          ? 'export_us'
          : cur.destinationMarket,
      budget_per_pack_inr: cur.budgetPerPackInr,
      retail_price_inr: cur.productRetailPriceInr,
      environment: {
        storage_type: storage_type,
        temperature_c: cur.routeLegs[0]?.temperatureC ?? (isChilled ? 4 : 30),
        relative_humidity_pct: cur.routeLegs[0]?.relativeHumidityPct ?? 75,
        legs: cur.routeLegs,
      },
      pack_geometry: {
        product_mass_kg: cur.packSizeGrams / 1000,
        pack_area_m2: cur.packAreaM2,
        filling_line: cur.fillingMachine,
      },
    }

    console.log('[AAVARAN] recommend request:', JSON.stringify(payload, null, 2))
    onCalculate(payload)
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)]">
      {/* Header with cyan accent */}
      <div className="bg-cyan border-b-3 border-ink p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <span className="font-mono text-xs font-bold uppercase tracking-wider bg-ink text-paper px-2 py-0.5 inline-block mb-1">
            BUSINESS MODE SPECIFICATION BUILDER
          </span>
          <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
            Progressive Packaging Brief
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold">
            {input.routeLegs.length} JOURNEY LEGS · {input.targetShelfLifeDays}D TARGET
          </span>
        </div>
      </div>

      {/* Step Navigation Tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 border-b-3 border-ink bg-grey/30">
        {[
          { id: 'product', label: '1. PRODUCT & PACK', icon: '📦' },
          { id: 'shelf_life', label: '2. SHELF LIFE & BUDGET', icon: '⏱️' },
          { id: 'route', label: '3. JOURNEY BUILDER', icon: '🚚' },
          { id: 'machine', label: '4. MACHINE & MARKET', icon: '⚙️' },
        ].map((tab) => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`p-3 font-display text-xs sm:text-sm uppercase tracking-wide border-r-3 border-b-3 sm:border-b-0 border-ink cursor-pointer transition-colors ${
                isActive ? 'bg-cyan text-ink font-bold' : 'bg-paper text-ink/80 hover:bg-grey/50'
              }`}
            >
              <span className="mr-1.5">{tab.icon}</span>
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab Contents */}
      <div className="p-5 sm:p-6 space-y-6">
        {/* TAB 1: PRODUCT & PACK SIZE */}
        {activeTab === 'product' && (
          <div className="space-y-6">
            <div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                <label className="block font-display text-sm uppercase text-ink m-0">
                  Select Commodity / Product Type
                </label>
                <span className="font-mono text-xs text-ink/70">
                  Select a preset below or type any food commodity
                </span>
              </div>

              {/* Direct Search / Input */}
              <div className="mb-4">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Type commodity (e.g. besan namkeen, spinach, turmeric powder)..."
                    value={input.commodityName}
                    onChange={(e) => {
                      const val = e.target.value
                      const valLow = val.toLowerCase().trim()
                      const preset = COMMODITY_PRESETS.find(
                        (p) =>
                          p.name.toLowerCase().includes(valLow) ||
                          p.id.toLowerCase().includes(valLow)
                      )
                      onChange({
                        ...input,
                        commodityName: val,
                        commodityId: preset ? preset.id : valLow || input.commodityId,
                        ...(preset
                          ? {
                              packSizeGrams: preset.defaultPackGrams,
                              targetShelfLifeDays: preset.defaultShelfLifeDays,
                              productRetailPriceInr: preset.defaultRetailInr,
                              currentLossRatePct: preset.defaultLossPct,
                            }
                          : {}),
                      })
                    }}
                    className="w-full border-3 border-ink p-3 font-display text-sm bg-paper text-ink shadow-[3px_3px_0_var(--ink)] focus:outline-none focus:ring-2 focus:ring-cyan"
                  />
                  {input.commodityId && (
                    <span className="absolute right-3 top-3 font-mono text-[10px] bg-ink text-paper px-2 py-0.5 font-bold uppercase">
                      ID: {input.commodityId}
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {COMMODITY_PRESETS.map((preset) => {
                  const isSelected = input.commodityId === preset.id
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => handleSelectPreset(preset.id)}
                      className={`text-left p-3 border-3 border-ink transition-transform cursor-pointer ${
                        isSelected
                          ? 'bg-cyan translate-x-[2px] translate-y-[2px] shadow-[2px_2px_0_var(--ink)]'
                          : 'bg-paper shadow-[4px_4px_0_var(--ink)] hover:bg-grey/20'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-display text-xs uppercase">{preset.category}</span>
                        {isSelected && (
                          <span className="bg-ink text-cyan font-mono text-[10px] px-1 font-bold">
                            SELECTED
                          </span>
                        )}
                      </div>
                      <div className="font-display text-sm text-ink mb-1">{preset.name}</div>
                      <div className="font-body text-xs text-ink/80 line-clamp-2">
                        {preset.sensitivity}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div>
                <label className="block font-mono text-xs font-bold uppercase mb-1">
                  Pack Size (Net Weight)
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min="10"
                    max="10000"
                    step="10"
                    value={input.packSizeGrams}
                    onChange={(e) =>
                      onChange({ ...input, packSizeGrams: Math.max(1, Number(e.target.value)) })
                    }
                    className="w-full border-3 border-ink p-2.5 font-mono text-base bg-paper text-ink"
                  />
                  <span className="absolute right-3 top-2.5 font-mono text-xs font-bold text-ink/60">
                    GRAMS
                  </span>
                </div>
              </div>

              <div>
                <label className="block font-mono text-xs font-bold uppercase mb-1">
                  Estimated Pack Surface Area
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min="0.01"
                    max="1.5"
                    step="0.005"
                    value={input.packAreaM2}
                    onChange={(e) =>
                      onChange({ ...input, packAreaM2: Math.max(0.005, Number(e.target.value)) })
                    }
                    className="w-full border-3 border-ink p-2.5 font-mono text-base bg-paper text-ink"
                  />
                  <span className="absolute right-3 top-2.5 font-mono text-xs font-bold text-ink/60">
                    M² / PACK
                  </span>
                </div>
              </div>

              <div>
                <label className="block font-mono text-xs font-bold uppercase mb-1">
                  Product Retail Price
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min="1"
                    max="5000"
                    step="5"
                    value={input.productRetailPriceInr}
                    onChange={(e) =>
                      onChange({
                        ...input,
                        productRetailPriceInr: Math.max(1, Number(e.target.value)),
                      })
                    }
                    className="w-full border-3 border-ink p-2.5 font-mono text-base bg-paper text-ink"
                  />
                  <span className="absolute right-3 top-2.5 font-mono text-xs font-bold text-ink/60">
                    ₹ / PACK
                  </span>
                </div>
              </div>
            </div>

            {/* Preparation State & Storage Condition */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t-2 border-ink">
              <div>
                <label className="block font-mono text-xs font-bold uppercase mb-1">
                  Physical State / Preparation Form
                </label>
                <select
                  value={input.state || 'fresh'}
                  onChange={(e) => onChange({ ...input, state: e.target.value })}
                  className="w-full border-3 border-ink p-2.5 font-mono text-sm bg-paper text-ink"
                >
                  <option value="fresh">Fresh / Whole Produce</option>
                  <option value="fried">Fried / Savory Snack</option>
                  <option value="powder">Ground Spice / Dry Powder</option>
                  <option value="cut">Cut / Sliced Fresh Produce</option>
                  <option value="blanched">Blanched / Inactivated</option>
                </select>
              </div>

              <div>
                <label className="block font-mono text-xs font-bold uppercase mb-1">
                  Storage Condition / Cold Chain
                </label>
                <select
                  value={input.storageType || 'ambient'}
                  onChange={(e) => onChange({ ...input, storageType: e.target.value as any })}
                  className="w-full border-3 border-ink p-2.5 font-mono text-sm bg-paper text-ink"
                >
                  <option value="ambient">Ambient Storage (18–35 °C)</option>
                  <option value="chilled">Chilled / Refrigerated Cold Chain (2–8 °C)</option>
                  <option value="frozen">Frozen Deep Cold Chain (-18 °C)</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: SHELF LIFE & BUDGET */}
        {activeTab === 'shelf_life' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="p-4 border-3 border-ink bg-paper space-y-3">
                <div className="flex items-center justify-between">
                  <label className="font-display text-sm uppercase">Target Commercial Shelf Life</label>
                  <span className="font-mono text-lg font-bold bg-cyan px-2 border-2 border-ink">
                    {input.targetShelfLifeDays} DAYS
                  </span>
                </div>
                <input
                  type="range"
                  min="7"
                  max="365"
                  step="7"
                  value={input.targetShelfLifeDays}
                  onChange={(e) =>
                    onChange({ ...input, targetShelfLifeDays: Number(e.target.value) })
                  }
                  className="w-full accent-black cursor-pointer"
                />
                <div className="flex justify-between font-mono text-[10px] text-ink/60">
                  <span>7 DAYS (FRESH)</span>
                  <span>90 DAYS (QUARTER)</span>
                  <span>180 DAYS (SEMI-ANNUAL)</span>
                  <span>365 DAYS (ANNUAL)</span>
                </div>
              </div>

              <div className="p-4 border-3 border-ink bg-paper space-y-3">
                <div className="flex items-center justify-between">
                  <label className="font-display text-sm uppercase">Packaging Material Budget</label>
                  <span className="font-mono text-lg font-bold bg-yellow px-2 border-2 border-ink">
                    ₹{input.budgetPerPackInr.toFixed(2)} / PACK
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="10.0"
                  step="0.1"
                  value={input.budgetPerPackInr}
                  onChange={(e) =>
                    onChange({ ...input, budgetPerPackInr: Number(e.target.value) })
                  }
                  className="w-full accent-black cursor-pointer"
                />
                <div className="flex justify-between font-mono text-[10px] text-ink/60">
                  <span>₹0.50 (MONO-FILM)</span>
                  <span>₹2.50 (LAMINATE)</span>
                  <span>₹5.00 (HIGH BARRIER)</span>
                  <span>₹10.00 (RETORT)</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block font-mono text-xs font-bold uppercase mb-1">
                  Annual Pack Volume
                </label>
                <input
                  type="number"
                  min="10000"
                  max="50000000"
                  step="50000"
                  value={input.annualPackVolume}
                  onChange={(e) =>
                    onChange({ ...input, annualPackVolume: Math.max(1000, Number(e.target.value)) })
                  }
                  className="w-full border-3 border-ink p-2.5 font-mono text-base bg-paper text-ink"
                />
                <p className="font-body text-xs text-ink/70 mt-1">
                  Used for EPR quota liability and converter roll MOQ feasibility.
                </p>
              </div>

              <div>
                <label className="block font-mono text-xs font-bold uppercase mb-1">
                  Current Baseline Spoilage Rate
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min="0"
                    max="50"
                    step="0.5"
                    value={input.currentLossRatePct}
                    onChange={(e) =>
                      onChange({ ...input, currentLossRatePct: Number(e.target.value) })
                    }
                    className="w-full border-3 border-ink p-2.5 font-mono text-base bg-paper text-ink"
                  />
                  <span className="absolute right-3 top-2.5 font-mono text-xs font-bold text-ink/60">
                    % OF PRODUCTION
                  </span>
                </div>
                <p className="font-body text-xs text-ink/70 mt-1">
                  Used in the Cost-Benefit panel to calculate break-even margin protection.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: JOURNEY BUILDER (MULTI-LEG ROUTE) */}
        {activeTab === 'route' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="font-display text-base uppercase text-ink m-0">
                  Multi-Leg Cold & Dry Supply Chain Journey Builder
                </h3>
                <p className="font-body text-xs text-ink/80">
                  Specify transit temperatures, humidity, duration, and vibration stress to test Gelbo flex fatigue.
                </p>
              </div>
              <button
                type="button"
                onClick={handleAddLeg}
                className="font-display text-xs uppercase px-3 py-2 bg-cyan text-ink border-2 border-ink shadow-[2px_2px_0_var(--ink)] hover:bg-cyan/80 cursor-pointer self-start sm:self-auto"
              >
                + ADD ROUTE LEG
              </button>
            </div>

            <div className="space-y-3">
              {input.routeLegs.map((leg, index) => (
                <div
                  key={leg.id}
                  className="p-3 sm:p-4 border-3 border-ink bg-paper shadow-[3px_3px_0_var(--ink)] space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-ink pb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-display text-xs bg-ink text-paper px-2 py-0.5">
                        LEG {index + 1}
                      </span>
                      <input
                        type="text"
                        value={leg.name}
                        onChange={(e) => handleUpdateLeg(leg.id, { name: e.target.value })}
                        className="font-display text-sm uppercase bg-transparent border-b border-ink/40 focus:border-ink outline-none px-1 text-ink"
                      />
                    </div>
                    {input.routeLegs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveLeg(leg.id)}
                        className="font-mono text-xs text-coral hover:underline font-bold"
                      >
                        ✕ REMOVE
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div>
                      <label className="block font-mono font-bold mb-1">MODE</label>
                      <select
                        value={leg.mode}
                        onChange={(e) =>
                          handleUpdateLeg(leg.id, { mode: e.target.value as TransportMode })
                        }
                        className="w-full border-2 border-ink p-1.5 font-mono bg-paper text-ink"
                      >
                        <option value="ambient_truck">Ambient Truck</option>
                        <option value="refrigerated_truck">Refrigerated (Reefer)</option>
                        <option value="rail_container">Rail Container</option>
                        <option value="air_freight">Air Freight</option>
                        <option value="local_van">Local Delivery Van</option>
                      </select>
                    </div>

                    <div>
                      <label className="block font-mono font-bold mb-1">DURATION (HRS)</label>
                      <input
                        type="number"
                        min="1"
                        max="5000"
                        value={leg.durationHours}
                        onChange={(e) =>
                          handleUpdateLeg(leg.id, { durationHours: Number(e.target.value) })
                        }
                        className="w-full border-2 border-ink p-1.5 font-mono bg-paper text-ink"
                      />
                    </div>

                    <div>
                      <label className="block font-mono font-bold mb-1">TEMP (°C)</label>
                      <input
                        type="number"
                        min="-25"
                        max="55"
                        value={leg.temperatureC}
                        onChange={(e) =>
                          handleUpdateLeg(leg.id, { temperatureC: Number(e.target.value) })
                        }
                        className="w-full border-2 border-ink p-1.5 font-mono bg-paper text-ink"
                      />
                    </div>

                    <div>
                      <label className="block font-mono font-bold mb-1">VIBRATION / FLEX</label>
                      <select
                        value={leg.vibrationSeverity}
                        onChange={(e) =>
                          handleUpdateLeg(leg.id, {
                            vibrationSeverity: e.target.value as 'low' | 'moderate' | 'severe',
                          })
                        }
                        className={`w-full border-2 border-ink p-1.5 font-mono font-bold ${
                          leg.vibrationSeverity === 'severe'
                            ? 'bg-coral text-ink'
                            : leg.vibrationSeverity === 'moderate'
                            ? 'bg-yellow text-ink'
                            : 'bg-lime text-ink'
                        }`}
                      >
                        <option value="low">Low (Smooth Highway)</option>
                        <option value="moderate">Moderate (Interstate)</option>
                        <option value="severe">Severe (Rough Corrugated Road)</option>
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: FILLING MACHINE & DESTINATION MARKET */}
        {activeTab === 'machine' && (
          <div className="space-y-6">
            <div>
              <label className="block font-display text-sm uppercase mb-2">
                Filling Machine Type (Governs COF & Sealing Windows)
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {[
                  {
                    id: 'vffs',
                    label: 'Vertical Form Fill Seal (VFFS)',
                    desc: 'High speed reel-fed packing (70–120 ppm). Strict COF 0.18–0.22 required.',
                  },
                  {
                    id: 'hffs',
                    label: 'Horizontal Form Fill Seal (HFFS)',
                    desc: 'Flow-wrap machines for biscuits/bars. High hot-tack seal window required.',
                  },
                  {
                    id: 'premade_pouch',
                    label: 'Premade Pouch / Doypack',
                    desc: 'Pick, open, fill and seal machine. Pouch stiffness & zipper alignment key.',
                  },
                  {
                    id: 'thermoforming',
                    label: 'Vacuum Skin / Thermoform',
                    desc: 'Rigid base with high-barrier top web. Deep draw elongation required.',
                  },
                  {
                    id: 'manual_sealer',
                    label: 'Manual Impulse Sealer',
                    desc: 'Hand or pedal heat sealer for micro-enterprises and small batches.',
                  },
                ].map((m) => {
                  const isSelected = input.fillingMachine === m.id
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() =>
                        onChange({ ...input, fillingMachine: m.id as FillingMachineType })
                      }
                      className={`text-left p-3 border-3 border-ink transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-cyan translate-x-[2px] translate-y-[2px] shadow-[2px_2px_0_var(--ink)] font-bold'
                          : 'bg-paper shadow-[4px_4px_0_var(--ink)] hover:bg-grey/30'
                      }`}
                    >
                      <div className="font-display text-xs uppercase mb-1">{m.label}</div>
                      <div className="font-body text-xs text-ink/80">{m.desc}</div>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="border-t-2 border-ink pt-4">
              <label className="block font-display text-sm uppercase mb-2">
                Destination Statutory Market
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { id: 'IN', label: 'INDIA (FSSAI + PWM 2022)', badge: 'EPR CAT I-IV' },
                  { id: 'EU', label: 'EUROPEAN UNION (PPWR)', badge: 'EFSA + RECYCLASS' },
                  { id: 'US', label: 'UNITED STATES (FDA)', badge: '21 CFR 177' },
                  { id: 'GLOBAL', label: 'GLOBAL EXPORT', badge: 'ISO 22000' },
                ].map((market) => {
                  const isSelected = input.destinationMarket === market.id
                  return (
                    <button
                      key={market.id}
                      type="button"
                      onClick={() =>
                        onChange({ ...input, destinationMarket: market.id as DestinationMarket })
                      }
                      className={`p-3 border-3 border-ink text-center transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-cyan translate-x-[2px] translate-y-[2px] shadow-[2px_2px_0_var(--ink)]'
                          : 'bg-paper shadow-[4px_4px_0_var(--ink)] hover:bg-grey/30'
                      }`}
                    >
                      <div className="font-display text-xs uppercase">{market.label}</div>
                      <div className="font-mono text-[10px] font-bold text-ink/70 mt-1">
                        {market.badge}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4 border-t-3 border-ink">
          <div className="font-mono text-xs text-ink/80">
            Selected: <span className="font-bold">{input.commodityName}</span> ·{' '}
            <span className="font-bold">{input.packSizeGrams}g</span> ·{' '}
            <span className="font-bold">{input.fillingMachine.toUpperCase()}</span>
          </div>
          <button
            type="button"
            onClick={handleGenerateClick}
            className="w-full sm:w-auto font-display text-sm sm:text-base uppercase px-6 py-3 bg-cyan text-ink border-3 border-ink shadow-[4px_4px_0_var(--ink)] hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[6px_6px_0_var(--ink)] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0_var(--ink)] cursor-pointer transition-all flex items-center justify-center gap-2"
          >
            <span>⚡</span>
            <span>GENERATE THREE RANKED STRUCTURES & SPECS</span>
          </button>
        </div>
      </div>
    </div>
  )
}
