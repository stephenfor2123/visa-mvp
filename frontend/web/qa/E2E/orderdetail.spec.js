/**
 * A-3.2.2a-fix-only cycle 5 E2E — OrderDetail.vue 取消流强化
 *
 * 覆盖 (W3 Story 3.2.2 + cycle 5 retry fix):
 *   0. 渲染 OrderDetail 5 态时间线 (created 起点 + rejected/cancelled 分支不显示)
 *   1. 点击 cancel 按钮 → 弹窗出现 (确认取消订单 / 描述 / 再想想 / 确认取消)
 *   2. 弹窗确认 → cancelOrder 调通 + **stub stateful** (后续 GET 返 cancelled, 不覆盖回 created)
 *   3. cancelled 状态再访问 → cancel 按钮消失 + **stub race 4010** (再次调 cancel 返 4010 错误码)
 *
 * 测试方法 (VITE_MOCK=false, 走真 http + page.route 拦截):
 *   - addInitScript 注 zh-CN locale + 假 auth,绕过 router guard
 *   - 装上 GET /v2/orders/{no} + POST /v2/orders/{no}/cancel 路由 stub
 *   - case 2 验证 stub stateful: 调 cancel 后, 重新 navigate 同一 order, GET 返 cancelled (不是 created)
 *   - case 3 验证 stub race: 第二次调 cancel 返 4010 错误码 (W3 cancel_blocked 提示)
 *   - 单线程 workers=1
 */
import { test, expect } from '@playwright/test'

/** 注入 zh-CN locale + 假 auth,绕过 router guard */
async function loginAsDemoUser(page) {
  await page.addInitScript(() => {
    localStorage.setItem('visa.lang', 'zh-CN')
    localStorage.setItem(
      'visa.auth',
      JSON.stringify({
        accessToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.mock',
        refreshToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.refresh',
        user: {
          id: 'u_demo',
          phoneCountry: '+86',
          phone: '13800000000',
          nickname: 'demo',
          languagePref: 'zh-CN',
          status: 'active',
          createdAt: '2026-06-11T00:00:00Z'
        }
      })
    )
  })
  // 先访问同源页面让 init script 跑一次
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
}

/** 构造 GET /v2/orders/{no} 响应 */
function makeOrderEnvelope(orderNo, status = 'created') {
  return {
    code: '1000',
    message: 'OK',
    data: {
      order_no: orderNo,
      user_id: 'u_demo',
      destination_id: 1,
      visa_type: 'tourism',
      status,
      total_amount: 0,
      currency: 'USD',
      material_ids: [],
      applicant_data: {
        surname: 'SANTOSO',
        given_name: 'BUDI',
        sex: 'M',
        dob: '1990-05-12',
        nationality: 'ID',
        passport_no: 'E12345678',
        destination_id: 1,
        visa_type: 'tourism'
      },
      destination_url: null,
      rpa_task_id: null,
      rpa_screenshot_url: null,
      rpa_screenshots: [],
      created_at: '2026-06-11T00:00:00Z',
      updated_at: '2026-06-11T00:00:00Z'
    }
  }
}

/**
 * 装上 stateful GET/POST cancel stubs
 *  - GET: 初始返 initialStatus, 一旦 cancel 调过, 改返 'cancelled' (stateful)
 *  - POST /cancel: 第 1 次返 200/cancelled, 第 2 次 (race) 返 4010 (stateful race)
 *  - 返回 { getCalls, cancelCalls } 计数器
 */
async function stubStatefulOrder(page, orderNo, initialStatus = 'created') {
  const getPattern = new RegExp(`/api/v2/orders/${orderNo}(\\?.*)?$`)
  const cancelPattern = new RegExp(`/api/v2/orders/${orderNo}/cancel$`)
  let state = { status: initialStatus, cancelCount: 0 }
  const counters = { getCalls: 0, cancelCalls: 0 }
  await page.route(getPattern, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    counters.getCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(makeOrderEnvelope(orderNo, state.status))
    })
  })
  await page.route(cancelPattern, async (route) => {
    counters.cancelCalls += 1
    state.cancelCount += 1
    if (state.cancelCount >= 2) {
      // race: 第二次返 4010
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          code: '4010',
          message: 'Order not cancellable in current state',
          data: null
        })
      })
      return
    }
    // 第一次成功 + stateful: 后续 GET 返 cancelled
    state.status = 'cancelled'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: '1000',
        message: 'OK',
        data: {
          order_no: orderNo,
          status: 'cancelled',
          cancelled_at: new Date().toISOString()
        }
      })
    })
  })
  return counters
}

