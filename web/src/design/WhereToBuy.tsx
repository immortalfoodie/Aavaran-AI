import React from 'react'
import { useTranslation } from 'react-i18next'

/**
 * "Where to buy" card: links that open a marketplace search for the recommended packaging.
 *
 * We link to *searches*, not to individual seller pages. Individual listings, prices and minimum
 * order quantities change every week; a search on these sites always returns current sellers.
 *   - IndiaMART: wholesale sellers across India, filterable by city; you ask for a quote
 *   - Amazon.in / Flipkart: small retail packs (25–100 pieces), home delivery
 *   - TradeIndia: manufacturers, bulk orders
 */

export interface BuySource {
  id: 'indiamart' | 'amazon' | 'flipkart' | 'tradeindia'
  name: string
  url: string
}

export function buySources(searchTerm: string, district?: string | null): BuySource[] {
  const q = encodeURIComponent(searchTerm)
  // IndiaMART ranks local sellers higher when the city name is part of the query.
  const qLocal = encodeURIComponent(district ? `${searchTerm} ${district}` : searchTerm)
  return [
    { id: 'indiamart', name: 'IndiaMART', url: `https://dir.indiamart.com/search.mp?ss=${qLocal}` },
    { id: 'amazon', name: 'Amazon.in', url: `https://www.amazon.in/s?k=${q}` },
    { id: 'flipkart', name: 'Flipkart', url: `https://www.flipkart.com/search?q=${q}` },
    { id: 'tradeindia', name: 'TradeIndia', url: `https://www.tradeindia.com/search.html?keyword=${q}` },
  ]
}

/** Marketplace search words for each shop pouch kind (see modes/business/shopPouch.ts). */
export const POUCH_SEARCH_TERMS: Record<string, string> = {
  foil: 'aluminium foil laminated food pouch',
  metal: 'metallised laminated food pouch',
  clear_strong: 'PET LLDPE laminated food pouch',
  clear: 'LDPE food packaging pouch',
  breathable: 'perforated vegetable packaging bag',
}

/** Marketplace search words for each farmer packaging structure (see offline/engine). */
export const FARM_SEARCH_TERMS: Record<string, string> = {
  ventilated_crate: 'plastic vegetable crate',
  mesh_sack: 'leno mesh bag vegetables',
  perforated_pouch: 'perforated vegetable packaging bag',
  barrier_pouch: 'laminated food packaging pouch',
}

interface WhereToBuyProps {
  searchTerm: string
  district?: string | null
  className?: string
}

export const WhereToBuy: React.FC<WhereToBuyProps> = ({ searchTerm, district, className = '' }) => {
  const { t } = useTranslation()
  return (
    <div className={`border-3 border-ink bg-paper p-4 shadow-[4px_4px_0_var(--ink)] space-y-3 ${className}`}>
      <div className="font-display text-lg">🛒 {t('buy.title')}</div>
      <p className="font-body text-sm m-0">
        {t('buy.search_for')} <span className="font-mono font-bold">“{searchTerm}”</span>
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {buySources(searchTerm, district).map((s) => (
          <a
            key={s.id}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="border-3 border-ink bg-cyan/20 px-3 py-2 no-underline text-ink hover:bg-yellow shadow-[3px_3px_0_var(--ink)] block"
          >
            <div className="font-display text-base">{s.name} ↗</div>
            <div className="font-mono text-xs">{t(`buy.src_${s.id}`)}</div>
          </a>
        ))}
      </div>
      <ul className="list-disc pl-6 font-body text-sm space-y-1 m-0">
        <li>{t('buy.tip_local')}</li>
        <li>{t('buy.tip_sample')}</li>
      </ul>
    </div>
  )
}

export default WhereToBuy
