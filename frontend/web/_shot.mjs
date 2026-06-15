// 临时截图脚本(非测试)— 仅用于 Story 1.1.1b 截图验证
// 用法: node /tmp/_shot.mjs
import { chromium } from '@playwright/test'

const url = process.argv[2] || 'http://127.0.0.1:5173/materials'
const out = process.argv[3] || '/Users/stephen/Desktop/签证项目/frontend/web/screenshots/a-1.1.1b/materials.png'

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 1
})
const page = await ctx.newPage()

// 预置登录态:在 localStorage 塞一个 fake JWT,绕过 /login guard
await page.addInitScript(() => {
  localStorage.setItem('visa.auth', JSON.stringify({
    user: { id: 'u_demo', phone: '13800138000', phoneCountry: '+86', nickname: 'Demo', languagePref: 'zh-CN', status: 'active', createdAt: new Date().toISOString() },
    accessToken: 'demo.access.token',
    refreshToken: 'demo.refresh.token'
  }))
})

try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 })
  await page.waitForTimeout(1200)
  await page.screenshot({ path: out, fullPage: false })
  console.log('OK', out)
} catch (e) {
  console.error('FAIL', e.message)
  process.exitCode = 1
} finally {
  await browser.close()
}