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
    path: '/schengen-countries',
    name: 'SchengenCountries',
    component: () => import('@/views/SchengenCountries.vue'),
    meta: { title: 'nav.schengen' }
  },
  {
    path: '/materials/scan',
    name: 'MaterialsScan',
    component: () => import('@/views/MaterialsScan.vue'),
    meta: { title: 'materials.scan_title', requiresAuth: true }
  },
  {
    path: '/passport-review',
    name: 'PassportReview',
    component: () => import('@/views/PassportReview.vue'),
    meta: { title: 'passport.review_title', requiresAuth: true }
  },
  {
    path: '/materials',
    name: 'Materials',
    component: () => import('@/views/Materials.vue'),
    meta: { title: 'nav.materials', requiresAuth: true }
  },
  {
    // W36: 分大类材料收集向导 — Apply.vue 选完国家后先到这里，逐类强校验上传，
    // 完成后带 material_ids 跳 OrderNew。
    path: '/materials-wizard',
    name: 'MaterialWizard',
    component: () => import('@/views/MaterialWizard.vue'),
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
    // W29: 免登录可访问,登录墙后移到 onSubmit 触发(详见 OrderNew.vue 顶部)
    path: '/orders/new',
    name: 'OrderNew',
    component: () => import('@/views/OrderNew.vue'),
    meta: { title: 'orders.title' }
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
    // W31: 签证办理 — 选国家 → RAG 拉材料清单 → 上传/OCR → 跳 OrderNew
    path: '/apply',
    name: 'Apply',
    component: () => import('@/views/Apply.vue'),
    meta: { title: 'nav.mega.apply' }
  },
  {
    // W31: 数据诊断 — 选国家 → 个人条件表单 → 签率综合判断
    path: '/diagnose',
    name: 'Diagnose',
    component: () => import('@/views/Diagnose.vue'),
    meta: { title: 'nav.mega.diagnose' }
  },
  {
    // W31: 资源中心 — RAG FAQ + 政策查询 + 材料模板
    path: '/resources',
    name: 'Resources',
    component: () => import('@/views/Resources.vue'),
    meta: { title: 'nav.mega.resources' }
  },
  {
    // W31: 联系我们 — 邮箱/电话/微信/工作时间(纯静态展示)
    path: '/contact',
    name: 'Contact',
    component: () => import('@/views/ContactView.vue'),
    meta: { title: 'nav.mega.contact' }
  },
  {
    // W14: RPA 状态查询页
    path: '/rpa/status',
    name: 'RpaStatus',
    component: () => import('@/views/RpaStatus.vue'),
    meta: { title: 'rpa.status_page_title', requiresAuth: true }
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
  // W32: page-specific title when route declares one (e.g. "上传材料");
  //      otherwise fall back to "Htex · {app_slogan}" so the brand+slogan
  //      pattern is consistent across pages that don't set their own title.
  if (i18nKey) {
    document.title = `Htex · ${i18n.global.t(i18nKey)}`
  } else {
    const slogan = (() => {
      try {
        const v = i18n.global.t('common.app_slogan')
        return v && !v.startsWith('common.') ? v : null
      } catch { return null }
    })()
    document.title = slogan ? `Htex · ${slogan}` : i18n.global.t('common.app_name') || 'Htex'
  }
})

export default router