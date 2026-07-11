import { chromium } from 'playwright'
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1400, height: 2000 }, locale: 'zh-CN' })
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism&step=travel')
await page.waitForTimeout(2500)
const originInput = page.locator('input[placeholder*="Beijing"]').first()
if (await originInput.count()) {
  await originInput.fill('北京')
}
await page.waitForTimeout(500)
const dateInputs = await page.locator('input[type="date"], input[placeholder*="YYYY-MM-DD"]').all()
console.log(`date inputs: ${dateInputs.length}`)
for (const di of dateInputs) {
  await di.fill('2026-07-02')
  await page.waitForTimeout(120)
}
if (dateInputs.length > 0) {
  await dateInputs[dateInputs.length - 1].fill('2026-07-08')
}
await page.waitForTimeout(800)
const aiBtn = page.locator('button:has-text("智能补充"), button:has-text("AI")').first()
if (await aiBtn.count()) {
  console.log('clicking AI button...')
  await aiBtn.click()
  await page.waitForTimeout(5500)
}
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
}
await browser.close()
