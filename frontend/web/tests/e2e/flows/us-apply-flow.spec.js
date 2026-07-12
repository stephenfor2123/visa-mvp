/**
 * US apply → materials-wizard full-flow E2E
 *
 * Covers the product path:
 *   /apply (选 US) → checklist → CTA → /materials-wizard?country=US&visa_type=tourism
 *
 * Auth: register via email API (W26), inject JWT — no login UI interaction.
 */
import { test, expect } from '@playwright/test'

test.use({ baseURL: process.env.PW_BASE_URL || 'http://127.0.0.1:5173' })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('visa.lang', 'zh-CN') } catch (e) {}
  })
})

const API = 'http://127.0.0.1:8000/api/v2'
const PASSWORD = 'E2eTest@2024'

function uniqueSuffix() {
  return Date.now().toString().slice(-8) + Math.floor(Math.random() * 10000).toString().padStart(4, '0')
}

async function postWithRetry(request, url, data, maxRetries = 5) {
  let lastRes
  for (let i = 0; i < maxRetries; i++) {
    lastRes = await request.post(url, { data })
    if (lastRes.status() < 500) return lastRes
    await new Promise((r) => setTimeout(r, 500 + i * 800))
  }
  return lastRes
}

async function registerEmailUser(request) {
  const suffix = uniqueSuffix()
  const email = `e2e_${suffix}@htex.test`
  const username = `e2e_${suffix}`
  const res = await postWithRetry(request, `${API}/auth/register`, {
    username,
    email,
    password: PASSWORD,
    nickname: `E2E-${suffix}`,
    language_pref: 'zh-CN',
  })
  expect(res.status()).toBeLessThan(400)
  const body = await res.json()
  expect(body.code).toBe('1000')
  return {
    email,
    username,
    accessToken: body.data.access_token,
    refreshToken: body.data.refresh_token,
    user: body.data.user,
  }
}

async function injectAuth(page, auth) {
  await page.goto('/login')
  await page.evaluate((d) => {
    localStorage.setItem('visa.auth', JSON.stringify(d))
  }, {
    accessToken: auth.accessToken,
    refreshToken: auth.refreshToken,
    user: auth.user,
  })
}

test.describe('US apply → materials-wizard', () => {
  test('happy path: 选 US → 材料清单 → CTA → materials-wizard', async ({ page, request }) => {
    const health = await request.get('http://127.0.0.1:8000/health')
    expect(health.ok()).toBeTruthy()

    const auth = await registerEmailUser(request)
    await injectAuth(page, auth)

    await page.goto('/apply', { waitUntil: 'networkidle' })
    await expect(page.getByTestId('apply-step-1')).toBeVisible({ timeout: 15_000 })

    await page.getByTestId('apply-country-US').click()
    await expect(page.getByTestId('apply-step-2')).toBeVisible({ timeout: 15_000 })

    // Wait for RAG checklist to load (not spinner)
    await expect(page.getByTestId('apply-loading')).toHaveCount(0, { timeout: 20_000 })
    const material = page.locator('[data-testid^="apply-material-"]').first()
    await expect(material).toBeVisible({ timeout: 20_000 })

    await page.getByTestId('apply-cta').click()
    await page.waitForURL(/\/materials-wizard/, { timeout: 10_000 })
    await expect(page).toHaveURL(/country=US/)
    await expect(page).toHaveURL(/visa_type=tourism/)

    // Wizard shell visible
    await expect(page.locator('[data-testid^="mw-step-"]').first()).toBeVisible({ timeout: 15_000 })
  })

  test('Schengen country shows zh-CN name on /apply step 1', async ({ page, request }) => {
    const auth = await registerEmailUser(request)
    await injectAuth(page, auth)

    await page.goto('/apply', { waitUntil: 'networkidle' })
    const frCard = page.getByTestId('apply-country-FR')
    await expect(frCard).toBeVisible({ timeout: 15_000 })
    await expect(frCard).toContainText(/法国|申根/)
  })
})
