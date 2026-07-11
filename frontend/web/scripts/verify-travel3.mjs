import { chromium } from 'playwright'
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1400, height: 2000 }, locale: 'zh-CN' })
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism&step=travel')
await page.waitForTimeout(2500)
// 填所有 day 字段 - 7 days
// 用 JS 直接修改 input value
const fills = [
  // day 0: city 纽约, transport flight
  { sel: '[data-testid="tp-day-city-0"]', val: '纽约' },
  { sel: '[data-testid="tp-day-transport-0"]', val: 'flight' },
  { sel: '[data-testid="tp-day-city-1"]', val: '纽约' },
  { sel: '[data-testid="tp-day-transport-1"]', val: 'walk' },
  { sel: '[data-testid="tp-day-city-2"]', val: '纽约' },
  { sel: '[data-testid="tp-day-transport-2"]', val: 'walk' },
  { sel: '[data-testid="tp-day-city-3"]', val: '旧金山' },
  { sel: '[data-testid="tp-day-transport-3"]', val: 'flight' },
  { sel: '[data-testid="tp-day-city-4"]', val: '旧金山' },
  { sel: '[data-testid="tp-day-transport-4"]', val: 'walk' },
  { sel: '[data-testid="tp-day-city-5"]', val: '旧金山' },
  { sel: '[data-testid="tp-day-transport-5"]', val: 'walk' },
  { sel: '[data-testid="tp-day-city-6"]', val: '旧金山' },
  { sel: '[data-testid="tp-day-transport-6"]', val: 'flight' },
]
for (const f of fills) {
  const el = page.locator(f.sel)
  if (await el.count()) {
    if (f.sel.includes('transport')) {
      await el.selectOption(f.val)
    } else {
      await el.fill(f.val)
    }
    await page.waitForTimeout(50)
  }
}
await page.waitForTimeout(500)
// 抓 sub cells
const cells = await page.locator('[data-testid^="tp-day-city-from-"]').all()
console.log(`sub cells: ${cells.length}`)
for (let i = 0; i < cells.length; i++) {
  const text = await cells[i].textContent()
  const cellVal = await page.locator(`[data-testid="tp-day-city-${i}"]`).inputValue().catch(() => null)
  console.log(`day ${i}: cell="${cellVal}" sub="${text?.trim()}"`)
}
const panel = page.locator('.mw-panel').first()
if (await panel.count()) {
  await panel.screenshot({ path: '/tmp/trav-US.png' })
  console.log('saved panel screenshot')
}
await browser.close()
