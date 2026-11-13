import dayjs from 'dayjs';
import 'dayjs/locale/hi';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import type { Language } from '../api/types';
import en from './en';
import hi from './hi';

const STORAGE_KEY = 'fms.uiLanguage';

function storedLanguage(): Language {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'hi' ? 'hi' : 'en';
  } catch {
    return 'en';
  }
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi } },
  lng: storedLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false }, // React already escapes
});
dayjs.locale(storedLanguage());

/** Switch the app's language now, and remember it on this device for the next start. */
export function setUiLanguage(lang: Language): void {
  void i18n.changeLanguage(lang);
  dayjs.locale(lang);
  document.documentElement.lang = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* private mode: fine, the hub setting still applies */
  }
}

/** A worker or worker-type name in the chosen language, falling back to English. */
export function localName(nameEn: string, nameHi: string | null | undefined, lang: string): string {
  return lang === 'hi' && nameHi ? nameHi : nameEn;
}

export default i18n;
