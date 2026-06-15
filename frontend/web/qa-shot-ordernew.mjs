/* eslint-disable */
// 截图脚本:打开 /orders/new 演示表单
import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'

const URL = process.env.URL || 'http://127.0.0.1:5173'
const OUT = process.argv[2] || '/Users/stephen/Desktop/签证项目/frontend/web/screenshots/ordernew.png'

const MOCK_USER = {
  user: {
    id: 'u_demo',
    phone: '13800138000',
    phoneCountry: '+86',
    nickname: '签证用户_demo',
    languagePref: 'zh-CN',
    status: 'active'
  },
  accessToken: 'mock.access.' + Date.now(),
  refreshToken: 'mock.refresh.' + Date.now()
}

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()

// 1) 注入登录态
await page.addInitScript(({ user }) => {
  localStorage.setItem('visa.auth', JSON.stringify(user))
}, { user: MOCK_USER })

const consoleMsgs = []
const errors = []
page.on('console', (msg) => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`))
page.on('pageerror', (e) => errors.push(String(e)))

// 2) 访问 /orders/new
const url = `${URL}/orders/new?material_ids=mat_demo_passport&country=US&visa_type=tourism`
console.log('[shot] goto', url)
await page.goto(url, { waitUntil: 'domcontentloaded' })
// 等待 redirect 解析
await page.waitForTimeout(1500)
console.log('[shot] final URL:', page.url())

// 3) 等表单出现
try {
  await page.waitForSelector('[data-testid="ordernew-section-basic"]', { timeout: 5000 })
  console.log('[shot] form section visible')
} catch (e) {
  console.log('[shot] form section NOT visible:', e.message)
}

await page.waitForTimeout(500)

// 4) 截图
await page.screenshot({ path: OUT, fullPage: false })
console.log('[shot] saved', OUT)

console.log('---console---')
for (const m of consoleMsgs) console.log(m)
console.log('---errors---')
for (const e of errors) console.log(e)

await browser.close()

