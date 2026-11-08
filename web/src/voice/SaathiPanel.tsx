import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useWavRecorder, MAX_RECORD_SECONDS, HANDS_FREE_DEFAULTS } from './recorder'
import {
  SAATHI_LANGS,
  VoiceApiError,
  browserRecognitionAvailable,
  playBase64Mp3,
  recognizeWithBrowser,
  sendAudioTurn,
  sendTextTurn,
  speakWithBrowser,
  startSaathi,
  stopAllPlayback,
  useVoiceStatus,
  getVoiceStatus,
  type VoiceStatus,
  uiLangFromSaathi,
  type SaathiLang,
  type SaathiMode,
  type SaathiSlots,
  type SaathiTurn,
} from './voiceApi'
import { commodityLabel } from './labels'
import { setUiLanguage } from '../i18n'

interface ChatLine {
  who: 'user' | 'saathi'
  text: string
}

export interface SaathiPanelProps {
  mode: SaathiMode
  initialLang: SaathiLang
  onClose: () => void
  /** Called when the user taps "See full result" after Saathi has an answer. */
  onResult: (turn: SaathiTurn) => void
}

export const SaathiPanel: React.FC<SaathiPanelProps> = ({ mode, initialLang, onClose, onResult }) => {
  const { t } = useTranslation()
  const firstStatus = useVoiceStatus()
  const [retried, setRetried] = useState<VoiceStatus | null>(null)
  const status = retried ?? firstStatus
  const unreachable = status !== null && !status.reachable
  const gnani = !!status?.gnani_enabled

  const [lang, setLang] = useState<SaathiLang>(initialLang)
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [sessionMode, setSessionMode] = useState<SaathiMode>(mode)
  const [lines, setLines] = useState<ChatLine[]>([])
  const [slots, setSlots] = useState<SaathiSlots>({})
  const [last, setLast] = useState<SaathiTurn | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [typed, setTyped] = useState('')
  const [browserListening, setBrowserListening] = useState(false)
  const [handsFree, setHandsFree] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)
  // Hands-free loop: after Saathi finishes speaking a question, start listening again.
  const listenAgainRef = useRef<() => void>(() => undefined)
  const handsFreeRef = useRef(false)
  useEffect(() => {
    handsFreeRef.current = handsFree
  }, [handsFree])

  const speakTurn = useCallback(
    (turn: SaathiTurn) => {
      const handle = turn.reply_audio_b64
        ? playBase64Mp3(turn.reply_audio_b64)
        : speakWithBrowser(turn.reply_text, turn.lang || lang)
      handle.done.then(() => {
        if (handsFreeRef.current && turn.status === 'asking') listenAgainRef.current()
      })
    },
    [lang],
  )

  const applyTurn = useCallback(
    (turn: SaathiTurn, userText?: string) => {
      setSessionId(turn.session_id)
      setSessionMode(turn.mode)
      setSlots(turn.slots || {})
      setLast(turn)
      setLines((prev) => [
        ...prev,
        ...(userText !== undefined && userText !== '' ? [{ who: 'user' as const, text: userText }] : []),
        { who: 'saathi' as const, text: turn.reply_text },
      ])
      speakTurn(turn)
    },
    [speakTurn],
  )

  const begin = useCallback(
    async (l: SaathiLang) => {
      stopAllPlayback()
      setLines([])
      setSlots({})
      setLast(null)
      setSessionId(undefined)
      setSessionMode(mode)
      setError(null)
      setBusy(true)
      try {
        const turn = await startSaathi(mode, l, gnani)
        applyTurn(turn)
      } catch {
        setError(t('saathi.server_down'))
      } finally {
        setBusy(false)
      }
    },
    [mode, gnani, applyTurn, t],
  )

  // Open the session once voice status is known (so we know whether to request Timbre audio).
  useEffect(() => {
    if (status !== null && status.reachable) begin(lang)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status === null, status?.reachable])

  const retryConnection = async () => {
    setError(null)
    setBusy(true)
    const s = await getVoiceStatus()
    setBusy(false)
    setRetried(s)
    if (!s.reachable) setError(t('saathi.server_down'))
  }

  useEffect(() => () => stopAllPlayback(), [])

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [lines, busy])

  const submitText = useCallback(
    async (text: string) => {
      const clean = text.trim()
      if (!clean) return
      setBusy(true)
      setError(null)
      try {
        const turn = await sendTextTurn(clean, { sessionId, mode: sessionMode, lang, speak: gnani })
        applyTurn(turn, clean)
      } catch {
        setError(t('saathi.error'))
      } finally {
        setBusy(false)
      }
    },
    [sessionId, sessionMode, lang, gnani, applyTurn, t],
  )

  const onWav = useCallback(
    async (wav: Blob) => {
      setBusy(true)
      setError(null)
      try {
        const turn = await sendAudioTurn(wav, { sessionId, mode: sessionMode, lang })
        applyTurn(turn, turn.transcript || '…')
      } catch (e) {
        setError(e instanceof VoiceApiError && e.message ? e.message : t('saathi.error'))
      } finally {
        setBusy(false)
      }
    },
    [sessionId, sessionMode, lang, applyTurn, t],
  )

  const recorder = useWavRecorder(onWav)
  const canHandsFree = gnani && recorder.state !== 'unsupported'
  useEffect(() => {
    listenAgainRef.current = () => {
      if (recorder.state !== 'recording') recorder.start(HANDS_FREE_DEFAULTS)
    }
  }, [recorder])

  const onMic = async () => {
    stopAllPlayback()
    if (gnani && recorder.state !== 'unsupported') {
      if (recorder.state === 'recording') recorder.stop()
      else await recorder.start(handsFree ? HANDS_FREE_DEFAULTS : undefined)
      return
    }
    // Fallback: browser speech recognition -> same dialogue via text.
    if (browserRecognitionAvailable()) {
      setBrowserListening(true)
      try {
        const heard = await recognizeWithBrowser(lang)
        if (heard) await submitText(heard)
      } catch {
        setError(t('saathi.mic_denied'))
      } finally {
        setBrowserListening(false)
      }
      return
    }
    setError(t('saathi.mic_unsupported'))
  }

  useEffect(() => {
    if (recorder.state === 'denied') setError(t('saathi.mic_denied'))
  }, [recorder.state, t])

  const recording = recorder.state === 'recording' || browserListening
  const finished = last?.status === 'done' || last?.status === 'blocked'
  const blocked = last?.status === 'blocked'

  const chips: Array<[string, string]> = []
  if (slots.commodity_id) chips.push([t('saathi.slot_commodity_id'), commodityLabel(slots.commodity_id, lang, t)])
  if (sessionMode === 'kisan') {
    if (slots.physical_state) chips.push([t('saathi.slot_physical_state'), t(`saathi.state_${slots.physical_state}`)])
    if (slots.time_interval) chips.push([t('saathi.slot_time_interval'), t(`saathi.time_${slots.time_interval}`)])
  } else {
    if (slots.pack_size_g) chips.push([t('saathi.slot_pack_size_g'), `${Math.round(slots.pack_size_g)} ${t('saathi.grams')}`])
    if (slots.target_days) chips.push([t('saathi.slot_target_days'), `${Math.round(slots.target_days)} ${t('saathi.days')}`])
  }
  if (slots.storage) chips.push([t('saathi.slot_storage'), t(`saathi.storage_${slots.storage}`)])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-ink/70 backdrop-blur-sm p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t('saathi.title')}
    >
      <div className="w-full sm:max-w-xl max-h-[100dvh] sm:max-h-[90vh] flex flex-col border-4 border-ink bg-paper shadow-[10px_10px_0_var(--ink)]">
        {/* Header */}
        <div className="border-b-4 border-ink bg-yellow p-3 sm:p-4 space-y-2">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-display uppercase text-xl sm:text-2xl text-ink m-0 leading-tight">
                🎙 {t('saathi.title')}
              </h2>
              <p className="font-mono text-[11px] font-bold text-ink/80 m-0">
                {unreachable ? t('saathi.offline_short') : gnani ? t('saathi.powered') : t('saathi.browser_voice')}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                stopAllPlayback()
                onClose()
              }}
              className="min-h-[44px] min-w-[44px] border-3 border-ink bg-paper font-display text-lg cursor-pointer shadow-[3px_3px_0_var(--ink)]"
              aria-label={t('saathi.close')}
            >
              ✕
            </button>
          </div>
          <label className="flex items-center gap-2 font-mono text-xs font-bold">
            <span aria-hidden="true">🌐</span>
            <select
              value={lang}
              onChange={(e) => {
                const next = e.target.value as SaathiLang
                if (next === lang) return
                setLang(next)
                // Speaking language = screen language: buttons here and the result page follow it.
                setUiLanguage(uiLangFromSaathi(next))
                begin(next)
              }}
              className="min-h-[40px] border-3 border-ink bg-paper px-2 font-display text-sm text-ink cursor-pointer"
              aria-label="Language"
            >
              {SAATHI_LANGS.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* Conversation */}
        <div ref={logRef} className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3 min-h-[200px]" aria-live="polite">
          {lines.map((line, i) => (
            <div key={i} className={`flex ${line.who === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] border-3 border-ink px-3 py-2 font-body text-base leading-snug shadow-[3px_3px_0_var(--ink)] ${
                  line.who === 'user' ? 'bg-cyan' : 'bg-paper'
                }`}
              >
                <div className="font-mono text-[10px] uppercase font-bold text-ink/60">
                  {line.who === 'user' ? t('saathi.you') : t('saathi.saathi')}
                </div>
                {line.text}
              </div>
            </div>
          ))}
          {busy && (
            <div className="font-mono text-xs font-bold text-ink/70 flex items-center gap-2">
              <span className="inline-block w-2.5 h-2.5 bg-lime border border-ink animate-pulse" />
              {t('saathi.thinking')}
            </div>
          )}
          {(error || unreachable) && (
            <div className="border-3 border-ink bg-coral px-3 py-2 font-body text-sm space-y-2" role="alert">
              <div>{error || t('saathi.server_down')}</div>
              {unreachable && (
                <button
                  type="button"
                  onClick={retryConnection}
                  disabled={busy}
                  className="min-h-[40px] px-3 border-2 border-ink bg-paper font-display text-xs uppercase cursor-pointer disabled:opacity-60"
                >
                  ↻ {t('saathi.retry')}
                </button>
              )}
            </div>
          )}
          {recording && (
            <div className="font-mono text-sm font-bold flex items-center gap-2" aria-live="assertive">
              <span className="inline-block w-3 h-3 rounded-full bg-coral border-2 border-ink animate-pulse" />
              {t('saathi.listening')}
            </div>
          )}
        </div>

        {/* Understood slots */}
        {chips.length > 0 && (
          <div className="border-t-3 border-ink px-3 sm:px-4 py-2 bg-grey/20">
            <div className="font-mono text-[10px] uppercase font-bold text-ink/60 mb-1">{t('saathi.heard')}</div>
            <div className="flex flex-wrap gap-1.5">
              {chips.map(([k, v]) => (
                <span key={k} className="border-2 border-ink bg-lime px-2 py-0.5 font-mono text-xs font-bold">
                  {k}: {v} ✓
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Result actions */}
        {finished && last && (
          <div className="border-t-3 border-ink p-3 sm:p-4 flex flex-col sm:flex-row gap-2">
            {blocked && (
              <span className="self-start sm:self-center border-2 border-ink bg-coral px-2 py-1 font-display text-xs uppercase">
                ⚠ {t('saathi.blocked_badge')}
              </span>
            )}
            <button
              type="button"
              onClick={() => {
                stopAllPlayback()
                onResult(last)
              }}
              className="flex-1 min-h-[56px] border-3 border-ink bg-lime font-display uppercase text-base cursor-pointer shadow-[4px_4px_0_var(--ink)] active:translate-x-[3px] active:translate-y-[3px]"
            >
              {t('saathi.see_result')} →
            </button>
            <button
              type="button"
              onClick={() => begin(lang)}
              className="min-h-[56px] px-4 border-3 border-ink bg-paper font-display uppercase text-sm cursor-pointer"
            >
              ↺ {t('saathi.start_over')}
            </button>
          </div>
        )}

        {/* Input */}
        <div className="border-t-4 border-ink p-3 sm:p-4 space-y-3 bg-paper">
          <button
            type="button"
            onClick={onMic}
            disabled={(busy && !recording) || unreachable}
            className={`w-full min-h-[72px] border-4 border-ink font-display uppercase text-lg sm:text-xl cursor-pointer flex items-center justify-center gap-3 transition-all duration-[80ms] disabled:opacity-60 disabled:cursor-wait ${
              recording
                ? 'bg-coral shadow-[3px_3px_0_var(--ink)] translate-x-[3px] translate-y-[3px] animate-pulse'
                : 'bg-yellow shadow-[6px_6px_0_var(--ink)] hover:-translate-x-[2px] hover:-translate-y-[2px]'
            }`}
            aria-pressed={recording}
          >
            <span className="text-3xl" aria-hidden="true">
              {recording ? '⏹' : '🎙'}
            </span>
            <span>{recording ? t('saathi.tap_to_stop') : t('saathi.tap_to_speak')}</span>
            {recorder.state === 'recording' && (
              <span className="font-mono text-sm">
                {Math.floor(recorder.elapsed)}s / {MAX_RECORD_SECONDS}s
              </span>
            )}
          </button>
          {canHandsFree && (
            <label className="flex items-center gap-2 font-mono text-xs font-bold cursor-pointer select-none">
              <input
                type="checkbox"
                checked={handsFree}
                onChange={(e) => {
                  setHandsFree(e.target.checked)
                  if (e.target.checked && !finished) {
                    stopAllPlayback()
                    recorder.start(HANDS_FREE_DEFAULTS)
                  }
                }}
                className="w-5 h-5 accent-black"
              />
              🙌 {t('saathi.hands_free')}
            </label>
          )}
          {recorder.state === 'recording' && (
            <div className="h-3 border-2 border-ink bg-grey/30" aria-hidden="true">
              <div className="h-full bg-ink transition-[width] duration-100" style={{ width: `${Math.round(recorder.level * 100)}%` }} />
            </div>
          )}
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              const v = typed
              setTyped('')
              submitText(v)
            }}
          >
            <input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={t('saathi.type_instead')}
              className="flex-1 min-h-[48px] border-3 border-ink px-3 font-body text-base bg-paper text-ink"
              aria-label={t('saathi.type_instead')}
            />
            <button
              type="submit"
              disabled={busy || !typed.trim() || unreachable}
              className="min-h-[48px] px-4 border-3 border-ink bg-cyan font-display uppercase text-sm cursor-pointer disabled:opacity-50"
            >
              {t('saathi.send')}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default SaathiPanel
