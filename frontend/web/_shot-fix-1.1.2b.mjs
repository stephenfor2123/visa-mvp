// A-fix-1.1.2b: 截图验证 error severity 真的渲染了
import { chromium } from '@playwright/test'
import fs from 'node:fs'

const url = 'http://localhost:5173/materials/validate?material_ids=mat_a1,mat_b2,mat_c3,mat_d4,mat_e5'
const outDir = '/Users/stephen/Desktop/签证项目/frontend/web/screenshots/a-fix-1.1.2b'
fs.mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errs = []
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message))
page.on('console', (msg) => {
  if (msg.type() === 'error') errs.push('console.error: ' + msg.text())
})
// seed fake auth so router allows /materials/validate
await page.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded', timeout: 20000 })
await page.evaluate(() => {
  localStorage.setItem('visa.auth', JSON.stringify({
    user: { id: 'u_demo', phone: '13800000000', nickname: 'demo' },
    accessToken: 'demo-token',
    refreshToken: 'demo-refresh'
  }))
})
page.on('request', (req) => {
  if (req.url().includes('/api/')) console.log('API req:', req.method(), req.url().replace('http://localhost:5173', ''))
})
page.on('response', (res) => {
  if (res.url().includes('/api/')) console.log('API res:', res.status(), res.url().replace('http://localhost:5173', ''))
})
await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 })
await page.waitForTimeout(2000)
console.log('Final URL:', page.url())
console.log('Page title:', await page.title())
await page.screenshot({ path: `${outDir}/materials-validate-desktop.png`, fullPage: false })
await page.screenshot({ path: `${outDir}/materials-validate-full.png`, fullPage: true })
const counts = await page.evaluate(() => {
  const errorItems = document.querySelectorAll('[class*="item--error"]')
  const warnItems = document.querySelectorAll('[class*="item--warning"]')
  const passItems = document.querySelectorAll('[class*="item--pass"]')
  return {
    errorItems: errorItems.length,
    warnItems: warnItems.length,
    passItems: passItems.length,
    summaryText: document.querySelector('[data-testid="validate-summary"]')?.textContent?.trim() || null,
    failCard: document.querySelector('.stat-card--fail .stat-card__num')?.textContent?.trim() || null,
    warnCard: document.querySelector('.stat-card--warn .stat-card__num')?.textContent?.trim() || null,
    passCard: document.querySelector('.stat-card--pass .stat-card__num')?.textContent?.trim() || null,
    continueDisabled: document.querySelector('[data-testid="validate-continue"]')?.disabled
  }
})
console.log('DOM check:', JSON.stringify(counts, null, 2))
console.log('Errors:', errs.length === 0 ? 'NONE' : errs.join('\n'))
await browser.close()
