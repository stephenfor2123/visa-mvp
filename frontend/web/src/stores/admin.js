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

async function _forceAdminLocale() {
  try {
    const { setLocale } = await import('@/i18n')
    await setLocale('zh-CN', { markUser: false })
  } catch {}
}

export const useAdminStore = defineStore('admin', () => {
  const token = ref(null)
  const profile = ref(null)
  const permissions = ref([])

  const isAuthenticated = computed(() => !!token.value?.accessToken)
  const role = computed(() => token.value?.role || profile.value?.role || null)
  const username = computed(() => profile.value?.username || token.value?.username || null)

  function hasPermission(code) {
    return permissions.value.includes(code)
  }

  function hydrate() {
    if (token.value) {
      _forceAdminLocale()
      return
    }
    try {
      const tokRaw = localStorage.getItem(ADMIN_STORAGE_KEYS.TOKEN)
      const profRaw = localStorage.getItem(ADMIN_STORAGE_KEYS.PROFILE)
      token.value = tokRaw ? JSON.parse(tokRaw) : null
      profile.value = profRaw ? JSON.parse(profRaw) : null
      // Restore permissions from persisted token
      if (token.value?.permissions) {
        permissions.value = token.value.permissions
      }
    } catch {
      token.value = null
      profile.value = null
    }
  }

  async function login(credentials) {
    await _forceAdminLocale()
    const tok = await apiAdminLogin(credentials)
    token.value = tok
    // 登录响应含 permissions，直接用
    permissions.value = tok.permissions || []
    profile.value = {
      ...(profile.value || {}),
      username: tok.username || credentials.username,
      role_name: tok.role_name,
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
    permissions,
    isAuthenticated,
    role,
    username,
    hasPermission,
    hydrate,
    login,
    logout,
    checkAuth,
    refreshProfile
  }
})