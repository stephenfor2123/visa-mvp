/**
 * useTheme — light/dark theme composable with localStorage persistence.
 *
 * Sets data-theme attribute on <html> so the CSS variable cascade activates
 * the appropriate token set defined in tokens.scss.
 */
import { ref, watch } from 'vue'

const STORAGE_KEY = 'visa-theme'
const VALID_THEMES = ['light', 'dark']

function readInitialTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && VALID_THEMES.includes(stored)) return stored
  } catch {
    // localStorage may throw in privacy/SSR contexts — fall through
  }
  return 'light'
}

// Shared reactive state — same instance across all useTheme() calls
const theme = ref(readInitialTheme())

function applyTheme(t) {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', t)
  }
}

function setTheme(t) {
  if (!VALID_THEMES.includes(t)) return
  theme.value = t
}

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
}

// Apply immediately on module load (before any component mounts).
// This avoids a flash of light theme when the user has dark saved.
applyTheme(theme.value)

// Persist on change
watch(theme, (t) => {
  try {
    localStorage.setItem(STORAGE_KEY, t)
  } catch {
    // ignore quota / privacy errors
  }
  applyTheme(t)
})

export function useTheme() {
  return { theme, setTheme, toggleTheme }
}