import { createI18n } from 'vue-i18n'
import zhCN from '@shared/i18n/zh-CN.json'
import enUS from '@shared/i18n/en.json'
import idID from '@shared/i18n/id.json'
import viVN from '@shared/i18n/vi.json'

// Locale files are loaded synchronously via static import (vite/webpack handle JSON imports).
// Lazy loading via dynamic import() caused init race conditions where t() returned raw keys
// because messages were still loading while Vue components rendered.
const LOCALE_MODULES = {
  'zh-CN': () => Promise.resolve(zhCN),
  'en':     () => Promise.resolve(enUS),
  'id-ID':  () => Promise.resolve(idID),
  'vi-VN':  () => Promise.resolve(viVN),
}

const STORAGE_KEY = 'visa.lang'
const STORAGE_USER_LOCK = 'visa.lang.user_locked'

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
  return detectByNavigator()
}

function detectByNavigator() {
  const nav = (navigator.language || 'zh-CN').toLowerCase()
  if (nav.startsWith('zh')) return 'zh-CN'
  if (nav.startsWith('id')) return 'id-ID'
  if (nav.startsWith('vi')) return 'vi-VN'
  return 'en'
}

/**
 * Country code (ISO 3166-1 alpha-2) → locale map used as a fallback when
 * the IP geo service doesn't return a `languages` field.
 * - zh-CN covers CN, HK, TW, MO, SG (majority-Chinese regions)
 * - id-ID covers ID
 * - vi-VN covers VN
 * - everything else falls back to English
 */
const COUNTRY_TO_LOCALE = {
  CN: 'zh-CN', HK: 'zh-CN', TW: 'zh-CN', MO: 'zh-CN', SG: 'zh-CN',
  ID: 'id-ID',
  VN: 'vi-VN',
}

function localeFromIPData(data) {
  if (!data) return null
  // Prefer the `languages` field (ordered, comma-separated) — gives the
  // user's actual preferred language in that country, not the official one.
  const langs = (data.languages || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
  for (const l of langs) {
    if (l.startsWith('zh')) return 'zh-CN'
    if (l.startsWith('id')) return 'id-ID'
    if (l.startsWith('vi')) return 'vi-VN'
    if (l.startsWith('en')) return 'en'
  }
  // Fallback to country code mapping
  const cc = String(data.country_code || data.countryCode || '').toUpperCase()
  if (cc && COUNTRY_TO_LOCALE[cc]) return COUNTRY_TO_LOCALE[cc]
  return 'en'
}

let _ipProbeInFlight = null

/**
 * Try to detect locale from the visitor's public IP. We use ipapi.co
 * (free tier, returns `languages` + `country_code` JSON). It supports HTTPS
 * and CORS, no API key needed. Times out at 3s; on any failure we silently
 * fall back to the navigator-based locale (no flash, no error).
 *
 * Returns:
 *   { locale: string|null, country: string|null, source: 'ipapi'|'cache'|null }
 */
export async function detectLocaleByIP({ timeoutMs = 3000, signal } = {}) {
  if (_ipProbeInFlight) return _ipProbeInFlight
  _ipProbeInFlight = (async () => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    if (signal) signal.addEventListener('abort', () => controller.abort())
    try {
      const r = await fetch('https://ipapi.co/json/', {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
        // Don't send credentials — this is a public IP lookup
        cache: 'no-store',
      })
      clearTimeout(timer)
      if (!r.ok) return { locale: null, country: null, source: null }
      const data = await r.json()
      const locale = localeFromIPData(data)
      const country = String(data.country_code || data.countryCode || '').toUpperCase() || null
      return { locale, country, source: 'ipapi' }
    } catch (_) {
      clearTimeout(timer)
      return { locale: null, country: null, source: null }
    } finally {
      _ipProbeInFlight = null
    }
  })()
  return _ipProbeInFlight
}

/**
 * Mark that the user has explicitly chosen a locale. Once set, future
 * IP-based detection will NOT override the user's preference.
 * (Writes both visa.lang and visa.lang.user_locked to localStorage.)
 */
export function markUserLocaleChoice() {
  try { localStorage.setItem(STORAGE_USER_LOCK, '1') } catch {}
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
  // Guard: only skip if locale messages are ACTUALLY loaded (not just an empty placeholder).
  // createI18n() below starts with `messages: { [detectedLocale]: {} }` which is truthy,
  // so naive `if (i18n.global.messages.value[lang]) return` skips real loading.
  const existing = i18n.global.messages.value[lang]
  if (existing && Object.keys(existing).length > 0) return

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

export async function setLocale(lang, { markUser = true, source = 'manual' } = {}) {
  if (!SUPPORTED_LOCALES.includes(lang)) return
  i18n.global.locale.value = lang
  try { localStorage.setItem(STORAGE_KEY, lang) } catch {}
  if (markUser) {
    try { localStorage.setItem(STORAGE_USER_LOCK, '1') } catch {}
  }
document.documentElement.lang = lang
  // Load locale messages first, then notify. If we emit before loadLocale
  // resolves, the consumer's t() returns the raw key (e.g. "common.lang_switched_by_ip")
  // because messages are still being fetched.
  await loadLocale(lang)
  // Refresh tab title + PWA manifest title after messages are in
  syncDocumentTitle(i18n)
  // Notify listeners (e.g. to show "已根据 IP 切换" hint)
  _emit('change', { locale: lang, source })
}

/**
 * Update <title> to "Htex · {app_slogan}" for the current locale.
 *
 * Why this lives here, not in a component:
 *  - title is global, not part of any view's render tree
 *  - LangSwitch is the trigger, but title must update even when locale
 *    changes via IP detection (no user interaction with LangSwitch)
 *  - locale is single-source-of-truth in i18n, so this is the natural home
 *
 * Safe to call before messages finish loading — falls back to bare "Htex".
 */
export function syncDocumentTitle(i18nInstance) {
  if (typeof document === 'undefined') return
  const t = i18nInstance.global.t
  const slogan = (() => {
    try {
      const v = t('common.app_slogan')
      // t() returns the raw key if messages aren't loaded yet — guard.
      return v && !v.startsWith('common.') ? v : null
    } catch { return null }
  })()
  document.title = slogan ? `Htex · ${slogan}` : 'Htex'
}

// ----- simple event bus for locale changes -----
const _listeners = { change: [] }
function _emit(evt, payload) {
  const arr = _listeners[evt] || []
  for (const fn of arr) {
    try { fn(payload) } catch (_) {}
  }
}
export function onLocaleChange(fn) {
  _listeners.change.push(fn)
  return () => {
    const i = _listeners.change.indexOf(fn)
    if (i >= 0) _listeners.change.splice(i, 1)
  }
}

export default i18n
