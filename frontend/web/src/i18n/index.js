import { createI18n } from 'vue-i18n'
// Locale files are loaded lazily to avoid bundling all 4 × 70 kB into the main chunk.
// Each locale is fetched on first use and cached in vue-i18n's message store.
const LOCALE_MODULES = {
  'zh-CN': () => import('@shared/i18n/zh-CN.json'),
  'en':     () => import('@shared/i18n/en.json'),
  'id-ID':  () => import('@shared/i18n/id.json'),
  'vi-VN':  () => import('@shared/i18n/vi.json'),
}

const STORAGE_KEY = 'visa.lang'

/**
 * 4 locales supported (L4 i18n full-locale, W10-2):
 *   - zh-CN  简体中文 (default for zh-* navigator locale)
 *   - en     English    (fallback)
 *   - id-ID  Bahasa Indonesia
 *   - vi-VN  Tiếng Việt
 *
 * detectLocale() recognises id / vi browser tags too (e.g. id, id-ID, vi, vi-VN).
 * BCP-47 tags used in the file names: 'zh-CN' / 'en' / 'id-ID' / 'vi-VN'.
 *
 * Naming convention (W12-4 spec gap fix):
 *   - Filenames are short codes: `zh-CN.json`, `en.json`, `id.json`, `vi.json`
 *     (webpack/vite import binding convention — no locale suffix on en/id/vi).
 *   - BCP-47 tags (`zh-CN`, `en-US`, `id-ID`, `vi-VN`) are used as the locale
 *     KEY in vue-i18n messages, in document.documentElement.lang, and in the
 *     LOCALES metadata table below. They are NOT filenames.
 *   - `code`   — the BCP-47 tag used as the locale key / lang attribute
 *                (also the filename stem for zh-CN, where code==filename).
 *   - `file`   — the actual import path (zh-CN / en / id / vi).
 *   - `tag`    — regional BCP-47 tag for translator / locale metadata.
 *   - `flag`   — UI emoji for LangSwitch display.
 */
export const LOCALES = {
  'zh-CN': {
    code: 'zh-CN',
    file: 'zh-CN',
    tag:  'zh-CN',
    name: '简体中文',
    short: '中文',
    flag: '🇨🇳',
  },
  'en': {
    code: 'en',
    file: 'en',
    tag:  'en-US',
    name: 'English',
    short: 'EN',
    flag: '🇺🇸',
  },
  'id-ID': {
    code: 'id-ID',
    file: 'id',
    tag:  'id-ID',
    name: 'Bahasa Indonesia',
    short: 'ID',
    flag: '🇮🇩',
  },
  'vi-VN': {
    code: 'vi-VN',
    file: 'vi',
    tag:  'vi-VN',
    name: 'Tiếng Việt',
    short: 'VI',
    flag: '🇻🇳',
  },
}

export const SUPPORTED_LOCALES = Object.keys(LOCALES)

function detectLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && SUPPORTED_LOCALES.includes(saved)) return saved
  } catch {}
  const nav = (navigator.language || 'zh-CN').toLowerCase()
  if (nav.startsWith('zh')) return 'zh-CN'
  if (nav.startsWith('id')) return 'id-ID'
  if (nav.startsWith('vi')) return 'vi-VN'
  return 'en'
}

// Eagerly load only the detected locale for fast first render.
// Other locales are loaded on-demand when the user switches language.
const detectedLocale = detectLocale()

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: detectedLocale,
  fallbackLocale: 'en',
  messages: {
    // Minimal placeholder — real messages loaded via loadLocale below
    [detectedLocale]: {}
  }
})

// Pre-load the detected locale immediately so there's no flash of untranslated content.
let _initDone = false
const _pending = []

export async function loadLocale(lang) {
  if (!SUPPORTED_LOCALES.includes(lang)) return
  if (i18n.global.messages.value[lang]) return // already loaded

  try {
    const mod = await LOCALE_MODULES[lang]()
    i18n.global.setLocaleMessage(lang, mod.default || mod)
  } catch (e) {
    console.error(`[i18n] Failed to load locale ${lang}:`, e)
  }
}

// Load detected locale synchronously on startup (no await — fire and forget).
// Pages that need the content immediately can await loadLocale(detectedLocale).
loadLocale(detectedLocale)

export function setLocale(lang) {
  if (!SUPPORTED_LOCALES.includes(lang)) return
  i18n.global.locale.value = lang
  try { localStorage.setItem(STORAGE_KEY, lang) } catch {}
  document.documentElement.lang = lang
  // Load locale on-demand if not yet loaded
  loadLocale(lang)
}

export default i18n
