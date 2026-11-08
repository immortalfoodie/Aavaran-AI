import type React from 'react'
import { ConfidenceMeter } from './ConfidenceMeter'
import { SourceBadge, type CitationInfo } from './SourceBadge'

export interface AssumptionRowProps {
  fieldName: string
  value: string | number
  unit?: string
  source: string
  citation?: CitationInfo
  confidence: number
  confidenceLabel?: string
  isExplicit?: boolean
  onEdit?: () => void
  onOpenCitation?: (citation: CitationInfo) => void
  className?: string
}

export const AssumptionRow: React.FC<AssumptionRowProps> = ({
  fieldName,
  value,
  unit,
  source,
  citation,
  confidence,
  confidenceLabel,
  isExplicit = false,
  onEdit,
  onOpenCitation,
  className = '',
}) => {
  return (
    <div
      tabIndex={0}
      role="region"
      aria-label={`Assumption for ${fieldName}: ${value} ${unit || ''}`}
      className={`
        border-3 border-ink bg-paper p-4 sm:p-5
        shadow-[6px_6px_0_var(--ink)]
        transition-[transform,box-shadow,background-color] duration-[80ms] ease-linear
        hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-[8px_8px_0_var(--ink)]
        focus:outline-none focus:ring-4 focus:ring-yellow
        flex flex-col lg:flex-row lg:items-center justify-between gap-4 select-none
        ${className}
      `.trim()}
    >
      {/* Left side: Field label, Value, and Source */}
      <div className="flex flex-col sm:flex-row sm:items-baseline gap-2 sm:gap-4 flex-wrap">
        <span className="font-display uppercase text-sm sm:text-base text-ink tracking-wide">
          {fieldName}
        </span>
        <div className="flex items-baseline gap-1 bg-grey/30 border-2 border-ink px-2.5 py-0.5">
          <span className="font-mono font-bold text-base sm:text-lg text-ink">
            {value}
          </span>
          {unit && (
            <span className="font-mono text-xs font-semibold text-ink/75">
              {unit}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <SourceBadge
            source={source}
            citation={citation}
            onOpenCitation={onOpenCitation}
          />
          {isExplicit && (
            <span className="font-mono text-[10px] bg-lime border border-ink text-ink font-bold px-1.5 py-0.5 uppercase">
              USER VERIFIED
            </span>
          )}
        </div>
      </div>

      {/* Right side: Confidence meter and Edit affordance */}
      <div className="flex items-center justify-between lg:justify-end gap-3 sm:gap-5 pt-2 sm:pt-0 border-t-2 border-ink/20 lg:border-t-0">
        <ConfidenceMeter
          score={confidence}
          label={confidenceLabel}
          showNumeric={false}
        />
        <button
          type="button"
          onClick={onEdit}
          aria-label={`Edit ${fieldName} parameter`}
          className="
            inline-flex items-center gap-1.5
            border-2 border-ink bg-yellow hover:bg-yellow text-ink
            font-display uppercase text-xs sm:text-sm px-3 py-1.5
            shadow-[2px_2px_0_var(--ink)]
            hover:-translate-x-[1px] hover:-translate-y-[1px] hover:shadow-[4px_4px_0_var(--ink)]
            active:translate-x-[2px] active:translate-y-[2px] active:shadow-none
            transition-[transform,box-shadow] duration-[80ms] ease-linear cursor-pointer
          "
        >
          <span aria-hidden="true">✎</span>
          <span>EDIT</span>
        </button>
      </div>
    </div>
  )
}

export default AssumptionRow
