// _shoot_material_templates.mjs — 截图验证 MaterialTemplatePreview
import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'

const BASE = 'http://127.0.0.1:4173'
const OUT_DIR = '/Users/apple/Desktop/签证项目_副本/screenshots'

async function main() {
  await mkdir(OUT_DIR, { recursive: true })
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1800 } })

  // 中文 + 美国 — identity
  let page = await ctx.newPage()
  await page.goto(`${BASE}/materials-wizard?country=US&lang=zh-CN`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${OUT_DIR}/mtp-identity-zh-US.png`, fullPage: true })
  await page.close()

  // 切换到财务大类 — financial
  page = await ctx.newPage()
  await page.goto(`${BASE}/materials-wizard?country=US&lang=zh-CN`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  await page.locator('[data-testid="mw-step-financial"]').click()
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${OUT_DIR}/mtp-financial-zh-US.png`, fullPage: true })
  await page.close()

  // 工作大类 — work
  page = await ctx.newPage()
  await page.goto(`${BASE}/materials-wizard?country=US&lang=zh-CN`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  await page.locator('[data-testid="mw-step-work"]').click()
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${OUT_DIR}/mtp-work-zh-US.png`, fullPage: true })
  await page.close()

  // 申根 — work（看 country note）
  page = await ctx.newPage()
  await page.goto(`${BASE}/materials-wizard?country=DE&lang=zh-CN`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  await page.locator('[data-testid="mw-step-work"]').click()
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${OUT_DIR}/mtp-work-zh-DE.png`, fullPage: true })
  await page.close()

  // 英文 — identity
  page = await ctx.newPage()
  await page.goto(`${BASE}/materials-wizard?country=UK&lang=en`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${OUT_DIR}/mtp-identity-en-UK.png`, fullPage: true })
  await page.close()

  await browser.close()
  console.log('done, see', OUT_DIR)
}

main().catch(e => { console.error(e); process.exit(1) })