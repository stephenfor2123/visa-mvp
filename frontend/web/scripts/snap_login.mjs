import { chromium } from 'playwright'
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'zh-CN' })
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:5173/login')
await page.waitForSelector('[data-testid="login-password"] input', { timeout: 10000 })
// 整页截图,然后单独裁密码框
await page.screenshot({ path: '/tmp/login-full-closed.png', fullPage: true })
const pass = page.locator('[data-testid="login-password"]')
await pass.scrollIntoViewIfNeeded()
const box = await pass.boundingBox()
console.log('box:', JSON.stringify(box))
await page.screenshot({
  path: '/tmp/login-closed.png',
  clip: { x: Math.max(0, box.x - 20), y: Math.max(0, box.y - 30), width: Math.min(1280, box.width + 40), height: 90 }
})
await page.locator('[data-testid="login-password"] input').fill('Abc1234567')
await page.locator('[data-testid="login-password-toggle"]').click()
await page.waitForTimeout(150)
await page.screenshot({
  path: '/tmp/login-open.png',
  clip: { x: Math.max(0, box.x - 20), y: Math.max(0, box.y - 30), width: Math.min(1280, box.width + 40), height: 90 }
})
await browser.close()
console.log('done')
