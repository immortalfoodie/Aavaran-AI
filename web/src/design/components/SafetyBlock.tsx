import React from 'react'
import { useTranslation } from 'react-i18next'
import '../../i18n'
import { getCommodityImage, FALLBACK_CROP_IMAGE } from '../../data/commodityImages'

export interface SafetyBlockProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string
  advisory?: string
  action?: string
  hazardCode?: string
  result?: any
  showAlternatives?: boolean
}

function renderWithCommodity(text: string, commodityName: string): React.ReactNode {
  if (!text) return text

  // 1. If text contains {commodity_name} placeholder
  if (text.includes('{commodity_name}')) {
    const parts = text.split('{commodity_name}')
    return parts.map((part, index) => (
      <React.Fragment key={index}>
        {part}
        {index < parts.length - 1 && <strong>{commodityName || 'produce'}</strong>}
      </React.Fragment>
    ))
  }

  // 2. If text contains {{commodity}} placeholder
  if (text.includes('{{commodity}}')) {
    const parts = text.split('{{commodity}}')
    return parts.map((part, index) => (
      <React.Fragment key={index}>
        {part}
        {index < parts.length - 1 && <strong>{commodityName || 'produce'}</strong>}
      </React.Fragment>
    ))
  }

  // 3. If commodityName is known and text contains hardcoded "potato" / "potatoes", replace it
  if (commodityName && /\bpotatoes\b|\bpotato\b/i.test(text) && !commodityName.toLowerCase().includes('potato')) {
    const parts = text.split(/\bpotatoes\b|\bpotato\b/gi)
    return parts.map((part, index) => (
      <React.Fragment key={index}>
        {part}
        {index < parts.length - 1 && <strong>{commodityName}</strong>}
      </React.Fragment>
    ))
  }

  // 4. Wrap commodityName with <strong>
  if (commodityName && text.includes(commodityName)) {
    const parts = text.split(commodityName)
    return parts.map((part, index) => (
      <React.Fragment key={index}>
        {part}
        {index < parts.length - 1 && <strong>{commodityName}</strong>}
      </React.Fragment>
    ))
  }

  return text
}

