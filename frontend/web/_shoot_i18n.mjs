/**
 * W10-2 L4 i18n full-locale — screenshot suite
 *
 * 4 locales (zh-CN / en / id-ID / vi-VN) × 3 guest pages (Home / Login / Register)
 * = 12 distinct PNGs. We also assert via sha256 that all 12 files are distinct
 * (the W6b A-W6-4 "3 files sha256 collision" trap from SPA hash routes).
 *
 * Uses the `vite preview` server on 4173 (started by tests/e2e/global-setup.cjs
 * or manually before this script). No backend required.
 */
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

const BASE = 'http://127.0.0.1:4173'
const OUT_DIR = '/Users/stephen/.mavis/plans/plan_e3775bec/outputs/A-W10-2/screenshots'

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

async function main() {
  await mkdir(OUT_DIR, { recursive: true })
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const results = []

  for (const locale of LOCALES) {
    // Per-locale context: avoid SPA shared state polluting language switch.
    const page = await ctx.newPage()
    await page.addInitScript((lang) => {
      try { localStorage.setItem('visa.lang', lang) } catch {}
      try { localStorage.removeItem('visa.auth') } catch {}
    }, locale)

    for (const p of PAGES) {
      await page.goto(BASE + p.route, { waitUntil: 'domcontentloaded' })
      // Wait for vue-i18n + LangSwitch to render the chosen locale.
      await page.waitForTimeout(600)
      const file = path.join(OUT_DIR, `${locale}_${p.name}.png`)
      await page.screenshot({ path: file, fullPage: false })
      const h = await sha256(file)
      const stat = await readFile(file).then(b => b.length)
      results.push({ locale, page: p.name, file, sha256: h, bytes: stat })
      console.log(`  shot: ${locale} ${p.name}  ${stat}B  sha256=${h.slice(0, 16)}…`)
    }
    await page.close()
  }
  await browser.close()

  // Distinctness check (catches the W6b 3-files-same-sha trap)
  const hashes = results.map(r => r.sha256)
  const distinct = new Set(hashes)
  console.log(`\nDistinct sha256 count: ${distinct.size} / ${hashes.length}`)
  if (distinct.size !== hashes.length) {
    const dupes = hashes.filter((h, i) => hashes.indexOf(h) !== i)
    console.error('DUPLICATES:', dupes)
    process.exit(1)
  }

  // Write index.json for the deliverable
  const index = {
    base: BASE,
    timestamp: new Date().toISOString(),
    count: results.length,
    distinct: distinct.size,
    items: results
  }
  await writeFile(path.join(OUT_DIR, 'index.json'), JSON.stringify(index, null, 2))
  console.log(`\nWrote index.json: ${results.length} entries, ${distinct.size} distinct sha256.`)
}

main().catch(e => { console.error(e); process.exit(1) })
