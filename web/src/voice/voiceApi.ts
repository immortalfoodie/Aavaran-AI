import { useEffect, useState } from 'react'
import { getApiUrl } from '../api/config'

/** Saathi conversation languages. `hi-en` = Hinglish (code-mixed). */
export type SaathiLang =
  | 'hi-IN'
  | 'mr-IN'
  | 'en-IN'
  | 'hi-en'
  | 'ta-IN'
  | 'te-IN'
  | 'kn-IN'
  | 'gu-IN'
  | 'pa-IN'
  | 'bn-IN'
export type SaathiMode = 'kisan' | 'business'

export const SAATHI_LANGS: Array<{ id: SaathiLang; label: string }> = [
  { id: 'hi-IN', label: 'हिंदी' },
  { id: 'mr-IN', label: 'मराठी' },
  { id: 'hi-en', label: 'Hinglish' },
  { id: 'en-IN', label: 'English' },
  { id: 'ta-IN', label: 'தமிழ்' },
  { id: 'te-IN', label: 'తెలుగు' },
  { id: 'kn-IN', label: 'ಕನ್ನಡ' },
  { id: 'gu-IN', label: 'ગુજરાતી' },
  { id: 'pa-IN', label: 'ਪੰਜਾਬੀ' },
  { id: 'bn-IN', label: 'বাংলা' },
]

/** Screen language for a Saathi voice language (Hinglish uses the Hindi screens). */
export function uiLangFromSaathi(lang: SaathiLang): string {
  return lang === 'hi-en' ? 'hi' : lang.split('-')[0]
}

export function saathiLangFromI18n(i18nLang: string | undefined): SaathiLang {
  if (i18nLang === 'hi-en') return 'hi-en'
  const base = (i18nLang || 'hi').split('-')[0]
  const match = SAATHI_LANGS.find((l) => l.id !== 'hi-en' && l.id.startsWith(`${base}-`))
  return match ? match.id : 'hi-IN'
}

export interface VoiceStatus {
  /** false = the Aavaran server could not be reached (offline, asleep, wrong URL or CORS). */
  reachable: boolean
  gnani_enabled: boolean
  stt_model: string | null
  tts_model: string | null
  languages: string[]
}

export interface SaathiResultSummary {
  result_id: string
  verdict: 'RECOMMENDED' | 'NOT_A_PACKAGING_PROBLEM' | string
  safety_status: string | null
  days_p50: number | null
  packaging_name: string | null
  key_action: string | null
  candidates: Array<{ name: string; layer_stack: string[]; cost_per_pack: number | null; epr_category: string | null }>
  guidance: Array<{ action: string; headline: string }>
}

export interface SaathiSlots {
  commodity_id?: string
  physical_state?: 'whole' | 'cut' | 'washed' | 'damaged'
  hours_since?: number
  time_interval?: 'today' | 'one_day' | 'two_days' | 'three_days_plus'
  storage?: 'shed' | 'cold_room' | 'ice'
  pack_size_g?: number
  target_days?: number
}

export interface SaathiTurn {
  session_id: string
  mode: SaathiMode
  lang: SaathiLang
  transcript?: string
  status: 'asking' | 'done' | 'blocked'
  asked_slot?: string | null
  reply_text: string
  reply_audio_b64: string | null
  tts_error?: string | null
  slots: SaathiSlots
  stt?: { model: string | null; detected_language: string | null; latency_s: number | null } | null
  result?: SaathiResultSummary | null
  recommend_input?: Record<string, any> | null
}

export class VoiceApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T
  let code = `HTTP_${res.status}`
  let message = res.statusText || 'Request failed'
  try {
    const body = await res.json()
    const d = body?.detail
    if (d && typeof d === 'object') {
      code = d.code || code
      message = d.message || message
    } else if (typeof d === 'string') {
      message = d
    }
  } catch {
    /* non-JSON error */
  }
  throw new VoiceApiError(message, code, res.status)
}

let statusPromise: Promise<VoiceStatus> | null = null

export function getVoiceStatus(): Promise<VoiceStatus> {
  if (!statusPromise) {
    statusPromise = fetch(getApiUrl('/api/v1/voice/status'))
      .then((r) => parseJson<Omit<VoiceStatus, 'reachable'>>(r))
      .then((s) => ({ ...s, reachable: true }))
      .catch((err) => {
        console.warn('[Aavaran] voice status unreachable:', err)
        statusPromise = null // retry next time (backend may be waking up)
        return { reachable: false, gnani_enabled: false, stt_model: null, tts_model: null, languages: [] }
      })
  }
  return statusPromise
}

/** React hook: Gnani availability (false while offline or when the server has no key). */
export function useVoiceStatus(): VoiceStatus | null {
  const [status, setStatus] = useState<VoiceStatus | null>(null)
  useEffect(() => {
    let alive = true
    getVoiceStatus().then((s) => alive && setStatus(s))
    return () => {
      alive = false
    }
  }, [])
  return status
}

