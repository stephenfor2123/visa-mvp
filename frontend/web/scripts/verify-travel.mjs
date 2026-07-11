import { chromium } from 'playwright'
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1600 }, locale: 'zh-CN' })
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism&step=travel')
await page.waitForTimeout(2500)
// 抓所有 city cell + 副标题
const cells = await page.locator('[data-testid^="tp-day-city-from-"]').all()
console.log(`sub cells: ${cells.length}`)
for (let i = 0; i < cells.length; i++) {
  const text = await cells[i].textContent()
  const cellVal = await page.locator(`[data-testid="tp-day-city-${i}"]`).inputValue().catch(() => null)
  console.log(`day ${i}: cell="${cellVal}" sub="${text?.trim()}"`)
}
// 截行程表本体
const tp = await page.locator('.tp, [class*="travel-planner"]').first()
if (await tp.count()) {
  await tp.screenshot({ path: '/tmp/trav-US.png' })
  console.log('saved /tmp/trav-US.png')
} else {
  // fallback: 截整个面板
  const panel = await page.locator('.mw-panel').first()
  if (await panel.count()) {
    await panel.screenshot({ path: '/tmp/trav-US.png' })
    console.log('saved panel /tmp/trav-US.png')
  }
}
await browser.close()
