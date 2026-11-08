import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getApiUrl } from '../api/config'
import { saathiLangFromI18n } from '../voice/voiceApi'

interface LowCostOption {
  id: string
  name: string
  how_to: string
  cost_low: number | null
  cost_high: number | null
  cost_basis: string | null
  ambient_days: [number, number] | null
  with_option_days: [number, number] | null
  loss_reduction_pct: [number, number] | null
  source: string | null
  source_url: string | null
}

interface MarketRow {
  market: string
  district: string
  state: string
  date: string
  min_price: number | null
  max_price: number | null
  modal_price: number
}

interface MarketInsight {
  latest: MarketRow | null
  markets: MarketRow[]
  advice: 'sell_now' | 'can_hold' | null
  hold_days: number | null
  source: string
}

/** District label in the picker looks like "Nashik (नाशिक)" — Agmarknet wants "Nashik". */
function districtForAgmarknet(label: string | undefined): string | undefined {
  if (!label) return undefined
  return label.split('(')[0].trim() || undefined
}

const span = (r: [number, number]) => (Math.round(r[0]) === Math.round(r[1]) ? `${Math.round(r[0])}` : `${Math.round(r[0])}–${Math.round(r[1])}`)

const inr = (n: number | null | undefined) => (typeof n === 'number' ? Math.round(n).toLocaleString('en-IN') : '–')

export const InsightsPanel: React.FC<{
  commodityId: string
  physicalState?: string
  shelfLifeDays?: number | null
  district?: string
  showMarket?: boolean
}> = ({ commodityId, physicalState, shelfLifeDays, district, showMarket = true }) => {
  const { t, i18n } = useTranslation()
  const lang = saathiLangFromI18n(i18n.language)
  const [options, setOptions] = useState<LowCostOption[]>([])
  const [market, setMarket] = useState<MarketInsight | null>(null)
  const [marketState, setMarketState] = useState<'idle' | 'loading' | 'unavailable' | 'ready'>(
    showMarket ? 'loading' : 'idle',
  )

  useEffect(() => {
    let alive = true
    const qs = new URLSearchParams({ lang })
    if (physicalState) qs.set('physical_state', physicalState)
    fetch(getApiUrl(`/api/v1/lowcost/${encodeURIComponent(commodityId)}?${qs}`))
      .then((r) => (r.ok ? r.json() : { options: [] }))
      .then((d) => alive && setOptions(d.options || []))
      .catch(() => alive && setOptions([]))
    return () => {
      alive = false
    }
  }, [commodityId, physicalState, lang])

  useEffect(() => {
    if (!showMarket) return
    let alive = true
    const fetchMarket = async (): Promise<MarketInsight | null> => {
      const qs = new URLSearchParams({ commodity_id: commodityId, lang })
      if (typeof shelfLifeDays === 'number') qs.set('shelf_life_days', String(shelfLifeDays))
      const d = districtForAgmarknet(district)
      if (d) qs.set('district', d) // server widens to the state, then all of India, if needed
      try {
        const r = await fetch(getApiUrl(`/api/v1/market/price?${qs}`))
        if (!r.ok) return null
        const body: MarketInsight = await r.json()
        return body.latest ? body : null
      } catch {
        return null
      }
    }
    fetchMarket().then((m) => {
      if (!alive) return
      setMarket(m)
      setMarketState(m ? 'ready' : 'unavailable')
    })
    return () => {
      alive = false
    }
  }, [commodityId, shelfLifeDays, district, lang, showMarket])

  if (options.length === 0 && marketState !== 'ready' && marketState !== 'loading') return null

  return (
    <div className="space-y-5">
      {options.length > 0 && (
        <section className="border-4 border-ink bg-lime p-4 sm:p-5 shadow-[6px_6px_0_var(--ink)] space-y-3">
          <h3 className="font-display uppercase text-lg sm:text-xl m-0">💡 {t('market.lowcost_title')}</h3>
          <ul className="space-y-3 list-none p-0 m-0">
            {options.slice(0, 4).map((o) => (
              <li key={o.id} className="border-3 border-ink bg-paper p-3 space-y-1">
                <div className="font-display text-base">{o.name}</div>
                {o.how_to && <p className="font-body text-sm m-0">{o.how_to}</p>}
                <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs font-bold">
                  {o.with_option_days && (
                    <span>
                      ✅ {t('market.lowcost_days', { days: span(o.with_option_days) })}
                      {o.ambient_days && (
                        <span className="font-normal">
                          {' '}
                          ({t('market.lowcost_instead', { days: span(o.ambient_days) })})
                        </span>
                      )}
                    </span>
                  )}
                  {typeof o.cost_low === 'number' && typeof o.cost_high === 'number' && (
                    <span>
                      💰{' '}
                      {o.cost_high === 0
                        ? t('market.lowcost_free')
                        : o.cost_low === o.cost_high
                        ? `₹${inr(o.cost_low)}`
                        : t('market.lowcost_cost', { low: inr(o.cost_low), high: inr(o.cost_high) })}
                    </span>
                  )}
                </div>
                {o.source && (
                  <div className="font-mono text-[10px] text-ink/70">
                    {t('market.lowcost_source')}:{' '}
                    {o.source_url ? (
                      <a href={o.source_url} target="_blank" rel="noreferrer" className="underline">
                        {o.source}
                      </a>
                    ) : (
                      o.source
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {showMarket && marketState === 'loading' && (
        <p className="font-mono text-xs font-bold">{t('market.loading')}</p>
      )}

      {showMarket && marketState === 'ready' && market?.latest && (
        <section className="border-4 border-ink bg-paper p-4 sm:p-5 shadow-[6px_6px_0_var(--ink)] space-y-3">
          <h3 className="font-display uppercase text-lg sm:text-xl m-0">📈 {t('market.title')}</h3>
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-mono text-xs font-bold">
              {t('market.today', { market: market.latest.market })} · {market.latest.date}
            </span>
            <span className="font-display text-3xl">₹{inr(market.latest.modal_price)}</span>
            <span className="font-mono text-xs">{t('market.per_q')}</span>
          </div>
          {market.latest.min_price !== null && market.latest.max_price !== null && (
            <div className="font-mono text-xs">
              {t('market.range', { min: inr(market.latest.min_price), max: inr(market.latest.max_price) })}
            </div>
          )}
          {market.advice && (
            <p
              className={`font-body text-base m-0 border-3 border-ink px-3 py-2 ${
                market.advice === 'sell_now' ? 'bg-coral' : 'bg-yellow'
              }`}
            >
              {market.advice === 'sell_now'
                ? t('market.sell_now')
                : t('market.can_hold', { days: market.hold_days ?? 0 })}
            </p>
          )}
          {market.markets.length > 1 && (
            <table className="w-full font-mono text-xs border-collapse">
              <tbody>
                {market.markets.slice(0, 5).map((m, i) => (
                  <tr key={`${m.market}-${m.date}-${i}`} className="border-t border-ink/30">
                    <td className="py-1 pr-2">{m.market}</td>
                    <td className="py-1 pr-2 text-ink/70">{m.date}</td>
                    <td className="py-1 text-right font-bold">₹{inr(m.modal_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="font-mono text-[10px] text-ink/70">{t('market.source_note')}</div>
        </section>
      )}
    </div>
  )
}

export default InsightsPanel
