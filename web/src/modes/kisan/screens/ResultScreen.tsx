import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { OfflineRecommendationResult } from '../../../offline/engine'
import { AudioSpeakerButton } from '../components/AudioSpeakerButton'
import { DistrictPickerModal } from '../components/DistrictPickerModal'
import { FeedbackModal } from '../components/FeedbackModal'
import { OfflineIndicator } from '../components/OfflineIndicator'
import { SafetyBlock } from '../../../design'
import { getCommodityImage, FALLBACK_CROP_IMAGE } from '../../../data/commodityImages'
import { getApiUrl } from '../../../api/config'
import { VoiceFeedbackButton } from '../../../voice/VoiceFeedbackButton'
import { InsightsPanel } from '../../../insights/InsightsPanel'
import { WhereToBuy, FARM_SEARCH_TERMS } from '../../../design/WhereToBuy'

interface ResultScreenProps {
  result: OfflineRecommendationResult
  onRestart: () => void
  onUpdateDistrict: (district: string) => void
  /** whole | cut | washed | damaged — low-cost tips are never offered for cut produce. */
  physicalState?: string
}

export const ResultScreen: React.FC<ResultScreenProps> = ({
  result,
  onRestart,
  onUpdateDistrict,
  physicalState,
}) => {
  const { t, i18n } = useTranslation()
  const [isDistrictPickerOpen, setIsDistrictPickerOpen] = useState<boolean>(false)
  const [isFeedbackModalOpen, setIsFeedbackModalOpen] = useState<boolean>(false)

  const currentLang = i18n.language || 'mr'
  const currentLangKey = currentLang.split('-')[0].toLowerCase()

  // Asynchronous LLM Explanation Polling State per language
  const [explanationsByLocale, setExplanationsByLocale] = useState<Record<string, string>>({})
  const resultId = (result as any).resultId || (result as any).result_id

  useEffect(() => {
    if (!resultId || result.isOffline) return

    let isCancelled = false
    const targetLocale = `${currentLangKey}-IN`

    // If already fetched and cached for this language, skip polling
    if (explanationsByLocale[currentLangKey]) return

    const fetchExplanation = async () => {
      try {
        const res = await fetch(getApiUrl(`/api/v1/recommend/${resultId}/explanation?locale=${targetLocale}`))
        if (!res.ok) return
        const data = await res.json()
        if (data.status === 'ready' && !isCancelled && data.explanation?.kisan_instruction) {
          setExplanationsByLocale((prev) => ({
            ...prev,
            [currentLangKey]: data.explanation.kisan_instruction,
          }))
        }
      } catch {
        // Fall back gracefully
      }
    }

    fetchExplanation()

    // Poll for deferred explanation every 1.5 seconds, max 10 attempts
    const maxAttempts = 10
    let attempts = 0
    const poll = setInterval(async () => {
      attempts++
      if (attempts > maxAttempts || isCancelled || explanationsByLocale[currentLangKey]) {
        clearInterval(poll)
        return
      }
      await fetchExplanation()
    }, 1500)

    return () => {
      isCancelled = true
      clearInterval(poll)
    }
  }, [resultId, result.isOffline, currentLangKey, explanationsByLocale])

  const isRefusal = result.verdict === 'NOT_A_PACKAGING_PROBLEM'
  const pkg = result.recommendedPackage

  const commodityId =
    result.resolved?.commodity?.id ||
    result.commodityId ||
    ''
  let rawCommName =
    result.resolved?.commodity?.display_name ||
    result.resolved?.commodity?.name ||
    result.commodityName ||
    'produce'

  // Ensure common names are always used instead of Latin binomials (e.g. solanum tuberosum)
  if (commodityId.includes('potato') || rawCommName.toLowerCase().includes('tuberosum')) {
    rawCommName = 'Potato'
  } else if (commodityId.includes('tomato') || rawCommName.toLowerCase().includes('lycopersicum')) {
    rawCommName = 'Tomato'
  } else if (commodityId.includes('onion') || rawCommName.toLowerCase().includes('cepa')) {
    rawCommName = 'Onion'
  } else if (commodityId.includes('mango') || rawCommName.toLowerCase().includes('indica')) {
    rawCommName = 'Mango'
  } else if (commodityId.includes('banana') || rawCommName.toLowerCase().includes('acuminata')) {
    rawCommName = 'Banana'
  } else if (commodityId.includes('chilli') || rawCommName.toLowerCase().includes('annuum')) {
    rawCommName = 'Green Chilli'
  } else if (commodityId.includes('cauliflower') || rawCommName.toLowerCase().includes('botrytis')) {
    rawCommName = 'Cauliflower'
  } else if (commodityId.includes('cabbage') || rawCommName.toLowerCase().includes('capitata')) {
    rawCommName = 'Cabbage'
  } else if (commodityId.includes('spinach') || rawCommName.toLowerCase().includes('spinacia')) {
    rawCommName = 'Spinach'
  } else if (commodityId.includes('okra') || rawCommName.toLowerCase().includes('esculentus')) {
    rawCommName = 'Okra'
  } else if (commodityId.includes('guava') || rawCommName.toLowerCase().includes('guajava')) {
    rawCommName = 'Guava'
  } else if (commodityId.includes('grape') || rawCommName.toLowerCase().includes('vinifera')) {
    rawCommName = 'Grapes'
  } else if (commodityId.includes('pomegranate') || rawCommName.toLowerCase().includes('granatum')) {
    rawCommName = 'Pomegranate'
  } else if (commodityId.includes('brinjal') || rawCommName.toLowerCase().includes('melongena')) {
    rawCommName = 'Brinjal'
  }

  let localizedCommName: string | undefined = undefined
  if (currentLangKey !== 'en') {
    for (const cropKey of ['potato', 'tomato', 'onion', 'banana', 'mango', 'okra', 'spinach', 'green_chilli', 'guava', 'cauliflower', 'cabbage', 'grape', 'pomegranate', 'brinjal']) {
      if (commodityId.toLowerCase().includes(cropKey) || rawCommName.toLowerCase().includes(cropKey)) {
        localizedCommName = t(`crops.${cropKey}`)
        break
      }
    }
  } else {
    localizedCommName = rawCommName
  }
  const commodityName = localizedCommName || rawCommName
  const heroImage = getCommodityImage(commodityId || rawCommName)

  const rawPackagingName =
    pkg?.name ||
    (result as any).recommendation?.packaging_name ||
    (result as any).candidates?.[0]?.structure_name ||
    'RECOMMENDED PACKAGING'
  const packagingLabel = rawPackagingName.toUpperCase()

  const insightCommodityId: string =
    (result as any).resolved?.commodity?.commodity_id || (result as any).commodityId || commodityId
  const daysP50 = result.shelfLifeDaysP50 || (result as any).shelf_life?.days_p50 || 7

  // Helper to generate verified local instruction sentence per language and package structure
  const getLocalizedKisanInstruction = (
    _lang: string,
    days: number,
    crop: string,
    packageInfo?: typeof pkg
  ) => {
    const pType =
      packageInfo?.structureType ||
      (packageInfo?.instructionKey?.includes('crate')
        ? 'ventilated_crate'
        : packageInfo?.instructionKey?.includes('pouch')
          ? 'perforated_pouch'
          : 'mesh_sack')

    if (pType === 'ventilated_crate') {
      return t('result.instruction_crate', {
        crop,
        days,
        defaultValue: `Store your ${crop} in a ventilated crate in a dry shaded place to keep it fresh for ${days} days.`,
      })
    }

    if (pType === 'perforated_pouch') {
      return t('result.instruction_pouch', {
        crop,
        days,
        defaultValue: `Store your ${crop} in a micro-perforated breathable pouch in a dry shaded place to keep it fresh for ${days} days.`,
      })
    }

    return t('result.instruction_sack', {
      crop,
      days,
      defaultValue: `Store your ${crop} in a ventilated mesh sack in a dry shaded place to keep it fresh for ${days} days.`,
    })
  }

  const dynamicInstruction = getLocalizedKisanInstruction(
    currentLangKey,
    daysP50,
    commodityName,
    pkg
  )

  // Whole days only (floored, matching the day counter and what Saathi speaks): "23.2 दिवस" -> "23 दिवस"
  const kisanInstruction = (explanationsByLocale[currentLangKey] || dynamicInstruction || '').replace(
    /(\d+)\.\d+/g,
    '$1',
  )

  const getDoNotText = (textKey: string) => {
    const rawKey = textKey.startsWith('donot.') ? textKey.replace('donot.', '') : textKey
    const normalizedKey = rawKey === 'donot_airtight' ? 'donot_seal_airtight' : rawKey
    return t(`donot.${normalizedKey}`, {
      defaultValue: t(`donot.${rawKey}`, {
        defaultValue: 'Do not seal airtight without ventilation.',
      }),
    })
  }

  // Construct text to read aloud
  let textToRead = ''
  if (isRefusal) {
    const heading = t('safety.heading', { commodity: commodityName })
    const adv = t('safety.body_cut_heat', { commodity: commodityName })
    const act = t('safety.action_cut', { commodity: commodityName })
    textToRead = `${heading}. ${adv}. ${act}`
  } else if (pkg) {
    const doNots = pkg.doNotItems.map((item) => getDoNotText(item.textKey)).join('. ')
    const speechInstruction = kisanInstruction
    textToRead = `${commodityName}. ${speechInstruction}. ${t('result.shelf_life_label')}: ${daysP50} ${t('result.days_suffix')}. ${t('result.indicative_price')}: ${pkg.costPerPack || result.indicativePrice}. ${t('result.do_not_title')}: ${doNots}`
  }

  // Row of sun icons for shelf life (e.g. 4 days -> ☀️☀️☀️☀️)
  const renderSunIcons = (days: number) => {
    const capped = Math.min(10, Math.max(1, days))
    const suns = Array.from({ length: capped }).map((_, i) => (
      <span key={i} className="text-2xl sm:text-3xl" aria-hidden="true">
        ☀️
      </span>
    ))
    return (
      <div className="flex items-center flex-wrap gap-1">
        {suns}
        <span className="font-display text-2xl sm:text-4xl text-ink ml-2">
          {days} <span className="text-base sm:text-lg font-mono">{t('result.days_suffix')}</span>
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Top Header: Offline status and Start Over button */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <OfflineIndicator isOffline={result.isOffline} isResultOffline={result.isOffline} />
        <button
          type="button"
          onClick={onRestart}
          className="min-h-[44px] px-4 font-display uppercase border-3 border-ink bg-paper hover:bg-grey/40 cursor-pointer shadow-[3px_3px_0_var(--ink)] text-sm"
        >
          🔄 {t('actions.back')}
        </button>
      </div>

      {/* --- CASE 1: REFUSAL (NOT_A_PACKAGING_PROBLEM) -> FULL CORAL SAFETY BLOCK --- */}
      {isRefusal ? (
        <div className="space-y-6">
          <SafetyBlock
            className="w-full"
            result={result}
          />

          {/* Speaker Button to read safety card aloud */}
          <AudioSpeakerButton textToSpeak={textToRead} className="w-full" />

          {/* Refused: today's mandi price helps decide where to sell right now */}
          <InsightsPanel
            commodityId={insightCommodityId}
            physicalState={physicalState ?? 'cut'}
            shelfLifeDays={0}
            district={result.whereToBuyDistrict}
          />
        </div>
      ) : (
        /* --- CASE 2: RECOMMENDED RESULT CARD FILLING SCREEN --- */
        <div className="border-6 border-ink bg-paper p-5 sm:p-8 shadow-[10px_10px_0_var(--ink)] space-y-6">
          {/* Card Top Title Banner */}
          <div className="flex items-center justify-between flex-wrap gap-2 border-b-3 border-ink pb-3">
            <div className="flex items-center gap-2">
              <span className="text-2xl">📦</span>
              <h2 className="font-display uppercase text-lg sm:text-2xl text-ink m-0">
                {t('result.recommended_title')}
              </h2>
            </div>
            <span className="font-mono text-xs sm:text-sm font-bold bg-lime border-2 border-ink px-2.5 py-0.5">
              {pkg?.eprCategory || 'RECYCLABLE'}
            </span>
          </div>

          {/* 1. Large Photograph of Selected Commodity Matching Recommended Packaging */}
          <div className="result-hero-image-wrap border-4 border-ink overflow-hidden bg-grey/30 max-h-72 sm:max-h-80 w-full relative">
            <img
              src={heroImage}
              alt={`${commodityName} — ${packagingLabel}`}
              onError={(e) => {
                (e.target as HTMLImageElement).src = FALLBACK_CROP_IMAGE
              }}
              className="w-full h-full object-cover"
            />
            <div className="result-hero-label absolute bottom-0 inset-x-0 bg-ink/80 text-paper p-2 font-display text-sm uppercase tracking-wide">
              {packagingLabel}
            </div>
          </div>

          {/* 2. One instruction sentence in the local language, large */}
          {kisanInstruction ? (
            <div className="border-3 border-ink bg-yellow p-4 sm:p-5 shadow-[4px_4px_0_var(--ink)] min-h-[72px] flex items-center transition-opacity duration-200">
              <p className="font-display text-xl sm:text-2xl text-ink leading-tight m-0">
                {kisanInstruction}
              </p>
            </div>
          ) : (
            <div
              className="border-3 border-ink bg-paper p-4 sm:p-5 shadow-[4px_4px_0_var(--ink)] min-h-[72px] flex items-center overflow-hidden relative skeleton-shimmer"
              aria-label="Loading instruction…"
            >
              <div className="w-3/4 h-6 bg-ink/15 animate-pulse" />
            </div>
          )}

          {/* 3. Shelf life expressed in days as a row of sun icons with number (never a chart) */}
          <div className="border-3 border-ink bg-paper p-4 shadow-[4px_4px_0_var(--ink)] space-y-1">
            <div className="font-mono text-xs uppercase font-bold text-ink/75">
              {t('result.shelf_life_label')}
            </div>
            {renderSunIcons(result.shelfLifeDaysP50)}
          </div>

          {/* 4. Up to three "do not" items as picture plus short phrase */}
          {pkg && pkg.doNotItems.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-display uppercase text-base sm:text-lg text-ink">
                {t('result.do_not_title')}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {pkg.doNotItems.map((item, idx) => (
                  <div
                    key={idx}
                    className="border-3 border-ink bg-grey/30 p-3 flex items-start gap-2.5 shadow-[3px_3px_0_var(--ink)]"
                  >
                    <span className="text-2xl" aria-hidden="true">
                      {item.icon}
                    </span>
                    <span className="font-body text-xs sm:text-sm font-bold text-ink leading-snug">
                      {getDoNotText(item.textKey)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. Indicative price and "where to buy" link keyed to user's district */}
          <div className="border-3 border-ink bg-cyan/20 p-4 shadow-[4px_4px_0_var(--ink)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="font-mono text-xs uppercase font-bold text-ink/70">
                {t('result.indicative_price')}
              </div>
              <div className="font-display text-2xl text-ink">
                {pkg?.costPerPack || result.indicativePrice}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setIsDistrictPickerOpen(true)}
                className="
                  min-h-[48px] px-4 font-display uppercase text-sm border-3 border-ink bg-yellow
                  hover:bg-yellow/90 shadow-[4px_4px_0_var(--ink)] cursor-pointer flex items-center gap-2
                "
              >
                <span>📍 {t('actions.where_to_buy')}</span>
                <span className="underline font-bold">({result.whereToBuyDistrict})</span>
              </button>
            </div>
          </div>

          {pkg && (
            <WhereToBuy
              searchTerm={FARM_SEARCH_TERMS[pkg.structureType] || FARM_SEARCH_TERMS.mesh_sack}
              district={result.whereToBuyDistrict}
            />
          )}

          {/* 6. Action Row: Prominent Speaker Button & "I did this" button */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <AudioSpeakerButton textToSpeak={textToRead} className="w-full" />

            <button
              type="button"
              onClick={() => setIsFeedbackModalOpen(true)}
              className="
                min-h-[64px] px-6 py-3 font-display uppercase tracking-wider text-base sm:text-lg
                border-3 border-ink bg-lime text-ink shadow-[6px_6px_0_var(--ink)] cursor-pointer
                hover:bg-lime/90 hover:-translate-x-[2px] hover:-translate-y-[2px]
                active:translate-x-[4px] active:translate-y-[4px] flex items-center justify-center gap-3
                transition-all duration-[80ms]
              "
            >
              <span className="text-3xl" aria-hidden="true">
                🤝
              </span>
              <span>{t('actions.i_did_this')}</span>
            </button>
          </div>

          {/* 7. Low-cost, no-plastic options and "sell today or store?" */}
          <InsightsPanel
            commodityId={insightCommodityId}
            physicalState={physicalState}
            shelfLifeDays={daysP50}
            district={result.whereToBuyDistrict}
          />

          {/* 8. Spoken outcome report (Gnani Prisma) — only for server-sealed results */}
          {!result.isOffline && resultId && !String(resultId).startsWith('offline_') && (
            <VoiceFeedbackButton resultId={String(resultId)} />
          )}
        </div>
      )}

      {/* District Picker Modal */}
      <DistrictPickerModal
        isOpen={isDistrictPickerOpen}
        currentDistrict={result.whereToBuyDistrict}
        onClose={() => setIsDistrictPickerOpen(false)}
        onSelectDistrict={onUpdateDistrict}
      />

      {/* "I Did This" Feedback Follow-up Modal */}
      {pkg && (
        <FeedbackModal
          isOpen={isFeedbackModalOpen}
          resultId={result.resultId}
          commodityId={result.commodityId}
          packageName={pkg.name}
          shelfLifeDays={result.shelfLifeDaysP50}
          district={result.whereToBuyDistrict}
          onClose={() => setIsFeedbackModalOpen(false)}
        />
      )}
    </div>
  )
}

export default ResultScreen
