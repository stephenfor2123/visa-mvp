// A-W9-2 专用截图脚本
// 用法: node _shot_w9_2.mjs
//
// 截 2 张:
//   1) ordernew-with-affiliate.png   OrderNew 带 aff_code 自动填 (URL ?aff=AFF001)
//   2) orderdetail-with-commission.png  OrderDetail 带 commission mock 数据
//
// Commission 数据用 page.evaluate 注入 localStorage 兜底(详情页会
// 调 /api/v2/affiliate/commission/{no} 静默,后端 mock-only)
// 改为: 用 localStorage 给 order 注入 aff_code, 同时 mock commission 走 page.route

import { chromium } from '@playwright/test'

const BASE = 'http://127.0.0.1:5173'
const OUT_DIR = '/Users/stephen/Desktop/签证项目/frontend/web/screenshots/a-w9-2'

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 1
})

// 预置登录态 + 推广点击 LS (OrderNew 会读 affiliate.js 的 loadPendingClick)
await pageInit(ctx)

try {
  // ---------- 截图 1: OrderNew 带 aff_code 自动填 ----------
  const page1 = await ctx.newPage()
  // 走 /orders/new?material_ids=mat_ocr_002&country=US&visa_type=tourism&aff=AFF001
  // 触发 URL 自动填 affiliate.code
  await page1.goto(`${BASE}/orders/new?material_ids=mat_ocr_002&country=US&visa_type=tourism&aff=AFF001&click=cid_demo_w9_2`, {
    waitUntil: 'domcontentloaded', timeout: 15000
  })
  await page1.waitForTimeout(1500)  // wait i18n hydrate + autoFillAffiliate + OCR prefill
  await page1.waitForSelector('[data-testid="ordernew-aff-code"]', { timeout: 5000 })
  // 滚到 aff_code 字段, 确保它在视图里 (basic section 末尾)
  await page1.locator('[data-testid="ordernew-aff-code"]').scrollIntoViewIfNeeded()
  await page1.waitForTimeout(400)
  const out1 = `${OUT_DIR}/ordernew-with-affiliate.png`
  await page1.screenshot({ path: out1, fullPage: true })
  console.log('OK', out1)
  await page1.close()

  // ---------- 截图 2: OrderDetail 带 commission mock ----------
  // B-W8-4 端点 /api/v2/affiliate/commission/{order_id} 需要 order 已 attribute 过
  // 演示场景: 预置 LS 给 visa.orders 加一笔带 aff_code 的订单,然后用 page.route
  // 拦截 commission API 返 mock data
  const page2 = await ctx.newPage()

  // route 拦截 commission API
  await page2.route('**/api/v2/affiliate/commission/**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: '1000',
        message: 'OK',
        data: {
          order_id: 'V2-20260612-DEMO01',
          commission_id: 'cm_W9-2_demo',
          commission_amount_cents: 1250,  // $12.50 (5% of $250)
          commission_rate: '0.05',
          currency: 'USD',
          partner_id: 'PARTNER001',
          computed_at: new Date().toISOString()
        }
      })
    })
  })
  // 也拦截 getOrder 返带 aff_code 的订单
  await page2.route('**/api/v2/orders/V2-20260612-DEMO01', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: '1000',
        message: 'OK',
        data: {
          order_no: 'V2-20260612-DEMO01',
          user_id: 'u_demo',
          destination_id: 1,
          visa_type: 'tourism',
          status: 'created',
          total_amount: 25000,  // $250.00
          currency: 'USD',
          material_ids: [101, 102],
          applicant_data: { surname: 'SANTOSO', given_name: 'BUDI' },
          aff_code: 'PARTNER001',
          click_id: 'cid_demo_w9_2',
          created_at: new Date(Date.now() - 3600 * 1000).toISOString(),
          updated_at: new Date().toISOString()
        }
      })
    })
  })

  await page2.goto(`${BASE}/orders/V2-20260612-DEMO01`, {
    waitUntil: 'domcontentloaded', timeout: 15000
  })
  await page2.waitForTimeout(2000)  // wait order load + commission load
  await page2.waitForSelector('[data-testid="orderdetail-affiliate-pill"]', { timeout: 5000 })
  // 滚到 affiliate pill 区域
  await page2.locator('[data-testid="orderdetail-affiliate-pill"]').scrollIntoViewIfNeeded()
  await page2.waitForTimeout(400)
  const out2 = `${OUT_DIR}/orderdetail-with-commission.png`
  await page2.screenshot({ path: out2, fullPage: true })
  console.log('OK', out2)
  await page2.close()
} catch (e) {
  console.error('FAIL', e.message)
  process.exitCode = 1
} finally {
  await browser.close()
}

async function pageInit(ctx) {
  await ctx.addInitScript(() => {
    localStorage.setItem('visa.auth', JSON.stringify({
      user: { id: 'u_demo', phone: '13800138000', phoneCountry: '+86', nickname: 'Demo', languagePref: 'zh-CN', status: 'active', createdAt: new Date().toISOString() },
      accessToken: 'demo.access.token',
      refreshToken: 'demo.refresh.token'
    }))
    // OrderNew 自动填 affiliate 来源: 预置一个 pending click (LS 兜底路径)
    localStorage.setItem('visa.aff.last_click', JSON.stringify({
      click_id: 'cid_ls_w9_2_demo',
      aff_code: 'PARTNER001',
      ts: Date.now()
    }))
    // 预置一个 partner 等待的订单 (V2 mock orders)
    const demoOrder = {
      order_no: 'V2-20260612-DEMO01',
      user_id: 'u_demo',
      destination_id: 1,
      visa_type: 'tourism',
      status: 'created',
      total_amount: 25000,
      currency: 'USD',
      material_ids: [101, 102],
      applicant_data: { surname: 'SANTOSO', given_name: 'BUDI' },
      aff_code: 'PARTNER001',
      click_id: 'cid_ls_w9_2_demo',
      rpa_screenshots: [
        'https://placehold.co/400x240/EAF0FE/2D5BFF?text=RPA+Step+1'
      ],
      created_at: new Date(Date.now() - 3600 * 1000).toISOString(),
      updated_at: new Date().toISOString()
    }
    const map = { 'V2-20260612-DEMO01': demoOrder }
    localStorage.setItem('visa.orders', JSON.stringify(map))
  })
}
