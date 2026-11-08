import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { CropId, CropInfo } from '../types'
import { VoiceInputButton } from '../components/VoiceInputButton'
import { PhotoClassifierModal } from '../components/PhotoClassifierModal'

interface WhatScreenProps {
  selectedCrop: CropId | null
  onSelectCrop: (crop: CropId) => void
  /** Opens the Aavaran Saathi voice conversation (Gnani Prisma + Timbre). */
  onOpenSaathi?: () => void
  /** The parent already shows a large Saathi button; render only the photo option here. */
  hideVoiceButton?: boolean
}

const CROPS: CropInfo[] = [
  {
    id: 'veg.potato.solanum_tuberosum',
    translationKey: 'crops.potato',
    photo: '/images/crops/potato.jpg',
    hindiName: 'आलू',
    marathiName: 'बटाटा',
    englishName: 'Potato',
  },
  {
    id: 'veg.tomato.solanum_lycopersicum',
    translationKey: 'crops.tomato',
    photo: '/images/crops/tomato.jpg',
    hindiName: 'टमाटर',
    marathiName: 'टोमॅटो',
    englishName: 'Tomato',
  },
  {
    id: 'veg.onion.allium_cepa',
    translationKey: 'crops.onion',
    photo: '/images/crops/onion.jpg',
    hindiName: 'प्याज़',
    marathiName: 'कांदा',
    englishName: 'Onion',
  },
  {
    id: 'fruit.banana.musa_acuminata',
    translationKey: 'crops.banana',
    photo: '/images/crops/banana.jpg',
    hindiName: 'केला',
    marathiName: 'केळी',
    englishName: 'Banana',
  },
  {
    id: 'fruit.mango.mangifera_indica',
    translationKey: 'crops.mango',
    photo: '/images/crops/mango.jpg',
    hindiName: 'आम',
    marathiName: 'आंबा',
    englishName: 'Mango',
  },
  {
    id: 'veg.okra.abelmoschus_esculentus',
    translationKey: 'crops.okra',
    photo: '/images/crops/okra.jpg',
    hindiName: 'भिंडी',
    marathiName: 'भेंडी',
    englishName: 'Okra',
  },
  {
    id: 'veg.spinach.spinacia_oleracea',
    translationKey: 'crops.spinach',
    photo: '/images/crops/spinach.jpg',
    hindiName: 'पालक',
    marathiName: 'पालक',
    englishName: 'Spinach',
  },
  {
    id: 'veg.green_chilli.capsicum_annuum',
    translationKey: 'crops.green_chilli',
    photo: '/images/crops/green_chilli.jpg',
    hindiName: 'हरी मिर्च',
    marathiName: 'हिरवी मिरची',
    englishName: 'Green Chilli',
  },
  {
    id: 'fruit.guava.psidium_guajava',
    translationKey: 'crops.guava',
    photo: '/images/crops/guava.jpg',
    hindiName: 'अमरूद',
    marathiName: 'पेरू',
    englishName: 'Guava',
  },
  {
    id: 'veg.cauliflower.brassica_oleracea_botrytis',
    translationKey: 'crops.cauliflower',
    photo: '/images/crops/cauliflower.jpg',
    hindiName: 'फूलगोभी',
    marathiName: 'फुलकोबी',
    englishName: 'Cauliflower',
  },
  {
    id: 'veg.cabbage.brassica_oleracea_capitata',
    translationKey: 'crops.cabbage',
    photo: '/images/crops/cabbage.jpg',
    hindiName: 'पत्ता गोभी',
    marathiName: 'कोबी',
    englishName: 'Cabbage',
  },
  {
    id: 'fruit.grape.vitis_vinifera',
    translationKey: 'crops.grape',
    photo: '/images/crops/grape.jpg',
    hindiName: 'अंगूर',
    marathiName: 'द्राक्षे',
    englishName: 'Grapes',
  },
  {
    id: 'fruit.pomegranate.punica_granatum',
    translationKey: 'crops.pomegranate',
    photo: '/images/crops/pomegranate.jpg',
    hindiName: 'अनार',
    marathiName: 'डाळिंब',
    englishName: 'Pomegranate',
  },
  {
    id: 'veg.brinjal.solanum_melongena',
    translationKey: 'crops.brinjal',
    photo: '/images/crops/brinjal.jpg',
    hindiName: 'बैंगन',
    marathiName: 'वांगी',
    englishName: 'Brinjal',
  },
]

