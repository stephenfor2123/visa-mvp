// 一次性截图脚本 — A-3.2.2a cycle 5 cancel 弹窗 + 终态
// 用法:
//   1) 后台启 vite dev (npm run dev)
//   2) node frontend/web/_shot_a322a.mjs
// 3) 输出: screenshots/a-3.2.2a/orderdetail-cancel-confirm.png + orderdetail-cancelled.png
import { chromium } from '@playwright/test'

const ORDER_NO = 'V2-20260612-222201'
const BASE = 'http://127.0.0.1:5173'
const OUT_DIR = '/Users/stephen/Desktop/签证项目/frontend/web/screenshots/a-3.2.2a'

function makeEnvelope(status) {
  return {
    code: '1000',
    message: 'OK',
    data: {
      order_no: ORDER_NO,
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

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 })
const page = await ctx.newPage()

// 注 auth + lang,绕过 router guard
await page.addInitScript(() => {
  localStorage.setItem('visa.lang', 'zh-CN')
  localStorage.setItem('visa.auth', JSON.stringify({
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
  }))
})

// 装 stub: 初始 created, cancel API 改 state 到 cancelled
const getPattern = new RegExp(`/api/v2/orders/${ORDER_NO}(\\?.*)?$`)
const cancelPattern = new RegExp(`/api/v2/orders/${ORDER_NO}/cancel$`)
let state = { status: 'created' }
await page.route(getPattern, async (route) => {
  if (route.request().method() !== 'GET') { await route.continue(); return }
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(makeEnvelope(state.status)) })
})
await page.route(cancelPattern, async (route) => {
  state.status = 'cancelled'
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: '1000', message: 'OK', data: { order_no: ORDER_NO, status: 'cancelled', cancelled_at: new Date().toISOString() } }) })
})

try {
  // ============ 截图 1: cancel 弹窗打开状态 ============
  await page.goto(`${BASE}/orders/${ORDER_NO}`, { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForSelector('[data-testid="orderdetail-cancel-btn"]', { timeout: 10000 })
  await page.getByTestId('orderdetail-cancel-btn').click()
  await page.waitForSelector('[data-testid="orderdetail-cancel-modal"]', { state: 'visible', timeout: 5000 })
  await page.waitForTimeout(400)  // modal 动画稳定
  const modal = page.getByTestId('orderdetail-cancel-modal')
  await modal.scrollIntoViewIfNeeded()
  const bbox1 = await modal.boundingBox()
  if (bbox1) {
    await page.screenshot({
      path: `${OUT_DIR}/orderdetail-cancel-confirm.png`,
      clip: { x: 0, y: 0, width: 1280, height: 900 }
    })
  } else {
    await page.screenshot({ path: `${OUT_DIR}/orderdetail-cancel-confirm.png`, fullPage: false })
  }
  console.log('OK', `${OUT_DIR}/orderdetail-cancel-confirm.png`)

  // ============ 截图 2: cancelled 终态 (5 态时间线) ============
  // 确认取消 → 弹窗关闭 + 状态变 cancelled
  await page.getByTestId('orderdetail-cancel-yes').click()
  await page.waitForSelector('[data-testid="orderdetail-cancel-modal"]', { state: 'hidden', timeout: 5000 })
  await page.waitForSelector('[data-testid="orderdetail-tl-cancelled"]', { state: 'visible', timeout: 5000 })
  await page.waitForTimeout(400)
  const tl = page.getByTestId('orderdetail-timeline')
  await tl.scrollIntoViewIfNeeded()
  await page.screenshot({
    path: `${OUT_DIR}/orderdetail-cancelled.png`,
    clip: { x: 0, y: 0, width: 1280, height: 900 }
  })
  console.log('OK', `${OUT_DIR}/orderdetail-cancelled.png`)
} catch (e) {
  console.error('FAIL', e.message)
  process.exitCode = 1
} finally {
  await browser.close()
}
