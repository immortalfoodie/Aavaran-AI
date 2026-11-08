import React, { useState } from 'react'
import type { PackagingSpecSheet } from '../types'

interface StructureCardsProps {
  structures: PackagingSpecSheet[]
  selectedStructureId: string
  onSelectStructure: (structure: PackagingSpecSheet) => void
  onOpenRfq: (structure: PackagingSpecSheet) => void
  rfqLoading?: boolean
  loadingStructureId?: string | null
}

export const StructureCards: React.FC<StructureCardsProps> = ({
  structures,
  selectedStructureId,
  onSelectStructure,
  onOpenRfq,
  rfqLoading = false,
  loadingStructureId = null,
}) => {
  const [expandedSpecId, setExpandedSpecId] = useState<string | null>(structures[0]?.structureId || null)

  const toggleExpand = (id: string) => {
    setExpandedSpecId((prev) => (prev === id ? null : id))
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <span className="font-mono text-xs font-bold uppercase tracking-wider bg-cyan text-ink px-2 py-0.5 inline-block mb-1 border border-ink">
            SOLVER RECOMMENDATION ENGINE · THREE RANKED CANDIDATES
          </span>
          <h2 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            01 · Ranked Structure Specifications
          </h2>
        </div>
        <p className="font-body text-xs sm:text-sm text-ink/80 max-w-md">
          Each card details full ASTM laboratory verification methods, machine runnability friction, and compliance tags.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {structures.map((s) => {
          const isSelected = selectedStructureId === s.structureId
          const isExpanded = expandedSpecId === s.structureId

          const rankBadgeColor =
            s.rank === 1 ? 'bg-cyan text-ink' : s.rank === 2 ? 'bg-yellow text-ink' : 'bg-lime text-ink'

          return (
            <div
              key={s.structureId}
              className={`border-3 border-ink bg-paper transition-all relative ${
                isSelected
                  ? 'shadow-[8px_8px_0_var(--ink)] ring-2 ring-ink'
                  : 'shadow-[5px_5px_0_var(--ink)] hover:translate-y-[-2px]'
              }`}
            >
              {/* Card Top Banner */}
              <div
                className={`p-3.5 border-b-3 border-ink flex items-center justify-between gap-2 ${rankBadgeColor}`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-display text-base uppercase bg-ink text-paper px-2 py-0.5">
                    RANK #{s.rank}
                  </span>
                  <span className="font-display text-xs tracking-wider uppercase font-bold">
                    {s.rankLabel}
                  </span>
                </div>
                <span className="font-mono text-xs font-bold uppercase bg-paper text-ink px-1.5 py-0.5 border border-ink">
                  {s.eprCategory}
                </span>
              </div>

              {/* Main Card Summary */}
              <div className="p-4 sm:p-5 space-y-4">
                <div>
                  <h3 className="font-display text-lg uppercase leading-snug text-ink m-0">
                    {s.name}
                  </h3>
                  <p className="font-mono text-xs text-ink/80 mt-1 font-semibold">
                    {s.layerStackDisplay}
                  </p>
                </div>

                {/* Layer Swatch Stack */}
                <div className="border-2 border-ink p-2 bg-grey/20 space-y-1">
                  <span className="font-mono text-[10px] uppercase font-bold text-ink/70 block mb-1">
                    LAYER STACK & THICKNESS ({s.compositeThicknessUm} µm TOTAL)
                  </span>
                  {s.layers.map((layer, idx) => (
                    <div
                      key={idx}
                      className={`flex items-center justify-between p-1.5 border border-ink text-xs font-mono font-bold ${layer.colorClass}`}
                    >
                      <span className="truncate">{layer.material}</span>
                      <span className="bg-ink text-paper px-1 py-0.2 text-[11px] shrink-0">
                        {layer.gaugeUm} µm
                      </span>
                    </div>
                  ))}
                </div>

                {/* Key Metrics Grid */}
                <div className="grid grid-cols-2 gap-2 text-center">
                  <div className="p-2 border-2 border-ink bg-paper">
                    <span className="block font-mono text-[10px] text-ink/70 uppercase">
                      INDICATIVE PACK COST
                    </span>
                    <span className="font-display text-lg text-ink">₹{s.costPerPackInr.toFixed(2)}</span>
                  </div>
                  <div className="p-2 border-2 border-ink bg-paper">
                    <span className="block font-mono text-[10px] text-ink/70 uppercase">
                      PREDICTED SHELF LIFE (P50)
                    </span>
                    <span className="font-display text-lg text-ink">
                      {s.predictedShelfLifeDaysP50} DAYS
                    </span>
                  </div>
                </div>

                {/* Machine Runnability & COF */}
                <div className="p-2.5 border-2 border-ink bg-grey/30 text-xs font-mono space-y-1">
                  <div className="flex justify-between">
                    <span className="text-ink/80">RUNNABILITY RATING:</span>
                    <span className="font-bold">{s.machineRunnabilityScore}/10</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ink/80">COF (STATIC / DYNAMIC):</span>
                    <span className="font-bold">
                      {s.cofStatic.toFixed(2)} / {s.cofDynamic.toFixed(2)}
                    </span>
                  </div>
                  <div className="text-[10px] text-ink/70 pt-0.5 truncate">
                    LIMITING: {s.limitingMechanism}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="space-y-2 pt-1">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => onSelectStructure(s)}
                      className={`flex-1 font-display text-xs uppercase py-2.5 px-3 border-2 border-ink cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-ink text-paper shadow-[2px_2px_0_var(--ink)]'
                          : 'bg-yellow text-ink shadow-[3px_3px_0_var(--ink)] hover:bg-yellow/80'
                      }`}
                    >
                      {isSelected ? '✓ ACTIVE SELECTION' : 'SELECT THIS SPEC'}
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleExpand(s.structureId)}
                      className="font-display text-xs uppercase px-3 py-2.5 border-2 border-ink bg-paper hover:bg-grey/40 shadow-[3px_3px_0_var(--ink)] cursor-pointer"
                      title="View ASTM test methods"
                    >
                      {isExpanded ? '▲ HIDE SPEC' : '▼ FULL SPEC'}
                    </button>
                  </div>

                  {(() => {
                    const isThisLoading = Boolean(rfqLoading && loadingStructureId === s.structureId)
                    return (
                      <button
                        type="button"
                        disabled={rfqLoading}
                        onClick={() => {
                          onSelectStructure(s)
                          onOpenRfq(s)
                        }}
                        style={
                          isThisLoading
                            ? {
                                animation: 'rfq-pulse 1s infinite ease-in-out',
                                pointerEvents: 'none',
                              }
                            : undefined
                        }
                        className={`w-full font-display text-xs uppercase py-2 px-3 border-2 border-ink flex items-center justify-center gap-1.5 transition-all ${
                          isThisLoading
                            ? 'bg-grey text-ink cursor-not-allowed shadow-none'
                            : 'bg-cyan text-ink hover:bg-cyan/80 shadow-[3px_3px_0_var(--ink)] cursor-pointer'
                        }`}
                      >
                        {isThisLoading ? (
                          <span>⚡ GENERATING RFQ…</span>
                        ) : (
                          <>
                            <span>📄</span>
                            <span>GENERATE CONVERTER RFQ SPEC</span>
                          </>
                        )}
                      </button>
                    )
                  })()}
                </div>

                {/* Expanded Full Spec Sheet with ASTM Test Methods */}
                {isExpanded && (
                  <div className="pt-3 border-t-2 border-ink space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-display text-xs uppercase text-ink">
                        LABORATORY SPECIFICATION SHEET
                      </span>
                      <span className="font-mono text-[10px] bg-paper px-1 border border-ink">
                        NABL CONFORMITY
                      </span>
                    </div>

                    <div className="space-y-2">
                      {s.properties.map((prop, pIdx) => {
                        const isGelbo = prop.testMethod.includes('ASTM F392')
                        return (
                          <div
                            key={pIdx}
                            className={`p-2 border border-ink text-xs ${
                              isGelbo && s.isMetallisedOrFoil
                                ? 'bg-yellow/30 border-ink font-semibold'
                                : 'bg-paper'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1 mb-0.5">
                              <span className="font-display text-[11px] uppercase">
                                {prop.propertyName}
                              </span>
                              <span className="font-mono text-[10px] font-bold bg-ink text-paper px-1">
                                {prop.testMethod}
                              </span>
                            </div>
                            <div className="font-mono text-sm font-bold text-ink">
                              {prop.value} <span className="text-xs font-normal">{prop.unit}</span>
                            </div>
                            <p className="font-body text-[10px] text-ink/80 mt-1 leading-tight">
                              {prop.specificationNote}
                            </p>
                          </div>
                        )
                      })}
                    </div>

                    <div className="p-2 border border-ink bg-grey/20 text-[10px] font-body text-ink/80">
                      <strong>Circularity:</strong> {s.recyclabilityStatus}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
