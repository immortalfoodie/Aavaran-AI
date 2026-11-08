import React from 'react'
import type { SavedScenario } from '../types'

interface ScenarioComparisonProps {
  scenarios: SavedScenario[]
  onSaveCurrentAsScenario: () => void
  onRemoveScenario: (id: string) => void
}

export const ScenarioComparison: React.FC<ScenarioComparisonProps> = ({
  scenarios,
  onSaveCurrentAsScenario,
  onRemoveScenario,
}) => {
  // Find extrema for diff color coding
  const minCost = Math.min(...scenarios.map((s) => s.costPerPackInr))
  const maxShelfLife = Math.max(...scenarios.map((s) => s.shelfLifeP50))
  const minEpr = Math.min(...scenarios.map((s) => s.annualEprLiabilityInr))
  const maxRecyclability = Math.max(...scenarios.map((s) => s.recyclabilityScorePct))

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              DECISION VARIANT MANAGEMENT
            </span>
            <span className="font-mono text-xs font-bold text-ink/70">
              {scenarios.length}/4 SAVED SCENARIOS
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            06 · Multi-Scenario Diffing Matrix
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Save up to four engineering configurations to benchmark barrier metallurgy, mono-material polymers, and cold-chain assumptions side-by-side.
          </p>
        </div>

        <div>
          {scenarios.length < 4 ? (
            <button
              type="button"
              onClick={onSaveCurrentAsScenario}
              className="font-display text-xs uppercase px-4 py-2.5 bg-violet text-ink border-2 border-ink shadow-[3px_3px_0_var(--ink)] hover:bg-violet/80 cursor-pointer flex items-center gap-1.5"
            >
              <span>💾</span>
              <span>SAVE CURRENT CONFIG</span>
            </button>
          ) : (
            <span className="font-mono text-xs text-ink/60 font-bold">
              MAXIMUM 4 SCENARIOS SAVED
            </span>
          )}
        </div>
      </div>

      {/* Comparison Diff Table */}
      <div className="border-3 border-ink overflow-x-auto bg-paper">
        <table className="w-full text-left border-collapse min-w-[700px]">
          <thead>
            <tr className="border-b-3 border-ink bg-grey/50 font-display text-xs uppercase text-ink">
              <th className="p-3 border-r-2 border-ink w-48">METRIC / SPECIFICATION</th>
              {scenarios.map((s) => (
                <th key={s.id} className="p-3 border-r-2 border-ink last:border-r-0">
                  <div className="flex items-start justify-between gap-1">
                    <div>
                      <div className="font-display text-xs text-ink uppercase leading-snug">
                        {s.label}
                      </div>
                      <div className="font-mono text-[10px] text-ink/60 font-normal">
                        {s.timestamp}
                      </div>
                    </div>
                    {scenarios.length > 1 && (
                      <button
                        type="button"
                        onClick={() => onRemoveScenario(s.id)}
                        className="text-coral hover:underline font-mono text-[10px] font-bold"
                        title="Delete scenario"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y-2 divide-ink font-mono text-xs">
            {/* Structure Name */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">Structure Name</td>
              {scenarios.map((s) => (
                <td key={s.id} className="p-3 border-r-2 border-ink last:border-r-0 font-bold text-ink">
                  {s.structureName}
                </td>
              ))}
            </tr>

            {/* Layer Stack */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">Layer Sequence</td>
              {scenarios.map((s) => (
                <td key={s.id} className="p-3 border-r-2 border-ink last:border-r-0 text-ink/80 text-[11px]">
                  {s.layerStack}
                </td>
              ))}
            </tr>

            {/* Shelf Life P50 */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">
                P50 Shelf Life (Days)
              </td>
              {scenarios.map((s) => {
                const isBest = s.shelfLifeP50 === maxShelfLife
                return (
                  <td
                    key={s.id}
                    className={`p-3 border-r-2 border-ink last:border-r-0 font-display text-sm ${
                      isBest ? 'bg-lime/30 text-ink font-bold' : ''
                    }`}
                  >
                    {s.shelfLifeP50} Days
                    {isBest && (
                      <span className="ml-1 text-[10px] font-mono bg-ink text-paper px-1">
                        MAX
                      </span>
                    )}
                  </td>
                )
              })}
            </tr>

            {/* P10 & P90 Range */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">
                Confidence Band [P10–P90]
              </td>
              {scenarios.map((s) => (
                <td key={s.id} className="p-3 border-r-2 border-ink last:border-r-0 text-[11px]">
                  [{s.shelfLifeP10}d — {s.shelfLifeP90}d]
                </td>
              ))}
            </tr>

            {/* Cost Per Pack */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">Cost per Pack (₹)</td>
              {scenarios.map((s) => {
                const isLowest = s.costPerPackInr === minCost
                return (
                  <td
                    key={s.id}
                    className={`p-3 border-r-2 border-ink last:border-r-0 font-display text-sm ${
                      isLowest ? 'bg-lime/30 text-ink font-bold' : ''
                    }`}
                  >
                    ₹{s.costPerPackInr.toFixed(2)}
                    {isLowest && (
                      <span className="ml-1 text-[10px] font-mono bg-ink text-paper px-1">
                        LOWEST
                      </span>
                    )}
                  </td>
                )
              })}
            </tr>

            {/* EPR Liability */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">
                Annual EPR Liability (₹)
              </td>
              {scenarios.map((s) => {
                const isLowest = s.annualEprLiabilityInr === minEpr
                return (
                  <td
                    key={s.id}
                    className={`p-3 border-r-2 border-ink last:border-r-0 ${
                      isLowest ? 'bg-lime/30 font-bold' : ''
                    }`}
                  >
                    ₹{s.annualEprLiabilityInr.toLocaleString()}
                  </td>
                )
              })}
            </tr>

            {/* Recyclability */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">
                Recyclability Index
              </td>
              {scenarios.map((s) => {
                const isBest = s.recyclabilityScorePct === maxRecyclability
                return (
                  <td
                    key={s.id}
                    className={`p-3 border-r-2 border-ink last:border-r-0 ${
                      isBest ? 'bg-lime/30 font-bold text-lime-900' : ''
                    }`}
                  >
                    {s.recyclabilityScorePct}% Score
                  </td>
                )
              })}
            </tr>

            {/* Limiting Mechanism */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">
                Limiting Mechanism
              </td>
              {scenarios.map((s) => (
                <td key={s.id} className="p-3 border-r-2 border-ink last:border-r-0 text-[11px] text-ink/80">
                  {s.limitingMechanism}
                </td>
              ))}
            </tr>

            {/* Overridden Parameter Count */}
            <tr className="hover:bg-grey/20">
              <td className="p-3 border-r-2 border-ink font-bold bg-grey/20">
                Active Ledgers Overridden
              </td>
              {scenarios.map((s) => (
                <td key={s.id} className="p-3 border-r-2 border-ink last:border-r-0">
                  {s.overriddenParameterCount > 0 ? (
                    <span className="font-bold text-violet">
                      {s.overriddenParameterCount} params edited
                    </span>
                  ) : (
                    <span className="text-ink/60">0 (Engine defaults)</span>
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
