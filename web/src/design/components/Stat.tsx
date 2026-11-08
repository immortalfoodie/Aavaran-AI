import type React from 'react'

export interface StatProps extends React.HTMLAttributes<HTMLDivElement> {
  /** The prominent numeric or quantitative value */
  value: string | number
  /** Unit indicator beside or inside the value (e.g., '%', 'DAYS', '₹/kg') */
  unit?: string
  /** Required uppercase descriptive label underneath */
  label: string
  /** Optional secondary subtitle or context text */
  helper?: string
}

export const Stat: React.FC<StatProps> = ({
  value,
  unit,
  label,
  helper,
  className = '',
  ...props
}) => {
  return (
    <div
      className={`inline-flex flex-col border-3 border-ink bg-paper p-4 sm:p-5 shadow-[6px_6px_0_var(--ink)] ${className}`.trim()}
      {...props}
    >
      <div className="flex items-baseline gap-1.5 font-display text-3xl sm:text-4xl lg:text-5xl text-ink tracking-tight">
        <span>{value}</span>
        {unit && (
          <span className="font-mono text-sm sm:text-base font-semibold tracking-normal text-ink">
            {unit}
          </span>
        )}
      </div>
      <div className="mt-2 text-xs sm:text-sm font-display uppercase tracking-wider text-ink border-t-2 border-ink pt-1.5">
        {label}
      </div>
      {helper && (
        <div className="mt-1 font-body text-xs text-ink/80">
          {helper}
        </div>
      )}
    </div>
  )
}

export default Stat
