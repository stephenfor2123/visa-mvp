import { chromium } from 'playwright'
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1600 }, locale: 'zh-CN' })
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism')
await page.waitForTimeout(2000)
// 直接抓所有 city cell 文本
const rows = await page.locator('.tp-row, .tp-tbody tr').all()
console.log(`found ${rows.length} rows`)
for (let i = 0; i < rows.length; i++) {
  const t = await rows[i].textContent()
  console.log(`row ${i}: ${t?.slice(0, 80).replace(/\n/g, ' | ')}`)
}
// 抓 city 单元格具体内容
const cityCells = await page.locator('[data-testid^="tp-day-city-"]').all()
console.log(`\ncity cells: ${cityCells.length}`)
for (let i = 0; i < cityCells.length; i++) {
  const v = await cityCells[i].inputValue().catch(() => null)
  const sub = await page.locator(`[data-testid="tp-day-city-from-${i}"]`).textContent().catch(() => 'no-sub')
  console.log(`day ${i}: cell="${v}" sub="${sub?.trim()}"`)
}
await browser.close()
