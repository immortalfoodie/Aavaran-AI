import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getApiUrl } from '../../api/config'
import { AudioSpeakerButton } from '../kisan/components/AudioSpeakerButton'
import type { SaathiTurn } from '../../voice/voiceApi'
import { pouchKind, scaledPackCost, sellerSpec } from './shopPouch'

/**
 * The shop owner's view of Business mode: 4 taps (or one sentence to Saathi) in,
 * one plain-language answer out — which pouch to buy, what it costs, how long the
 * food stays good, and the exact words to say to the packaging seller.
 */

type Storage = 'shop' | 'fridge'

const PRODUCTS: Array<{ id: string; key: string; emoji: string; fridge?: boolean }> = [
  { id: 'processed.besan_namkeen.fried_snack', key: 'namkeen', emoji: '🥨' },
  { id: 'cereal.wheat_atta.triticum_aestivum', key: 'atta', emoji: '🌾' },
  { id: 'pulse.toor_dal.cajanus_cajan', key: 'dal', emoji: '🫘' },
  { id: 'spice.turmeric_powder.curcuma_longa', key: 'haldi', emoji: '🟡' },
  { id: 'dairy.milk_powder.whole', key: 'milk_powder', emoji: '🥛' },
  { id: 'dairy.paneer.cottage_cheese', key: 'paneer', emoji: '🧀', fridge: true },
]
const SIZES = [100, 250, 500, 1000]
const DURATIONS = [7, 30, 90, 180]

interface Candidate {
  name?: string | null
  layer_stack: string[]
  cost_per_pack?: number | null
}

interface ShopAnswer {
  size: number
  verdict: string
  days: number | null
  candidates: Candidate[]
  lightSensitive: boolean
}

function buildInput(productId: string, sizeG: number, days: number, storage: Storage) {
  const input: Record<string, unknown> = {
    commodity_id: productId,
    pack_size_g: sizeG,
    target_shelf_life_days: days,
    pack_geometry: { product_mass_kg: sizeG / 1000 },
  }
  // Same mapping Saathi uses (api/voice/dialogue.py STORAGE_ENV)
  input.environment =
    storage === 'fridge'
      ? { storage_type: 'refrigerated', temperature_c: 4.0 }
      : { storage_type: 'ambient', temperature_c: 30.0 }
  return input
}

const inr = (n: number) => (n >= 100 ? Math.round(n).toLocaleString('en-IN') : n.toFixed(2).replace(/\.?0+$/, ''))

const Chip: React.FC<{ active: boolean; onClick: () => void; children: React.ReactNode }> = ({
  active,
  onClick,
  children,
}) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={active}
    className={`min-h-[52px] px-3 border-3 border-ink font-display text-base cursor-pointer transition-all duration-[80ms] ${
      active ? 'bg-ink text-paper shadow-none' : 'bg-paper text-ink shadow-[3px_3px_0_var(--ink)] hover:bg-grey/30'
    }`}
  >
    {children}
  </button>
)

