/**
 * A-W11-1 UI Polish 截图脚本
 * 目标: 12+ 截图 sha256 distinct
 * 覆盖: 桌面 + 移动端, 登录/注册/主页/申请表单 等关键页面
 * 跑法: cd frontend/web && node _shot_w11_1.mjs
 * 依赖: 4173 端口 (vite preview) 已在 serve 最新 dist
 */
import { chromium } from '@playwright/test'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const OUT = '/Users/stephen/.mavis/plans/plan_d4a6f4c1/outputs/A-W11-1/screenshots'
const BASE = 'http://127.0.0.1:4173'

// 截图配置: 桌面 + 移动端, 关键页面
const SCENES = [
  // 桌面 (1280×800)
  { name: 'home-zh',      route: '/home',     auth: false, locale: 'zh-CN', vp: { width: 1280, height: 800 } },
  { name: 'login-zh',    route: '/login',    auth: false, locale: 'zh-CN', vp: { width: 1280, height: 800 } },
  { name: 'register-zh', route: '/register', auth: false, locale: 'zh-CN', vp: { width: 1280, height: 800 } },
  { name: 'home-en',     route: '/home',     auth: false, locale: 'en',     vp: { width: 1280, height: 800 } },
  { name: 'login-en',    route: '/login',    auth: false, locale: 'en',     vp: { width: 1280, height: 800 } },
  { name: 'register-en', route: '/register', auth: false, locale: 'en',     vp: { width: 1280, height: 800 } },
  // 移动端 (390×844 - iPhone 14)
  { name: 'home-mobile-zh',   route: '/home',     auth: false, locale: 'zh-CN', vp: { width: 390, height: 844 } },
  { name: 'login-mobile-zh',  route: '/login',    auth: false, locale: 'zh-CN', vp: { width: 390, height: 844 } },
  { name: 'register-mobile-zh', route: '/register', auth: false, locale: 'zh-CN', vp: { width: 390, height: 844 } },
  { name: 'home-mobile-en',   route: '/home',     auth: false, locale: 'en',     vp: { width: 390, height: 844 } },
  { name: 'login-mobile-en',  route: '/login',    auth: false, locale: 'en',     vp: { width: 390, height: 844 } },
  { name: 'register-mobile-en', route: '/register', auth: false, locale: 'en',   vp: { width: 390, height: 844 } },
  // 印尼/越南语
  { name: 'home-id',       route: '/home',     auth: false, locale: 'id-ID', vp: { width: 1280, height: 800 } },
  { name: 'login-vi',      route: '/login',    auth: false, locale: 'vi-VN', vp: { width: 1280, height: 800 } },
]

const results = []

for (const scene of SCENES) {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({
    viewport: scene.vp,
    deviceScaleFactor: scene.vp.width < 500 ? 3 : 1
  })
  const page = await ctx.newPage()
  await page.addInitScript((lang) => {
    try { localStorage.setItem('visa.lang', lang) } catch {}
    try { localStorage.removeItem('visa.auth') } catch {}
  }, scene.locale)

  try {
    const resp = await page.goto(BASE + scene.route, { waitUntil: 'domcontentloaded', timeout: 15000 })
    await page.waitForTimeout(1500)
    const fname = `${scene.name}.png`
    const fpath = path.join(OUT, fname)
    await page.screenshot({ path: fpath, fullPage: false })
    const buf = fs.readFileSync(fpath)
    const hash = crypto.createHash('sha256').update(buf).digest('hex').slice(0, 16)
    results.push({ name: scene.name, file: fpath, hash, size: buf.length, status: resp?.status() })
    console.log(`OK ${scene.name} hash=${hash} size=${buf.length}`)
  } catch (e) {
    console.error(`FAIL ${scene.name}: ${e.message}`)
    results.push({ name: scene.name, error: e.message })
  } finally {
    await ctx.close()
    await browser.close()
  }
}

// distinct 校验
const hashes = results.filter(r => r.hash).map(r => r.hash)
const distinct = new Set(hashes)
const sizes = results.filter(r => r.size).map(r => r.size)
const sizeDistinct = new Set(sizes).size
console.log(`\n=== distinct: ${distinct.size}/${hashes.length} | size-distinct: ${sizeDistinct}/${sizes.length} ===`)

if (distinct.size !== hashes.length) {
  console.error('FAIL: sha256 collision')
  process.exit(1)
}

fs.writeFileSync(path.join(OUT, '_manifest.json'), JSON.stringify({
  total: results.length,
  fileDistinct: distinct.size,
  sizeDistinct: sizeDistinct,
  items: results
}, null, 2))
console.log('Manifest:', path.join(OUT, '_manifest.json'))