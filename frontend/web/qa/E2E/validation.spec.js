/**
 * C-test-1.1.2 E2E — AI 校验结果页 (N2: MaterialsValidate.vue)
 *
 * 覆盖 (与任务书对齐):
 *   1. 三档色渲染对 (.stat-card--pass / .stat-card--warn / .stat-card--fail)
 *   2. 整改指引文案在 i18n 命中 (label "整改指引" + message_key 渲染)
 *   3. error 项有 "重新拍摄" 按钮,点击跳 /materials/scan (带 ?field=&rule=)
 *
 * 测试方法 (独立、不依赖后端实现):
 *   - 用 page.route() 拦截 POST /api/v2/materials/validate,直接返 envelope {code:1000, data:{summary, results}}
 *   - 4 个 case:三档共显 / 单 error / 单 warn / 单 pass / 拦截失效
 *
 * 前置 (与已有 e2e 套件一致,见 tests/e2e/global-setup.cjs):
 *   - vite dev server 由 globalSetup 在 5173 启
 *   - backend (127.0.0.1:8000) 由 B agent 外部起;本套件用 page.route() 拦截,不需要后端真端点
 *
 * 设计选择 (测试架构):
 *   - 用 .toHaveCount(1) 验证 stat-card 的存在 (Vue 渲染后一定有 1 个)
 *   - 用 .toContainText() 验证数字 + label
 *   - 用 getByTestId() 验证 data-testid 挂载正确
 *   - 0 results 用例验证空状态 — empty-title 文案从 i18n 取
 */
import { test, expect } from '@playwright/test'

const VALIDATE_URL = /\/api\/v2\/materials\/validate$/

/**
 * /materials/validate 路由 requiresAuth:true (router/index.js:56),
 * 需在 localStorage 注入 visa.auth 才能进,否则会被 beforeEach guard
 * 重定向到 /login(实测命中 Login 页 "Welcome Back" 卡)。
 *
 * 关键:i18n 模块在 app 启动时一次性读 localStorage.visa.lang,
 *      之后再写 localStorage 已无效。必须用 page.addInitScript 在
 *      任何 Vue/i18n 模块加载前把 visa.lang + visa.auth 注入。
 *      实测:不加 visa.lang 时 Chromium 默认 en → 所有中文断言失败
 *      (例如 page-title 期望 "AI 校验结果" 实际 "AI Validation Result")。
 */
async function loginAsDemoUser(page) {
  await page.addInitScript(() => {
    localStorage.setItem('visa.lang', 'zh-CN')
    localStorage.setItem(
      'visa.auth',
      JSON.stringify({
        accessToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.mock',
        refreshToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.refresh',
        user: { id: 'u_demo', phoneCountry: '+86', phone: '13800000000', languagePref: 'zh-CN', status: 'active', createdAt: '2026-06-11T00:00:00Z' }
      })
    )
  })
  // 先访问同源页面让 init script 跑一次(about:blank localStorage 写不进去)
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
}

/**
 * 构造 envelope 响应:与 B 1.1.1a 端点 (MOCK_MODE=false 时) 的真实格式一致
 *   { code: "1000", data: { summary, results: [...] } }
 */
function buildEnvelope(results) {
  const summary = { pass: 0, warning: 0, error: 0 }
  for (const r of results) {
    if (r.severity === 'pass') summary.pass += 1
    else if (r.severity === 'warning') summary.warning += 1
    else if (r.severity === 'error') summary.error += 1
  }
  return { code: '1000', message: 'OK', data: { summary, results } }
}

/** 标准三档样本 (各 1 条) */
const SAMPLE_ERROR = {
  material_id: 'mat_001',
  field: 'passport_expiry',
  code: 'PASSPORT_EXPIRY_MIN_6M',
  severity: 'error',
  message_key: 'validation.passport.expiry_min_6m',
  details: { months_remaining: 2, expiry: '2025-08-15' }
}
const SAMPLE_WARN = {
  material_id: 'mat_002',
  field: 'photo',
  code: 'PASSPORT_PHOTO_FACE',
  severity: 'warning',
  message_key: 'validation.photo.face',
  details: { confidence: 0.62 }
}
const SAMPLE_PASS = {
  material_id: 'mat_003',
  field: 'passport_no',
  code: 'PASSPORT_OK',
  severity: 'pass',
  // 不带 message_key:验证 resolveMessage() 的 fallback (return r.message_key || r.code)
  // 没有 message_key → fallback 返回 code='PASSPORT_OK'
  details: {}
}

