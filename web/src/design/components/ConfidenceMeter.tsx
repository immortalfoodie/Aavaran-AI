import type React from 'react'

export type ConfidenceTier = 'LOW' | 'FAIR' | 'GOOD' | 'HIGH'

export interface ConfidenceMeterProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Score from 0 to 10 (or 0.0 to 1.0) */
  score: number
  /** Optional custom word label override. Defaults to auto-derived LOW/FAIR/GOOD/HIGH */
  label?: string
  /** Whether to show numeric score alongside tier label */
  showNumeric?: boolean
}

function getConfidenceTier(score: number): ConfidenceTier {
  // Normalize 0.0 - 1.0 scale to 0 - 10 if necessary
  const normalized = score <= 1.0 && score > 0 ? Math.round(score * 10) : Math.round(score)
  if (normalized <= 3) return 'LOW'
  if (normalized <= 6) return 'FAIR'
  if (normalized <= 8) return 'GOOD'
  return 'HIGH'
}

export const ConfidenceMeter: React.FC<ConfidenceMeterProps> = ({
  score,
  label,
  showNumeric = false,
  className = '',
  ...props
}) => {
  // Clamp between 0 and 10
  const normalizedScore = score <= 1.0 && score > 0 ? Math.round(score * 10) : Math.min(10, Math.max(0, Math.round(score)))
  const tier = getConfidenceTier(normalizedScore)
  const displayLabel = label || tier

  const tierColors: Record<ConfidenceTier, string> = {
    LOW: 'bg-coral text-ink',
    FAIR: 'bg-yellow text-ink',
    GOOD: 'bg-cyan text-ink',
    HIGH: 'bg-lime text-ink',
  }

  return (
    <div
      className={`inline-flex items-center gap-3 select-none ${className}`.trim()}
      role="meter"
      aria-valuenow={normalizedScore}
      aria-valuemin={0}
      aria-valuemax={10}
      aria-label={`Confidence: ${displayLabel}`}
      {...props}
    >
      {/* Discrete 10-block bar inside 3px border — never smooth */}
      <div className="flex border-3 border-ink bg-paper h-6 sm:h-7 p-0.5 gap-0.5">
        {Array.from({ length: 10 }).map((_, index) => {
          const isFilled = index < normalizedScore
          return (
            <div
              key={index}
              className={`
                w-2.5 sm:w-3.5 h-full transition-none
                ${isFilled ? 'bg-ink' : 'bg-grey/40'}
              `}
            />
          )
        })}
      </div>

      {/* Chunky word label */}
      <div className="flex items-center gap-1.5">
        <span
          className={`
            border-2 border-ink font-display uppercase text-xs px-2 py-0.5
            tracking-wider ${tierColors[tier]}
          `}
        >
          {displayLabel}
        </span>
        {showNumeric && (
          <span className="font-mono text-xs font-bold text-ink">
            ({normalizedScore}/10)
          </span>
        )}
      </div>
    </div>
  )
}

export default ConfidenceMeter