export const WhatScreen: React.FC<WhatScreenProps> = ({
  selectedCrop,
  onSelectCrop,
  onOpenSaathi,
  hideVoiceButton = false,
}) => {
  const { t, i18n } = useTranslation()
  const [isCameraOpen, setIsCameraOpen] = useState<boolean>(false)
  const [searchQuery, setSearchQuery] = useState<string>('')

  const getDisplayName = (crop: CropInfo): string => {
    const lang = i18n.language
    if (lang === 'mr') return crop.marathiName
    if (lang === 'hi') return crop.hindiName
    return crop.englishName
  }

  const getSecondaryName = (crop: CropInfo): string => {
    const lang = i18n.language
    if (lang === 'mr') return `${crop.hindiName} · ${crop.englishName}`
    if (lang === 'hi') return `${crop.marathiName} · ${crop.englishName}`
    return `${crop.hindiName} · ${crop.marathiName}`
  }

  const filteredCrops = CROPS.filter((c) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      c.englishName.toLowerCase().includes(q) ||
      c.hindiName.includes(q) ||
      c.marathiName.includes(q)
    )
  })

  return (
    <div className="space-y-6">
      {/* Top Action Buttons: Photo Camera & Voice Mic (Beside each other) */}
      <div className={`grid grid-cols-1 gap-4 ${hideVoiceButton ? '' : 'sm:grid-cols-2'}`}>
        <button
          type="button"
          onClick={() => setIsCameraOpen(true)}
          className="
            min-h-[64px] p-4 bg-yellow text-ink border-3 border-ink font-display
            uppercase text-base sm:text-lg shadow-[6px_6px_0_var(--ink)] cursor-pointer
            hover:bg-yellow/90 hover:-translate-x-[2px] hover:-translate-y-[2px]
            active:translate-x-[4px] active:translate-y-[4px]
            flex items-center justify-center gap-3 transition-all duration-[80ms]
          "
        >
          <span className="text-3xl" aria-hidden="true">
            📸
          </span>
          <span className="tracking-wide">{t('actions.take_photo')}</span>
        </button>

        {hideVoiceButton ? null : onOpenSaathi ? (
          <button
            type="button"
            onClick={onOpenSaathi}
            className="
              min-h-[64px] p-4 bg-coral text-ink border-3 border-ink font-display
              uppercase text-base sm:text-lg shadow-[6px_6px_0_var(--ink)] cursor-pointer
              hover:-translate-x-[2px] hover:-translate-y-[2px]
              active:translate-x-[4px] active:translate-y-[4px]
              flex items-center justify-center gap-3 transition-all duration-[80ms]
            "
          >
            <span className="text-3xl" aria-hidden="true">
              🎙
            </span>
            <span className="flex flex-col items-start leading-tight">
              <span className="tracking-wide">{t('saathi.open')}</span>
              <span className="font-mono normal-case text-xs font-bold">{t('saathi.open_sub')}</span>
            </span>
          </button>
        ) : (
          <VoiceInputButton onDetected={onSelectCrop} />
        )}
      </div>

      {/* Primary Section: Visual Crop Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display uppercase text-lg sm:text-xl text-ink tracking-tight">
            {t('steps.step1')}
          </h2>
          <span className="font-mono text-xs font-bold bg-grey border-2 border-ink px-2 py-0.5">
            TAP TO SELECT (TAP 1)
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {filteredCrops.map((crop) => {
            const isSelected = selectedCrop === crop.id
            return (
              <button
                key={crop.id}
                type="button"
                onClick={() => onSelectCrop(crop.id)}
                className={`
                  border-3 border-ink bg-paper p-2 text-left cursor-pointer
                  select-none transition-all duration-[80ms] flex flex-col justify-between
                  ${
                    isSelected
                      ? 'bg-yellow shadow-[4px_4px_0_var(--ink)] translate-x-[2px] translate-y-[2px] ring-4 ring-ink'
                      : 'shadow-[6px_6px_0_var(--ink)] hover:bg-yellow/10 hover:-translate-x-[2px] hover:-translate-y-[2px]'
                  }
                `.trim()}
              >
                {/* Large Crop Photograph */}
                <div className="aspect-square w-full overflow-hidden border-2 border-ink bg-grey/30 mb-2">
                  <img
                    src={crop.photo}
                    alt={getDisplayName(crop)}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </div>

                {/* Local Language Crop Name */}
                <div className="px-1 pb-1">
                  <div className="font-display text-lg sm:text-xl text-ink uppercase tracking-tight leading-tight">
                    {getDisplayName(crop)}
                  </div>
                  <div className="font-mono text-xs text-ink/70 font-semibold truncate mt-0.5">
                    {getSecondaryName(crop)}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Secondary Search Box (Placed bottom, not first) */}
      <div className="pt-2 border-t-2 border-ink/20">
        <label className="font-mono text-xs uppercase font-bold text-ink/75 block mb-1">
          🔍 {t('actions.search_placeholder')}
        </label>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={t('actions.search_placeholder')}
          className="w-full min-h-[48px] p-3 border-3 border-ink font-body text-base bg-paper text-ink focus:outline-none focus:bg-yellow/20"
        />
      </div>

      {/* Camera Capture Modal */}
      <PhotoClassifierModal
        isOpen={isCameraOpen}
        onClose={() => setIsCameraOpen(false)}
        onDetected={onSelectCrop}
      />
    </div>
  )
}

export default WhatScreen
