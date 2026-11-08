import React from 'react'
import { useTranslation } from 'react-i18next'

interface DistrictPickerModalProps {
  isOpen: boolean
  currentDistrict: string
  onClose: () => void
  onSelectDistrict: (district: string) => void
}

interface DistrictListing {
  id: string
  name: string
  state: string
  marketYard: string
  stallCount: number
  contact: string
}

export const DISTRICTS_LIST: DistrictListing[] = [
  {
    id: 'Nashik',
    name: 'Nashik (नाशिक)',
    state: 'Maharashtra',
    marketYard: 'APMC Market Yard, Dindori Road, Panchavati',
    stallCount: 14,
    contact: '0253-2512800 / Toll-free Mandi Sahayata',
  },
  {
    id: 'Pune',
    name: 'Pune (पुणे)',
    state: 'Maharashtra',
    marketYard: 'Shri Chhatrapati Shivaji Market Yard, Gultekdi',
    stallCount: 22,
    contact: '020-24264500 / Gate 4 Packaging Depot',
  },
  {
    id: 'Ahmednagar',
    name: 'Ahmednagar (अहमदनगर)',
    state: 'Maharashtra',
    marketYard: 'Krushi Utpanna Bazar Samiti, Station Road',
    stallCount: 9,
    contact: '0241-2451200 / Section 8 Shed',
  },
  {
    id: 'Nagpur',
    name: 'Nagpur (नागपूर)',
    state: 'Maharashtra',
    marketYard: 'APMC Kalamna Market Yard, Kamptee Road',
    stallCount: 18,
    contact: '0712-2681400 / Orange & Veg Packaging Wing',
  },
  {
    id: 'Indore',
    name: 'Indore (इंदौर)',
    state: 'Madhya Pradesh',
    marketYard: 'Devi Ahilya Bai Holkar Mandi, Choithram Square',
    stallCount: 16,
    contact: '0731-2401234 / Mandi Bhavan Ground Floor',
  },
  {
    id: 'Agra',
    name: 'Agra (आगरा)',
    state: 'Uttar Pradesh',
    marketYard: 'Khandari Potato Mandi & Cold Storage Depot',
    stallCount: 12,
    contact: '0562-2521100 / Cold Chain Packaging Hub',
  },
  {
    id: 'Kolar',
    name: 'Kolar (कोलार)',
    state: 'Karnataka',
    marketYard: 'APMC Tomato Market Yard, Bangarpet Rd',
    stallCount: 20,
    contact: '08152-222300 / Crate & Liner Association',
  },
]

export const DistrictPickerModal: React.FC<DistrictPickerModalProps> = ({
  isOpen,
  currentDistrict,
  onClose,
  onSelectDistrict,
}) => {
  const { t } = useTranslation()

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-ink/75 z-50 flex items-center justify-center p-4 overflow-y-auto"
    >
      <div className="bg-paper border-6 border-ink p-6 max-w-lg w-full shadow-[10px_10px_0_var(--ink)] space-y-4 my-8">
        <div className="flex items-center justify-between border-b-3 border-ink pb-3">
          <div className="flex items-center gap-2">
            <span className="text-2xl">📍</span>
            <h3 className="font-display uppercase text-lg sm:text-xl text-ink">
              {t('actions.where_to_buy')}
            </h3>
          </div>
          <span className="font-mono text-xs font-bold bg-yellow border-2 border-ink px-2 py-0.5">
            APMC DIRECTORY
          </span>
        </div>

        <p className="font-body text-sm text-ink/80">
          Showing certified food-grade packaging counters and authorized bag suppliers operating inside or near your local APMC Mandi.
        </p>

        <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
          {DISTRICTS_LIST.map((dist) => {
            const isSelected = dist.id.toLowerCase() === currentDistrict.toLowerCase()
            return (
              <div
                key={dist.id}
                onClick={() => {
                  onSelectDistrict(dist.id)
                  onClose()
                }}
                className={`
                  p-3 border-3 border-ink cursor-pointer transition-all select-none
                  ${
                    isSelected
                      ? 'bg-yellow shadow-[4px_4px_0_var(--ink)] translate-x-[2px]'
                      : 'bg-paper hover:bg-grey/40 shadow-[4px_4px_0_var(--ink)]'
                  }
                `.trim()}
              >
                <div className="flex items-center justify-between">
                  <h4 className="font-display text-base text-ink uppercase">
                    {dist.name}
                  </h4>
                  {isSelected && (
                    <span className="font-mono text-xs font-bold bg-ink text-paper px-2 py-0.5">
                      ✓ SELECTED
                    </span>
                  )}
                </div>
                <div className="font-body text-xs text-ink/85 mt-1">
                  🏛️ {dist.marketYard}
                </div>
                <div className="flex items-center justify-between font-mono text-[11px] text-ink/75 mt-2 pt-2 border-t border-ink/20">
                  <span>📦 {dist.stallCount} verified suppliers</span>
                  <span>📞 {dist.contact}</span>
                </div>
              </div>
            )
          })}
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[48px] px-6 font-display uppercase border-3 border-ink bg-ink text-paper hover:bg-ink/80 cursor-pointer shadow-[4px_4px_0_var(--ink)]"
          >
            {t('actions.close')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default DistrictPickerModal
