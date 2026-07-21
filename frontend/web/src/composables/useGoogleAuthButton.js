import { ref, onMounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const GIS_SCRIPT_ID = 'google-gis-client'

/** Map vue-i18n locale tag → Google Identity Services locale code. */
export function appLocaleToGoogleHl(locale) {
  const raw = (locale || 'en').toLowerCase()
  if (raw.startsWith('zh')) return 'zh_CN'
  if (raw.startsWith('id')) return 'id'
  if (raw.startsWith('vi')) return 'vi'
  return 'en'
}

function loadGisScript(hl) {
  return new Promise((resolve, reject) => {
    const existing = document.getElementById(GIS_SCRIPT_ID)
    if (window.google?.accounts?.id) {
      if (!existing || existing.dataset.hl === hl) {
        resolve()
        return
      }
      existing.remove()
      delete window.google
    } else if (existing) {
      existing.remove()
    }

    const script = document.createElement('script')
    script.id = GIS_SCRIPT_ID
    script.dataset.hl = hl
    script.src = `https://accounts.google.com/gsi/client?hl=${encodeURIComponent(hl)}`
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Google Identity Services'))
    document.head.appendChild(script)
  })
}

/**
 * Render GIS button that follows the active site locale (button label only;
 * Google account-picker UI still uses the user's Google/browser language).
 *
 * @param {{ buttonText: 'signin_with' | 'signup_with', onCredential: (response: { credential: string }) => void }} options
 */
export function useGoogleAuthButton({ buttonText, onCredential }) {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''
  const googleEnabled = !!clientId
  const googleBtnRef = ref(null)
  const { locale } = useI18n()

  async function renderGoogleButton() {
    if (!googleEnabled || !googleBtnRef.value) return
    const hl = appLocaleToGoogleHl(locale.value)
    try {
      await loadGisScript(hl)
    } catch {
      return
    }
    if (!window.google?.accounts?.id) return

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: onCredential,
      auto_select: false,
    })

    googleBtnRef.value.innerHTML = ''
    window.google.accounts.id.renderButton(googleBtnRef.value, {
      type: 'standard',
      shape: 'rectangular',
      theme: 'outline',
      text: buttonText,
      size: 'large',
      width: '340',
      locale: hl,
    })
  }

  onMounted(async () => {
    if (!googleEnabled) return
    // v-if mount: ref may not be ready in the same tick as onMounted
    await nextTick()
    await renderGoogleButton()
  })

  watch(locale, async () => {
    if (!googleEnabled) return
    await nextTick()
    await renderGoogleButton()
  })

  return { googleBtnRef, googleEnabled }
}
