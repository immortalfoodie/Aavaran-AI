import React, { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  fetchTts,
  playBlob,
  saathiLangFromI18n,
  speakWithBrowser,
  stopAllPlayback,
  useVoiceStatus,
  type PlaybackHandle,
} from '../../../voice/voiceApi'

interface AudioSpeakerButtonProps {
  textToSpeak: string
  className?: string
}

export const AudioSpeakerButton: React.FC<AudioSpeakerButtonProps> = ({
  textToSpeak,
  className = '',
}) => {
  const { t, i18n } = useTranslation()
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [isFetching, setIsFetching] = useState<boolean>(false)
  const voice = useVoiceStatus()
  const handleRef = useRef<PlaybackHandle | null>(null)

  // Stop speech when unmounting or text changes
  useEffect(() => {
    return () => {
      handleRef.current?.stop()
      setIsPlaying(false)
    }
  }, [textToSpeak])

  const lang = saathiLangFromI18n(i18n.language)

  const playBrowser = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      alert('Text-to-speech is not supported on this browser.')
      return
    }
    const h = speakWithBrowser(textToSpeak, lang)
    handleRef.current = h
    setIsPlaying(true)
    h.done.then(() => setIsPlaying(false))
  }

  const toggleSpeak = async () => {
    if (isPlaying) {
      stopAllPlayback()
      setIsPlaying(false)
      return
    }
    // Prefer Gnani Timbre (natural Indian-language voice); fall back to the browser voice.
    if (voice?.gnani_enabled) {
      try {
        setIsFetching(true)
        const blob = await fetchTts(textToSpeak.slice(0, 1200), lang)
        const h = playBlob(blob)
        handleRef.current = h
        setIsPlaying(true)
        h.done.then(() => setIsPlaying(false))
        return
      } catch {
        /* fall through to browser speech */
      } finally {
        setIsFetching(false)
      }
    }
    playBrowser()
  }

  return (
    <button
      type="button"
      onClick={toggleSpeak}
      disabled={isFetching}
      aria-label={isPlaying ? t('actions.stop_audio') : t('actions.read_aloud')}
      className={`
        min-h-[64px] px-6 py-3 font-display uppercase tracking-wider text-base sm:text-lg
        border-3 border-ink select-none cursor-pointer flex items-center justify-center gap-3
        transition-all duration-[80ms]
        ${
          isPlaying
            ? 'bg-coral text-ink shadow-[4px_4px_0_var(--ink)] translate-x-[2px] translate-y-[2px]'
            : 'bg-yellow text-ink shadow-[6px_6px_0_var(--ink)] hover:bg-yellow/90 hover:-translate-x-[2px] hover:-translate-y-[2px] active:translate-x-[4px] active:translate-y-[4px]'
        }
        ${className}
      `.trim()}
    >
      <span className="text-2xl sm:text-3xl" aria-hidden="true">
        {isFetching ? '⏳' : isPlaying ? '⏹' : '🔊'}
      </span>
      <span>{isPlaying ? t('actions.stop_audio') : t('actions.read_aloud')}</span>
    </button>
  )
}

export default AudioSpeakerButton
