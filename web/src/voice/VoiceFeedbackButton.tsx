import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useWavRecorder } from './recorder'
import {
  browserRecognitionAvailable,
  playBase64Mp3,
  recognizeWithBrowser,
  saathiLangFromI18n,
  sendVoiceFeedback,
  speakWithBrowser,
  stopAllPlayback,
  useVoiceStatus,
} from './voiceApi'

/**
 * "बोलकर बताइए कितने दिन चला" — the farmer reports the real outcome by voice.
 * Gnani Prisma transcribes; the server parses days + spoilage and stores it
 * against the SealedResult so predictions can be calibrated later.
 */
export const VoiceFeedbackButton: React.FC<{ resultId: string; className?: string }> = ({ resultId, className = '' }) => {
  const { t, i18n } = useTranslation()
  const voice = useVoiceStatus()
  const lang = saathiLangFromI18n(i18n.language)
  const [busy, setBusy] = useState(false)
  const [reply, setReply] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const handle = async (payload: { wav?: Blob; text?: string }) => {
    setBusy(true)
    try {
      const res = await sendVoiceFeedback({ resultId, lang, ...payload })
      setReply(res.transcript ? `“${res.transcript}” — ${res.reply_text}` : res.reply_text)
      setSaved(res.status === 'saved')
      if (res.reply_audio_b64) playBase64Mp3(res.reply_audio_b64)
      else speakWithBrowser(res.reply_text, lang)
    } catch {
      setReply(t('saathi.error'))
    } finally {
      setBusy(false)
    }
  }

  const recorder = useWavRecorder((wav) => handle({ wav }))
  const recording = recorder.state === 'recording'

  const onClick = async () => {
    stopAllPlayback()
    if (voice?.gnani_enabled && recorder.state !== 'unsupported') {
      if (recording) recorder.stop()
      else await recorder.start()
      return
    }
    if (browserRecognitionAvailable()) {
      try {
        setBusy(true)
        const text = await recognizeWithBrowser(lang)
        if (text) await handle({ text })
      } catch {
        setReply(t('saathi.mic_denied'))
      } finally {
        setBusy(false)
      }
      return
    }
    setReply(t('saathi.mic_unsupported'))
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <button
        type="button"
        onClick={onClick}
        disabled={busy || saved}
        className={`w-full min-h-[56px] px-4 border-3 border-ink font-display uppercase text-sm sm:text-base cursor-pointer flex items-center justify-center gap-2 disabled:opacity-60 ${
          recording ? 'bg-coral animate-pulse' : saved ? 'bg-lime' : 'bg-cyan shadow-[4px_4px_0_var(--ink)]'
        }`}
      >
        <span aria-hidden="true">{saved ? '✓' : recording ? '⏹' : '🎙'}</span>
        <span>{saved ? t('saathi.feedback_saved') : recording ? t('saathi.tap_to_stop') : t('saathi.feedback_btn')}</span>
      </button>
      {reply && <p className="font-body text-sm border-2 border-ink bg-paper px-3 py-2 m-0" aria-live="polite">{reply}</p>}
    </div>
  )
}

export default VoiceFeedbackButton
