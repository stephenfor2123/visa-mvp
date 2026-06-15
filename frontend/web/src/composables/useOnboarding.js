/**
 * useOnboarding.js — onboarding state + profile completeness
 *
 * localStorage key: visa.onboarding.completed  (boolean)
 *
 * Profile completeness: user has non-empty nickname AND languagePref.
 * If either is missing → profile is incomplete → banner shown on all pages.
 */

const ONBOARDING_KEY = 'visa.onboarding.completed'

export function useOnboarding() {
  /**
   * Has the user completed the onboarding wizard?
   * Stored in localStorage so it survives page reloads.
   */
  function isOnboardingCompleted() {
    try {
      return localStorage.getItem(ONBOARDING_KEY) === 'true'
    } catch {
      return false
    }
  }

  /**
   * Mark onboarding as completed (called when user finishes step 4 or clicks "Skip all").
   */
  function completeOnboarding() {
    try {
      localStorage.setItem(ONBOARDING_KEY, 'true')
    } catch {}
  }

  /**
   * Reset onboarding (useful for dev / re-trigger flow).
   */
  function resetOnboarding() {
    try {
      localStorage.removeItem(ONBOARDING_KEY)
    } catch {}
  }

  /**
   * Should the onboarding modal be shown right now?
   * Conditions: user is logged in AND onboarding not yet completed.
   */
  function shouldShowOnboarding(isLoggedIn) {
    return isLoggedIn && !isOnboardingCompleted()
  }

  /**
   * Is the user's profile considered complete?
   * Checks that nickname and languagePref are both non-empty.
   */
  function isProfileComplete(user) {
    if (!user) return false
    return !!(user.nickname && user.nickname.trim() !== '' && user.languagePref)
  }

  /**
   * Should the "profile incomplete" banner be shown?
   * Conditions: user is logged in AND profile is incomplete.
   */
  function shouldShowBanner(isLoggedIn, user) {
    return isLoggedIn && !isProfileComplete(user)
  }

  return {
    isOnboardingCompleted,
    completeOnboarding,
    resetOnboarding,
    shouldShowOnboarding,
    isProfileComplete,
    shouldShowBanner
  }
}
