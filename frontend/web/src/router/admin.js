// router/admin.js — admin sub-router module (W14-11)
//
// Owns everything under /admin/**. Mounted from src/router/index.js
// by concatenating `adminRoutes` into the main routes array.
//
// Exports:
//   - adminRoutes   : plain routes array (no router instance)
//   - adminGuard    : beforeEach-style guard for use with the main router.
//                     Guards the same flags (adminAuth / guestOnly).
//
// Storage check is performed via the admin Pinia store (which reads from
// localStorage['admin_token']) — the admin token is intentionally separate
// from the C-user `visa.auth` token.

import { useAdminStore } from '@/stores/admin'

export const adminRoutes = [
  {
    path: '/admin',
    redirect: '/admin/login'
  },
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/admin/AdminLogin.vue'),
    meta: { title: 'admin.login.title', guestOnly: true }
  },
  {
    path: '/admin/dashboard',
    name: 'AdminDashboard',
    component: () => import('@/views/admin/AdminDashboard.vue'),
    meta: { title: 'admin.dashboard', adminAuth: true }
  },
  {
    // W14-6 / W14-11: shared RateLimit page. W14-6 ships the full
    // element-plus-based view at views/admin/RateLimit.vue.
    // W14-11 originally wrote a slim AdminRateLimit.vue (7KB) that
    // collided on this route; deleted in W14-11 retry.
    path: '/admin/rate-limit',
    name: 'AdminRateLimit',
    component: () => import('@/views/admin/RateLimit.vue'),
    meta: { title: 'admin.menu_settings', adminAuth: true }
  },
  {
    path: '/admin/:pathMatch(.*)*',
    redirect: '/admin/login'
  }
]

/**
 * Vue Router beforeEach-compatible guard for admin routes.
 * Caller invokes it inside the main router's beforeEach:
 *   const result = adminGuard(to, from)
 *   if (result) return result
 *
 * Returns:
 *   - undefined  → allow navigation
 *   - { name, query } → navigation target to redirect
 */
export function adminGuard(to) {
  // Only act on /admin/** routes.
  if (!to.path.startsWith('/admin')) return undefined

  const admin = useAdminStore()
  admin.hydrate()

  if (to.meta.adminAuth && !admin.isAuthenticated) {
    return { name: 'AdminLogin', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && admin.isAuthenticated) {
    return { name: 'AdminDashboard' }
  }
  return undefined
}