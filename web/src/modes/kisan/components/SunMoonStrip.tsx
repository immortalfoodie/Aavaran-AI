import React from 'react'
import { useTranslation } from 'react-i18next'
import type { TimeInterval } from '../types'

interface SunMoonStripProps {
  value: TimeInterval
  onChange: (val: TimeInterval) => void
}

interface OptionConfig {
  id: TimeInterval
  labelKey: string
  icons: string
  subTextKey: string
}

export const SunMoonStrip: React.FC<SunMoonStripProps> = ({ value, onChange }) => {
  const { t } = useTranslation()

  const options: OptionConfig[] = [
    {
      id: 'today',
      labelKey: 'time_strip.today',
      icons: '☀️',
      subTextKey: 'ताज़ा / Fresh',
    },
    {
      id: 'one_day',
      labelKey: 'time_strip.one_day',
      icons: '🌙',
      subTextKey: '१ दिवस / 1 Day',
    },
    {
      id: 'two_days',
      labelKey: 'time_strip.two_days',
      icons: '☀️ 🌙',
      subTextKey: '२ दिवस / 2 Days',
    },
    {
      id: 'three_days_plus',
      labelKey: 'time_strip.three_days_plus',
      icons: '☀️ 🌙 ☀️',
      subTextKey: '३+ दिवस / 3+ Days',
    },
  ]

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="font-display uppercase text-sm sm:text-base text-ink tracking-wide">
          {t('time_strip.title')}
        </label>
        <span className="font-mono text-xs font-bold bg-yellow border-2 border-ink px-2 py-0.5">
          ☀️ ☽ TIMELINE
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {options.map((opt) => {
          const isSelected = value === opt.id
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => onChange(opt.id)}
              className={`
                min-h-[72px] p-3 text-left border-3 border-ink select-none cursor-pointer
                transition-all duration-[80ms] flex flex-col justify-between
                ${
                  isSelected
                    ? 'bg-yellow shadow-[4px_4px_0_var(--ink)] translate-x-[2px] translate-y-[2px]'
                    : 'bg-paper hover:bg-grey/40 shadow-[6px_6px_0_var(--ink)] hover:-translate-x-[1px] hover:-translate-y-[1px]'
                }
              `.trim()}
            >
              <div className="text-2xl sm:text-3xl leading-none tracking-tight">
                {opt.icons}
              </div>
              <div>
                <div className="font-display text-sm sm:text-base text-ink uppercase leading-tight mt-1">
                  {t(opt.labelKey)}
                </div>
                <div className="font-mono text-[11px] text-ink/75 font-semibold">
                  {opt.subTextKey}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default SunMoonStrip
