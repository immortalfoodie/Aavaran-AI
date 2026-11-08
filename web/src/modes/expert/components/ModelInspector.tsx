import React, { useState } from 'react'
import type { EquationItem } from '../types'

interface ModelInspectorProps {
  equations?: EquationItem[]
}

export function renderSubstitutedFormula(eq: EquationItem): string {
  let rendered = eq.formula_template || ''
  if (eq.inputs) {
    for (const [key, inp] of Object.entries(eq.inputs)) {
      const valStr = inp.unit ? `${inp.value} ${inp.unit}`.trim() : `${inp.value}`
      rendered = rendered.split(`{${key}}`).join(valStr)
    }
  }
  if (eq.output && eq.output.value !== undefined) {
    const outStr = eq.output.unit ? `${eq.output.value} ${eq.output.unit}`.trim() : `${eq.output.value}`
    rendered += ` = ${outStr}`
  }
  return rendered
}

export const ModelInspector: React.FC<ModelInspectorProps> = ({ equations = [] }) => {
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({
    'M-03': true,
    'MIC-01': true,
  })

  const toggleNode = (id: string) => {
    setExpandedNodes((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const expandAll = () => {
    const all: Record<string, boolean> = {}
    equations.forEach((node) => {
      all[node.equation_id] = true
    })
    setExpandedNodes(all)
  }

  const collapseAll = () => {
    setExpandedNodes({})
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              DETERMINISTIC PHYSICS AUDIT TRAIL
            </span>
            <span className="font-mono text-xs font-bold text-ink/70">
              {equations.length} DERIVED EQUATIONS WITH LIVE INPUTS
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            02 · Model Inspector (Real Inputs Substituted)
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Examine each governing physics equation with actual computed inputs substituted in, including source badges, provenance citations, and final verified outputs.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={expandAll}
            className="font-display text-[11px] uppercase px-3 py-1.5 bg-paper hover:bg-grey/40 border-2 border-ink shadow-[2px_2px_0_var(--ink)] cursor-pointer"
          >
            EXPAND ALL
          </button>
          <button
            type="button"
            onClick={collapseAll}
            className="font-display text-[11px] uppercase px-3 py-1.5 bg-paper hover:bg-grey/40 border-2 border-ink shadow-[2px_2px_0_var(--ink)] cursor-pointer"
          >
            COLLAPSE ALL
          </button>
        </div>
      </div>

      {equations.length === 0 ? (
        <div className="p-8 text-center border-2 border-ink bg-grey/10 font-mono text-sm">
          Run a recommendation to view evaluated physics equations.
        </div>
      ) : (
        /* Expandable Equation Cards */
        <div className="space-y-4">
          {equations.map((eq) => {
            const isExpanded = !!expandedNodes[eq.equation_id]
            const substitutedFormula = renderSubstitutedFormula(eq)

            return (
              <div
                key={eq.equation_id}
                className={`border-3 border-ink bg-paper transition-all ${
                  isExpanded ? 'shadow-[5px_5px_0_var(--ink)]' : 'shadow-[3px_3px_0_var(--ink)]'
                }`}
              >
                {/* Equation Header Accordion Trigger */}
                <button
                  type="button"
                  onClick={() => toggleNode(eq.equation_id)}
                  className="w-full text-left p-4 bg-paper hover:bg-violet/10 border-b-2 border-ink flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-bold bg-ink text-paper w-7 h-7 flex items-center justify-center shrink-0">
                      {isExpanded ? '−' : '+'}
                    </span>
                    <div>
                      <span className="font-mono text-[10px] font-bold uppercase text-ink/60 block">
                        {eq.equation_id}
                      </span>
                      <h4 className="font-display text-base uppercase text-ink m-0">
                        {eq.name}
                      </h4>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-auto">
                    <div className="text-right">
                      <span className="font-mono text-[10px] text-ink/70 block uppercase">OUTPUT:</span>
                      <span className="font-display text-sm text-ink font-bold">
                        {eq.output.value} {eq.output.unit}
                      </span>
                    </div>
                    <span className="font-mono text-xs text-ink/60">
                      {isExpanded ? '▲' : '▼'}
                    </span>
                  </div>
                </button>

                {/* Equation Body */}
                {isExpanded && (
                  <div className="p-4 sm:p-5 space-y-4 bg-paper">
                    {/* Substituted Formula Box */}
                    <div className="p-3 border-2 border-ink bg-grey/30 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] font-bold uppercase text-ink/70 block">
                          ACTUAL COMPUTED SUBSTITUTION
                        </span>
                        <span className="font-mono text-[10px] font-bold bg-lime text-ink px-1.5 py-0.5 border border-ink">
                          REAL NUMBERS
                        </span>
                      </div>
                      <div className="font-mono text-sm sm:text-base font-bold text-ink overflow-x-auto py-1">
                        {substitutedFormula}
                      </div>
                    </div>

                    {/* Input Parameter Table with Source Badges */}
                    <div>
                      <span className="font-display text-xs uppercase text-ink block mb-2">
                        Fed Input Variables & Source Provenance:
                      </span>
                      <div className="border-2 border-ink overflow-x-auto">
                        <table className="w-full text-left text-xs font-mono">
                          <thead className="bg-grey/50 border-b border-ink font-bold">
                            <tr>
                              <th className="p-2 border-r border-ink">VARIABLE KEY</th>
                              <th className="p-2 border-r border-ink text-right">SUBSTITUTED VALUE</th>
                              <th className="p-2">SOURCE BADGE / PROVENANCE</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-ink">
                            {Object.entries(eq.inputs || {}).map(([key, inp]) => (
                              <tr key={key} className="bg-paper hover:bg-grey/20">
                                <td className="p-2 border-r border-ink font-bold text-ink">
                                  {key}
                                </td>
                                <td className="p-2 border-r border-ink text-right font-bold text-ink">
                                  {inp.value} <span className="text-[10px] font-normal">{inp.unit}</span>
                                </td>
                                <td className="p-2">
                                  <span className="inline-block px-2 py-0.5 text-[11px] font-bold bg-violet/20 text-ink border border-ink">
                                    {inp.source}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Citation Box */}
                    {eq.citation && (
                      <div className="p-3 border-2 border-ink bg-violet/15 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-display text-[10px] uppercase bg-ink text-paper px-1.5 py-0.2">
                              ACADEMIC CITATION
                            </span>
                          </div>
                          <div className="font-body text-xs font-semibold text-ink">
                            {eq.citation}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
