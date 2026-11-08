import React from 'react'
import { useTranslation } from 'react-i18next'

interface OfflineIndicatorProps {
  isOffline: boolean
  isResultOffline?: boolean
}

export const OfflineIndicator: React.FC<OfflineIndicatorProps> = ({
  isOffline,
  isResultOffline,
}) => {
  const { t } = useTranslation()

  if (!isOffline && !isResultOffline) {
    return (
      <div className="flex items-center gap-1.5 border-2 border-ink bg-lime px-2.5 py-1 font-mono text-xs font-bold text-ink shadow-[2px_2px_0_var(--ink)]">
        <span className="w-2.5 h-2.5 rounded-full bg-ink animate-pulse" />
        <span>{t('app.online_badge')}</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 border-3 border-ink bg-yellow px-3 py-1 font-mono text-xs sm:text-sm font-black text-ink shadow-[3px_3px_0_var(--ink)] animate-bounce-short">
      <span className="text-base" aria-hidden="true">
        ⚡
      </span>
      <span>{t('app.offline_badge')}</span>
    </div>
  )
}

export default OfflineIndicator
