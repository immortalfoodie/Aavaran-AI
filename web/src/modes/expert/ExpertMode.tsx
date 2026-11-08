import React, { useState, useEffect, useCallback, useMemo } from 'react'
import type { LedgerParameter, SavedScenario, SealedResult } from './types'
import {
  INITIAL_LEDGER_PARAMETERS,
  generateParetoCandidates,
} from './engine'
import { ParameterEditor } from './components/ParameterEditor'
import { ModelInspector } from './components/ModelInspector'
import { SensitivityTornadoChart } from './components/SensitivityTornadoChart'
import { MonteCarloDistribution } from './components/MonteCarloDistribution'
import { ParetoFrontierPlot } from './components/ParetoFrontierPlot'
import { ScenarioComparison } from './components/ScenarioComparison'
import { ComplianceRuleTrace } from './components/ComplianceRuleTrace'
import { ExportAndShare } from './components/ExportAndShare'
import { RawJsonViewer } from './components/RawJsonViewer'
import { getApiUrl } from '../../api/config'

interface ExpertModeProps {
  result?: SealedResult | null
}

/** Convert SealedResult.assumptions[] into LedgerParameter[] for ParameterEditor */
function assumptionsToLedgerParameters(assumptions: SealedResult['assumptions']): LedgerParameter[] {
  if (!assumptions || assumptions.length === 0) return []

  const CATEGORY_MAP: Record<string, LedgerParameter['category']> = {
    moisture_pct: 'commodity',
    water_activity: 'commodity',
    fat_pct: 'commodity',
    pH: 'commodity',
    storage_temperature: 'environment',
    storage_rh: 'environment',
    respiration_rate_or_na: 'commodity',
    pack_area: 'geometry',
    otr: 'geometry',
    wvtr: 'geometry',
    composite_thickness_um: 'geometry',
    initial_count: 'microbial',
    growth_rate: 'microbial',
    lag_time: 'microbial',
  }

  const SYMBOL_MAP: Record<string, string> = {
    moisture_pct: 'm₀',
    water_activity: 'aᵥ',
    storage_temperature: 'T',
    storage_rh: 'RH',
    pack_area: 'A',
    respiration_rate_or_na: 'R',
    otr: 'OTR',
    wvtr: 'WVTR',
    fat_pct: 'fat%',
    pH: 'pH',
    composite_thickness_um: 'δ',
  }

  return assumptions.map((a, idx) => {
    const fieldName = a.field || `assumption_${idx}`
    const numVal = typeof a.value === 'number' ? a.value : parseFloat(a.value) || 0
    return {
      id: `assum_${fieldName}_${idx}`,
      category: CATEGORY_MAP[fieldName] || 'commodity',
      name: fieldName.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      symbol: SYMBOL_MAP[fieldName] || fieldName.slice(0, 4),
      defaultValue: numVal,
      currentValue: numVal,
      unit: a.unit || '',
      description: a.note || `Engine-resolved ${fieldName}`,
      provenance: a.source_type || 'ENGINE',
      citation: {
        source: a.source_id || 'Aavaran KB',
        title: a.note || fieldName,
      },
      confidence: a.confidence != null ? Math.round(a.confidence * 10) : 7,
      isOverridden: false,
      minAllowed: numVal * 0.1,
      maxAllowed: numVal * 10 || 1000,
      step: numVal * 0.01 || 0.01,
    }
  })
}

// Page-session module cache: retains fetched result and parameter modifications
// across tab switches (Kisan <-> Business <-> Expert) in the same session,
// but automatically resets when the whole page is refreshed/reloaded.
let sessionExpertResult: SealedResult | null = null
let sessionExpertParameters: LedgerParameter[] | null = null
let sessionExpertScenarios: SavedScenario[] | null = null
let sessionHasStartedFetch = false

