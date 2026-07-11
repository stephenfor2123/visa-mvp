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
  listPermissions as apiListPermissions,
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
  // W47: 后端拉来的 perm registry,AdminRoles.vue 用它分组渲染
  const permRegistry = ref({ groups: {}, groups_order: [] })

  const isAuthenticated = computed(() => !!token.value?.accessToken)
  const role = computed(() => token.value?.role || profile.value?.role || null)
  const username = computed(() => profile.value?.username || token.value?.username || null)
  const isSuperAdmin = computed(() => {
    const code = token.value?.role_name || profile.value?.role_code || ''
    // super_admin 角色直接放行; 兼容 env fallback admin
    return code === 'super_admin' || (username.value === 'admin' && (permissions.value?.length ?? 0) > 6)
  })

  function hasPermission(code) {
    if (isSuperAdmin.value) return true
    return permissions.value.includes(code)
  }

  // W63: token version 标记 — 老 token (env fallback 给 6-perm 那次之前的)
  // 客户端需要自动作废重登,避免菜单残缺 / perm 链断了的混乱
  const TOKEN_SCHEMA_VERSION = 2

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
      // 自动作废旧 schema token — version 不够 → 清掉,下次访问 admin/** 会跳 login
      if (!token.value || token.value.schema_version !== TOKEN_SCHEMA_VERSION) {
        // eslint-disable-next-line no-console
        console.log('[admin-store] stale token v=', token.value?.schema_version, '— clearing')
        token.value = null
        profile.value = null
        permissions.value = []
        try {
          localStorage.removeItem(ADMIN_STORAGE_KEYS.TOKEN)
          localStorage.removeItem(ADMIN_STORAGE_KEYS.PROFILE)
        } catch {}
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

  async function loadPermRegistry() {
    if (permRegistry.value?.groups && Object.keys(permRegistry.value.groups).length) {
      return permRegistry.value
    }
    try {
      const reg = await apiListPermissions()
      permRegistry.value = reg
      return reg
    } catch (e) {
      return permRegistry.value
    }
  }

  return {
    token,
    profile,
    permissions,
    permRegistry,
    isAuthenticated,
    role,
    username,
    isSuperAdmin,
    hasPermission,
    hydrate,
    login,
    logout,
    checkAuth,
    refreshProfile,
    loadPermRegistry,
  }
})