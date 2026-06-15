/**
 * A-W10-2 L4 i18n full-locale — screenshot suite
 *
 * 4 locales (zh-CN / en / id-ID / vi-VN) × 3 pages (Home / Login / Register)
 * = 12 distinct PNGs. sha256 + pixel-layer distinct check (W6b SPA collision trap).
 *
 * Requires _spa_server.mjs running on 4174.
 */
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

const BASE = 'http://127.0.0.1:4174'
const OUT_DIR = '/Users/stephen/.mavis/plans/plan_04387add/outputs/A-W10-2/screenshots'

const LOCALES = ['zh-CN', 'en', 'id-ID', 'vi-VN']
const PAGES = [
  { name: 'home',     route: '/home' },
  { name: 'login',    route: '/login' },
  { name: 'register', route: '/register' }
]

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
  await mkdir(OUT_DIR, { recursive: true })
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const results = []

  for (const locale of LOCALES) {
    const page = await ctx.newPage()
    await page.addInitScript((lang) => {
      try { localStorage.setItem('visa.lang', lang) } catch {}
      try { localStorage.removeItem('visa.auth') } catch {}
    }, locale)

    for (const p of PAGES) {
      await page.goto(BASE + p.route, { waitUntil: 'networkidle', timeout: 15000 })
      await page.waitForTimeout(1200)
      const file = path.join(OUT_DIR, `${locale}_${p.name}.png`)
      await page.screenshot({ path: file, fullPage: false })
      const h = await sha256(file)
      const px = await pixelHash(file)
      const stat = await readFile(file).then(b => b.length)
      results.push({ locale, page: p.name, file, sha256: h, pixel_sha: px, bytes: stat })
      console.log(`  shot: ${locale} ${p.name}  ${stat}B  sha256=${h.slice(0, 16)}…  pixel=${px}`)
    }
    await page.close()
  }
  await browser.close()

  const hashes = results.map(r => r.sha256)
  const pixelHashes = results.map(r => r.pixel_sha)
  const distinct = new Set(hashes)
  const distinctPixel = new Set(pixelHashes)
  console.log(`\nDistinct file sha256: ${distinct.size} / ${hashes.length}`)
  console.log(`Distinct pixel sha256: ${distinctPixel.size} / ${pixelHashes.length}`)

  const index = {
    base: BASE,
    timestamp: new Date().toISOString(),
    count: results.length,
    distinct_file_sha256: distinct.size,
    distinct_pixel_sha256: distinctPixel.size,
    items: results
  }
  await writeFile(path.join(OUT_DIR, 'index.json'), JSON.stringify(index, null, 2))
  console.log(`\nDone: ${results.length} screenshots, file sha256 distinct=${distinct.size}, pixel distinct=${distinctPixel.size}.`)
}

main().catch(e => { console.error(e); process.exit(1) })