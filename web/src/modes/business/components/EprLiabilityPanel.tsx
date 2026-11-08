import React from 'react'
import type { EprLiabilityComparison } from '../types'

interface EprLiabilityPanelProps {
  epr: EprLiabilityComparison
}

export const EprLiabilityPanel: React.FC<EprLiabilityPanelProps> = ({ epr }) => {
  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="font-mono text-xs font-bold uppercase tracking-wider bg-yellow text-ink px-2 py-0.5 inline-block mb-1 border border-ink">
            PLASTIC WASTE MANAGEMENT (PWM) RULES 2022 · EPR OBLIGATIONS
          </span>
          <h3 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
            03 · Extended Producer Responsibility (EPR) Liability
          </h3>
        </div>
        <span className="font-mono text-xs font-bold bg-cyan text-ink border-2 border-ink px-3 py-1">
          FINANCIAL YEAR 2025–26 TARGETS
        </span>
      </div>

      <p className="font-body text-xs sm:text-sm text-ink/80">
        CPCB statutory recycling obligations and indicative rupee credit offset fees calculated against annual production tonnage. Compare your baseline multi-layer structure against the recyclable mono-material alternative.
      </p>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-3 border-2 border-ink bg-paper">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            CPCB EPR CATEGORY
          </span>
          <span className="font-display text-sm sm:text-base text-ink block mt-1">
            {epr.category}
          </span>
        </div>

        <div className="p-3 border-2 border-ink bg-paper">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            STATUTORY RECYCLING TARGET
          </span>
          <span className="font-display text-xl sm:text-2xl text-ink">
            {epr.recyclingTargetPct}%
          </span>
          <span className="block font-mono text-[10px] text-ink/70">FY 2025-26 Mandate</span>
        </div>

        <div className="p-3 border-2 border-ink bg-paper">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            RECYCLED CONTENT (PCR) TARGET
          </span>
          <span className="font-display text-xl sm:text-2xl text-ink">
            {epr.recycledContentTargetPct}%
          </span>
          <span className="block font-mono text-[10px] text-ink/70">Mandatory virgin offset</span>
        </div>

        <div className="p-3 border-2 border-ink bg-yellow/30 border-ink">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            ANNUAL PLASTIC TONNAGE
          </span>
          <span className="font-display text-xl sm:text-2xl text-ink">
            {epr.totalPlasticTonnagePerYear} T
          </span>
          <span className="block font-mono text-[10px] text-ink/70">
            {epr.currentAnnualVolume.toLocaleString()} units @ {epr.packWeightGrams}g
          </span>
        </div>
      </div>

      {/* Side-by-side comparison against Mono-Material Alternative */}
      <div className="border-3 border-ink bg-grey/20 p-4 sm:p-5 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h4 className="font-display text-base sm:text-lg uppercase text-ink m-0">
            Side-By-Side Comparison: Multi-Layer (Cat III) vs Mono-Material (Cat II)
          </h4>
          <span className="font-mono text-xs font-bold bg-lime px-2 py-0.5 border border-ink">
            HIGH CIRCULARITY ALTERNATIVE
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Multi-Layer Box */}
          <div className="p-4 border-2 border-ink bg-paper space-y-3">
            <div className="flex items-center justify-between border-b-2 border-ink pb-2">
              <span className="font-display text-sm uppercase">CURRENT MULTI-LAYER (MLP)</span>
              <span className="font-mono text-xs font-bold bg-coral/30 px-2 py-0.5 border border-ink">
                CAT III
              </span>
            </div>

            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-ink/70">EPR Credit Cost:</span>
                <span className="font-bold">₹{epr.creditRateInrPerTonne.toLocaleString()} / tonne</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink/70">Indicative Cost / Pack:</span>
                <span className="font-bold text-coral">₹{epr.indicativeCostPerPackInr.toFixed(2)}</span>
              </div>
              <div className="flex justify-between border-t border-ink pt-2 text-sm">
                <span className="font-bold text-ink">Annual Rupee Liability:</span>
                <span className="font-display text-lg text-coral">
                  ₹{epr.indicativeAnnualLiabilityInr.toLocaleString()}
                </span>
              </div>
            </div>

            <p className="font-body text-[11px] text-ink/75 leading-tight">
              Difficult to mechanically recycle. Requires end-of-life co-processing in cement kilns or chemical pyrolysis.
            </p>
          </div>

          {/* Mono-Material Box */}
          <div className="p-4 border-2 border-ink bg-cyan/15 space-y-3">
            <div className="flex items-center justify-between border-b-2 border-ink pb-2">
              <span className="font-display text-sm uppercase">MONO-MATERIAL ALTERNATIVE</span>
              <span className="font-mono text-xs font-bold bg-lime px-2 py-0.5 border border-ink">
                CAT II (RECYCLABLE)
              </span>
            </div>

            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-ink/70">EPR Credit Cost:</span>
                <span className="font-bold">₹9,200 / tonne</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink/70">Indicative Cost / Pack:</span>
                <span className="font-bold text-lime-800">
                  ₹{epr.monoAlternative.indicativeCostPerPackInr.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between border-t border-ink pt-2 text-sm">
                <span className="font-bold text-ink">Annual Rupee Liability:</span>
                <span className="font-display text-lg text-ink">
                  ₹{epr.monoAlternative.indicativeAnnualLiabilityInr.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="p-2 border border-ink bg-lime text-ink font-display text-xs flex items-center justify-between">
              <span>ANNUAL EPR RUPEE SAVINGS:</span>
              <span className="text-sm">₹{epr.monoAlternative.annualRupeeSavings.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
