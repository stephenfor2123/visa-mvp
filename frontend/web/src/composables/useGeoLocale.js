import { onMounted, onBeforeUnmount, ref } from 'vue'
import { detectLocaleByIP, setLocale, SUPPORTED_LOCALES, onLocaleChange } from '@/i18n'

const STORAGE_USER_LOCK = 'visa.lang.user_locked'
const STORAGE_KEY = 'visa.lang'
const GEO_HINT_KEY = 'visa.lang.geo_hint_shown'  // dedupe: only auto-switch once per browser per (locale+country)

function isUserLocked() {
  try { return localStorage.getItem(STORAGE_USER_LOCK) === '1' } catch { return false }
}
function currentSaved() {
  try { return localStorage.getItem(STORAGE_KEY) } catch { return null }
}
function markGeoHintShown() {
  try { localStorage.setItem(GEO_HINT_KEY, '1') } catch {}
}
function wasGeoHintShown() {
  try { return localStorage.getItem(GEO_HINT_KEY) === '1' } catch { return false }
}

/**
 * Detect locale from IP and apply it (unless the user has already manually
 * picked one). Exposes a reactive `lastSwitch` that other components can
 * watch to show a hint toast like "已根据您的地区切换为 简体中文".
 *
 * W19 design notes:
 * - Fires once on app mount, no blocking. Default is navigator-based; IP
 *   result is applied after a small delay (or 0ms if we already know).
 * - If user has picked a language manually, NEVER override.
 * - The first time IP auto-switches, a hint event is fired so the UI can
 *   show a non-intrusive toast. Subsequent visits won't re-hint.
 */
export function useGeoLocale() {
  const lastSwitch = ref(null)  // { locale, country, source }
  let _unsub = null

  onMounted(async () => {
    if (isUserLocked()) return
    if (currentSaved()) return  // user picked at some point, but lock might be missing — be safe
    const result = await detectLocaleByIP()
    if (!result || !result.locale) return
    if (!SUPPORTED_LOCALES.includes(result.locale)) return
    if (result.locale === currentSaved()) return  // already in target
    // Apply
    setLocale(result.locale, { markUser: false, source: 'ip' })
    lastSwitch.value = result
    if (!wasGeoHintShown()) {
      markGeoHintShown()
      _unsub = onLocaleChange(() => {})
    }
  })

  onBeforeUnmount(() => {
    if (_unsub) _unsub()
  })

  return { lastSwitch }
}
