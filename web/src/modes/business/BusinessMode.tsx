import React, { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { BusinessInputState, PackagingSpecSheet, DestinationMarket } from './types'
import {
  DEFAULT_BUSINESS_INPUT,
  COMMODITY_PRESETS,
  calculateBusinessResults,
  candidateToSpecSheet,
} from './engine'
import { ProgressiveForm } from './components/ProgressiveForm'
import { StructureCards } from './components/StructureCards'
import { ShelfLifeBandChart } from './components/ShelfLifeBandChart'
import { ComplianceChecklist } from './components/ComplianceChecklist'
import { EprLiabilityPanel } from './components/EprLiabilityPanel'
import { RfqGenerator } from './components/RfqGenerator'
import { CostBenefitPanel } from './components/CostBenefitPanel'
import { getApiUrl } from '../../api/config'
import { SaathiPanel } from '../../voice/SaathiPanel'
import { saathiLangFromI18n, type SaathiTurn } from '../../voice/voiceApi'
import { BUSINESS_PRESET_FOR, businessDisplayName } from '../../voice/labels'

const DESTINATION_MARKET_LABELS: Record<DestinationMarket, string> = {
  IN: 'India',
  EU: 'European Union',
  US: 'United States',
  GLOBAL: 'Global Export',
}

interface BusinessModeProps {
  /** A finished Saathi voice consultation handed over from Kisan mode. */
  voiceTurn?: SaathiTurn | null
}

export const BusinessMode: React.FC<BusinessModeProps> = ({ voiceTurn }) => {
  const { t, i18n } = useTranslation()
  const [inputState, setInputState] = useState<BusinessInputState>(DEFAULT_BUSINESS_INPUT)
  const [isSaathiOpen, setIsSaathiOpen] = useState<boolean>(false)
  const [voiceRefusal, setVoiceRefusal] = useState<SaathiTurn | null>(null)
  const [voiceSummary, setVoiceSummary] = useState<SaathiTurn | null>(null)
  const [calculationResults, setCalculationResults] = useState(() =>
    calculateBusinessResults(DEFAULT_BUSINESS_INPUT)
  )
  const [selectedStructureId, setSelectedStructureId] = useState<string>(
    calculationResults.structures[0]?.structureId || ''
  )
  const [rfqLoading, setRfqLoading] = useState(false)
  const [loadingStructureId, setLoadingStructureId] = useState<string | null>(null)
  const [rfqResult, setRfqResult] = useState<{
    structure: PackagingSpecSheet
    timestamp: string
  } | null>(null)
  const rfqRef = useRef<HTMLDivElement>(null)

  const handleGenerateRFQ = async (structure: PackagingSpecSheet) => {
    setRfqLoading(true)
    setLoadingStructureId(structure.structureId)
    setSelectedStructureId(structure.structureId)

    // Simulate realistic async operation (500ms)
    await new Promise((resolve) => setTimeout(resolve, 500))

    const now = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    setRfqResult({
      structure,
      timestamp: now,
    })
    setRfqLoading(false)
    setLoadingStructureId(null)

    // Scroll AFTER state update and re-render:
    setTimeout(() => {
      rfqRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120) // 120ms gives React time to commit the DOM update
  }

  const handleCalculate = async (payload?: any, override?: BusinessInputState) => {
    const cur = override ?? inputState
    if (!override) {
      setVoiceRefusal(null)
      setVoiceSummary(null)
    }
    const targetDays = payload?.target_shelf_life_days ?? cur.targetShelfLifeDays

    const reqBody = {
      mode: 'business',
      input: payload || {
        commodity_id: cur.commodityId,
        commodity_name: cur.commodityName,
        state: cur.state || 'fresh',
        storage_type: cur.storageType || 'ambient',
        target_shelf_life_days: targetDays,
        pack_size_g: cur.packSizeGrams,
        pack_area_m2: cur.packAreaM2,
        machine_type: cur.fillingMachine,
        destination_market: cur.destinationMarket,
        budget_per_pack_inr: cur.budgetPerPackInr,
        retail_price_inr: cur.productRetailPriceInr,
        environment: {
          storage_type: cur.storageType || 'ambient',
          temperature_c: cur.routeLegs[0]?.temperatureC ?? 30,
          relative_humidity_pct: cur.routeLegs[0]?.relativeHumidityPct ?? 75,
          legs: cur.routeLegs,
        },
        pack_geometry: {
          product_mass_kg: cur.packSizeGrams / 1000,
          pack_area_m2: cur.packAreaM2,
          filling_line: cur.fillingMachine,
        },
      },
      locale: 'en-IN',
    }

    try {
      const response = await fetch(getApiUrl('/api/v1/recommend'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody),
      })

      if (response.ok) {
        const sealed = await response.json()
        if (sealed && Array.isArray(sealed.candidates) && sealed.candidates.length > 0) {
          const totalRouteHours = cur.routeLegs.reduce((acc, l) => acc + l.durationHours, 0)
          const weightedTemp =
            cur.routeLegs.reduce((acc, l) => acc + l.temperatureC * l.durationHours, 0) /
            Math.max(1, totalRouteHours)
          const weightedRh =
            cur.routeLegs.reduce((acc, l) => acc + l.relativeHumidityPct * l.durationHours, 0) /
            Math.max(1, totalRouteHours)
          const hasSevereVibration = cur.routeLegs.some((l) => l.vibrationSeverity === 'severe')
          const tempStressFactor = Math.exp((weightedTemp - 25) / 18)
          const rhStressFactor = Math.max(0.6, weightedRh / 65)
          const flexStressMultiplier = hasSevereVibration ? 1.45 : 1.15
          const stressFactors = { tempStressFactor, rhStressFactor, flexStressMultiplier }

          const dynamicStructures: PackagingSpecSheet[] = sealed.candidates
            .slice(0, 3)
            .map((c: any, idx: number) => {
              const rank = (idx + 1) as 1 | 2 | 3
              return candidateToSpecSheet(c, rank, targetDays, stressFactors)
            })

          const baseResults = calculateBusinessResults({
            ...cur,
            commodityId: payload?.commodity_id ?? cur.commodityId,
            commodityName: payload?.commodity_name ?? cur.commodityName,
            targetShelfLifeDays: targetDays,
          })

          const newResults = {
            ...baseResults,
            structures: dynamicStructures,
          }

          setCalculationResults(newResults)
          setSelectedStructureId(dynamicStructures[0]?.structureId || '')
          return
        }
      }
    } catch (err) {
      console.warn('[AAVARAN] recommend API error, falling back to local engine:', err)
    }

    const fallbackResults = calculateBusinessResults({
      ...cur,
      commodityId: payload?.commodity_id ?? cur.commodityId,
      commodityName: payload?.commodity_name ?? cur.commodityName,
      targetShelfLifeDays: targetDays,
    })
    setCalculationResults(fallbackResults)
    setSelectedStructureId(fallbackResults.structures[0]?.structureId || '')
  }

  // Apply a Saathi voice consultation: fill the brief, then run the exact same engine input
  // Saathi used for its spoken answer, so the cards and the voice agree.
  const applyVoiceTurn = (turn: SaathiTurn) => {
    const slots = turn.slots
    const backendId = slots.commodity_id || ''
    const preset = COMMODITY_PRESETS.find((p) => p.id === BUSINESS_PRESET_FOR[backendId])
    const chilled = slots.storage === 'cold_room' || slots.storage === 'ice'
    const next: BusinessInputState = {
      ...inputState,
      commodityId: preset?.id ?? backendId,
      commodityName: preset?.name ?? businessDisplayName(backendId),
      packSizeGrams: slots.pack_size_g ?? preset?.defaultPackGrams ?? inputState.packSizeGrams,
      targetShelfLifeDays: slots.target_days ?? preset?.defaultShelfLifeDays ?? inputState.targetShelfLifeDays,
      productRetailPriceInr: preset?.defaultRetailInr ?? inputState.productRetailPriceInr,
      currentLossRatePct: preset?.defaultLossPct ?? inputState.currentLossRatePct,
      storageType: chilled ? 'chilled' : 'ambient',
      routeLegs: chilled
        ? inputState.routeLegs.map((l) => ({ ...l, temperatureC: slots.storage === 'ice' ? 2 : 4 }))
        : inputState.routeLegs,
    }
    setInputState(next)
    if (turn.status === 'blocked' || turn.result?.verdict === 'NOT_A_PACKAGING_PROBLEM') {
      setVoiceRefusal(turn)
      setVoiceSummary(null)
      return
    }
    setVoiceRefusal(null)
    setVoiceSummary(turn)
    if (turn.recommend_input) {
      handleCalculate({ ...turn.recommend_input, commodity_name: next.commodityName }, next)
    } else {
      handleCalculate(undefined, next)
    }
  }

  useEffect(() => {
    if (voiceTurn) applyVoiceTurn(voiceTurn)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceTurn])

  const selectedStructure =
    calculationResults.structures.find((s) => s.structureId === selectedStructureId) ||
    calculationResults.structures[0]

  return (
    <div className="w-full space-y-10" data-mode="business">
      {/* Shop / small food business banner: voice first, technical brief below */}
      <section className="border-4 border-ink bg-cyan p-5 sm:p-6 shadow-[6px_6px_0_var(--ink)] space-y-4">
        <div>
          <h2 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">{t('nav.shop_title')}</h2>
          <p className="font-body text-base text-ink mt-1 mb-0">{t('nav.shop_sub')}</p>
        </div>
        <button
          type="button"
          onClick={() => setIsSaathiOpen(true)}
          className="w-full min-h-[72px] border-4 border-ink bg-coral font-display uppercase text-lg sm:text-xl cursor-pointer shadow-[6px_6px_0_var(--ink)] hover:-translate-x-[2px] hover:-translate-y-[2px] flex items-center justify-center gap-3"
        >
          <span className="text-3xl" aria-hidden="true">🎙</span>
          <span>{t('saathi.open')}</span>
        </button>
        <div className="font-mono text-xs">
          <span className="text-ink/70">Market: </span>
          <span className="font-bold text-ink">
            {DESTINATION_MARKET_LABELS[inputState.destinationMarket] || inputState.destinationMarket}
          </span>
          <span className="text-ink/70"> · Detailed brief, converter RFQ, EPR and compliance below ↓</span>
        </div>
      </section>

      {isSaathiOpen && (
        <SaathiPanel
          mode="business"
          initialLang={saathiLangFromI18n(i18n.language)}
          onClose={() => setIsSaathiOpen(false)}
          onResult={(turn) => {
            setIsSaathiOpen(false)
            applyVoiceTurn(turn)
          }}
        />
      )}

      {voiceRefusal && (
        <section
          className="border-4 border-ink bg-coral p-5 sm:p-6 shadow-[6px_6px_0_var(--ink)] space-y-3"
          role="alert"
        >
          <div className="font-display uppercase text-xl sm:text-2xl">⚠ Not a packaging problem</div>
          <p className="font-body text-base m-0">{voiceRefusal.reply_text}</p>
          {voiceRefusal.result?.guidance?.length ? (
            <ul className="list-disc pl-6 font-body text-sm space-y-1 m-0">
              {voiceRefusal.result.guidance.map((g) => (
                <li key={g.action}>
                  <strong>{g.action.replace(/_/g, ' ')}:</strong> {g.headline}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="font-mono text-xs m-0">
            No packaging structure is shown because the Aavaran engine refused this case. Change the storage
            conditions in the brief below and recalculate.
          </p>
        </section>
      )}

      {voiceSummary && !voiceRefusal && (
        <section className="border-3 border-ink bg-lime p-4 shadow-[4px_4px_0_var(--ink)]">
          <div className="font-mono text-[11px] uppercase font-bold">🎙 Saathi said</div>
          <p className="font-body text-base m-0">{voiceSummary.reply_text}</p>
        </section>
      )}

      {/* 1. Progressive Brief Form */}
      <section>
        <ProgressiveForm
          input={inputState}
          onChange={setInputState}
          onCalculate={handleCalculate}
        />
      </section>

      {/* 2. Results: Three Ranked Structure Cards */}
      <section className={voiceRefusal ? 'hidden' : undefined}>
        <StructureCards
          structures={calculationResults.structures}
          selectedStructureId={selectedStructureId}
          onSelectStructure={(s) => setSelectedStructureId(s.structureId)}
          onOpenRfq={handleGenerateRFQ}
          rfqLoading={rfqLoading}
          loadingStructureId={loadingStructureId}
        />
      </section>

      {/* 3. Shelf-Life Chart: P10 to P90 Band */}
      {selectedStructure && !voiceRefusal && (
        <section>
          <ShelfLifeBandChart
            structure={selectedStructure}
            targetDays={inputState.targetShelfLifeDays}
            routeLegs={inputState.routeLegs}
          />
        </section>
      )}

      {/* 4. Compliance Checklist with Linked Clauses & Named Dossiers */}
      <section>
        <ComplianceChecklist items={calculationResults.complianceItems} />
      </section>

      {/* 5. EPR Liability Panel & Mono-Material Comparison */}
      <section>
        <EprLiabilityPanel epr={calculationResults.eprLiability} />
      </section>

      {/* 6. RFQ Generator Section with Visual Anchor and Auto-Scroll */}
      {rfqResult && (
        <section id="rfq-section">
          <div ref={rfqRef} className="rfq-result-section">
            <div className="rfq-section-header">
              <span className="font-display font-black text-sm sm:text-base">
                ✓ RFQ GENERATED — {rfqResult.structure.name}
              </span>
              <span className="font-mono text-xs normal-case opacity-90">
                Generated {rfqResult.timestamp}
              </span>
            </div>
            <div className="mt-4">
              <RfqGenerator
                input={inputState}
                structure={rfqResult.structure}
                onClose={() => setRfqResult(null)}
              />
            </div>
          </div>
        </section>
      )}

      {/* 7. Cost-Benefit & Break-Even Spoilage Panel */}
      <section>
        <CostBenefitPanel
          costBenefit={calculationResults.costBenefit}
          commodityName={inputState.commodityName}
        />
      </section>
    </div>
  )
}
