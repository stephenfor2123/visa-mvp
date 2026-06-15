// stores/admin.js — Pinia store for admin auth (W14-11)
//
// State:
//   - token   : { accessToken, tokenType, expiresIn, role, issuedAt } | null
//   - profile : { admin_id, username, role, display_name, email, last_login } | null
//
// Actions:
//   - login({username,password}) → calls adminLogin, persists, fetches profile
//   - logout()                  → clears storage + state
//   - checkAuth()               → guards use this: re-hydrate + ensure profile
//
// Storage keys live in api/admin.js (ADMIN_STORAGE_KEYS) — single source of truth.

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  adminLogin as apiAdminLogin,
  adminLogout as apiAdminLogout,
  getAdminProfile as apiGetProfile,
  ADMIN_STORAGE_KEYS
} from '@/api/admin'

export const useAdminStore = defineStore('admin', () => {
  const token = ref(null)
  const profile = ref(null)

  const isAuthenticated = computed(() => !!token.value?.accessToken)
  const role = computed(() => token.value?.role || profile.value?.role || null)
  const username = computed(() => profile.value?.username || token.value?.username || null)

  function hydrate() {
    if (token.value) return
    try {
      const tokRaw = localStorage.getItem(ADMIN_STORAGE_KEYS.TOKEN)
      const profRaw = localStorage.getItem(ADMIN_STORAGE_KEYS.PROFILE)
      token.value = tokRaw ? JSON.parse(tokRaw) : null
      profile.value = profRaw ? JSON.parse(profRaw) : null
    } catch {
      token.value = null
      profile.value = null
    }
  }

  async function login(credentials) {
    const tok = await apiAdminLogin(credentials)
    token.value = tok
    // Login already persists token; fetch profile for display
    try {
      const prof = await apiGetProfile()
      profile.value = prof
    } catch {
      // profile is best-effort
    }
    return tok
  }

  function logout() {
    apiAdminLogout()
    token.value = null
    profile.value = null
  }

  /**
   * Guard helper: returns true iff there is a valid-looking admin token.
   * Re-hydrates from localStorage each call so direct deep-link / refresh works.
   */
  function checkAuth() {
    hydrate()
    return isAuthenticated.value
  }

  async function refreshProfile() {
    try {
      const prof = await apiGetProfile()
      profile.value = prof
      return prof
    } catch (e) {
      return null
    }
  }

  return {
    token,
    profile,
    isAuthenticated,
    role,
    username,
    hydrate,
    login,
    logout,
    checkAuth,
    refreshProfile
  }
})