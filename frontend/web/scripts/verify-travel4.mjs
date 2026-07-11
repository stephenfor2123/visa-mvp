import { chromium } from 'playwright'
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1400, height: 2200 }, locale: 'zh-CN' })
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism&step=travel')
await page.waitForTimeout(2500)
// 用 page.fill 填日期 input
const dateInputs = await page.locator('input[type="date"]').all()
console.log(`date inputs: ${dateInputs.length}`)
for (let i = 0; i < dateInputs.length; i++) {
  const val = i === 0 ? '2026-07-02' : '2026-07-08'
  await dateInputs[i].fill(val)
  await page.waitForTimeout(300)
  console.log(`set input ${i} = ${val}`)
}
// origin / returnDestination
const originInputs = await page.locator('input[placeholder*="Beijing"]').first()
if (await originInputs.count()) {
  await originInputs.fill('北京')
  await page.waitForTimeout(200)
}
const returnFromInput = await page.locator('input[placeholder*="destination"], .tp-row input').all()
console.log(`other inputs: ${returnFromInput.length}`)
await page.waitForTimeout(500)
// 看看 days
const dayCells = await page.locator('[data-testid^="tp-day-city-"]:not([data-testid*="-from-"])').all()
console.log(`day city cells: ${dayCells.length}`)
for (let i = 0; i < Math.min(dayCells.length, 10); i++) {
  const v = await dayCells[i].inputValue().catch(() => null)
  console.log(`  cell ${i}: "${v}"`)
}
// 抓 sub cells
const subCells = await page.locator('[data-testid^="tp-day-city-from-"]').all()
console.log(`sub cells: ${subCells.length}`)
for (let i = 0; i < subCells.length; i++) {
  const text = await subCells[i].textContent()
  console.log(`  day ${i} sub: "${text?.trim()}"`)
}
// 手动 fill 几个 day city 和 transport
for (let i = 0; i < 7; i++) {
  const cityEl = page.locator(`[data-testid="tp-day-city-${i}"]`)
  if (await cityEl.count()) {
    const v = i < 3 ? '纽约' : '旧金山'
    if (i === 0 || i === 3 || i === 6) await cityEl.fill(v)
    await page.waitForTimeout(50)
  }
  const transEl = page.locator(`[data-testid="tp-day-transport-${i}"]`)
  if (await transEl.count()) {
    const v = (i === 0 || i === 3 || i === 6) ? 'flight' : 'walk'
    await transEl.selectOption(v)
    await page.waitForTimeout(50)
  }
}
await page.waitForTimeout(800)
console.log('\nafter manual fill:')
const subCells2 = await page.locator('[data-testid^="tp-day-city-from-"]').all()
console.log(`sub cells: ${subCells2.length}`)
for (let i = 0; i < subCells2.length; i++) {
  const text = await subCells2[i].textContent()
  console.log(`  day ${i} sub: "${text?.trim()}"`)
}
const panel = page.locator('.mw-panel').first()
if (await panel.count()) {
  await panel.screenshot({ path: '/tmp/trav-US.png' })
  console.log('saved panel')
}
await browser.close()
