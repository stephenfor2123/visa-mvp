import { createRouter, createWebHistory } from 'vue-router'
import i18n from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { adminRoutes, adminGuard } from './admin'

const routes = [
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { title: 'nav.home' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: 'nav.login', guestOnly: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { title: 'nav.signup', guestOnly: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/Profile.vue'),
    meta: { title: 'nav.profile', requiresAuth: true }
  },
  {
    path: '/destinations',
    name: 'Destinations',
    component: () => import('@/views/Destinations.vue'),
    meta: { title: 'nav.destinations' }
  },
  {
    path: '/materials/scan',
    name: 'MaterialsScan',
    component: () => import('@/views/MaterialsScan.vue'),
    meta: { title: 'materials.scan_title', requiresAuth: true }
  },
  {
    path: '/materials',
    name: 'Materials',
    component: () => import('@/views/Materials.vue'),
    meta: { title: 'nav.materials', requiresAuth: true }
  },
  {
    // Story 1.1.2b: AI 校验结果页 N2 — 字段级校验 + 整改指引 + 重新拍摄
    path: '/materials/validate',
    name: 'MaterialsValidate',
    component: () => import('@/views/MaterialsValidate.vue'),
    meta: { title: 'validation.page_title', requiresAuth: true }
  },
  {
    // 2026-06-25: AI 拒签风险诊断 — 基于 RAG + 规则引擎综合评估
    path: '/materials/diagnose',
    name: 'MaterialsDiagnose',
    component: () => import('@/views/MaterialsDiagnose.vue'),
    meta: { title: 'diagnose.title', requiresAuth: true }
  },
  {
    // Story 1.2.1b: 申请表填写页 (OCR 预填 + 手动编辑 + 紧急联系人)
    path: '/orders/new',
    name: 'OrderNew',
    component: () => import('@/views/OrderNew.vue'),
    meta: { title: 'orders.title', requiresAuth: true }
  },
  {
    // Story 1.2.2a: 订单状态详情页 N4 — 5 态时间线 + WS + 30s polling 兜底
    path: '/orders/:orderNo',
    name: 'OrderDetail',
    component: () => import('@/views/OrderDetail.vue'),
    meta: { title: 'orderdetail.page_title', requiresAuth: true }
  },
  {
    // W12: 订单列表页
    path: '/orders',
    name: 'Orders',
    component: () => import('@/views/Orders.vue'),
    meta: { title: 'orders.title', requiresAuth: true }
  },
  {
    // W12: 忘记密码页
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPassword.vue'),
    meta: { title: 'forgot.page_title', guestOnly: true }
  },
  {
    // W12: 服务协议页
    path: '/agreement',
    name: 'Agreement',
    component: () => import('@/views/Agreement.vue'),
    meta: { title: 'agreement.page_title' }
  },
  {
    // W14: RPA 提交页 (材料校验通过后自动跳转)
    path: '/rpa/submit',
    name: 'RpaSubmit',
    component: () => import('@/views/RpaSubmit.vue'),
    meta: { title: 'rpa.page_title', requiresAuth: true }
  },
  {
    // W14: RPA 状态查询页
    path: '/rpa/status',
    name: 'RpaStatus',
    component: () => import('@/views/RpaStatus.vue'),
    meta: { title: 'rpa.status_page_title', requiresAuth: true }
  },
  {
    // W14-6: 后台限流配置可视化页
    //   - 实时统计卡片 (今日访问 / 当前排队 / 24h 失败率 / 活跃账号)
    //   - 限流参数编辑 (IP/day / 提交间隔 / 错峰 / rate key)
    //   - 保存 → PUT /api/v2/admin/config/rpa
    path: '/admin/rate-limit',
    name: 'AdminRateLimit',
    component: () => import('@/views/admin/RateLimit.vue'),
    meta: { title: 'admin.ratelimit.page_title' }
  },
  {
    // W14: 支付结果页 (4 状态:success/failed/pending/cancelled + 30s polling)
    // route: /payment/result?orderId=xxx&status=xxx
    path: '/payment/result',
    name: 'PaymentResult',
    component: () => import('@/views/PaymentResult.vue'),
    meta: { title: 'payment.page_title', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue')
  },
  // W14-11: admin sub-router mounted as a sibling module.
  // Its own guard (adminGuard) checks admin_token independently from C-user auth.
  ...adminRoutes
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  // W14-11: admin guard runs first for /admin/** — admin_token check is
  // independent from C-user JWT, so we don't pollute the C-user auth path.
  const adminRedirect = adminGuard(to)
  if (adminRedirect) return next(adminRedirect)

  const auth = useAuthStore()
  auth.hydrate()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }
  if (to.meta.guestOnly && auth.isLoggedIn) {
    return next({ name: 'Home' })
  }
  next()
})

router.afterEach((to) => {
  const i18nKey = to.meta?.title
  // W19-3: use i18n.global.t to translate (was showing raw key like "nav.home" before)
  if (i18nKey) {
    document.title = `签证助手 · ${i18n.global.t(i18nKey)}`
  } else {
    document.title = i18n.global.t('common.app_name') || '签证助手'
  }
})

export default router