import React from 'react'
import type { CostBenefitAnalysis } from '../types'

interface CostBenefitPanelProps {
  costBenefit: CostBenefitAnalysis
  commodityName: string
}

export const CostBenefitPanel: React.FC<CostBenefitPanelProps> = ({
  costBenefit,
  commodityName,
}) => {
  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="font-mono text-xs font-bold uppercase tracking-wider bg-yellow text-ink px-2 py-0.5 inline-block mb-1 border border-ink">
            ECONOMIC FEASIBILITY · BREAK-EVEN SPOILAGE THRESHOLD
          </span>
          <h3 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
            04 · Packaging Cost vs. Product Value Protected
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold bg-lime text-ink border-2 border-ink px-3 py-1">
            ROI FACTOR: {costBenefit.roiMultiple}x SAVINGS
          </span>
        </div>
      </div>

      <p className="font-body text-xs sm:text-sm text-ink/80">
        Comparing packaging investment against the retail value of the protected food commodity. The stated break-even loss rate specifies the exact threshold of spoilage prevention where the packaging becomes 100% cost-neutral.
      </p>

      {/* Hero Break-Even Callout Banner */}
      <div className="p-4 sm:p-5 border-3 border-ink bg-cyan/25 space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-display text-xs uppercase bg-ink text-cyan px-2 py-0.5 font-bold">
            KEY DECISION BENCHMARK
          </span>
          <span className="font-mono text-xs font-bold text-ink">
            BREAK-EVEN LOSS RATE
          </span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-baseline gap-2 sm:gap-4">
          <span className="font-display text-3xl sm:text-4xl text-ink">
            {costBenefit.breakEvenLossRatePct.toFixed(2)}%
          </span>
          <span className="font-body text-xs sm:text-sm text-ink/90 leading-tight">
            If this packaging prevents just{' '}
            <strong className="font-bold underline text-ink">
              {costBenefit.breakEvenLossRatePct.toFixed(2)}%
            </strong>{' '}
            of spoilage for {commodityName}, your entire packaging investment is{' '}
            <strong className="font-bold">100% cost-neutral</strong>.
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-3.5 border-2 border-ink bg-paper">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            PACKAGING COST
          </span>
          <span className="font-display text-xl sm:text-2xl text-ink block mt-1">
            ₹{costBenefit.costPerPackInr.toFixed(2)}
          </span>
          <span className="block font-mono text-[10px] text-ink/70">Per unit (film + EPR)</span>
        </div>

        <div className="p-3.5 border-2 border-ink bg-paper">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            PRODUCT VALUE PROTECTED
          </span>
          <span className="font-display text-xl sm:text-2xl text-ink block mt-1">
            ₹{costBenefit.productRetailValueInr.toFixed(2)}
          </span>
          <span className="block font-mono text-[10px] text-ink/70">Retail MRP per pack</span>
        </div>

        <div className="p-3.5 border-2 border-ink bg-paper">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            PACK-TO-PRODUCT RATIO
          </span>
          <span className="font-display text-xl sm:text-2xl text-ink block mt-1">
            {costBenefit.packagingCostRatioPct.toFixed(1)}%
          </span>
          <span className="block font-mono text-[10px] text-ink/70">Below 5% FMCG benchmark</span>
        </div>

        <div className="p-3.5 border-2 border-ink bg-lime/30 border-ink">
          <span className="block font-mono text-[10px] text-ink/70 uppercase font-bold">
            NET ANNUAL MARGIN PROTECTED
          </span>
          <span className="font-display text-xl sm:text-2xl text-ink block mt-1">
            ₹{costBenefit.netAnnualMarginProtectedInr.toLocaleString()}
          </span>
          <span className="block font-mono text-[10px] text-ink/70">Net profit saved / year</span>
        </div>
      </div>

      {/* Spoilage Loss Comparison Bar */}
      <div className="p-4 border-2 border-ink bg-paper space-y-3">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="font-bold text-ink">ANNUAL PRODUCT LOSS SIMULATION:</span>
          <span className="text-ink/80">Current Baseline vs Aavaran High-Barrier Spec</span>
        </div>

        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-[11px] font-mono mb-1">
              <span>Baseline Spoilage Loss (Current Packaging):</span>
              <span className="font-bold text-coral">
                ₹{costBenefit.currentAnnualLossInr.toLocaleString()}
              </span>
            </div>
            <div className="w-full bg-grey h-4 border-2 border-ink">
              <div className="bg-coral h-full w-[85%]" />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-[11px] font-mono mb-1">
              <span>Predicted Spoilage Loss (With Recommended Barrier):</span>
              <span className="font-bold text-lime-800">
                ₹{costBenefit.predictedAnnualLossInr.toLocaleString()}
              </span>
            </div>
            <div className="w-full bg-grey h-4 border-2 border-ink">
              <div className="bg-lime h-full w-[12%]" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
