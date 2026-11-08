import type React from 'react'

export type AppMode = 'kisan' | 'business' | 'expert'

export interface ModeSwitchProps {
  activeMode: AppMode
  onChange: (mode: AppMode) => void
  className?: string
}

interface ModeTabConfig {
  id: AppMode
  label: string
  icon: string
  colorClass: string
  ariaLabel: string
}

const MODES: ModeTabConfig[] = [
  {
    id: 'kisan',
    label: 'KISAN',
    icon: '🌱',
    colorClass: 'bg-yellow text-ink',
    ariaLabel: 'Kisan mode: Simple, visual, vernacular food packaging advice',
  },
  {
    id: 'business',
    label: 'BUSINESS',
    icon: '💼',
    colorClass: 'bg-cyan text-ink',
    ariaLabel: 'Business mode: Specs, RFQ generator, cost & EPR compliance',
  },
  {
    id: 'expert',
    label: 'EXPERT',
    icon: '🔬',
    colorClass: 'bg-violet text-ink',
    ariaLabel: 'Expert mode: Full physics equations, isotherms, and model transparent dump',
  },
]

export const ModeSwitch: React.FC<ModeSwitchProps> = ({
  activeMode,
  onChange,
  className = '',
}) => {
  return (
    <div
      role="tablist"
      aria-label="Aavaran Persona Mode Switcher"
      className={`inline-flex items-end gap-2 sm:gap-3 p-1.5 select-none ${className}`.trim()}
    >
      {MODES.map((mode) => {
        const isActive = activeMode === mode.id

        return (
          <button
            key={mode.id}
            role="tab"
            type="button"
            aria-selected={isActive}
            aria-label={mode.ariaLabel}
            onClick={() => onChange(mode.id)}
            className={`
              inline-flex items-center gap-2
              font-display uppercase text-xs sm:text-sm lg:text-base
              px-3.5 sm:px-5 py-2 sm:py-2.5
              border-3 border-ink cursor-pointer
              transition-[transform,box-shadow,background-color] duration-[80ms] ease-linear
              ${
                isActive
                  ? `${mode.colorClass} translate-y-[3px] shadow-[3px_3px_0_var(--ink)] z-10`
                  : 'bg-paper text-ink shadow-[6px_6px_0_var(--ink)] hover:bg-grey/40 hover:-translate-y-[1px]'
              }
            `}
          >
            <span aria-hidden="true" className="text-sm sm:text-base">
              {mode.icon}
            </span>
            <span className="tracking-wider">{mode.label}</span>
          </button>
        )
      })}
    </div>
  )
}

export default ModeSwitch