export const ExpertMode: React.FC<ExpertModeProps> = ({ result: externalResult }) => {
  const [liveResult, setLiveResult] = useState<SealedResult | null>(() => {
    if (externalResult) return externalResult
    return sessionExpertResult
  })
  const [loading, setLoading] = useState<boolean>(() => {
    if (externalResult || sessionExpertResult) return false
    return !sessionHasStartedFetch
  })
  const [fetchError, setFetchError] = useState<string | null>(null)

  // Derive parameters from session cache or externalResult or fallback to engine.ts INITIAL for editing
  const [parameters, setParameters] = useState<LedgerParameter[]>(() => {
    if (sessionExpertParameters && sessionExpertParameters.length > 0) {
      return sessionExpertParameters
    }
    if (externalResult?.assumptions && externalResult.assumptions.length > 0) {
      return assumptionsToLedgerParameters(externalResult.assumptions)
    }
    return []
  })
  const [scenarios, setScenarios] = useState<SavedScenario[]>(() => {
    return sessionExpertScenarios || []
  })

  const result = externalResult || liveResult

  const performFetch = useCallback(async () => {
    setLoading(true)
    setFetchError(null)
    try {
      const response = await fetch(getApiUrl('/api/v1/recommend'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'expert',
          input: {
            commodity_id: 'food.snack.namkeen_bhujia',
            environment: {
              temperature_c: 30,
              relative_humidity_pct: 65,
            },
            pack_geometry: {
              product_mass_kg: 0.18,
              pack_area_m2: 0.055,
            },
            target_shelf_life_days: 180,
            destination_market: 'IN',
          },
          locale: 'en-IN',
        }),
      })
      if (!response.ok) {
        throw new Error(`Engine returned ${response.status}`)
      }
      const sealed: SealedResult = await response.json()
      sessionExpertResult = sealed
      setLiveResult(sealed)

      // Only populate parameters if user hasn't already modified them in this session
      if (!sessionExpertParameters || sessionExpertParameters.length === 0) {
        if (sealed.assumptions && sealed.assumptions.length > 0) {
          const parsed = assumptionsToLedgerParameters(sealed.assumptions)
          sessionExpertParameters = parsed
          setParameters(parsed)
        } else {
          sessionExpertParameters = INITIAL_LEDGER_PARAMETERS
          setParameters(INITIAL_LEDGER_PARAMETERS)
        }
      }
    } catch (err: any) {
      setFetchError(err.message || 'Failed to fetch recommendation')
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-fetch ONLY on initial page load if no result is available in memory or props.
  // Tab switching will NEVER re-fetch!
  useEffect(() => {
    if (externalResult) return

    // If we already have the result in memory, ensure state is synced and do NOT fetch!
    if (sessionExpertResult) {
      if (!liveResult) setLiveResult(sessionExpertResult)
      if (parameters.length === 0 && sessionExpertParameters && sessionExpertParameters.length > 0) {
        setParameters(sessionExpertParameters)
      }
      setLoading(false)
      return
    }

    // Only start fetch once per page load
    if (sessionHasStartedFetch) return
    sessionHasStartedFetch = true
    performFetch()
  }, [externalResult, liveResult, parameters.length, performFetch])

  // Populate parameters from result.assumptions when result arrives IF not already populated
  useEffect(() => {
    if (parameters.length > 0) return
    if (result?.assumptions && result.assumptions.length > 0) {
      const parsed = assumptionsToLedgerParameters(result.assumptions)
      sessionExpertParameters = parsed
      setParameters(parsed)
    } else if (parameters.length === 0 && !loading) {
      sessionExpertParameters = INITIAL_LEDGER_PARAMETERS
      setParameters(INITIAL_LEDGER_PARAMETERS)
    }
  }, [result, parameters.length, loading])

  const paretoCandidates = useMemo(() => generateParetoCandidates(), [])

  const handleUpdateParameter = (id: string, newValue: number) => {
    setParameters((prev) => {
      const updated = prev.map((p) =>
        p.id === id
          ? {
              ...p,
              currentValue: newValue,
              isOverridden: newValue !== p.defaultValue,
            }
          : p
      )
      sessionExpertParameters = updated
      return updated
    })
  }

  const handleResetParameter = (id: string) => {
    setParameters((prev) => {
      const updated = prev.map((p) =>
        p.id === id
          ? {
              ...p,
              currentValue: p.defaultValue,
              isOverridden: false,
            }
          : p
      )
      sessionExpertParameters = updated
      return updated
    })
  }

  const handleResetAll = () => {
    setParameters((prev) => {
      const updated = prev.map((p) => ({
        ...p,
        currentValue: p.defaultValue,
        isOverridden: false,
      }))
      sessionExpertParameters = updated
      return updated
    })
  }

  const handleSaveCurrentAsScenario = () => {
    if (scenarios.length >= 4) return
    const overrideCount = parameters.filter((p) => p.isOverridden).length
    const slotLetter = String.fromCharCode(65 + scenarios.length)
    const topCandidate = result?.candidates?.[0]
    const newScen: SavedScenario = {
      id: `scen_${Date.now()}`,
      label: `Scenario ${slotLetter}: ${overrideCount > 0 ? `${overrideCount} Overrides` : 'Baseline'}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      structureName: topCandidate?.name || 'N/A',
      layerStack: topCandidate?.layer_stack?.join(' / ') || 'N/A',
      costPerPackInr: topCandidate?.cost_per_pack || 0,
      shelfLifeP10: result?.shelf_life?.days_p10 || 0,
      shelfLifeP50: result?.shelf_life?.days_p50 || 0,
      shelfLifeP90: result?.shelf_life?.days_p90 || 0,
      annualEprLiabilityInr: 0,
      recyclabilityScorePct: (topCandidate?.recyclability_score || 0) * 100,
      limitingMechanism: result?.shelf_life?.limiting_mechanism || result?.shelf_life?.mechanism || 'N/A',
      overriddenParameterCount: overrideCount,
    }
    const updated = [...scenarios, newScen]
    sessionExpertScenarios = updated
    setScenarios(updated)
  }

  const handleRemoveScenario = (id: string) => {
    if (scenarios.length <= 1) return
    const updated = scenarios.filter((s) => s.id !== id)
    sessionExpertScenarios = updated
    setScenarios(updated)
  }

  const overrideCount = parameters.filter((p) => p.isOverridden).length

  // Freshness indicator data
  const formatComputedAt = (isoStr?: string | null) => {
    if (!isoStr) return null
    const normalized = isoStr.endsWith('Z') || isoStr.includes('+') ? isoStr : `${isoStr}Z`
    const d = new Date(normalized)
    return isNaN(d.getTime()) ? isoStr : d.toLocaleString()
  }
  const computedAt = formatComputedAt(result?.computed_at)
  const engineVersion = result?.engine_version || '—'
  const kbVersion = result?.kb_version || '—'
  const rulesetVersion = result?.ruleset_version || '—'

  // Build a SealedResult-shaped object for ExportAndShare / RawJsonViewer
  const sealedResultJson: SealedResult = result || {
    result_id: '',
    engine_version: '',
    kb_version: '',
    ruleset_version: '',
    verdict: '',
    computed_at: '',
    assumptions: [],
    candidates: [],
    shelf_life: { days_p10: 0, days_p50: 0, days_p90: 0, confidence: 0 },
    equations: [],
    sensitivity: [],
    compliance: { is_compliant: false, destination_market: 'IN', rules_evaluated: [] },
    citations: [],
  }

  return (
    <div className="w-full space-y-10" data-mode="expert">
      {/* Step 7: Data Freshness Indicator */}
      {result && (
        <section className="border-3 border-ink bg-lime/20 px-4 py-2.5 shadow-[4px_4px_0_var(--ink)] font-mono text-xs flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="font-bold uppercase text-ink">
            ✓ LIVE ENGINE DATA
          </span>
          {computedAt && (
            <span className="text-ink/80">
              Result computed <span className="font-bold">{computedAt}</span>
            </span>
          )}
          <span className="text-ink/70">
            Engine v<span className="font-bold">{engineVersion}</span>
          </span>
          <span className="text-ink/70">
            KB v<span className="font-bold">{kbVersion}</span>
          </span>
          <span className="text-ink/70">
            Rules v<span className="font-bold">{rulesetVersion}</span>
          </span>
        </section>
      )}

      {/* Loading / Error states: ONLY displayed if no data is present yet */}
      {loading && !result && (
        <section className="border-3 border-ink bg-violet/10 p-6 shadow-[6px_6px_0_var(--ink)] text-center">
          <div className="font-display text-lg uppercase text-ink animate-pulse">
            ⚡ Fetching Live Engine Recommendation…
          </div>
          <div className="font-mono text-xs text-ink/60 mt-2">
            POST /api/v1/recommend · food.snack.namkeen_bhujia · ambient
          </div>
          <div className="font-mono text-[10px] text-ink/60 mt-4 max-w-md mx-auto border-t border-ink/10 pt-3">
            Note: It may take up to 2 minutes to load live data. The backend is hosted on Render's free tier, which takes a minimum of 50 seconds to start when inactive.
          </div>
        </section>
      )}
      {fetchError && !result && (
        <section className="border-3 border-ink bg-coral/20 p-5 shadow-[6px_6px_0_var(--ink)] space-y-2">
          <div className="font-display text-sm uppercase text-ink font-bold">
            ⚠ Engine Fetch Failed
          </div>
          <div className="font-mono text-xs text-ink/80">{fetchError}</div>
          <button
            type="button"
            onClick={performFetch}
            className="font-display text-xs uppercase px-4 py-2 bg-yellow text-ink border-2 border-ink shadow-[2px_2px_0_var(--ink)] hover:bg-yellow/80 cursor-pointer"
          >
            RETRY
          </button>
        </section>
      )}

      {/* Expert Persona Mode Banner */}
      <section className="border-3 border-ink bg-paper p-5 sm:p-6 shadow-[6px_6px_0_var(--ink)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="bg-violet text-ink border-2 border-ink px-2 py-0.5 font-display text-xs font-bold uppercase">
              🔬 EXPERT PERSONA MODE
            </span>
            <span className="font-mono text-xs font-bold text-ink/70">
              FIRST-PRINCIPLES FOOD PHYSICS & TRANSPARENT DUMP
            </span>
          </div>
          <h2 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            Biochemical & Engineering Workbench
          </h2>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            GAB isotherms, Fickian moisture diffusion integrals, Arrhenius reaction scaling, Monte Carlo distributions, sensitivity tornado ranking, and multi-scenario diffing.
          </p>
        </div>

        <div className="flex items-center">
          <div className="p-2 border-2 border-ink bg-paper text-center font-mono text-xs">
            <span className="block text-[10px] text-ink/70 uppercase">OVERRIDES</span>
            <span className="font-bold text-violet">{overrideCount} ACTIVE</span>
          </div>
        </div>
      </section>

      {/* 1. Full Parameter Editor & Ledger */}
      <section>
        <ParameterEditor
          parameters={parameters}
          onUpdateParameter={handleUpdateParameter}
          onResetParameter={handleResetParameter}
          onResetAll={handleResetAll}
        />
      </section>

      {/* 2. Model Inspector — real equations from result */}
      <section>
        <ModelInspector equations={result?.equations} />
      </section>

      {/* 3. Sensitivity Tornado Chart — real sensitivity from result */}
      <section>
        <SensitivityTornadoChart items={result?.sensitivity} />
      </section>

      {/* 4. Monte Carlo — real shelf_life from result */}
      <section>
        <MonteCarloDistribution shelfLife={result?.shelf_life} />
      </section>

      {/* 5. Pareto Frontier Plot */}
      <section>
        <ParetoFrontierPlot candidates={paretoCandidates} />
      </section>

      {/* 6. Scenario Comparison Matrix */}
      <section>
        <ScenarioComparison
          scenarios={scenarios}
          onSaveCurrentAsScenario={handleSaveCurrentAsScenario}
          onRemoveScenario={handleRemoveScenario}
        />
      </section>

      {/* 7. Full Compliance Rule Trace — real compliance from result */}
      <section>
        <ComplianceRuleTrace compliance={result?.compliance} />
      </section>

      {/* 8. Export to CSV, JSON, PDF & Permanent Replay Link */}
      <section>
        <ExportAndShare parameters={parameters} sealedResult={sealedResultJson} />
      </section>

      {/* 9. Raw SealedResult JSON View */}
      <section>
        <RawJsonViewer sealedResult={sealedResultJson} />
      </section>
    </div>
  )
}
