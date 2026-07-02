// router/admin.js — admin sub-router module
import { useAdminStore } from '@/stores/admin'

export const adminRoutes = [
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/admin/AdminLogin.vue'),
    meta: { title: 'admin.login.title', guestOnly: true }
  },
  {
    // Shared layout: sidebar + <router-view> for all authenticated admin pages
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { adminAuth: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
      },
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/AdminDashboard.vue'),
        meta: { title: 'admin.dashboard', adminAuth: true }
      },
      {
        path: 'orders',
        name: 'AdminOrders',
        component: () => import('@/views/admin/AdminOrders.vue'),
        meta: { title: 'admin.orders.page_title', adminAuth: true }
      },
      {
        path: 'orders/:id(\\d+)',
        name: 'AdminOrderDetail',
        component: () => import('@/views/admin/AdminOrderDetail.vue'),
        meta: { title: 'admin.order_detail.page_title', adminAuth: true }
      },
      {
        path: 'payments',
        name: 'AdminPayments',
        component: () => import('@/views/admin/AdminPayments.vue'),
        meta: { title: 'admin.payments.page_title', adminAuth: true }
      },
      {
        path: 'rate-limit',
        name: 'AdminRateLimit',
        component: () => import('@/views/admin/RateLimit.vue'),
        meta: { title: 'admin.menu_settings', adminAuth: true }
      },
      {
        path: 'roles',
        name: 'AdminRoles',
        component: () => import('@/views/admin/AdminRoles.vue'),
        meta: { title: 'admin.roles.page_title', adminAuth: true, permission: 'users' }
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/AdminUsers.vue'),
        meta: { title: 'admin.users.page_title', adminAuth: true, permission: 'users' }
      },
      {
        path: 'c-users',
        name: 'AdminCUsers',
        component: () => import('@/views/admin/AdminCUsers.vue'),
        meta: { title: 'admin.c_users.page_title', adminAuth: true, permission: 'users' }
      },
      {
        path: 'c-users/:id(\\d+)',
        name: 'AdminCUserDetail',
        component: () => import('@/views/admin/AdminCUserDetail.vue'),
        meta: { title: 'admin.c_users.detail_title', adminAuth: true, permission: 'users' }
      },
      {
        path: 'countries',
        name: 'AdminCountries',
        component: () => import('@/views/admin/AdminCountries.vue'),
        meta: { title: 'admin.countries.page_title', adminAuth: true, permission: 'countries' }
      },
      {
        path: 'ai-rules',
        name: 'AdminAiRules',
        component: () => import('@/views/admin/AdminAiRules.vue'),
        meta: { title: 'admin.ai_rules.page_title', adminAuth: true, permission: 'settings' }
      },
      {
        path: 'rpa-strategy',
        name: 'AdminRpaStrategy',
        component: () => import('@/views/admin/AdminRpaStrategy.vue'),
        meta: { title: 'admin.rpa_strategy.page_title', adminAuth: true, permission: 'settings' }
      },
      {
        path: 'i18n',
        name: 'AdminI18n',
        component: () => import('@/views/admin/AdminI18n.vue'),
        meta: { title: 'admin.i18n.page_title', adminAuth: true, permission: 'settings' }
      },
      {
        path: 'logs',
        name: 'AdminLogs',
        component: () => import('@/views/admin/AdminLogs.vue'),
        meta: { title: 'admin.logs.page_title', adminAuth: true, permission: 'dashboard' }
      },
      {
        path: 'cleanup',
        name: 'AdminCleanup',
        component: () => import('@/views/admin/AdminCleanup.vue'),
        meta: { title: 'admin.cleanup.page_title', adminAuth: true, permission: 'settings' }
      },
    ]
  },
  {
    path: '/admin/:pathMatch(.*)*',
    redirect: '/admin/login'
  }
]

export function adminGuard(to) {
  if (!to.path.startsWith('/admin')) return undefined

  const admin = useAdminStore()
  admin.hydrate()

  if (to.meta.adminAuth && !admin.isAuthenticated) {
    return { name: 'AdminLogin', query: { redirect: to.fullPath } }
  }
  if (to.meta.permission && !admin.hasPermission(to.meta.permission)) {
    return { name: 'AdminDashboard' }
  }
  if (to.meta.guestOnly && admin.isAuthenticated) {
    return { name: 'AdminDashboard' }
  }
  return undefined
}
