import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

const BASE = 'http://127.0.0.1:4174'
const OUT_DIR = '/Users/stephen/.mavis/plans/plan_04387add/outputs/A-W10-2/screenshots'

async function sha256(file) {
  const buf = await readFile(file)
  return createHash('sha256').update(buf).digest('hex')
}

async function pixelHash(file) {
  const buf = await readFile(file)
  const data = buf.subarray(8, 8 + 65536)
  return createHash('sha256').update(data).digest('hex').slice(0, 16)
}

async function main() {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })

  // Test 1: zh-CN Home page
  const page = await ctx.newPage()
  await page.addInitScript((lang) => {
    try { localStorage.setItem('visa.lang', lang) } catch {}
    try { localStorage.removeItem('visa.auth') } catch {}
  }, 'zh-CN')
  await page.goto(BASE + '/home', { waitUntil: 'networkidle', timeout: 15000 })
  await page.waitForTimeout(2000)
  const file = path.join(OUT_DIR, 'test_zh_home.png')
  await mkdir(OUT_DIR, { recursive: true })
  await page.screenshot({ path: file, fullPage: false })
  const h = await sha256(file)
  const px = await pixelHash(file)
  const stat = await readFile(file).then(b => b.length)
  console.log(`test_zh_home: ${stat}B sha256=${h.slice(0,16)} pixel=${px}`)
  // Print page title/content
  const title = await page.title()
  const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 200))
  console.log(`  title: ${title}`)
  console.log(`  body: ${bodyText}`)

  // Check what JS chunks loaded
  const loadedScripts = await page.evaluate(() => {
    return [...document.querySelectorAll('script[src]')].map(s => s.src)
  })
  console.log(`  scripts: ${loadedScripts.length}`)
  loadedScripts.forEach(s => console.log(`    ${s}`))

  // Check vue-i18n state
  const i18nLocale = await page.evaluate(() => {
    const app = document.querySelector('#app')
    return app ? 'app exists' : 'no app'
  })
  console.log(`  app: ${i18nLocale}`)

  await page.close()
  await browser.close()
}

main().catch(e => { console.error(e); process.exit(1) })