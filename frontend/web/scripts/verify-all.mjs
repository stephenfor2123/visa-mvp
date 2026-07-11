import { chromium } from 'playwright'
const browser = await chromium.launch()
async function snap(url, out, opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: opts.height || 1800 }, locale: opts.locale || 'zh-CN' })
  const page = await ctx.newPage()
  await page.goto(url)
  await page.waitForTimeout(2200)
  if (opts.selector) {
    const t = await page.locator(opts.selector).first()
    if (await t.count()) {
      await t.scrollIntoViewIfNeeded()
      await page.waitForTimeout(300)
      await t.screenshot({ path: out })
    } else {
      await page.screenshot({ path: out, fullPage: true })
    }
  } else if (opts.collectCells) {
    const cells = await page.locator('[data-testid^="tp-day-city-from-"]').all()
    for (let i = 0; i < cells.length; i++) {
      const text = await cells[i].textContent()
      const cellVal = await page.locator(`[data-testid="tp-day-city-${i}"]`).inputValue().catch(() => null)
      console.log(`day ${i}: cell="${cellVal}" sub="${text?.trim()}"`)
    }
  } else {
    await page.screenshot({ path: out, fullPage: true })
  }
  await ctx.close()
}

// 财务页: US
await snap('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism&step=financial', '/tmp/fin-US.png', { selector: '.mtp' })
console.log('--- US financial saved')
// 财务页: VN
await snap('http://127.0.0.1:5173/materials-wizard?country=VN&visa_type=tourism&step=financial', '/tmp/fin-VN.png', { selector: '.mtp' })
console.log('--- VN financial saved')
// 行程表: US (会渲染 TravelPlanner)
await snap('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism&step=travel', '/tmp/trav-US.png', { collectCells: true })
console.log('--- travel cells verified')

await browser.close()
