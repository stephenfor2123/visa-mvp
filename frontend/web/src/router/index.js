import { createRouter, createWebHistory } from 'vue-router'
import i18n from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { adminRoutes, adminGuard } from './admin'
import { FEATURE_RPA } from '@/config/features'
import { applyRouteSeo, rememberRouteForSeo } from '@/seo/applySeo'

function rpaDisabledRedirect() {
  return FEATURE_RPA ? true : { name: 'Orders' }
}

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
    // W48: cross-device document hub — list + upload-from-PC + open-QR-for-phone
    path: '/profile/documents',
    name: 'ProfileDocuments',
    component: () => import('@/views/Documents.vue'),
    meta: { title: 'documents.page_title', requiresAuth: true }
  },
  {
    // W48: H5 upload page reached by scanning the QR. Public — auth comes via
    // session-bound X-Transfer-Token header that the phone keeps in memory.
    path: '/transfer',
    name: 'Transfer',
    component: () => import('@/views/Transfer.vue'),
    meta: { title: 'transfer.h5_title' }
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
    // W36: 分大类材料收集向导 — Apply.vue 选完国家后先到这里，逐类强校验上传。
    // W47: 完成后表单内嵌在同一页（第 6 大类"签证表格"），登录墙在 onSubmitForm 触发。
    // 游客可填表（与 OrderNew 一致），所以不要求登录。
    path: '/materials-wizard',
    name: 'MaterialWizard',
    component: () => import('@/views/MaterialWizard.vue'),
    meta: { title: 'nav.materials' }
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
    // W47: 同样的表单内容已经内嵌到 MaterialWizard 第 6 大类(签证表格),
    // 旧 /orders/new 保留为直链入口(老 e2e / 外部链接兼容)
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
    // W50: AI 拒签风险预审(美签专用,US-only)
    // 插在 createOrder 之后 → 跳 RpaSubmit 之前。
    // 全展示不阻断,用户点"继续提交 RPA"才走原 RpaSubmit 流程。
    path: '/orders/:orderNo/precheck',
    name: 'OrderPrecheck',
    component: () => import('@/views/OrderPrecheck.vue'),
    meta: { title: 'precheck.title', requiresAuth: true },
    beforeEnter: rpaDisabledRedirect,
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
    // W14: RPA 提交页 — MVP 阶段关闭 (FEATURE_RPA=false)
    path: '/rpa/submit',
    name: 'RpaSubmit',
    component: () => import('@/views/RpaSubmit.vue'),
    meta: { title: 'rpa.page_title', requiresAuth: true },
    beforeEnter: rpaDisabledRedirect,
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
    // W47d: 4 张子页(百科/政策/模板/FAQ)— Resources.vue 顶部 4 卡 → 各国家、各分类的精选内容。
    // 共享 CuratedResourceView 渲染列表,i18n key 结构:
    //   resources_curated.{wiki|policy|templates|faq}.{us|gb|au|schengen}.{title,intro,items[],_verified_at}
    path: '/resources/wiki',
    name: 'ResourcesWiki',
    component: () => import('@/views/curated/ResourcesCuratedView.vue'),
    meta: { title: 'nav.mega.resources_i1' },
    props: { section: 'wiki' }
  },
  {
    path: '/resources/policy',
    name: 'ResourcesPolicy',
    component: () => import('@/views/curated/ResourcesCuratedView.vue'),
    meta: { title: 'nav.mega.resources_i2' },
    props: { section: 'policy' }
  },
  {
    path: '/resources/templates',
    name: 'ResourcesTemplates',
    component: () => import('@/views/curated/ResourcesCuratedView.vue'),
    meta: { title: 'nav.mega.resources_i3' },
    props: { section: 'templates' }
  },
  {
    path: '/resources/faq',
    name: 'ResourcesFaq',
    component: () => import('@/views/curated/ResourcesCuratedView.vue'),
    meta: { title: 'nav.mega.resources_i4' },
    props: { section: 'faq' }
  },
  {
    // W31: 联系我们 — 邮箱/电话/微信/工作时间(纯静态展示)
    path: '/contact',
    name: 'Contact',
    component: () => import('@/views/ContactView.vue'),
    meta: { title: 'nav.mega.contact' }
  },
  {
    // W56: 产品定价页 — 从首页迁出来的 4 国使馆费 + 平台服务费 + 退款规则详情页
    path: '/pricing',
    name: 'Pricing',
    component: () => import('@/views/PricingPage.vue'),
    meta: { title: 'nav.mega.pricing' }
  },
  {
    // W14: RPA 状态查询页
    path: '/rpa/status',
    name: 'RpaStatus',
    component: () => import('@/views/RpaStatus.vue'),
    meta: { title: 'rpa.status_page_title', requiresAuth: true },
    beforeEnter: rpaDisabledRedirect,
  },
  {
    // W74: 支付 checkout 页 — 创建支付单 + Mock 轮询 / Stripe Elements
    path: '/payment/:orderNo',
    name: 'PaymentCheckout',
    component: () => import('@/views/PaymentCheckout.vue'),
    meta: { title: 'payment.checkout_title', requiresAuth: true }
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

  // W63: 业务端 auth guard 不接管 /admin/** 路径。
  // 否则业务端已登录用户访问 /admin/login 时,会被业务端的
  // guestOnly 拦截跳到 /home,而 /admin/** 应该完全由 adminGuard 决定。
  if (to.path.startsWith('/admin')) return next()

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
  rememberRouteForSeo(to)
  applyRouteSeo(to, i18n)
})

export default router