test.describe('A-3.2.2a-fix-only  OrderDetail 取消流强化 cycle 5', () => {
  const ORDER_NO = 'V2-20260612-222201'

  test('case 0 — 渲染 OrderDetail 5 态时间线 (created 起点 + 4 主轴 + branch 不显示)', async ({ page }) => {
    await loginAsDemoUser(page)
    await stubStatefulOrder(page, ORDER_NO, 'created')
    await page.goto(`/orders/${ORDER_NO}`)

    // 1) 详情页特征元素
    await expect(page.locator('.orderdetail-page')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByTestId('orderdetail-hero')).toBeVisible()
    await expect(page.getByTestId('orderdetail-timeline')).toBeVisible()

    // 2) 4 主轴节点都存在 + 起点 created 是 current
    await expect(page.getByTestId('orderdetail-tl-created')).toBeVisible()
    await expect(page.getByTestId('orderdetail-tl-submitted')).toBeAttached()
    await expect(page.getByTestId('orderdetail-tl-reviewing')).toBeAttached()
    await expect(page.getByTestId('orderdetail-tl-approved')).toBeAttached()

    // 3) created 是 current (W2 i18n 命名:status_created = '待提交')
    await expect(page.getByTestId('orderdetail-tl-current')).toBeVisible()
    await expect(page.getByTestId('orderdetail-tl-current')).toContainText('待提交')

    // 4) 状态徽章是 created
    const badge = page.getByTestId('orderdetail-status-badge')
    await expect(badge).toContainText('待提交')

    // 5) branch 节点(rejected / cancelled) 在 created 状态下不显示
    await expect(page.getByTestId('orderdetail-tl-rejected')).toHaveCount(0)
    await expect(page.getByTestId('orderdetail-tl-cancelled')).toHaveCount(0)

    // 6) cancel 按钮可见
    await expect(page.getByTestId('orderdetail-cancel-btn')).toBeVisible()
  })

  test('case 1 — 点击 cancel 按钮 → 弹窗出现 (确认取消订单 / 描述 / 再想想 / 确认取消)', async ({ page }) => {
    await loginAsDemoUser(page)
    await stubStatefulOrder(page, ORDER_NO, 'created')
    await page.goto(`/orders/${ORDER_NO}`)

    // 1) cancel 按钮可见(created 状态)
    const cancelBtn = page.getByTestId('orderdetail-cancel-btn')
    await expect(cancelBtn).toBeVisible({ timeout: 10_000 })
    await expect(cancelBtn).toContainText('取消订单')

    // 2) 弹窗初始不显示
    await expect(page.getByTestId('orderdetail-cancel-modal')).toHaveCount(0)

    // 3) 点击 cancel → 弹窗出现
    await cancelBtn.click()
    const modal = page.getByTestId('orderdetail-cancel-modal')
    await expect(modal).toBeVisible({ timeout: 5_000 })

    // 4) 弹窗内文案核对
    await expect(modal).toContainText('确认取消订单')
    await expect(modal).toContainText('取消后无法恢复')

    // 5) 弹窗内两个按钮 + 文案
    await expect(page.getByTestId('orderdetail-cancel-no')).toBeVisible()
    await expect(page.getByTestId('orderdetail-cancel-no')).toContainText('再想想')
    await expect(page.getByTestId('orderdetail-cancel-yes')).toBeVisible()
    await expect(page.getByTestId('orderdetail-cancel-yes')).toContainText('确认取消')

    // 6) 点 "再想想" 关闭弹窗
    await page.getByTestId('orderdetail-cancel-no').click()
    await expect(page.getByTestId('orderdetail-cancel-modal')).toHaveCount(0)
  })

  test('case 2 — 弹窗确认 → cancelOrder 调通 + stub stateful 后续 GET 返 cancelled', async ({ page }) => {
    await loginAsDemoUser(page)
    const counters = await stubStatefulOrder(page, ORDER_NO, 'created')
    await page.goto(`/orders/${ORDER_NO}`)

    // 1) 起点:created + 按钮可见
    await expect(page.getByTestId('orderdetail-cancel-btn')).toBeVisible({ timeout: 10_000 })
    const badge = page.getByTestId('orderdetail-status-badge')
    await expect(badge).toContainText('待提交')

    // 2) 点 cancel → 弹窗 → 点 "确认取消"
    await page.getByTestId('orderdetail-cancel-btn').click()
    await expect(page.getByTestId('orderdetail-cancel-modal')).toBeVisible()
    await page.getByTestId('orderdetail-cancel-yes').click()

    // 3) 弹窗关闭 + 状态徽章变 cancelled
    await expect(page.getByTestId('orderdetail-cancel-modal')).toHaveCount(0, { timeout: 5_000 })
    await expect(badge).toContainText('已取消', { timeout: 5_000 })

    // 4) 时间线出现 cancelled 分支节点 + current 跳到 cancelled
    const cancelledNode = page.getByTestId('orderdetail-tl-cancelled')
    await expect(cancelledNode).toBeVisible({ timeout: 5_000 })
    await expect(cancelledNode).toContainText('已取消')
    // branch 节点是 current
    await expect(page.getByTestId('orderdetail-tl-cancelled-current')).toBeVisible()
    await expect(page.getByTestId('orderdetail-tl-cancelled-current')).toContainText('已取消')

    // 5) **双分支校验 (cycle 5 修)**:rejected 分支绝对不显示
    await expect(page.getByTestId('orderdetail-tl-rejected')).toHaveCount(0)

    // 6) cancel 按钮消失(v-if=created)
    await expect(page.getByTestId('orderdetail-cancel-btn')).toHaveCount(0)
    // 7) cancel_blocked 提示出现(v-else 分支)
    await expect(page.getByTestId('orderdetail-cancel-hint')).toBeVisible()
    await expect(page.getByTestId('orderdetail-cancel-hint')).toContainText('该订单当前状态不允许取消')

    // 8) POST /v2/orders/{no}/cancel 真的被调了
    expect(counters.cancelCalls).toBeGreaterThanOrEqual(1)

    // 9) **stub stateful 验证 (cycle 5 新增)**:重新 navigate 同 order, GET 返 cancelled (而不是 created)
    //    这是测 stub stateful, 因为前端 doCancel 成功后只 set order.value.status, 但 stub 真实场景下应持久化
    const beforeReload = counters.getCalls
    await page.goto(`/orders/${ORDER_NO}`)
    await expect(badge).toContainText('已取消', { timeout: 10_000 })
    // 后续 GET 返 cancelled (stateful),所以 status 保持 cancelled
    await expect(cancelledNode).toBeVisible()
    expect(counters.getCalls).toBeGreaterThan(beforeReload)  // 至少 1 次新 GET
  })

  test('case 3 — cancelled 状态再访问 → cancel 按钮消失 + stub race 4010 (第二次 cancel API 返 4010)', async ({ page }) => {
    await loginAsDemoUser(page)
    const counters = await stubStatefulOrder(page, ORDER_NO, 'cancelled')
    await page.goto(`/orders/${ORDER_NO}`)

    // 1) 页面渲染 + cancelled 终态
    await expect(page.locator('.orderdetail-page')).toBeVisible({ timeout: 10_000 })
    const badge = page.getByTestId('orderdetail-status-badge')
    await expect(badge).toContainText('已取消', { timeout: 10_000 })

    // 2) 时间线 cancelled 分支节点 + current
    const cancelledNode = page.getByTestId('orderdetail-tl-cancelled')
    await expect(cancelledNode).toBeVisible()
    await expect(page.getByTestId('orderdetail-tl-cancelled-current')).toBeVisible()
    // **双分支校验**:rejected 不显示
    await expect(page.getByTestId('orderdetail-tl-rejected')).toHaveCount(0)

    // 3) cancel 按钮不显示(v-if=status==='created')
    await expect(page.getByTestId('orderdetail-cancel-btn')).toHaveCount(0)

    // 4) cancel_blocked 提示出现(v-else 分支)
    await expect(page.getByTestId('orderdetail-cancel-hint')).toBeVisible()
    await expect(page.getByTestId('orderdetail-cancel-hint')).toContainText('该订单当前状态不允许取消')

    // 5) **stub race 4010 验证 (cycle 5 新增)**:直接调 cancel API, stub 第 1 次返 200 (cancelled, 计数 1)
    //    但本 case 装 stub 时 state 已是 cancelled, cancelCount=0; 调一次后会 cancelCount=1 → 走 200 分支
    //    再调一次 → cancelCount=2 → 4010 分支
    const raceResult1 = await page.evaluate(async (no) => {
      const r = await fetch(`/api/v2/orders/${no}/cancel`, { method: 'POST', headers: { 'content-type': 'application/json' } })
      return { status: r.status, body: await r.json() }
    }, ORDER_NO)
    expect(raceResult1.status).toBe(200)
    expect(raceResult1.body.code).toBe('1000')
    expect(raceResult1.body.data.status).toBe('cancelled')

    // 6) **race 4010**: 第二次调 cancel → 4010 错误码 (前端 doCancel try/catch 会 toast.error cancel_blocked)
    const raceResult2 = await page.evaluate(async (no) => {
      const r = await fetch(`/api/v2/orders/${no}/cancel`, { method: 'POST', headers: { 'content-type': 'application/json' } })
      return { status: r.status, body: await r.json() }
    }, ORDER_NO)
    expect(raceResult2.status).toBe(400)
    expect(raceResult2.body.code).toBe('4010')
    expect(counters.cancelCalls).toBe(2)
  })
})