export const SafetyBlock: React.FC<SafetyBlockProps> = ({
  title,
  advisory,
  action,
  hazardCode: propsHazardCode,
  result,
  showAlternatives = true,
  className = '',
  ...props
}) => {
  const { t, i18n } = useTranslation()

  // Extract commodity display name or local name from result prop
  const commObj = result?.resolved?.commodity ?? result?.commodity
  let localName =
    typeof commObj === 'object' && commObj !== null ? commObj.local_name : undefined
  const displayName =
    typeof commObj === 'object' && commObj !== null
      ? commObj.display_name || commObj.name
      : typeof commObj === 'string'
        ? commObj
        : undefined

  // If localName is not explicitly given, translate known crops in non-English locales
  if (!localName && i18n.language !== 'en') {
    const rawId = commObj?.id || result?.commodityId || displayName || ''
    const cropKeys = ['potato', 'tomato', 'onion', 'banana', 'mango', 'okra', 'spinach', 'green_chilli', 'guava', 'cauliflower', 'cabbage', 'grape', 'pomegranate', 'brinjal']
    for (const cropKey of cropKeys) {
      if (rawId.toLowerCase().includes(cropKey)) {
        localName = t(`crops.${cropKey}`)
        break
      }
    }
  }

  const commodityName =
    localName ||
    displayName ||
    result?.commodityName ||
    result?.commodity_name ||
    ''

  const rawId = commObj?.id || result?.commodityId || result?.resolved?.commodity?.id || displayName || ''
  const cropImage = getCommodityImage(rawId)

  const hazardCode = result?.safety?.rule_id || result?.safety?.ruleId || propsHazardCode

  const headingText =
    title && title !== 'PACKAGING WILL NOT SAVE THIS FOOD'
      ? title
      : t('safety.heading', { commodity: commodityName })
  const renderedHeading = renderWithCommodity(headingText, commodityName)

  const defaultAdvisory = t('safety.body_cut_heat', { commodity: commodityName })
  const advisoryText = advisory || defaultAdvisory
  const renderedAdvisory = renderWithCommodity(advisoryText, commodityName)

  const defaultAction = t('safety.action_cut', { commodity: commodityName })
  const actionText = action || defaultAction
  const renderedAction = actionText ? renderWithCommodity(actionText, commodityName) : null

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`
        border-6 border-ink bg-coral text-ink p-5 sm:p-7
        shadow-[10px_10px_0_var(--ink)]
        select-none relative flex flex-col gap-3
        ${className}
      `.trim()}
      {...props}
    >
      {/* Header with paired ⚠ icon and mandatory "UNSAFE" word label */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-3 border-ink pb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl sm:text-3xl font-display" aria-hidden="true">
            ⚠
          </span>
          <span className="font-display uppercase text-lg sm:text-xl tracking-wider bg-ink text-paper px-2.5 py-0.5">
            {t('safety.badge')}
          </span>
          <span className="font-display uppercase text-base sm:text-lg tracking-wide">
            {t('safety.subtitle')}
          </span>
        </div>
        {hazardCode && (
          <span className="font-mono text-xs font-bold bg-paper text-ink border-2 border-ink px-2 py-0.5">
            {`${t('safety.hazard_ref')} ${hazardCode}`}
          </span>
        )}
      </div>

      {/* Main warning headline */}
      <h3 className="font-display text-xl sm:text-2xl tracking-tight text-ink uppercase mt-1">
        {renderedHeading}
      </h3>

      {/* Visual Crop Danger Photo with subtle red/coral overlay */}
      <div className="relative border-4 border-ink overflow-hidden max-h-56 sm:max-h-64 w-full bg-ink/10 my-1">
        <img
          src={cropImage}
          alt={commodityName || 'Produce'}
          onError={(e) => {
            (e.target as HTMLImageElement).src = FALLBACK_CROP_IMAGE
          }}
          className="w-full h-48 sm:h-56 object-cover"
          style={{ filter: 'brightness(0.7)' }}
        />
        <div
          className="absolute inset-0 bg-coral pointer-events-none"
          style={{ opacity: 0.3 }}
        />
        <div className="absolute bottom-2 left-2 bg-ink text-paper px-2.5 py-1 font-display text-xs sm:text-sm uppercase tracking-wider border border-paper">
          ⚠ {commodityName} — {t('safety.badge', 'UNSAFE')}
        </div>
      </div>

      {/* Safety explanation */}
      <p className="font-body text-base sm:text-lg font-medium leading-relaxed text-ink">
        {renderedAdvisory}
      </p>

      {/* Required non-dismissible actionable next step */}
      {renderedAction && (
        <div className="mt-2 pt-3 border-t-2 border-ink/40 font-mono text-sm sm:text-base font-bold bg-paper/20 p-3 border-2 border-ink">
          <span className="uppercase mr-2 font-display bg-ink text-paper px-1.5 py-0.5 text-xs">
            {t('safety.action_label')}
          </span>
          <span>{renderedAction}</span>
        </div>
      )}

      {/* Actionable "What to do instead" list */}
      {showAlternatives && (
        <div className="mt-4 pt-4 border-t-3 border-ink space-y-3">
          <div className="flex items-center gap-2.5 border-b-2 border-ink pb-2">
            <img
              src={cropImage}
              alt=""
              onError={(e) => {
                (e.target as HTMLImageElement).src = FALLBACK_CROP_IMAGE
              }}
              className="w-8 h-8 rounded-full object-cover border-2 border-ink"
            />
            <span className="text-2xl" aria-hidden="true">📋</span>
            <h4 className="font-display uppercase text-lg sm:text-xl text-ink m-0">
              {t('safety.alternatives_heading')}
            </h4>
          </div>

          <div className="space-y-3">
            {/* 1. Chill */}
            <div className="p-3 border-3 border-ink bg-cyan/20 flex items-start gap-3">
              <span className="text-2xl mt-0.5" aria-hidden="true">❄️</span>
              <div>
                <h5 className="font-display text-base text-ink uppercase m-0">
                  {`1. ${t('safety.alt_chill_title')}`}
                </h5>
                <p className="font-body text-xs sm:text-sm text-ink/85 mt-0.5 mb-0">
                  {t('safety.alt_chill_body')}
                </p>
              </div>
            </div>

            {/* 2. Sell / Cook */}
            <div className="p-3 border-3 border-ink bg-yellow/20 flex items-start gap-3">
              <span className="text-2xl mt-0.5" aria-hidden="true">🍳</span>
              <div>
                <h5 className="font-display text-base text-ink uppercase m-0">
                  {`2. ${t('safety.alt_sell_title')}`}
                </h5>
                <p className="font-body text-xs sm:text-sm text-ink/85 mt-0.5 mb-0">
                  {renderWithCommodity(t('safety.alt_sell_body', { commodity: commodityName }), commodityName)}
                </p>
                <p className="font-body text-xs text-ink/85 mt-1 font-bold mb-0">
                  {t('safety.alt_dont_seal')}
                </p>
              </div>
            </div>

            {/* 3. Next Time / Future */}
            <div className="p-3 border-3 border-ink bg-lime/25 flex items-start gap-3">
              <span className="text-2xl mt-0.5" aria-hidden="true">⚡</span>
              <div>
                <h5 className="font-display text-base text-ink uppercase m-0">
                  {`3. ${t('safety.alt_future_title')}`}
                </h5>
                <p className="font-body text-xs sm:text-sm text-ink/85 mt-0.5 mb-0">
                  {renderWithCommodity(t('safety.alt_future_body', { commodity: commodityName }), commodityName)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SafetyBlock
