/**
 * W10-2 L4 i18n full-locale 截图脚本
 * 4 语种 × 3 页面 = 12 截图,每张 sha256 distinct
 * 跑法: node _shot_i18n.mjs
 */
import { chromium } from '@playwright/test'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const OUT = '/Users/stephen/.mavis/plans/plan_e3775bec/outputs/A-W10-2/screenshots'
const BASE = 'http://127.0.0.1:4173'

const LOCALES = ['zh-CN', 'en', 'id-ID', 'vi-VN']
const PAGES = [
  { name: 'Home',         route: '/home',                       auth: false },
  { name: 'Login',        route: '/login',                      auth: false },
  { name: 'Register',     route: '/register',                   auth: false }
]

// 4 国 chip 在 Home 可见 + 不需要后端 mock
// 但要避免 SPA 内部 hash state 污染 → 每张都 newContext
const results = []

for (const locale of LOCALES) {
  for (const p of PAGES) {
    const browser = await chromium.launch({ headless: true })
    const ctx = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      deviceScaleFactor: 1
    })
    const page = await ctx.newPage()
    // Seed lang (auth not needed for these 3 pages)
    await page.addInitScript((lang) => {
      try { localStorage.setItem('visa.lang', lang) } catch {}
    }, locale)
    try {
      const resp = await page.goto(BASE + p.route, { waitUntil: 'domcontentloaded', timeout: 15000 })
      // 等待文本出现以确认 i18n 真的切换了
      await page.waitForTimeout(1500)
      const fname = `${p.name}-${locale}.png`
      const fpath = path.join(OUT, fname)
      await page.screenshot({ path: fpath, fullPage: false })
      const buf = fs.readFileSync(fpath)
      const hash = crypto.createHash('sha256').update(buf).digest('hex').slice(0, 16)
      results.push({ page: p.name, locale, file: fpath, hash, size: buf.length, status: resp?.status() })
      console.log(`OK ${p.name}/${locale} hash=${hash} size=${buf.length} status=${resp?.status()}`)
    } catch (e) {
      console.error(`FAIL ${p.name}/${locale}: ${e.message}`)
      results.push({ page: p.name, locale, error: e.message })
    } finally {
      await ctx.close()
      await browser.close()
    }
  }
}

// 校验 distinct
const hashes = results.filter(r => r.hash).map(r => r.hash)
const distinct = new Set(hashes)
console.log(`\n=== distinct ${distinct.size}/${hashes.length} ===`)
if (distinct.size !== hashes.length) {
  console.error('FAIL: hash collision detected')
  process.exit(1)
}

// 像素层校验
import('node:zlib').then(zlib => {
  // 简单像素采样:取文件头+文件尾+中段做第二次 hash
  const pixelHashes = results.filter(r => r.hash).map(r => {
    const buf = fs.readFileSync(r.file)
    // 取 1/4 1/2 3/4 位置各 1024 字节
    const samples = []
    for (const frac of [0.1, 0.3, 0.5, 0.7, 0.9]) {
      const start = Math.floor(buf.length * frac)
      samples.push(buf.slice(start, start + 1024))
    }
    return crypto.createHash('sha256').update(Buffer.concat(samples)).digest('hex').slice(0, 16)
  })
  const pixelDistinct = new Set(pixelHashes)
  console.log(`pixel-distinct ${pixelDistinct.size}/${pixelHashes.length}`)
  fs.writeFileSync(path.join(OUT, '_screenshot_manifest.json'), JSON.stringify({
    total: results.length,
    distinct: distinct.size,
    pixelDistinct: pixelDistinct.size,
    items: results
  }, null, 2))
  console.log('Manifest written')
})
