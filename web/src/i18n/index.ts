import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './en.json'
import hi from './hi.json'
import mr from './mr.json'
import ta from './ta.json'
import te from './te.json'
import kn from './kn.json'
import gu from './gu.json'
import pa from './pa.json'
import bn from './bn.json'

/** UI languages. Hinglish is a Saathi *voice* option and uses the Hindi UI. */
export const UI_LANGUAGES: Array<{ id: string; label: string }> = [
  { id: 'hi', label: 'हिंदी' },
  { id: 'mr', label: 'मराठी' },
  { id: 'en', label: 'English' },
  { id: 'ta', label: 'தமிழ்' },
  { id: 'te', label: 'తెలుగు' },
  { id: 'kn', label: 'ಕನ್ನಡ' },
  { id: 'gu', label: 'ગુજરાતી' },
  { id: 'pa', label: 'ਪੰਜਾਬੀ' },
  { id: 'bn', label: 'বাংলা' },
]

export const LANG_STORAGE_KEY = 'aavaran_lang'

const savedLang =
  typeof localStorage !== 'undefined'
    ? localStorage.getItem(LANG_STORAGE_KEY)
    : null

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    mr: { translation: mr },
    ta: { translation: ta },
    te: { translation: te },
    kn: { translation: kn },
    gu: { translation: gu },
    pa: { translation: pa },
    bn: { translation: bn },
  },
  lng: savedLang || 'hi',
  // Newer languages only translate the voice + navigation strings; everything else falls back to English.
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
})

export function setUiLanguage(lang: string) {
  i18n.changeLanguage(lang)
  if (typeof localStorage !== 'undefined') localStorage.setItem(LANG_STORAGE_KEY, lang)
}

export default i18n
