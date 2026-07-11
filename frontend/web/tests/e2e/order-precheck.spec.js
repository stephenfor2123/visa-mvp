// tests/e2e/order-precheck.spec.js — W50: AI 拒签风险预审(美签)插入流程
//
// 端到端:
//   1) 已登录状态访问 /orders/DEMO/precheck?countryCode=US&...
//      不经任何业务跳转,直接验证 OrderPrecheck.vue 渲染 + API 调用 + 结果展示。
//   2) 关键交互点:点"继续提交 RPA"按钮应该跳到 RpaSubmit;
//                  点"查看完整诊断"应该跳到 /materials/diagnose。
//   3) US-only:这页本身不判断国家,但调用方跳转条件是国家=US。
//      这个 spec 不需要测调用方逻辑(那是 wizard 里 destCountry==='US' 的分支,
//      已经在 wizard 单测覆盖),只测 precheck 页自身。
//
// 走真实 dev server + 真实 vite 已编译 OK 的 chunk。
import { test, expect } from '@playwright/test'

const ORDER_NO = 'VT-DEMO-PRECHECK'
const COUNTRY = 'US'
const VISA = 'tourism'
const MATERIAL_IDS = [101, 102, 103]

// 简单 mock 返回一个 critical issue 用于断言能看到 "🛑 critical"
function mockOkResponse() {
  return {
    overall_risk: 'critical',
    risk_score: 0.62,
    summary: '本次申请存在关键问题,建议先补齐材料再提交。',
    issues: [
      {
        code: 'passport.expiry_short',
        severity: 'critical',
        title: '护照有效期不足 6 个月',
        detail: '剩余约 3 个月,大多数国家要求 ≥6 个月',
        fix_suggestion: '出发前必须续期护照,否则会被直接拒签。',
        related_material_id: MATERIAL_IDS[0],
      },
      {
        code: 'checklist.incomplete',
        severity: 'warning',
        title: '材料不完整',
        detail: '建议补充签证照片和申请表',
        fix_suggestion: '请上传白底照片 + 填写完整的申请表',
      },
    ],
    positives: ['已识别申请人基本信息', '行程单日期一致'],
    policy_refs: ['https://travel.state.gov/content/travel.html'],
    rule_count: 8,
  }
}