export const ShopSimple: React.FC<{ voiceTurn?: SaathiTurn | null; onOpenVoice: () => void }> = ({
  voiceTurn,
  onOpenVoice,
}) => {
  const { t, i18n } = useTranslation()
  const [product, setProduct] = useState<string | null>(null)
  const [size, setSize] = useState<number>(250)
  const [days, setDays] = useState<number>(90)
  const [storage, setStorage] = useState<Storage>('shop')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [answer, setAnswer] = useState<ShopAnswer | null>(null)
  const [voiceSaid, setVoiceSaid] = useState<string | null>(null)

  const run = async (input: Record<string, unknown>) => {
    setLoading(true)
    setError(false)
    try {
      const locale = i18n.language === 'mr' ? 'mr-IN' : i18n.language === 'en' ? 'en-IN' : 'hi-IN'
      const r = await fetch(getApiUrl('/api/v1/recommend'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'business', input, locale }),
      })
      if (!r.ok) throw new Error(String(r.status))
      const sealed = await r.json()
      setAnswer({
        size: Number(input.pack_size_g) || size,
        verdict: sealed.verdict,
        days: typeof sealed.shelf_life?.days_p50 === 'number' ? Math.floor(sealed.shelf_life.days_p50) : null,
        candidates: (sealed.candidates || []).slice(0, 2),
        lightSensitive: sealed.safety?.rule_id === 'SAFE-LIGHT-01',
      })
    } catch {
      setError(true)
      setAnswer(null)
    } finally {
      setLoading(false)
    }
  }

  // A finished Saathi conversation fills the same 4 answers and shows the same result.
  useEffect(() => {
    if (!voiceTurn) return
    const s = voiceTurn.slots
    if (s.commodity_id) setProduct(s.commodity_id)
    if (s.pack_size_g) setSize(s.pack_size_g)
    if (s.target_days) setDays(s.target_days)
    const st: Storage = s.storage === 'cold_room' || s.storage === 'ice' ? 'fridge' : 'shop'
    setStorage(st)
    setVoiceSaid(voiceTurn.reply_text)
    if (voiceTurn.recommend_input) run(voiceTurn.recommend_input)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceTurn])

  const pick = (id: string) => {
    setProduct(id)
    setAnswer(null)
    setVoiceSaid(null)
    const p = PRODUCTS.find((x) => x.id === id)
    setStorage(p?.fridge ? 'fridge' : 'shop')
  }

  const productLabel = product ? t(`shop.p_${PRODUCTS.find((p) => p.id === product)?.key ?? 'namkeen'}`) : ''
  const refused = answer?.verdict === 'NOT_A_PACKAGING_PROBLEM'
  const best = answer?.candidates[0]
  const other = answer?.candidates[1]
  const costFor = (c?: Candidate) =>
    c && typeof c.cost_per_pack === 'number' ? scaledPackCost(c.cost_per_pack, answer?.size ?? size) : null
  const bestCost = costFor(best)
  const otherCost = costFor(other)
  const short = answer?.days !== null && answer?.days !== undefined && answer.days < days

  const speech = (() => {
    if (!answer) return ''
    if (refused) return `${t('shop.refusal_title')}. ${t('shop.refusal_body')}`
    if (!best) return ''
    const kind = pouchKind(best.layer_stack)
    const parts = [`${t('shop.best')}: ${t(`shop.kind_${kind}`)}.`]
    if (bestCost !== null) parts.push(t('shop.cost_each', { cost: inr(bestCost) }) + '.')
    if (answer.days !== null) parts.push(t('shop.lasts', { days: answer.days }) + '.')
    return parts.join(' ')
  })()

  return (
    <div className="space-y-5">
      {/* Header + voice */}
      <section className="border-4 border-ink bg-cyan p-5 sm:p-6 shadow-[6px_6px_0_var(--ink)] space-y-4">
        <div>
          <h2 className="font-display text-2xl sm:text-3xl tracking-tight text-ink m-0">{t('nav.shop_title')}</h2>
          <p className="font-body text-base text-ink mt-1 mb-0">{t('nav.shop_sub')}</p>
        </div>
        <button
          type="button"
          onClick={onOpenVoice}
          className="w-full min-h-[72px] border-4 border-ink bg-coral font-display text-lg sm:text-xl cursor-pointer shadow-[6px_6px_0_var(--ink)] hover:-translate-x-[2px] hover:-translate-y-[2px] flex items-center justify-center gap-3"
        >
          <span className="text-3xl" aria-hidden="true">🎙</span>
          <span>{t('saathi.open')}</span>
        </button>
      </section>

      <h3 className="font-display text-base sm:text-lg text-ink/80 m-0">{t('shop.or_tap')} ↓</h3>

      {/* Q1: product */}
      <section className="space-y-2">
        <div className="font-display text-lg">1. {t('shop.q_what')}</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {PRODUCTS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => pick(p.id)}
              aria-pressed={product === p.id}
              className={`min-h-[72px] border-3 border-ink px-3 py-2 font-display text-base sm:text-lg cursor-pointer flex items-center gap-3 text-left ${
                product === p.id ? 'bg-yellow shadow-none translate-x-[2px] translate-y-[2px]' : 'bg-paper shadow-[4px_4px_0_var(--ink)]'
              }`}
            >
              <span className="text-3xl" aria-hidden="true">{p.emoji}</span>
              <span>{t(`shop.p_${p.key}`)}</span>
            </button>
          ))}
        </div>
      </section>

      {product && (
        <>
          {/* Q2: size */}
          <section className="space-y-2">
            <div className="font-display text-lg">2. {t('shop.q_size')}</div>
            <div className="flex flex-wrap gap-2">
              {SIZES.map((g) => (
                <Chip key={g} active={size === g} onClick={() => setSize(g)}>
                  {g >= 1000 ? `${g / 1000} kg` : `${g} g`}
                </Chip>
              ))}
            </div>
          </section>

          {/* Q3: how long */}
          <section className="space-y-2">
            <div className="font-display text-lg">3. {t('shop.q_days')}</div>
            <div className="flex flex-wrap gap-2">
              {DURATIONS.map((d) => (
                <Chip key={d} active={days === d} onClick={() => setDays(d)}>
                  {t(`shop.d_${d}`)}
                </Chip>
              ))}
            </div>
          </section>

          {/* Q4: where kept */}
          <section className="space-y-2">
            <div className="font-display text-lg">4. {t('shop.q_where')}</div>
            <div className="flex flex-wrap gap-2">
              <Chip active={storage === 'shop'} onClick={() => setStorage('shop')}>
                🏪 {t('shop.where_shop')}
              </Chip>
              <Chip active={storage === 'fridge'} onClick={() => setStorage('fridge')}>
                🧊 {t('shop.where_fridge')}
              </Chip>
            </div>
          </section>

          <button
            type="button"
            onClick={() => {
              setVoiceSaid(null)
              run(buildInput(product, size, days, storage))
            }}
            disabled={loading}
            className="w-full min-h-[64px] border-4 border-ink bg-lime font-display text-lg sm:text-xl cursor-pointer shadow-[6px_6px_0_var(--ink)] active:translate-x-[3px] active:translate-y-[3px] disabled:opacity-60"
          >
            {loading ? t('shop.loading') : `✅ ${t('shop.go')}`}
          </button>
        </>
      )}

      {error && (
        <p className="border-3 border-ink bg-coral px-3 py-2 font-body m-0" role="alert">
          {t('shop.error')}
        </p>
      )}

      {/* Answer */}
      {answer && (
        <section className="space-y-4" aria-live="polite">
          {voiceSaid && (
            <div className="border-3 border-ink bg-paper px-3 py-2 font-body text-sm">
              <span className="font-mono text-[11px] font-bold">🎙 {t('saathi.saathi')}: </span>
              {voiceSaid}
            </div>
          )}

          {refused ? (
            <div className="border-4 border-ink bg-coral p-5 shadow-[6px_6px_0_var(--ink)] space-y-2" role="alert">
              <div className="font-display text-xl sm:text-2xl">⚠ {t('shop.refusal_title')}</div>
              <p className="font-body text-base m-0">{t('shop.refusal_body')}</p>
            </div>
          ) : best ? (
            <>
              <div className="border-4 border-ink bg-lime p-5 shadow-[6px_6px_0_var(--ink)] space-y-3">
                <div className="font-mono text-xs font-bold">
                  {productLabel} · {size >= 1000 ? `${size / 1000} kg` : `${size} g`}
                </div>
                <div className="font-display text-xl sm:text-2xl leading-tight">
                  ✅ {t('shop.best')}: {t(`shop.kind_${pouchKind(best.layer_stack)}`)}
                </div>
                <p className="font-body text-sm m-0">{t(`shop.kind_${pouchKind(best.layer_stack)}_d`)}</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {bestCost !== null && (
                    <div className="border-3 border-ink bg-paper p-3">
                      <div className="font-display text-2xl">₹{inr(bestCost)}</div>
                      <div className="font-mono text-xs">{t('shop.per_packet')}</div>
                    </div>
                  )}
                  {bestCost !== null && (
                    <div className="border-3 border-ink bg-paper p-3">
                      <div className="font-display text-2xl">₹{inr(bestCost * 100)}</div>
                      <div className="font-mono text-xs">{t('shop.per_100')}</div>
                    </div>
                  )}
                  {answer.days !== null && (
                    <div className="border-3 border-ink bg-paper p-3">
                      <div className="font-display text-2xl">
                        {answer.days} {t('saathi.days')}
                      </div>
                      <div className="font-mono text-xs">{t('shop.stays_good')}</div>
                    </div>
                  )}
                </div>
                {short && (
                  <p className="border-3 border-ink bg-yellow px-3 py-2 font-body text-sm m-0">
                    ⚠ {t('shop.short', { target: days })}
                  </p>
                )}
                <div className="border-3 border-dashed border-ink bg-paper px-3 py-2">
                  <div className="font-mono text-xs font-bold">🗣 {t('shop.ask_seller')}</div>
                  <div className="font-display text-base">“{sellerSpec(best.name, best.layer_stack)}”</div>
                </div>
              </div>

              {other && (
                <div className="border-3 border-ink bg-paper p-4 shadow-[4px_4px_0_var(--ink)] space-y-1">
                  <div className="font-mono text-xs font-bold">{t('shop.option2')}</div>
                  <div className="font-display text-lg">{t(`shop.kind_${pouchKind(other.layer_stack)}`)}</div>
                  <div className="font-body text-sm">
                    {otherCost !== null && <>₹{inr(otherCost)} {t('shop.per_packet')} · </>}
                    “{sellerSpec(other.name, other.layer_stack)}”
                  </div>
                </div>
              )}

              <div className="border-3 border-ink bg-paper p-4 space-y-1">
                <div className="font-display text-lg">💡 {t('shop.tips')}</div>
                <ul className="list-disc pl-6 font-body text-base space-y-1 m-0">
                  <li>{t('shop.tip_seal')}</li>
                  <li>{answer.lightSensitive ? t('shop.tip_sun') : t('shop.tip_dry')}</li>
                  {storage === 'fridge' && <li>{t('shop.tip_fridge')}</li>}
                  <li>{t('shop.tip_fifo')}</li>
                </ul>
              </div>
            </>
          ) : null}

          {speech && <AudioSpeakerButton textToSpeak={speech} className="w-full" />}
        </section>
      )}
    </div>
  )
}

export default ShopSimple
