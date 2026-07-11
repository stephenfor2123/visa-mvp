/**
 * Htex 全部前端页面截图
 * 4 语言 × 30 用户端页面 + admin 子页(只 zh 即可,admin 内部页面不强调多语言)
 * 输出到 /Users/apple/Desktop/签证项目_副本/screenshots_all/
 *
 * 设计:
 *  - 30 用户端页面按"是否需要登录"分组;logged-in 用 demo1 账号注入 localStorage
 *  - admin 端单独跑(只 zh + en),admin_token 注入
 *  - 每个页面等 600ms 让 vue-i18n + 数据 fetch 完成
 */

import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const BASE = 'http://127.0.0.1:5173'
const OUT_DIR = '/Users/apple/Desktop/签证项目_副本/screenshots_all'

const LOCALES = ['zh-CN', 'en', 'id-ID', 'vi-VN']

// === 用户端页面 ===
const GUEST_PAGES = [
  { name: 'home',              route: '/home' },
  { name: 'login',             route: '/login' },
  { name: 'register',          route: '/register' },
  { name: 'forgot_password',   route: '/forgot-password' },
  { name: 'agreement',         route: '/agreement' },
  { name: 'destinations',      route: '/destinations' },
  { name: 'schengen_countries',route: '/schengen-countries' },
  { name: 'pricing',           route: '/pricing' },
  { name: 'contact',           route: '/contact' },
  { name: 'resources',         route: '/resources' },
  { name: 'resources_wiki',    route: '/resources/wiki' },
  { name: 'resources_policy',  route: '/resources/policy' },
  { name: 'resources_templates', route: '/resources/templates' },
  { name: 'resources_faq',     route: '/resources/faq' },
  { name: 'apply',             route: '/apply' },
  { name: 'diagnose',          route: '/diagnose' },
  { name: 'materials_wizard',  route: '/materials-wizard' },
  { name: 'orders_new',        route: '/orders/new' },
]

const LOGGED_IN_PAGES = [
  { name: 'profile',           route: '/profile' },
  { name: 'materials',         route: '/materials' },
  { name: 'materials_scan',    route: '/materials/scan' },
  { name: 'materials_validate',route: '/materials/validate' },
  { name: 'materials_diagnose',route: '/materials/diagnose' },
  { name: 'passport_review',   route: '/passport-review' },
  { name: 'orders',            route: '/orders' },
  { name: 'rpa_submit',        route: '/rpa/submit' },
  { name: 'rpa_status',        route: '/rpa/status' },
  { name: 'payment_result',    route: '/payment/result?orderId=DEMO&status=success' },
]

// === Admin 端 ===
const ADMIN_PAGES = [
  { name: 'admin_login',          route: '/admin/login' },
  { name: 'admin_dashboard',      route: '/admin/dashboard' },
  { name: 'admin_users',          route: '/admin/users' },
  { name: 'admin_c_users',        route: '/admin/c-users' },
  { name: 'admin_orders',         route: '/admin/orders' },
  { name: 'admin_countries',      route: '/admin/countries' },
  { name: 'admin_rag_review',     route: '/admin/rag-review' },
  { name: 'admin_rpa_strategy',   route: '/admin/rpa-strategy' },
  { name: 'admin_ai_rules',       route: '/admin/ai-rules' },
  { name: 'admin_i18n',           route: '/admin/i18n' },
  { name: 'admin_roles',          route: '/admin/roles' },
  { name: 'admin_payments',       route: '/admin/payments' },
  { name: 'admin_logs',           route: '/admin/logs' },
  { name: 'admin_cleanup',        route: '/admin/cleanup' },
  { name: 'admin_rate_limit',     route: '/admin/rate-limit' },
]

// 模拟登录态: 注入 localStorage 的 user + token (fake,够绕过 router guard)
async function injectUserAuth(page) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('visa.auth', JSON.stringify({
        user: { id: 1, email: 'demo138001380001@htex.app', name: 'Demo User', languagePref: 'zh-CN' },
        accessToken: 'demo-fake-token-for-screenshot',
        refreshToken: 'demo-fake-refresh'
      }))
    } catch {}
  })
}

async function injectAdminAuth(page) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('visa.admin.token', 'demo-admin-token')
      localStorage.setItem('visa.admin.profile', JSON.stringify({
        username: 'admin', role: 'superadmin'
      }))
    } catch {}
  })
}

async function setLocale(page, locale) {
  await page.addInitScript((lang) => {
    try { localStorage.setItem('visa.lang', lang) } catch {}
  }, locale)
}

async function shoot(page, route, file) {
  await page.goto(BASE + route, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(900) // 让 i18n + 异步数据稳定
  await page.screenshot({ path: file, fullPage: true })
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true })
  const browser = await chromium.launch()
  const summary = { user_pages: 0, admin_pages: 0, errors: [] }

  // ===== 用户端: 4 语言 × (guest + logged-in) =====
  for (const locale of LOCALES) {
    // guest pages
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
      const page = await ctx.newPage()
      await setLocale(page, locale)
      for (const p of GUEST_PAGES) {
        const file = path.join(OUT_DIR, `user_${locale}_${p.name}.png`)
        try {
          await shoot(page, p.route, file)
          summary.user_pages++
          console.log(`✓ user/${locale}/${p.name}`)
        } catch (e) {
          summary.errors.push({ scope: 'user', locale, page: p.name, err: e.message })
          console.error(`✗ user/${locale}/${p.name}: ${e.message}`)
        }
      }
      await ctx.close()
    }
    // logged-in pages
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
      const page = await ctx.newPage()
      await setLocale(page, locale)
      await injectUserAuth(page)
      for (const p of LOGGED_IN_PAGES) {
        const file = path.join(OUT_DIR, `user_${locale}_${p.name}.png`)
        try {
          await shoot(page, p.route, file)
          summary.user_pages++
          console.log(`✓ user/${locale}/${p.name} (auth)`)
        } catch (e) {
          summary.errors.push({ scope: 'user-auth', locale, page: p.name, err: e.message })
          console.error(`✗ user/${locale}/${p.name} (auth): ${e.message}`)
        }
      }
      await ctx.close()
    }
  }

  // ===== Admin: zh + en =====
  for (const locale of ['zh-CN', 'en']) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await ctx.newPage()
    await setLocale(page, locale)
    await injectAdminAuth(page)
    for (const p of ADMIN_PAGES) {
      const file = path.join(OUT_DIR, `admin_${locale}_${p.name}.png`)
      try {
        await shoot(page, p.route, file)
        summary.admin_pages++
        console.log(`✓ admin/${locale}/${p.name}`)
      } catch (e) {
        summary.errors.push({ scope: 'admin', locale, page: p.name, err: e.message })
        console.error(`✗ admin/${locale}/${p.name}: ${e.message}`)
      }
    }
    await ctx.close()
  }

  await browser.close()

  await writeFile(path.join(OUT_DIR, 'index.json'), JSON.stringify(summary, null, 2))
  console.log(`\n--- DONE ---`)
  console.log(`User pages: ${summary.user_pages}`)
  console.log(`Admin pages: ${summary.admin_pages}`)
  console.log(`Errors: ${summary.errors.length}`)
}

main().catch(e => { console.error(e); process.exit(1) })