export async function startSaathi(mode: SaathiMode, lang: SaathiLang, speak = true): Promise<SaathiTurn> {
  const res = await fetch(getApiUrl('/api/v1/voice/start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, lang, speak }),
  })
  return parseJson<SaathiTurn>(res)
}

export async function sendTextTurn(
  text: string,
  opts: { sessionId?: string; mode: SaathiMode; lang: SaathiLang; speak?: boolean },
): Promise<SaathiTurn> {
  const res = await fetch(getApiUrl('/api/v1/voice/text-turn'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      session_id: opts.sessionId,
      mode: opts.mode,
      lang: opts.lang,
      speak: opts.speak ?? true,
    }),
  })
  return parseJson<SaathiTurn>(res)
}

export async function sendAudioTurn(
  wav: Blob,
  opts: { sessionId?: string; mode: SaathiMode; lang: SaathiLang },
): Promise<SaathiTurn> {
  const form = new FormData()
  form.append('audio_file', wav, 'speech.wav')
  if (opts.sessionId) form.append('session_id', opts.sessionId)
  form.append('mode', opts.mode)
  form.append('lang', opts.lang)
  const res = await fetch(getApiUrl('/api/v1/voice/turn'), { method: 'POST', body: form })
  return parseJson<SaathiTurn>(res)
}

export async function sendVoiceFeedback(opts: {
  resultId: string
  lang: SaathiLang
  wav?: Blob
  text?: string
}): Promise<{ status: 'saved' | 'asking'; transcript: string; reply_text: string; reply_audio_b64: string | null }> {
  const form = new FormData()
  form.append('result_id', opts.resultId)
  form.append('lang', opts.lang)
  if (opts.text) form.append('text', opts.text)
  if (opts.wav) form.append('audio_file', opts.wav, 'speech.wav')
  const res = await fetch(getApiUrl('/api/v1/voice/feedback'), { method: 'POST', body: form })
  return parseJson(res)
}

export async function fetchTts(text: string, lang: SaathiLang): Promise<Blob> {
  const res = await fetch(getApiUrl('/api/v1/voice/tts'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, lang }),
  })
  if (!res.ok) await parseJson(res)
  return res.blob()
}

// --------------------------------------------------------------------------- playback

export interface PlaybackHandle {
  stop: () => void
  done: Promise<void>
}

let current: PlaybackHandle | null = null

export function stopAllPlayback() {
  current?.stop()
  current = null
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
}

function playUrl(url: string, revoke: boolean): PlaybackHandle {
  stopAllPlayback()
  const audio = new Audio(url)
  let resolve: () => void = () => undefined
  const done = new Promise<void>((r) => (resolve = r))
  const finish = () => {
    if (revoke) URL.revokeObjectURL(url)
    resolve()
  }
  audio.onended = finish
  audio.onerror = finish
  audio.play().catch(finish) // autoplay may be blocked; UI still shows the text
  const handle = {
    stop: () => {
      audio.pause()
      finish()
    },
    done,
  }
  current = handle
  return handle
}

export function playBase64Mp3(b64: string): PlaybackHandle {
  return playUrl(`data:audio/mpeg;base64,${b64}`, false)
}

export function playBlob(blob: Blob): PlaybackHandle {
  return playUrl(URL.createObjectURL(blob), true)
}

/** Browser speechSynthesis fallback when Gnani Timbre is unavailable. */
export function speakWithBrowser(text: string, lang: SaathiLang): PlaybackHandle {
  stopAllPlayback()
  let resolve: () => void = () => undefined
  const done = new Promise<void>((r) => (resolve = r))
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    resolve()
    return { stop: () => undefined, done }
  }
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang === 'hi-en' ? 'hi-IN' : lang
  u.rate = 0.95
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith(u.lang))
  if (voice) u.voice = voice
  u.onend = () => resolve()
  u.onerror = () => resolve()
  window.speechSynthesis.speak(u)
  const handle = { stop: () => window.speechSynthesis.cancel(), done }
  current = handle
  return handle
}

// --------------------------------------------------------------------------- browser STT fallback

export function browserRecognitionAvailable(): boolean {
  return typeof window !== 'undefined' && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
}

/** One-shot browser speech recognition (used only when Gnani is not configured). */
export function recognizeWithBrowser(lang: SaathiLang): Promise<string> {
  return new Promise((resolve, reject) => {
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!Ctor) {
      reject(new Error('unsupported'))
      return
    }
    const rec = new Ctor()
    rec.lang = lang === 'hi-en' ? 'en-IN' : lang
    rec.continuous = false
    rec.interimResults = false
    rec.maxAlternatives = 1
    rec.onresult = (e: any) => resolve(e.results?.[0]?.[0]?.transcript ?? '')
    rec.onerror = (e: any) => reject(new Error(e?.error || 'recognition_error'))
    rec.onend = () => resolve('')
    rec.start()
  })
}