test.describe('OrderPrecheck W50', () => {
  test('renders risk badge + issues + actions', async ({ page, context }) => {
    // 登录态:直接放一个 fake token 到 localStorage(requiresAuth 通过即可,实际后端
    // 这条 mock 路由不会打到登录接口,所以什么 token 都行)。
    // 字段名 accessToken / user 必须跟 src/stores/auth.js hydrate 保持一致。
    await context.addInitScript(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          accessToken: 'fake-jwt',
          refreshToken: 'fake-refresh',
          user: { id: 1, email: 'demo@htex.com', name: 'Demo' },
        }))
      } catch {}
    })

    // 拦截 /v2/materials/diagnose —— 默认走 mock 模式(MOCK_MODE=true)就走前端 mock,
    // 不真的打到后端。这里我们额外 mock 一次,即使 MOCK_MODE=false 也能稳定出结果。
    await page.route('**/v2/materials/diagnose', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: '1000', message: 'ok', data: mockOkResponse() }),
      })
    })

    const url = `/orders/${ORDER_NO}/precheck?countryCode=${COUNTRY}&visaType=${VISA}&materialIds=${MATERIAL_IDS.join(',')}&fields=eyJzdXJuYW1lIjoiREVNIiwicGFzc3BvcnRfbm8iOiJYMTAwMDExIn0%3D`
    await page.goto(url)

    // 标题 + 副标题渲染
    await expect(page.locator('[data-testid="precheck-order-no"]')).toHaveText(ORDER_NO)
    await expect(page.locator('[data-testid="precheck-material-count"]')).toContainText('3')
    await expect(page.locator('[data-testid="precheck-order-no"]')).toBeVisible()

    // 等诊断结果
    await expect(page.locator('[data-testid="precheck-risk-badge"]')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('[data-testid="precheck-risk-badge"]')).toContainText(/critical/i)

    // issue 卡片渲染两条
    await expect(page.locator('[data-testid="precheck-issues"]')).toBeVisible()
    await expect(page.locator('[data-testid="precheck-issue-passport.expiry_short"]')).toBeVisible()
    await expect(page.locator('[data-testid="precheck-issue-checklist.incomplete"]')).toBeVisible()

    // 已达标项 + 政策引用
    await expect(page.locator('[data-testid="precheck-positives"]')).toBeVisible()

    // 操作按钮存在
    await expect(page.locator('[data-testid="precheck-continue-btn"]')).toBeVisible()
    await expect(page.locator('[data-testid="precheck-go-diagnose-btn"]')).toBeVisible()

    // 截图作为证据(留作未来回归用,不强制)
    await page.screenshot({ path: 'tests/e2e/screenshots/order-precheck-US.png', fullPage: true })
  })

  test('"查看完整诊断" navigates to /materials/diagnose', async ({ page, context }) => {
    await context.addInitScript(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          token: 'fake-jwt',
          accessToken: 'fake-jwt',
          refreshToken: 'fake-refresh',
          user: { id: 1, email: 'demo@htex.com', name: 'Demo' },
        }))
      } catch {}
    })
    await page.route('**/v2/materials/diagnose', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: '1000', message: 'ok', data: mockOkResponse() }),
      })
    })

    await page.goto(`/orders/${ORDER_NO}/precheck?countryCode=${COUNTRY}&visaType=${VISA}&materialIds=${MATERIAL_IDS.join(',')}&fields=eyJ9`)
    await expect(page.locator('[data-testid="precheck-go-diagnose-btn"]')).toBeVisible({ timeout: 10000 })
    await page.locator('[data-testid="precheck-go-diagnose-btn"]').click()
    await page.waitForURL('**/materials/diagnose**', { timeout: 5000 })
    expect(page.url()).toContain('/materials/diagnose')
  })

  test('"继续提交 RPA" navigates to RpaSubmit', async ({ page, context }) => {
    await context.addInitScript(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          token: 'fake-jwt',
          accessToken: 'fake-jwt',
          refreshToken: 'fake-refresh',
          user: { id: 1, email: 'demo@htex.com', name: 'Demo' },
        }))
      } catch {}
    })
    await page.route('**/v2/materials/diagnose', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: '1000', message: 'ok', data: mockOkResponse() }),
      })
    })

    await page.goto(`/orders/${ORDER_NO}/precheck?countryCode=${COUNTRY}&visaType=${VISA}&materialIds=${MATERIAL_IDS.join(',')}&fields=eyJ9`)
    await expect(page.locator('[data-testid="precheck-continue-btn"]')).toBeVisible({ timeout: 10000 })
    await page.locator('[data-testid="precheck-continue-btn"]').click()
    await page.waitForURL('**/rpa/submit**', { timeout: 5000 })
    expect(page.url()).toContain('/rpa/submit')
  })

  // W51: 流水覆盖期不足 + 月入低 — 模拟后端 bank_statement_parser 的输出
  test('renders bank.completeness issues from real backend shape', async ({ page, context }) => {
    await context.addInitScript(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          token: 'fake-jwt',
          accessToken: 'fake-jwt',
          refreshToken: 'fake-refresh',
          user: { id: 1, email: 'demo@htex.com', name: 'Demo' },
        }))
      } catch {}
    })
    // 模拟 visa_diagnoser 看到 bank mtype 的 ocr_result 后输出的完整 shape
    const bankIssuesPayload = {
      overall_risk: 'medium',
      risk_score: 0.35,
      summary: '美国旅游签证申请基本可行,但有 2 项建议优化。',
      issues: [
        {
          code: 'bank.coverage_short',
          severity: 'warning',
          title: '银行流水仅覆盖 2 个月',
          title_key: 'diagnose.bank_coverage_short_title',
          detail: '识别出来的交易横跨 2 个月,大多数使馆建议提供最近 3-6 个月的银行流水。',
          detail_key: 'diagnose.bank_coverage_short_detail',
          fix_suggestion: '请上传近 3-6 个月的银行流水(含本月)。',
          fix_key: 'diagnose.bank_coverage_short_fix',
          related_material_id: MATERIAL_IDS[0],
          params: { months: 2 },
        },
        {
          code: 'bank.income_low',
          severity: 'warning',
          title: '月均收入偏低',
          title_key: 'diagnose.bank_income_low_title',
          detail: '识别到的月均收入约 ¥1,500,签证官通常会要求补充存款证明。',
          detail_key: 'diagnose.bank_income_low_detail',
          fix_suggestion: '建议同步上传:存款证明 / 房产证 / 资助人收入证明。',
          fix_key: 'diagnose.bank_income_low_fix',
          related_material_id: MATERIAL_IDS[0],
          params: { monthly_income: 1500.0 },
        },
      ],
      positives: ['护照有效期充足 (2030-12-31, 约 56 个月)', '已识别 12 条交易记录'],
      policy_refs: ['https://travel.state.gov/content/travel.html'],
      rule_count: 7,
    }
    await page.route('**/v2/materials/diagnose', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: '1000', message: 'ok', data: bankIssuesPayload }),
      })
    })

    await page.goto(`/orders/${ORDER_NO}/precheck?countryCode=${COUNTRY}&visaType=${VISA}&materialIds=${MATERIAL_IDS.join(',')}&fields=eyJ9`)
    await expect(page.locator('[data-testid="precheck-risk-badge"]')).toBeVisible({ timeout: 10000 })

    // 两个 issue 都渲染
    await expect(page.locator('[data-testid="precheck-issue-bank.coverage_short"]')).toBeVisible()
    await expect(page.locator('[data-testid="precheck-issue-bank.income_low"]')).toBeVisible()

    // positives 包含交易识别
    await expect(page.locator('[data-testid="precheck-positives"]')).toContainText('12 条交易')

    // 截图留证
    await page.screenshot({ path: 'tests/e2e/screenshots/order-precheck-bank-issues.png', fullPage: true })
  })

  // W52: 工资断档 + 余额不足行程预算 — 模拟后端新的两个规则
  test('renders bank.income_gap + bank.balance_coverage issues', async ({ page, context }) => {
    await context.addInitScript(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          token: 'fake-jwt',
          accessToken: 'fake-jwt',
          refreshToken: 'fake-refresh',
          user: { id: 1, email: 'demo@htex.com', name: 'Demo' },
        }))
      } catch {}
    })
    const payload = {
      overall_risk: 'medium',
      risk_score: 0.45,
      summary: '美国旅游签证申请基本可行,但有 2 项建议优化。',
      issues: [
        {
          code: 'bank.income_gap',
          severity: 'warning',
          title: '银行流水出现连续 2 个月无工资入账',
          title_key: 'diagnose.bank_income_gap_title',
          detail: '识别出 2 个月(2024-11 → 2024-12)未收到任何工资/入账记录,签证官可能质疑经济稳定性。',
          detail_key: 'diagnose.bank_income_gap_detail',
          fix_suggestion: '若是换工作/失业,建议提供:离职证明、新公司 offer、补贴信 (资助人/家人);若是留学/休学,提供在读证明。',
          fix_key: 'diagnose.bank_income_gap_fix',
          related_material_id: MATERIAL_IDS[0],
          params: { gap_months: 2, start_month: '2024-11', end_month: '2024-12', gap_count: 1 },
        },
        {
          code: 'bank.balance_coverage',
          severity: 'warning',
          title: '余额不足以覆盖行程预算',
          title_key: 'diagnose.bank_balance_coverage_title',
          detail: '识别到的账户余额约 ¥5,000,按 10 天行程粗估预算约 ¥19,000 (机票+酒店+餐食+杂费),余额 < 预算,签证官可能怀疑支付能力。',
          detail_key: 'diagnose.bank_balance_coverage_detail',
          fix_suggestion: '建议补充存款证明 / 资产证明 (房/车/理财),或缩短行程 / 降低酒店规格。',
          fix_key: 'diagnose.bank_balance_coverage_fix',
          related_material_id: MATERIAL_IDS[0],
          params: { ending_balance: 5000.0, budget_total: 19000.0, ratio: 0.26, stay_days: 10 },
        },
      ],
      positives: ['护照有效期充足', '银行流水覆盖 6 个月'],
      policy_refs: ['https://travel.state.gov/content/travel.html'],
      rule_count: 9,
    }
    await page.route('**/v2/materials/diagnose', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: '1000', message: 'ok', data: payload }),
      })
    })

    await page.goto(`/orders/${ORDER_NO}/precheck?countryCode=${COUNTRY}&visaType=${VISA}&materialIds=${MATERIAL_IDS.join(',')}&fields=eyJ9`)
    await expect(page.locator('[data-testid="precheck-risk-badge"]')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('[data-testid="precheck-issue-bank.income_gap"]')).toBeVisible()
    await expect(page.locator('[data-testid="precheck-issue-bank.balance_coverage"]')).toBeVisible()
    // income_gap 标题里有"2 个月"
    await expect(page.locator('[data-testid="precheck-issue-bank.income_gap"]')).toContainText('2 个月')
    // balance_coverage 标题里有"余额"
    await expect(page.locator('[data-testid="precheck-issue-bank.balance_coverage"]')).toContainText('余额')

    await page.screenshot({ path: 'tests/e2e/screenshots/order-precheck-income-gap-balance.png', fullPage: true })
  })
})
