import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { CropId, PhysicalState, TimeInterval, StorageMethod, KisanState } from './types'
import { WhatScreen } from './screens/WhatScreen'
import { StateScreen } from './screens/StateScreen'
import { ResultScreen } from './screens/ResultScreen'
import { recommendOffline, type OfflineRecommendationResult } from '../../offline/engine'
import { useNetworkStatus, initOfflineSync } from '../../offline/sync'
import { getApiUrl } from '../../api/config'
import { getCommodityImage, FALLBACK_CROP_IMAGE } from '../../data/commodityImages'
import { SaathiPanel } from '../../voice/SaathiPanel'
import { saathiLangFromI18n, type SaathiTurn } from '../../voice/voiceApi'

interface KisanModeProps {
  /** Saathi detected a packaged-food business query: hand it to Business mode. */
  onVoiceBusiness?: (turn: SaathiTurn) => void
}

export const KisanMode: React.FC<KisanModeProps> = ({ onVoiceBusiness }) => {
  const { t, i18n } = useTranslation()
  const isOnline = useNetworkStatus()

  // 3-screen step: 1 (WHAT), 2 (STATE), 3 (RESULT)
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1)

  // Loading overlay and button states
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [showOverlay, setShowOverlay] = useState<boolean>(false)
  const [loadingStepText, setLoadingStepText] = useState<string>('')

  // Kisan user state
  const [kisanState, setKisanState] = useState<KisanState>({
    selectedCrop: null,
    physicalState: 'whole',
    timeInterval: 'today',
    storageMethod: 'shed',
    district: 'Nashik',
  })

  const [isSaathiOpen, setIsSaathiOpen] = useState<boolean>(false)

  // Final recommendation result
  const [recommendationResult, setRecommendationResult] =
    useState<OfflineRecommendationResult | null>(null)

  // Initialize background offline synchronizer
  useEffect(() => {
    const cleanup = initOfflineSync()
    return cleanup
  }, [])

  // Tap 1: Select Crop -> Advance to Screen 2
  const handleSelectCrop = (crop: CropId) => {
    setKisanState((prev) => ({ ...prev, selectedCrop: crop }))
    setCurrentStep(2)
  }

  // Tap 2: Select State
  const handleChangeState = (state: PhysicalState) => {
    setKisanState((prev) => ({ ...prev, physicalState: state }))
  }

  // Tap 3: Select Time Interval
  const handleChangeTime = (time: TimeInterval) => {
    setKisanState((prev) => ({ ...prev, timeInterval: time }))
  }

  const handleChangeStorage = (storage: StorageMethod) => {
    setKisanState((prev) => ({ ...prev, storageMethod: storage }))
  }

  // Trigger recommendation calculation (Tap 3 / Submit)
  const handleCalculate = async (override?: KisanState) => {
    const ks = override ?? kisanState
    const hoursMap: Record<TimeInterval, number> = {
      today: 4,
      one_day: 24,
      two_days: 48,
      three_days_plus: 72,
    }

    const cropKey = (ks.selectedCrop || '').toLowerCase()
    let cropName = 'Crop'
    for (const k of ['potato', 'tomato', 'onion', 'banana', 'mango', 'okra', 'spinach', 'chilli']) {
      if (cropKey.includes(k)) {
        cropName = t(`crops.${k === 'chilli' ? 'green_chilli' : k}`, { defaultValue: k })
        break
      }
    }

    setIsLoading(true)
    setLoadingStepText(`Checking ${cropName} properties…`)

    const overlayTimer = setTimeout(() => {
      setShowOverlay(true)
    }, 100)

    const stepTimers: ReturnType<typeof setTimeout>[] = [
      setTimeout(() => setLoadingStepText('Calculating packaging requirements…'), 400),
      setTimeout(() => setLoadingStepText('Finding best structures…'), 800),
      setTimeout(() => setLoadingStepText('Almost ready…'), 1200),
    ]

    const finishLoading = (resultData: OfflineRecommendationResult) => {
      clearTimeout(overlayTimer)
      stepTimers.forEach((timer) => clearTimeout(timer))
      setShowOverlay(false)
      setIsLoading(false)
      setRecommendationResult(resultData)
      setCurrentStep(3)
    }

    const inputPayload = {
      commodityId: ks.selectedCrop || 'veg.potato.solanum_tuberosum',
      state: {
        cut: ks.physicalState === 'cut',
        washed: ks.physicalState === 'washed',
        bruised: ks.physicalState === 'damaged',
        hoursSinceCut: hoursMap[ks.timeInterval],
        hoursSinceHarvest: hoursMap[ks.timeInterval],
      },
      storage: ks.storageMethod,
      district: ks.district,
    }

    // Try online API if connected, fallback seamlessly to client-side engine
    if (isOnline) {
      try {
        const response = await fetch(getApiUrl('/api/v1/recommend'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mode: 'kisan',
            input: {
              commodity_id: inputPayload.commodityId,
              state: inputPayload.state,
              environment: {
                storage_type:
                  inputPayload.storage === 'cold_room'
                    ? 'refrigerated'
                    : inputPayload.storage === 'ice'
                    ? 'chilled'
                    : 'ambient',
                temperature:
                  inputPayload.storage === 'cold_room' ? 4.0 : inputPayload.storage === 'ice' ? 2.0 : 30.0,
              },
            },
            locale: i18n.language === 'mr' ? 'mr-IN' : i18n.language === 'hi' ? 'hi-IN' : 'en-IN',
          }),
        })

        if (response.ok) {
          const apiData = await response.json()
          if (apiData.verdict === 'NOT_A_PACKAGING_PROBLEM') {
            const refusalRes = recommendOffline(inputPayload)
            refusalRes.isOffline = false
            if (apiData.safety) refusalRes.safety = apiData.safety
            if (apiData.resolved) refusalRes.resolved = apiData.resolved
            finishLoading(refusalRes)
            return
          } else if (apiData.candidates && apiData.candidates.length > 0) {
            const recRes = recommendOffline(inputPayload)
            recRes.isOffline = false
            recRes.resultId = apiData.result_id || recRes.resultId
            if (apiData.resolved) recRes.resolved = apiData.resolved
            if (apiData.recommendation) {
              (recRes as any).recommendation = apiData.recommendation
            }
            if (apiData.candidates) {
              (recRes as any).candidates = apiData.candidates
            }
            if (apiData.shelf_life?.days_p50) {
              recRes.shelfLifeDaysP50 = Math.round(apiData.shelf_life.days_p50)
            }
            finishLoading(recRes)
            return
          }
        }
      } catch {
        // Fall through to offline calculation
      }
    }

    // Run client-side offline engine
    const offlineRes = recommendOffline(inputPayload)
    finishLoading(offlineRes)
  }

  // Saathi finished a voice consultation: show the same result screen the taps produce.
  const handleSaathiResult = (turn: SaathiTurn) => {
    setIsSaathiOpen(false)
    if (turn.mode === 'business') {
      onVoiceBusiness?.(turn)
      return
    }
    const s = turn.slots
    const next: KisanState = {
      ...kisanState,
      selectedCrop: (s.commodity_id as CropId) || kisanState.selectedCrop,
      physicalState: s.physical_state ?? 'whole',
      timeInterval: s.time_interval ?? 'one_day',
      storageMethod: s.storage ?? 'shed',
    }
    setKisanState(next)
    setCurrentStep(2)
    handleCalculate(next)
  }

  const handleRestart = () => {
    setCurrentStep(1)
  }

  const handleUpdateDistrict = (newDist: string) => {
    setKisanState((prev) => ({ ...prev, district: newDist }))
    if (recommendationResult) {
      setRecommendationResult({ ...recommendationResult, whereToBuyDistrict: newDist })
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Step pills (language now lives in the app bar) */}
      {currentStep > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          {[1, 2, 3].map((stepNum) => {
            const isCurrent = currentStep === stepNum
            const isDone = currentStep > stepNum
            return (
              <div
                key={stepNum}
                className={`flex items-center gap-1.5 px-3 py-1 border-2 border-ink font-display text-xs uppercase ${
                  isCurrent ? 'bg-yellow shadow-[2px_2px_0_var(--ink)]' : isDone ? 'bg-lime text-ink' : 'bg-grey/30 text-ink/60'
                }`}
              >
                <span>{t(`nav.step${stepNum}`)}</span>
                {isDone && <span>✓</span>}
              </div>
            )
          })}
        </div>
      )}

      {/* Hero: one huge button. Speaking is the primary way in. */}
      {currentStep === 1 && (
        <button
          type="button"
          onClick={() => setIsSaathiOpen(true)}
          className="w-full text-left border-4 border-ink bg-coral p-5 sm:p-7 shadow-[8px_8px_0_var(--ink)] cursor-pointer hover:-translate-x-[2px] hover:-translate-y-[2px] active:translate-x-[4px] active:translate-y-[4px] transition-all duration-[80ms] flex items-center gap-4 sm:gap-6"
        >
          <span
            className="shrink-0 w-20 h-20 sm:w-24 sm:h-24 border-4 border-ink bg-yellow flex items-center justify-center text-5xl sm:text-6xl shadow-[4px_4px_0_var(--ink)]"
            aria-hidden="true"
          >
            🎙
          </span>
          <span className="space-y-1.5">
            <span className="block font-display uppercase text-2xl sm:text-4xl leading-tight text-ink">
              {t('nav.hero_title')}
            </span>
            <span className="block font-body text-base sm:text-lg text-ink">{t('nav.hero_sub')}</span>
          </span>
        </button>
      )}

      {currentStep === 1 && (
        <h2 className="font-display uppercase text-base sm:text-lg text-ink/80 m-0 pt-2">{t('nav.or_tap')} ↓</h2>
      )}

      {/* Screen Views */}
      {currentStep === 1 && (
        <WhatScreen
          selectedCrop={kisanState.selectedCrop}
          onSelectCrop={handleSelectCrop}
          hideVoiceButton
        />
      )}

      {currentStep === 2 && (
        <StateScreen
          cropId={kisanState.selectedCrop}
          physicalState={kisanState.physicalState}
          timeInterval={kisanState.timeInterval}
          storageMethod={kisanState.storageMethod}
          isLoading={isLoading}
          onChangeState={handleChangeState}
          onChangeTime={handleChangeTime}
          onChangeStorage={handleChangeStorage}
          onCalculate={handleCalculate}
          onBack={() => setCurrentStep(1)}
        />
      )}

      {currentStep === 3 && recommendationResult && (
        <div className="transition-opacity duration-200 opacity-100">
          <ResultScreen
            result={recommendationResult}
            onRestart={handleRestart}
            onUpdateDistrict={handleUpdateDistrict}
            physicalState={kisanState.physicalState}
          />
        </div>
      )}

      {isSaathiOpen && (
        <SaathiPanel
          mode="kisan"
          initialLang={saathiLangFromI18n(i18n.language)}
          onClose={() => setIsSaathiOpen(false)}
          onResult={handleSaathiResult}
        />
      )}

      {/* Full-screen Loading Overlay with blurred crop background and animated progress bar */}
      {showOverlay && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/80 backdrop-blur-md transition-opacity duration-200">
          {/* Blurred crop photo background */}
          <div
            className="absolute inset-0 bg-cover bg-center filter blur-md opacity-25 scale-105 pointer-events-none"
            style={{
              backgroundImage: `url(${getCommodityImage(kisanState.selectedCrop)})`,
            }}
            aria-hidden="true"
          />

          {/* Center brutalist modal card */}
          <div className="relative z-10 w-full max-w-md border-4 border-ink bg-paper p-6 sm:p-8 shadow-[10px_10px_0_var(--ink)] space-y-6">
            <div className="flex items-center gap-4">
              <img
                src={getCommodityImage(kisanState.selectedCrop)}
                alt="Selected crop"
                className="w-16 h-16 sm:w-20 sm:h-20 object-cover border-3 border-ink shadow-[3px_3px_0_var(--ink)] bg-grey/30"
                onError={(e) => {
                  ;(e.target as HTMLImageElement).src = FALLBACK_CROP_IMAGE
                }}
              />
              <div className="space-y-1">
                <div className="font-mono text-[11px] uppercase font-bold text-ink/70 flex items-center gap-1.5">
                  <span className="inline-block w-2.5 h-2.5 bg-lime border border-ink animate-pulse" />
                  AAVARAN ENGINE ⚡
                </div>
                <h3 className="font-display uppercase text-lg sm:text-xl text-ink leading-tight">
                  ANALYSING CROP…
                </h3>
              </div>
            </div>

            {/* Prominent animated progress bar (thick yellow bar, fills left -> right) */}
            <div className="space-y-2">
              <div className="w-full h-7 border-3 border-ink bg-grey/30 overflow-hidden relative shadow-[4px_4px_0_var(--ink)]">
                <div className="loading-progress-bar h-full bg-yellow border-r-3 border-ink" />
              </div>
              <div className="flex items-center justify-between font-mono text-xs text-ink/90 font-bold">
                <span className="truncate pr-2">{loadingStepText}</span>
                <span className="text-sm">⚡</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default KisanMode
