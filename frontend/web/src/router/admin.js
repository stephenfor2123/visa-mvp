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
        path: 'analytics',
        name: 'AdminAnalytics',
        component: () => import('@/views/admin/AdminAnalytics.vue'),
        meta: { title: 'admin.analytics.page_title', adminAuth: true, permission: 'dashboard.view' }
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
        meta: { title: 'admin.roles.page_title', adminAuth: true, permission: 'role.manage' }
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/AdminUsers.vue'),
        meta: { title: 'admin.users.page_title', adminAuth: true, permission: 'user.view' }
      },
      // W63: /admin/c-users 路由删除 — 后端 /v2/admin/c-users 接口不存在,
      // 老用户管理已迁移到 /admin/users。如果需要回退可从 git history 拿
      {
        path: 'countries',
        name: 'AdminCountries',
        component: () => import('@/views/admin/AdminCountries.vue'),
        meta: { title: 'admin.countries.page_title', adminAuth: true, permission: 'country.manage' }
      },
      {
        path: 'pricing',
        name: 'AdminPricing',
        component: () => import('@/views/admin/AdminPricing.vue'),
        meta: { title: 'admin.pricing.page_title', adminAuth: true, permission: ['pricing.manage', 'settings'] }
      },
      {
        path: 'ai-rules',
        name: 'AdminAiRules',
        component: () => import('@/views/admin/AdminAiRules.vue'),
        meta: { title: 'admin.ai_rules.page_title', adminAuth: true, permission: 'ai_rules.edit' }
      },
      {
        // W62 — RAG 内容审核 (singleton 页面,详情用 modal 形式)
        path: 'rag-review',
        name: 'AdminRagReview',
        component: () => import('@/views/admin/AdminRagReview.vue'),
        meta: { title: 'admin.rag_review.page_title', adminAuth: true, permission: 'rag.review' }
      },
      // W63: RPA 策略 / i18n 路由下线 (MVP 不在 scope, 历史保留 git)
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
    const perms = Array.isArray(to.meta.permission) ? to.meta.permission : [to.meta.permission]
    if (!perms.some((p) => admin.hasPermission(p))) {
      return { name: 'AdminDashboard' }
    }
  }
  if (to.meta.guestOnly && admin.isAuthenticated) {
    return { name: 'AdminDashboard' }
  }
  return undefined
}
