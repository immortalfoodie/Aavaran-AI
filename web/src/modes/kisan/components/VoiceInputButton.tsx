import React, { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import type { CropId } from '../types'

interface VoiceInputButtonProps {
  onDetected: (cropId: CropId) => void
  className?: string
}

// Define minimal SpeechRecognition types
interface SpeechRecognitionResult {
  transcript: string
}
interface SpeechRecognitionEvent {
  results: {
    [index: number]: {
      [index: number]: SpeechRecognitionResult
    }
  }
}
interface ISpeechRecognition {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: (event: SpeechRecognitionEvent) => void
  onerror: () => void
  onend: () => void
}

declare global {
  interface Window {
    SpeechRecognition?: new () => ISpeechRecognition
    webkitSpeechRecognition?: new () => ISpeechRecognition
  }
}

export const VoiceInputButton: React.FC<VoiceInputButtonProps> = ({
  onDetected,
  className = '',
}) => {
  const { t, i18n } = useTranslation()
  const [isListening, setIsListening] = useState<boolean>(false)
  const recognitionRef = useRef<ISpeechRecognition | null>(null)

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
    }
  }, [])

  const matchCrop = (text: string): CropId | null => {
    const s = text.toLowerCase()
    if (s.includes('aloo') || s.includes('आलू') || s.includes('बटाटा') || s.includes('potato') || s.includes('batata')) {
      return 'veg.potato.solanum_tuberosum'
    }
    if (s.includes('tamatar') || s.includes('टमाटर') || s.includes('टोमॅटो') || s.includes('tomato')) {
      return 'veg.tomato.solanum_lycopersicum'
    }
    if (s.includes('pyaz') || s.includes('pyaaz') || s.includes('प्याज़') || s.includes('कांदा') || s.includes('onion') || s.includes('kanda')) {
      return 'veg.onion.allium_cepa'
    }
    if (s.includes('kela') || s.includes('केला') || s.includes('केळी') || s.includes('banana')) {
      return 'fruit.banana.musa_acuminata'
    }
    if (s.includes('aam') || s.includes('आम') || s.includes('आंबा') || s.includes('mango')) {
      return 'fruit.mango.mangifera_indica'
    }
    if (s.includes('bhindi') || s.includes('भिंडी') || s.includes('भेंडी') || s.includes('okra')) {
      return 'veg.okra.abelmoschus_esculentus'
    }
    if (s.includes('palak') || s.includes('पालक') || s.includes('spinach')) {
      return 'veg.spinach.spinacia_oleracea'
    }
    if (s.includes('mirch') || s.includes('mirchi') || s.includes('हरी मिर्च') || s.includes('हिरवी मिरची') || s.includes('chilli')) {
      return 'veg.green_chilli.capsicum_annuum'
    }
    return null
  }

  const toggleListen = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      // Fallback prompt for browser without Web Speech
      const spoken = window.prompt(
        'Speech recognition not supported in this browser. Enter crop name (e.g. Aloo, Tomato, Onion):',
      )
      if (spoken) {
        const found = matchCrop(spoken)
        if (found) onDetected(found)
        else alert(`Could not match "${spoken}". Please select from the grid below.`)
      }
      return
    }

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop()
      setIsListening(false)
      return
    }

    const recognition = new SpeechRecognition()
    recognitionRef.current = recognition
    recognition.continuous = false
    recognition.interimResults = false

    const lang = i18n.language || 'hi'
    recognition.lang = lang === 'mr' ? 'mr-IN' : lang === 'en' ? 'en-IN' : 'hi-IN'

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript
      setIsListening(false)
      const crop = matchCrop(transcript)
      if (crop) {
        onDetected(crop)
      } else {
        alert(`Heard: "${transcript}". Please tap your crop from the photos below.`)
      }
    }

    recognition.onerror = () => setIsListening(false)
    recognition.onend = () => setIsListening(false)

    try {
      recognition.start()
      setIsListening(true)
    } catch {
      setIsListening(false)
    }
  }

  return (
    <button
      type="button"
      onClick={toggleListen}
      className={`
        min-h-[64px] px-5 py-3 font-display uppercase tracking-wider text-base
        border-3 border-ink select-none cursor-pointer flex items-center justify-center gap-3
        transition-all duration-[80ms]
        ${
          isListening
            ? 'bg-coral text-ink animate-pulse shadow-[4px_4px_0_var(--ink)]'
            : 'bg-paper hover:bg-grey/40 text-ink shadow-[6px_6px_0_var(--ink)] hover:-translate-x-[2px] hover:-translate-y-[2px] active:translate-x-[4px] active:translate-y-[4px]'
        }
        ${className}
      `.trim()}
    >
      <span className="text-2xl sm:text-3xl" aria-hidden="true">
        {isListening ? '🎙️' : '🎤'}
      </span>
      <span>{isListening ? t('actions.listening') : t('actions.speak')}</span>
    </button>
  )
}

export default VoiceInputButton
