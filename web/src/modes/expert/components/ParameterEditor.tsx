import React, { useState } from 'react'
import type { LedgerParameter } from '../types'

interface ParameterEditorProps {
  parameters: LedgerParameter[]
  onUpdateParameter: (id: string, newValue: number) => void
  onResetParameter: (id: string) => void
  onResetAll: () => void
}

export const ParameterEditor: React.FC<ParameterEditorProps> = ({
  parameters,
  onUpdateParameter,
  onResetParameter,
  onResetAll,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<
    'all' | 'commodity' | 'environment' | 'geometry' | 'microbial'
  >('all')
  const [editingParamId, setEditingParamId] = useState<string | null>(null)
  const [tempEditValue, setTempEditValue] = useState<string>('')

  const overrideCount = parameters.filter((p) => p.isOverridden).length

  const filteredParameters = parameters.filter((p) =>
    selectedCategory === 'all' ? true : p.category === selectedCategory
  )

  const handleStartEdit = (param: LedgerParameter) => {
    setEditingParamId(param.id)
    setTempEditValue(param.currentValue.toString())
  }

  const handleSaveEdit = (param: LedgerParameter) => {
    const val = parseFloat(tempEditValue)
    if (!isNaN(val)) {
      const clamped = Math.max(param.minAllowed, Math.min(param.maxAllowed, val))
      onUpdateParameter(param.id, clamped)
    }
    setEditingParamId(null)
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      {/* Header with violet accent */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              TRANSPARENT RECALCULATION LEDGER
            </span>
            {overrideCount > 0 && (
              <span className="font-mono text-xs font-bold bg-yellow px-2 py-0.5 border border-ink">
                ⚡ {overrideCount} ACTIVE OVERRIDES
              </span>
            )}
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            01 · Full Parameter Editor & Provenance Ledger
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Every thermodynamic, microbial, and geometric value resolved by the engine can be manually adjusted. Overrides are visibly logged in the audit ledger and trigger immediate model recalculation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {overrideCount > 0 && (
            <button
              type="button"
              onClick={onResetAll}
              className="font-display text-xs uppercase px-3.5 py-2 bg-coral text-ink border-2 border-ink shadow-[2px_2px_0_var(--ink)] hover:bg-coral/80 cursor-pointer"
            >
              RESET ALL OVERRIDES
            </button>
          )}
        </div>
      </div>

      {/* Category Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: 'all', label: 'ALL PARAMETERS' },
          { id: 'commodity', label: 'COMMODITY ISOTHERMS' },
          { id: 'environment', label: 'STORAGE & CLIMATE' },
          { id: 'geometry', label: 'PACKAGING & BARRIER' },
          { id: 'microbial', label: 'MICROBIAL KINETICS' },
        ].map((cat) => {
          const isSelected = selectedCategory === cat.id
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelectedCategory(cat.id as typeof selectedCategory)}
              className={`font-display text-xs uppercase px-3 py-1.5 border-2 border-ink transition-all cursor-pointer ${
                isSelected
                  ? 'bg-violet text-ink shadow-[2px_2px_0_var(--ink)] font-bold'
                  : 'bg-paper text-ink/75 hover:bg-grey/40'
              }`}
            >
              {cat.label}
            </button>
          )
        })}
      </div>

      {/* Parameter Table */}
      <div className="border-3 border-ink overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[760px]">
          <thead>
            <tr className="border-b-3 border-ink bg-grey/50 font-display text-xs uppercase text-ink">
              <th className="p-3 border-r-2 border-ink">PARAMETER & SYMBOL</th>
              <th className="p-3 border-r-2 border-ink text-right">RESOLVED DEFAULT</th>
              <th className="p-3 border-r-2 border-ink text-right">ACTIVE VALUE</th>
              <th className="p-3 border-r-2 border-ink">STATUS</th>
              <th className="p-3 border-r-2 border-ink">PROVENANCE & CITATION</th>
              <th className="p-3 text-right">ACTION</th>
            </tr>
          </thead>
          <tbody className="divide-y-2 divide-ink font-mono text-xs">
            {filteredParameters.map((param) => {
              const deltaPct =
                param.defaultValue !== 0
                  ? ((param.currentValue - param.defaultValue) / param.defaultValue) * 100
                  : 0
              const isEditing = editingParamId === param.id

              return (
                <tr
                  key={param.id}
                  className={`transition-colors ${
                    param.isOverridden
                      ? 'bg-violet/15 font-semibold'
                      : 'hover:bg-grey/20 bg-paper'
                  }`}
                >
                  {/* Name and Symbol */}
                  <td className="p-3 border-r-2 border-ink">
                    <div className="flex items-center gap-2">
                      <span className="font-display text-sm bg-ink text-paper px-1.5 py-0.2 shrink-0">
                        {param.symbol}
                      </span>
                      <div>
                        <div className="font-display text-xs text-ink uppercase">{param.name}</div>
                        <div className="font-body text-[10px] text-ink/70 leading-tight">
                          {param.description}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Resolved Default */}
                  <td className="p-3 border-r-2 border-ink text-right font-mono text-ink/70">
                    {param.defaultValue} <span className="text-[10px]">{param.unit}</span>
                  </td>

                  {/* Active Value (Editable) */}
                  <td className="p-3 border-r-2 border-ink text-right">
                    {isEditing ? (
                      <div className="flex items-center justify-end gap-1.5">
                        <input
                          type="number"
                          step={param.step}
                          min={param.minAllowed}
                          max={param.maxAllowed}
                          value={tempEditValue}
                          onChange={(e) => setTempEditValue(e.target.value)}
                          className="w-24 border-2 border-ink p-1 font-mono text-xs bg-paper text-ink"
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveEdit(param)}
                          className="px-2 py-1 bg-lime text-ink font-display text-[10px] border border-ink"
                        >
                          SAVE
                        </button>
                      </div>
                    ) : (
                      <div className="font-mono text-sm font-bold text-ink">
                        {param.currentValue} <span className="text-xs font-normal">{param.unit}</span>
                      </div>
                    )}
                  </td>

                  {/* Status Pill */}
                  <td className="p-3 border-r-2 border-ink">
                    {param.isOverridden ? (
                      <div className="space-y-0.5">
                        <span className="font-display text-[10px] uppercase bg-violet text-ink px-2 py-0.5 border border-ink inline-block">
                          OVERRIDDEN (USER)
                        </span>
                        <div className="text-[10px] font-mono text-ink/80">
                          Δ {deltaPct > 0 ? `+${deltaPct.toFixed(1)}%` : `${deltaPct.toFixed(1)}%`}
                        </div>
                      </div>
                    ) : (
                      <span className="font-display text-[10px] uppercase bg-grey text-ink/80 px-2 py-0.5 border border-ink/40 inline-block">
                        DEFAULT (CALCULATED)
                      </span>
                    )}
                  </td>

                  {/* Provenance & Citation */}
                  <td className="p-3 border-r-2 border-ink text-[11px]">
                    <div className="font-bold text-ink truncate max-w-[200px]">
                      {param.provenance}
                    </div>
                    <div className="font-body text-[10px] text-ink/70 truncate max-w-[220px]">
                      {param.citation.title} ({param.citation.source})
                    </div>
                  </td>

                  {/* Action */}
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {!isEditing && (
                        <button
                          type="button"
                          onClick={() => handleStartEdit(param)}
                          className="font-display text-[10px] uppercase px-2.5 py-1 bg-paper hover:bg-grey/40 border border-ink shadow-[1px_1px_0_var(--ink)] cursor-pointer"
                        >
                          EDIT
                        </button>
                      )}
                      {param.isOverridden && (
                        <button
                          type="button"
                          onClick={() => onResetParameter(param.id)}
                          className="font-mono text-[10px] uppercase text-coral font-bold hover:underline cursor-pointer"
                          title="Restore default"
                        >
                          RESET
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
