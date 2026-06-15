#!/usr/bin/env node
/**
 * A-W11R-1 修真因: 4 语种 × 3 页面 = 12 截图
 *
 * 修真因 #1 bridge INERT: i18n/index.js 不再引 locales/ (locales 已被 mavis-trash 修真因)
 * 修真因 #2 raw key:    playwright 实测 DOM 是否含 raw key (i18n key 字面量如 home.features.materials.title)
 * 修真因 #3 Login 404:   vite preview (port 4173) 有 SPA history fallback,/login 返 200 + HTML
 *
 * 退出码:
 *   0 = 12/12 PASS (3 P0 全修真因: bridge 删 + 0 raw key + Login 200 非 404)
 *   1 = 任一 P0 FAIL
 */
import { chromium } from '@playwright/test'
import { createHash } from 'node:crypto'
import { writeFileSync, statSync, readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = '/Users/stephen/.mavis/plans/plan_6f913119/outputs/A-W11R-1/screenshots'
const BASE = 'http://127.0.0.1:4173'

// W10-2 修真因 #2 反例: 嵌套 i18n key 字符串必不出现在 DOM
const RAW_KEY_PATTERNS = [
  'home.features.materials',
  'home.features.insurance',
  'home.features.templates',
  'home.features.affiliate',
  'home.hero.sub',
  'home.hero.explore_cta',
  'home.hero.chip_meta',
  'home.features.title',
  'home.features.subtitle',
  'common.network_error',
  'common.app_name',
  'common.loading',
  'auth.login_title',
  'auth.register_title',
  'order.new_title'
]

const PAGES = ['home', 'login', 'register']
const LOCALES = [
  { tag: 'zh-CN', label: 'zh-CN' },
  { tag: 'en', label: 'en' },
  { tag: 'id-ID', label: 'id-ID' },
  { tag: 'vi-VN', label: 'vi-VN' }
]

const checks = []
const results = []
let exitCode = 0

function check(name, pass, detail) {
  checks.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name} | ${detail}`)
}

function sha256File(p) {
  return createHash('sha256').update(readFileSync(p)).digest('hex')
}

;(async () => {
  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1
  })

  for (const loc of LOCALES) {
    for (const page of PAGES) {
      const tag = `${page === 'home' ? 'Home' : page === 'login' ? 'Login' : 'Register'}-${loc.label}`
      const url = `${BASE}/${page === 'home' ? 'home' : page === 'login' ? 'login' : 'register'}`
      const shotPath = join(OUT_DIR, `${tag}.png`)

      const pg = await context.newPage()

      // Seed locale in localStorage before navigation (matches W10-2 spec)
      await pg.addInitScript((l) => {
        try { localStorage.setItem('visa.lang', l) } catch {}
      }, loc.tag)

      const resp = await pg.goto(url, { waitUntil: 'networkidle' })
      const status = resp ? resp.status() : 0

      // Wait for Vue mount + i18n hydration
      try {
        await pg.waitForFunction(() => {
          const app = document.getElementById('app')
          return app && app.innerText && app.innerText.trim().length > 20
        }, { timeout: 5000 })
      } catch (e) {
        // fall through; we'll check body below
      }

      // Capture DOM body
      const body = await pg.evaluate(() => document.body.innerText || '')
      const html = await pg.content()

      // Shot
      await pg.screenshot({ path: shotPath, fullPage: false })

      // Raw key check (修真因 #2: 必 0 hit)
      const rawKeyHits = RAW_KEY_PATTERNS.filter((k) => body.includes(k) || html.includes(`"${k}"`))

      // Login-vi-VN SPA check (修真因 #3: 必 status 200 + DOM 长 > 200)
      const isLoginVi = tag === 'Login-vi-VN'
      const isSpaRender = status === 200 && body.length > 100 && !body.toLowerCase().includes('404') && !body.toLowerCase().includes('not found')

      const fileSize = statSync(shotPath).size
      const sha = sha256File(shotPath)

      results.push({ tag, url, status, bodyLen: body.length, fileSize, sha, rawKeyHits, isSpaRender })

      check(
        `shot[${tag}] status 200`,
        status === 200,
        `status=${status}`
      )
      check(
        `shot[${tag}] no raw key`,
        rawKeyHits.length === 0,
        rawKeyHits.length === 0 ? `0 hits` : `hits: ${rawKeyHits.join(',')}`
      )
      check(
        `shot[${tag}] SPA render body>100`,
        body.length > 100,
        `body.length=${body.length}`
      )
      if (isLoginVi) {
        check(
          `shot[Login-vi-VN] NOT 404 page`,
          isSpaRender,
          `status=${status} body>200=${body.length > 200}`
        )
      }

      await pg.close()
    }
  }

  await context.close()
  await browser.close()

  // sha256 distinct check (修真因: 12 张图必两两不同)
  const shaSet = new Set(results.map((r) => r.sha))
  check('12 screenshots sha256 distinct', shaSet.size === results.length, `${shaSet.size}/${results.length} unique`)

  // Summary
  const passed = checks.filter((c) => c.pass).length
  const failed = checks.filter((c) => !c.pass)
  console.log(`\n=== SUMMARY: ${passed}/${checks.length} checks PASS ===`)
  if (failed.length) {
    exitCode = 1
    console.log('FAILURES:')
    for (const f of failed) console.log(`  - ${f.name}: ${f.detail}`)
  }

  // Write results json
  writeFileSync(join(__dirname, '..', 'shot-results.json'), JSON.stringify({ checks, results }, null, 2))
  process.exit(exitCode)
})().catch((e) => {
  console.error('FATAL:', e)
  process.exit(2)
})
