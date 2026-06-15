/* eslint-disable */
// A-1.2.2a 截图脚本:5 态时间线 + WS 状态
// 用法:node /Users/stephen/Desktop/签证项目/frontend/web/_shot-orderdetail.mjs [status]
//  - status: created | submitted | reviewing | approved | rejected (默认 created)
//  不传 status 就 5 态全截

import { chromium } from '@playwright/test'
import fs from 'node:fs'

const BASE = 'http://127.0.0.1:5173'
const OUT_DIR = '/Users/stephen/Desktop/签证项目/frontend/web/screenshots/a-1.2.2a'
fs.mkdirSync(OUT_DIR, { recursive: true })

const MOCK_USER = {
  user: {
    id: 'u_demo',
    phone: '13800138000',
    phoneCountry: '+86',
    nickname: '签证用户_demo',
    languagePref: 'zh-CN',
    status: 'active',
    createdAt: new Date().toISOString()
  },
  accessToken: 'mock.access.' + Date.now(),
  refreshToken: 'mock.refresh.' + Date.now()
}

const STATUSES = ['created', 'submitted', 'reviewing', 'approved', 'rejected']

// 5 个订单号,每个对应一个状态
function genOrderNo(status) {
  const d = new Date()
  const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
  const seq = String(Math.floor(Math.random() * 1_000_000)).padStart(6, '0')
  return `V2-${ymd}-${seq}-${status.slice(0, 3).toUpperCase()}`
}

// 在 page evaluate 里把 5 个订单 + 状态注入 localStorage
async function seedOrders(page) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.evaluate(({ user, orders }) => {
    localStorage.setItem('visa.auth', JSON.stringify(user))
    localStorage.setItem('visa.orders', JSON.stringify(orders))
  }, { user: MOCK_USER, orders: window.__seedOrders || {} })
}

// 浏览器内构造 5 个 mock order 并注入 localStorage
async function injectSeedOrders(page) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 20000 })
  const seed = await page.evaluate(({ user, statuses }) => {
    localStorage.setItem('visa.auth', JSON.stringify(user))
    const map = {}
    const d = new Date()
    const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
    for (const s of statuses) {
      const seq = String(Math.floor(Math.random() * 1_000_000)).padStart(6, '0')
      const orderNo = `V2-${ymd}-${seq}-${s.slice(0, 3).toUpperCase()}`
      const baseOrder = {
        order_no: orderNo,
        user_id: 'u_demo',
        destination_id: 1,
        visa_type: 'tourism',
        status: s,
        total_amount: 89.0,
        currency: 'USD',
        material_ids: [101, 102, 103],
        applicant_data: {
          surname: 'SANTOSO',
          given_name: 'BUDI',
          sex: 'M',
          dob: '1990-05-12',
          nationality: 'ID',
          passport_no: 'E12345678',
          passport_expiry: '2031-08-22',
          arrival_date: '2026-07-20',
          departure_date: '2026-07-30',
          stay_days: 10,
          emergency_contact: { name: 'SARI WIJAYA', phone: '+62 81345678901', relation: 'spouse' }
        },
        destination_url: null,
        rpa_task_id: s !== 'created' ? `rpa-${s}-${seq}` : null,
        rpa_screenshot_url: null,
        rpa_screenshots: [],
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
        updated_at: new Date().toISOString()
      }
      // 给 submitted/reviewing/approved/rejected 加 RPA 截图
      if (['submitted', 'reviewing', 'approved', 'rejected'].includes(s)) {
        baseOrder.rpa_screenshots = [
          'https://placehold.co/400x240/EAF0FE/2D5BFF?text=RPA+Step+1',
          'https://placehold.co/400x240/FEF3C7/D97706?text=RPA+Step+2',
          'https://placehold.co/400x240/DCFCE7/16A34A?text=RPA+Step+3'
        ]
      }
      if (s === 'approved') {
        baseOrder.visa_pdf_url = 'https://placehold.co/600x800/EAF0FE/2D5BFF?text=VISA+PDF'
        baseOrder.reviewed_at = new Date().toISOString()
      }
      if (s === 'rejected') {
        baseOrder.rejection_reason = {
          zh: '资料不完整:未提供近 6 个月的银行流水',
          en: 'Incomplete documents: missing last 6 months bank statement',
          id: 'Dokumen tidak lengkap: laporan bank 6 bulan terakhir hilang',
          vi: 'Hồ sơ chưa đầy đủ: thiếu sao kê ngân hàng 6 tháng gần nhất'
        }
        baseOrder.reviewed_at = new Date().toISOString()
      }
      map[orderNo] = baseOrder
    }
    localStorage.setItem('visa.orders', JSON.stringify(map))
    return map
  }, { user: MOCK_USER, statuses: STATUSES })
  return seed
}

const filterStatus = process.argv[2]
const toShoot = filterStatus ? [filterStatus] : STATUSES

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()

const consoleErrors = []
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push('console.error: ' + m.text()) })
page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message))

const seed = await injectSeedOrders(page)
console.log('[seed] orders:', Object.keys(seed))

for (const s of toShoot) {
  const orderNo = Object.keys(seed).find((k) => k.endsWith(`-${s.slice(0, 3).toUpperCase()}`))
  if (!orderNo) {
    console.log('[shot] no order for status', s)
    continue
  }
  const url = `${BASE}/orders/${orderNo}`
  console.log(`[shot] ${s} -> ${url}`)
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 })
  // 等数据加载
  try {
    await page.waitForSelector('[data-testid="orderdetail-timeline"]', { timeout: 5000 })
  } catch (e) {
    console.log(`[shot] ${s}: timeline not visible, continuing anyway`)
  }
  // 等 WS / polling tick 跑完一轮
  await page.waitForTimeout(800)
  const out = `${OUT_DIR}/orderdetail-${s}.png`
  await page.screenshot({ path: out, fullPage: false })
  console.log(`[shot] saved ${out}`)
  // 同时截一张 fullPage 备用
  await page.screenshot({ path: `${OUT_DIR}/orderdetail-${s}-full.png`, fullPage: true })
  console.log(`[shot] saved full ${OUT_DIR}/orderdetail-${s}-full.png`)
}

console.log('---console errors---')
console.log(consoleErrors.length === 0 ? 'NONE' : consoleErrors.join('\n'))

await browser.close()
