import React from 'react'
import { useTranslation } from 'react-i18next'
import type { PhysicalState, TimeInterval, StorageMethod, CropId } from '../types'
import { SunMoonStrip } from '../components/SunMoonStrip'

interface StateScreenProps {
  cropId: CropId | null
  physicalState: PhysicalState
  timeInterval: TimeInterval
  storageMethod?: StorageMethod
  isLoading?: boolean
  onChangeState: (state: PhysicalState) => void
  onChangeTime: (time: TimeInterval) => void
  onChangeStorage: (storage: StorageMethod) => void
  onCalculate: () => void
  onBack: () => void
}

interface StateCardConfig {
  id: PhysicalState
  labelKey: string
  image: string
  captionKey: string
}

interface StorageCardConfig {
  id: StorageMethod
  labelKey: string
  image: string
  caption: string
}

export const StateScreen: React.FC<StateScreenProps> = ({
  physicalState,
  timeInterval,
  storageMethod = 'shed',
  isLoading = false,
  onChangeState,
  onChangeTime,
  onChangeStorage,
  onCalculate,
  onBack,
}) => {
  const { t } = useTranslation()

  const stateCards: StateCardConfig[] = [
    {
      id: 'whole',
      labelKey: 'states.whole',
      image: '/images/states/whole.svg',
      captionKey: 'states.whole_sub',
    },
    {
      id: 'cut',
      labelKey: 'states.cut',
      image: '/images/states/cut.svg',
      captionKey: 'states.cut_sub',
    },
    {
      id: 'washed',
      labelKey: 'states.washed',
      image: '/images/states/washed.svg',
      captionKey: 'states.washed_sub',
    },
    {
      id: 'damaged',
      labelKey: 'states.damaged',
      image: '/images/states/damaged.svg',
      captionKey: 'states.damaged_sub',
    },
  ]

  const storageCards: StorageCardConfig[] = [
    {
      id: 'shed',
      labelKey: 'storage.shed',
      image: '/images/storage/shed.svg',
      caption: 'storage.shed_sub',
    },
    {
      id: 'cold_room',
      labelKey: 'storage.cold_room',
      image: '/images/storage/cold_room.svg',
      caption: 'storage.cold_room_sub',
    },
    {
      id: 'ice',
      labelKey: 'storage.ice',
      image: '/images/storage/ice.svg',
      caption: 'storage.ice_sub',
    },
  ]

  return (
    <div className="space-y-8">
      {/* 1. Large Illustrated State Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display uppercase text-lg sm:text-xl text-ink tracking-tight">
            {t('steps.step2')}
          </h2>
          <span className="font-mono text-xs font-bold bg-yellow border-2 border-ink px-2 py-0.5">
            {t('actions.crop_condition_badge', 'TAP 2 · CROP CONDITION')}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          {stateCards.map((card) => {
            const isSelected = physicalState === card.id
            return (
              <button
                key={card.id}
                type="button"
                onClick={() => onChangeState(card.id)}
                className={`
                  border-3 border-ink p-3 text-center cursor-pointer select-none
                  transition-all duration-[80ms] flex flex-col items-center justify-between
                  ${
                    isSelected
                      ? 'bg-yellow shadow-[4px_4px_0_var(--ink)] translate-x-[2px] translate-y-[2px] ring-4 ring-ink'
                      : 'bg-paper hover:bg-grey/40 shadow-[6px_6px_0_var(--ink)] hover:-translate-x-[2px] hover:-translate-y-[2px]'
                  }
                `.trim()}
              >
                <div className="w-20 h-20 sm:w-24 sm:h-24 p-1 my-1">
                  <img
                    src={card.image}
                    alt={t(card.labelKey)}
                    className="w-full h-full object-contain"
                  />
                </div>
                <div className="mt-2 w-full">
                  <div className="font-display text-sm sm:text-base text-ink uppercase leading-tight">
                    {t(card.labelKey)}
                  </div>
                  <div className="font-mono text-[11px] text-ink/75 font-semibold mt-0.5">
                    {t(card.captionKey)}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* 2. Sun-and-Moon Timeline Strip */}
      <div className="pt-2">
        <SunMoonStrip value={timeInterval} onChange={onChangeTime} />
      </div>

      {/* 3. Optional Storage Cards with 3 Pictures: Open Shed, Cold Room, Ice */}
      <div className="space-y-3 pt-2 border-t-2 border-ink/20">
        <label className="font-display uppercase text-sm sm:text-base text-ink tracking-wide block">
          {t('storage.title')}
        </label>
        <div className="grid grid-cols-3 gap-3">
          {storageCards.map((scard) => {
            const isSelected = storageMethod === scard.id
            return (
              <button
                key={scard.id}
                type="button"
                onClick={() => onChangeStorage(scard.id)}
                className={`
                  border-3 border-ink p-2 sm:p-3 text-center cursor-pointer select-none
                  transition-all duration-[80ms] flex flex-col items-center justify-between
                  ${
                    isSelected
                      ? 'bg-cyan shadow-[3px_3px_0_var(--ink)] translate-x-[2px] translate-y-[2px] ring-3 ring-ink'
                      : 'bg-paper hover:bg-grey/40 shadow-[4px_4px_0_var(--ink)]'
                  }
                `.trim()}
              >
                <div className="w-14 h-14 sm:w-16 sm:h-16 my-1">
                  <img
                    src={scard.image}
                    alt={t(scard.labelKey)}
                    className="w-full h-full object-contain"
                  />
                </div>
                <div className="mt-1">
                  <div className="font-display text-xs sm:text-sm text-ink uppercase leading-tight">
                    {t(scard.labelKey)}
                  </div>
                  <div className="font-mono text-[10px] text-ink/70">
                    {t(scard.caption)}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Navigation Buttons: Back and Action Button (Min height 64px) */}
      <div className="flex flex-col sm:flex-row gap-4 pt-4">
        <button
          type="button"
          onClick={onBack}
          className="
            min-h-[64px] px-6 border-3 border-ink bg-paper font-display uppercase
            text-base text-ink shadow-[4px_4px_0_var(--ink)] hover:bg-grey/40 cursor-pointer
            sm:w-1/3
          "
        >
          ← {t('actions.back')}
        </button>

        <button
          type="button"
          onClick={onCalculate}
          disabled={isLoading}
          className={`
            min-h-[64px] p-4 font-display uppercase text-lg sm:text-xl
            border-3 border-ink flex items-center justify-center gap-3 transition-all duration-[80ms]
            sm:w-2/3
            ${
              isLoading
                ? 'bg-grey/70 text-ink/70 cursor-not-allowed shadow-[2px_2px_0_var(--ink)] pointer-events-none'
                : 'bg-yellow text-ink shadow-[6px_6px_0_var(--ink)] cursor-pointer hover:bg-yellow/90 hover:-translate-x-[2px] hover:-translate-y-[2px] active:translate-x-[4px] active:translate-y-[4px]'
            }
          `}
        >
          {isLoading ? (
            <span>⚡ {t('actions.analysing', 'ANALYSING…')}</span>
          ) : (
            <>
              <span>✓ {t('actions.see_recommendation')}</span>
              <span className="text-2xl">➔</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}

export default StateScreen