/** 装上 page.route,只在被调用时返 envelope(避免 1 个 case 装多次) */
async function stubValidateEndpoint(page, results) {
  let called = 0
  await page.route(VALIDATE_URL, async (route) => {
    called += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildEnvelope(results))
    })
  })
  return () => called
}

test.describe('C-test-1.1.2  AI 校验结果页 E2E', () => {
  // -----------------------------------------------------------------------
  // REGRESSION GUARD (cycle 2 / 2026-06-11 20:46): router/index.js:55 已修
  // 为 MaterialsValidate.vue(原 A-side bug:写成 Profile.vue)。本 case 由
  // "锁定 bug" 改为 "锁定修复":访问 /materials/validate 必须渲染
  // MaterialsValidate 页(.validate-page + .page-title="AI 校验结果" +
  // data-testid='validate-summary' + .item__remediation 命中),且不能再
  // 渲染 Profile 页 (.profile-page / .section-title="Profile")。
  // -----------------------------------------------------------------------
  test('case 0 — REGRESSION (fixed): /materials/validate 渲染 MaterialsValidate 页,不是 Profile', async ({
    page
  }) => {
    // 装一个最小 envelope 让 MaterialsValidate 进 results 分支,
    // 顺便验证 stub 真的被调到
    const getCallCount = await stubValidateEndpoint(page, [SAMPLE_ERROR])

    await loginAsDemoUser(page)
    await page.goto('/materials/validate?material_ids=1&order_no=test_order')

    // 1) MaterialsValidate 的特征元素必须出现
    await expect(page.locator('.validate-page')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.page-title')).toHaveText('AI 校验结果')
    await expect(page.getByTestId('validate-summary')).toBeVisible({ timeout: 10_000 })

    // 2) 因为 stub 返 1 个 error,应能看到色卡 + 整改指引 + 重新拍摄按钮
    await expect(page.locator('.stat-card--fail')).toHaveCount(1)
    await expect(page.locator('.item__remediation')).toHaveCount(1)

    // 3) Profile 页的元素不能出现(防回归)
    await expect(page.locator('.profile-page')).toHaveCount(0)
    await expect(page.locator('.section-title', { hasText: 'Profile' })).toHaveCount(0)

    // 4) endpoint 真的被调到 (route 没漏接)
    expect(getCallCount()).toBe(1)
  })

  test('case 1 — 三档共显:pass+warn+error 各 1 条,色卡/整改/重新拍摄按钮都到位', async ({
    page
  }) => {
    const getCallCount = await stubValidateEndpoint(page, [
      SAMPLE_ERROR,
      SAMPLE_WARN,
      SAMPLE_PASS
    ])

    await loginAsDemoUser(page)
    await page.goto('/materials/validate?material_ids=1,2,3&order_no=test_order')

    // 等首屏 + 接口完成 (request hit)
    await expect(page.getByTestId('validate-summary')).toBeVisible({ timeout: 10_000 })

    // 1) 三档色卡渲染 + 数字
    const totalCard = page.locator('.stat-card--total')
    const passCard = page.locator('.stat-card--pass')
    const warnCard = page.locator('.stat-card--warn')
    const failCard = page.locator('.stat-card--fail')

    await expect(totalCard).toHaveCount(1)
    await expect(totalCard.locator('.stat-card__num')).toHaveText('3')
    await expect(totalCard.locator('.stat-card__label')).toHaveText('总项数')

    await expect(passCard).toHaveCount(1)
    await expect(passCard.locator('.stat-card__num')).toHaveText('1')
    await expect(passCard.locator('.stat-card__label')).toHaveText('通过')

    await expect(warnCard).toHaveCount(1)
    await expect(warnCard.locator('.stat-card__num')).toHaveText('1')
    await expect(warnCard.locator('.stat-card__label')).toHaveText('警告')

    await expect(failCard).toHaveCount(1)
    await expect(failCard.locator('.stat-card__num')).toHaveText('1')
    await expect(failCard.locator('.stat-card__label')).toHaveText('需修正')

    // 2) 三档 item 都渲染出来
    const errorItem = page.getByTestId('validate-item-error').first()
    const warnItem = page.getByTestId('validate-item-warning').first()
    const passItem = page.getByTestId('validate-item-pass').first()
    await expect(errorItem).toBeVisible()
    await expect(warnItem).toBeVisible()
    await expect(passItem).toBeVisible()

    // 3) error item 内部:rule code + i18n 整改指引 label + 详情 months_remaining
    await expect(errorItem.locator('.item__rule')).toContainText('PASSPORT_EXPIRY_MIN_6M')
    await expect(errorItem.locator('.item__remediation-label')).toContainText('整改指引')
    await expect(errorItem.locator('.item__remediation')).toContainText('整改指引')
    // i18n message 命中 (zh-CN)
    await expect(errorItem.locator('.item__msg')).toContainText('护照有效期不足 6 个月')
    // 详情:months_remaining 渲染
    await expect(errorItem.locator('.item__value')).toContainText('剩 2 个月')

    // 4) warn item:有 details (confidence %) + 没有整改/重新拍摄按钮
    await expect(warnItem.locator('.item__value')).toContainText('62%')
    await expect(warnItem.locator('.item__remediation')).toHaveCount(0)
    await expect(warnItem.getByTestId(/^validate-rescan-/)).toHaveCount(0)

    // 5) pass item:没详情,没整改,没重新拍摄
    await expect(passItem.locator('.item__details')).toHaveCount(0)
    await expect(passItem.locator('.item__remediation')).toHaveCount(0)

    // 6) 底部"继续创建订单"按钮因有 fail 被灰显
    const continueBtn = page.getByTestId('validate-continue')
    await expect(continueBtn).toBeDisabled()
    await expect(continueBtn).toContainText('继续创建订单')

    // 7) error 项的"重新拍摄"按钮跳 /materials/scan 带 field+rule
    const rescanBtn = page.getByTestId(`validate-rescan-${SAMPLE_ERROR.code}`)
    await expect(rescanBtn).toBeVisible()
    await expect(rescanBtn).toContainText('重新拍摄')
    await rescanBtn.click()
    await page.waitForURL(/\/materials\/scan/, { timeout: 5_000 })
    const url = new URL(page.url())
    expect(url.pathname).toBe('/materials/scan')
    expect(url.searchParams.get('field')).toBe(SAMPLE_ERROR.field)
    expect(url.searchParams.get('rule')).toBe(SAMPLE_ERROR.code)

    // 8) endpoint 确实被调到 (route 没漏接)
    expect(getCallCount()).toBe(1)
  })

  test('case 2 — 单 error:fail 色卡数字=1,无 pass/warn 色卡,整改指引 + 重新拍摄按钮都在', async ({
    page
  }) => {
    const getCallCount = await stubValidateEndpoint(page, [SAMPLE_ERROR])

    await loginAsDemoUser(page)
    await page.goto('/materials/validate?material_ids=1&order_no=test_order')
    await expect(page.getByTestId('validate-summary')).toBeVisible({ timeout: 10_000 })

    await expect(page.locator('.stat-card--fail')).toHaveCount(1)
    await expect(page.locator('.stat-card--fail .stat-card__num')).toHaveText('1')
    await expect(page.locator('.stat-card--pass')).toHaveCount(1)  // .stat-card--pass 永远挂载 (只是 num=0)
    await expect(page.locator('.stat-card--pass .stat-card__num')).toHaveText('0')
    await expect(page.locator('.stat-card--warn .stat-card__num')).toHaveText('0')

    // 只有 error item
    await expect(page.getByTestId('validate-item-error')).toHaveCount(1)
    await expect(page.getByTestId('validate-item-warning')).toHaveCount(0)
    await expect(page.getByTestId('validate-item-pass')).toHaveCount(0)

    // 整改 + 重新拍摄
    const errorItem = page.getByTestId('validate-item-error').first()
    await expect(errorItem.locator('.item__remediation-label')).toContainText('整改指引')
    await expect(errorItem.locator('.item__msg')).toContainText('护照有效期不足 6 个月')

    const rescan = page.getByTestId(`validate-rescan-${SAMPLE_ERROR.code}`)
    await expect(rescan).toBeVisible()
    await rescan.click()
    await page.waitForURL(/\/materials\/scan/, { timeout: 5_000 })
    const url = new URL(page.url())
    expect(url.searchParams.get('rule')).toBe(SAMPLE_ERROR.code)

    expect(getCallCount()).toBe(1)
  })

  test('case 3 — 单 warn:warn 色卡数字=1,无 fail 色卡数字=0,无整改/无重新拍摄,有 confidence 详情', async ({
    page
  }) => {
    const getCallCount = await stubValidateEndpoint(page, [SAMPLE_WARN])

    await loginAsDemoUser(page)
    await page.goto('/materials/validate?material_ids=2&order_no=test_order')
    await expect(page.getByTestId('validate-summary')).toBeVisible({ timeout: 10_000 })

    await expect(page.locator('.stat-card--warn .stat-card__num')).toHaveText('1')
    await expect(page.locator('.stat-card--fail .stat-card__num')).toHaveText('0')
    await expect(page.locator('.stat-card--pass .stat-card__num')).toHaveText('0')

    const warnItem = page.getByTestId('validate-item-warning').first()
    await expect(warnItem).toBeVisible()
    await expect(warnItem.locator('.item__rule')).toContainText('PASSPORT_PHOTO_FACE')
    await expect(warnItem.locator('.item__msg')).toContainText('未检测到清晰人脸')
    await expect(warnItem.locator('.item__value')).toContainText('62%')

    // warn 不应有整改/重新拍摄 (仅 error 才有)
    await expect(warnItem.locator('.item__remediation')).toHaveCount(0)
    await expect(warnItem.getByTestId(/^validate-rescan-/)).toHaveCount(0)

    // 底部"继续创建订单"应当可点 (warn 不阻塞)
    await expect(page.getByTestId('validate-continue')).toBeEnabled()

    expect(getCallCount()).toBe(1)
  })

  test('case 4 — 单 pass:pass 色卡数字=1,继续按钮可点,无整改无详情', async ({ page }) => {
    const getCallCount = await stubValidateEndpoint(page, [SAMPLE_PASS])

    await loginAsDemoUser(page)
    await page.goto('/materials/validate?material_ids=3&order_no=test_order')
    await expect(page.getByTestId('validate-summary')).toBeVisible({ timeout: 10_000 })

    await expect(page.locator('.stat-card--pass .stat-card__num')).toHaveText('1')
    await expect(page.locator('.stat-card--warn .stat-card__num')).toHaveText('0')
    await expect(page.locator('.stat-card--fail .stat-card__num')).toHaveText('0')

    const passItem = page.getByTestId('validate-item-pass').first()
    await expect(passItem).toBeVisible()
    await expect(passItem.locator('.item__rule')).toContainText('PASSPORT_OK')
    await expect(passItem.locator('.item__msg')).toContainText('PASSPORT_OK')  // fallback 渲染 message_key
    await expect(passItem.locator('.item__details')).toHaveCount(0)
    await expect(passItem.locator('.item__remediation')).toHaveCount(0)
    await expect(passItem.getByTestId(/^validate-rescan-/)).toHaveCount(0)

    // 全部通过 → continue 可点
    await expect(page.getByTestId('validate-continue')).toBeEnabled()

    expect(getCallCount()).toBe(1)
  })

  test('case 5 — 0 results:空状态 (empty_title + 去材料页按钮),三档色卡不渲染', async ({
    page
  }) => {
    const getCallCount = await stubValidateEndpoint(page, [])

    await loginAsDemoUser(page)
    await page.goto('/materials/validate?material_ids=999&order_no=test_order')

    // 等接口返回 → 进入空状态分支
    await expect(page.locator('.state-empty')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.empty-title')).toHaveText('暂无可校验材料')
    await expect(page.locator('.empty-desc')).toContainText('请先到材料页')

    // summary / stat-grid 都不应出现
    await expect(page.getByTestId('validate-summary')).toHaveCount(0)
    await expect(page.locator('.stat-card--pass')).toHaveCount(0)
    await expect(page.locator('.stat-card--warn')).toHaveCount(0)
    await expect(page.locator('.stat-card--fail')).toHaveCount(0)

    // 空状态下的"去材料页"按钮跳 /materials
    await page.locator('.state-empty').getByRole('button').click()
    await page.waitForURL(/\/materials(\?|$)/, { timeout: 5_000 })

    expect(getCallCount()).toBe(1)
  })
})
