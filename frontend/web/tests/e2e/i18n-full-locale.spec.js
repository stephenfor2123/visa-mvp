/**
 * W10-2 L4 i18n full-locale — E2E spot-check
 *
 * Verifies that switching to each of the 4 supported locales (zh-CN / en / id-ID / vi-VN)
 * actually swaps the visible page text. Per locale, we run two suites:
 *
 *   SUITE A — guest pages (Home / Login / Register): no auth required.
 *   SUITE B — auth-required pages (OrderNew / OrderDetail): we seed a fake
 *             `visa.auth` localStorage value so the router guard lets us in.
 *
 * The test deliberately uses *only* front-end state (localStorage) and visible text —
 * no backend calls — so it runs deterministically against `npm run build` output
 * served by `vite preview`.
 */
import { test, expect } from '@playwright/test'

const SUPPORTED = ['zh-CN', 'en', 'id-ID', 'vi-VN']

// W10-2: Home slogan spot-check (verifier feedback — must NOT show raw key)
// W25: slogan moved from `home.hero.sub` to `common.app_slogan`
const HOME_SPOT = {
  'zh-CN': '无限可能,随行而至',
  'en':    'Wherever you go, life is infinite',
  'id-ID': 'Ke mana pun Anda pergi',
  'vi-VN': 'Đi đến nơi nào'
}

const SPOT_CHECKS = {
  Home: {
    'zh-CN': 'Htex',
    'en':    'Htex',
    'id-ID': 'Htex',
    'vi-VN': 'Htex'
  },
  Login: {
    'zh-CN': '欢迎回来',
    'en':    'Welcome Back',
    'id-ID': 'Selamat Datang Kembali',
    'vi-VN': 'Chào mừng trở lại'
  },
  Register: {
    'zh-CN': '创建账号',
    'en':    'Create Your Account',
    'id-ID': 'Buat Akun Anda',
    'vi-VN': 'Tạo tài khoản của bạn'
  },
  OrderNew: {
    // Body text only (orders.title is a router meta used for document.title, not body)
    'zh-CN': '基本信息',
    'en':    'Basic Information',
    'id-ID': 'Informasi Dasar',
    'vi-VN': 'Thông tin cơ bản'
  },
  OrderDetail: {
    // OrderDetail body always shows common.app_name in the nav header regardless
    // of whether the order fetch succeeded (we don't need a real backend for an i18n check).
    'zh-CN': 'Htex',
    'en':    'Htex',
    'id-ID': 'Htex',
    'vi-VN': 'Htex'
  }
}

const ROUTES_GUEST = {
  Home:     '/home',
  Login:    '/login',
  Register: '/register'
}

const ROUTES_AUTH = {
  OrderNew:    '/orders/new',
  OrderDetail: '/orders/TEST-LOCALE-CHECK'
}

for (const locale of SUPPORTED) {
  test(`i18n locale=${locale} home.* keys render (W10-2 13 keys)`, async ({ page }) => {
    // W10-2: 14 home.* keys must render in body, NOT raw 'home.hero.sub' etc.
    // Verifier feedback attempt 4/5: must cover 4 features × {title, desc} = 8 keys
    // not just 'home.features.materials' — that substring was found in body
    // when nested keys were missing.
    await page.addInitScript((lang) => {
      try { localStorage.setItem('visa.lang', lang) } catch {}
      try { localStorage.removeItem('visa.auth') } catch {}
    }, locale)
    await page.goto('/home', { waitUntil: 'domcontentloaded' })
    // Wait for Vue to render — domcontentloaded fires before Vue finishes mounting
    await page.waitForLoadState('networkidle')
    await page.waitForSelector('.hero', { timeout: 10000 })
    const body = await page.locator('body').innerText()
    // Must contain the locale-specific translated string AND must NOT contain raw key
    const expected = HOME_SPOT[locale]
    expect(body).toContain(expected)
    // Hero (3 keys)
    expect(body).not.toContain('home.hero.sub')
    expect(body).not.toContain('home.hero.explore_cta')
    expect(body).not.toContain('home.hero.chip_meta')
    // Features section (2 keys)
    expect(body).not.toContain('home.features.title')
    expect(body).not.toContain('home.features.subtitle')
    // 4 features × {title, desc} = 8 keys (path-aligned A: nested structure)
    expect(body).not.toContain('home.features.materials.title')
    expect(body).not.toContain('home.features.materials.desc')
    expect(body).not.toContain('home.features.insurance.title')
    expect(body).not.toContain('home.features.insurance.desc')
    expect(body).not.toContain('home.features.templates.title')
    expect(body).not.toContain('home.features.templates.desc')
    expect(body).not.toContain('home.features.affiliate.title')
    expect(body).not.toContain('home.features.affiliate.desc')
  })

  test(`i18n locale=${locale} guest-pages render translated text`, async ({ page }) => {
    // Seed only the language (no auth), so Home / Login / Register are reachable.
    await page.addInitScript((lang) => {
      try { localStorage.setItem('visa.lang', lang) } catch {}
      try { localStorage.removeItem('visa.auth') } catch {}
    }, locale)

    for (const [pageName, route] of Object.entries(ROUTES_GUEST)) {
      await page.goto(route, { waitUntil: 'domcontentloaded' })
      await page.waitForLoadState('networkidle')
      const expected = SPOT_CHECKS[pageName][locale]
      await expect(page.locator('body')).toContainText(expected, { timeout: 10000 })
    }
  })

  test(`i18n locale=${locale} auth-pages render translated text`, async ({ page }) => {
    // Seed language + a fake auth payload so OrderNew / OrderDetail pass the guard.
    // auth.js hydrate() reads this exact JSON shape.
    await page.addInitScript((lang) => {
      try { localStorage.setItem('visa.lang', lang) } catch {}
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          user: { id: 't-i18n', phone: '+8613800000000', nickname: 'i18n' },
          accessToken: 'test.i18n.token',
          refreshToken: 'test.i18n.refresh'
        }))
      } catch {}
    }, locale)

    // W10-2: Mock /api/v2/destinations so OrderNew can render without backend.
    // OrderNew needs destination data to render the form section title "基本信息".
    await page.route('**/api/v2/destinations*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, country_code: 'US', country_name: 'United States', visa_types: ['tourism', 'student'], enabled: true },
          { id: 2, country_code: 'JP', country_name: 'Japan', visa_types: ['tourism', 'student'], enabled: false }
        ])
      })
    })

    for (const [pageName, route] of Object.entries(ROUTES_AUTH)) {
      await page.goto(route, { waitUntil: 'domcontentloaded' })
      await page.waitForLoadState('networkidle')
      // W10-2: Wait for form to load (OrderNew loads destinations async)
      await expect(page.locator('body')).toContainText(SPOT_CHECKS[pageName][locale], { timeout: 10000 })
    }
  })
}
