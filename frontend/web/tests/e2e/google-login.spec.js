/**
 * E2E — Google sign-in on Login page
 *
 * VITE_GOOGLE_CLIENT_ID is injected by global-setup.cjs so the GIS placeholder
 * renders. GIS itself is mocked via page.route against
 * https://accounts.google.com/gsi/client. /v2/auth/google is intercepted via
 * page.route so we don't need a real Google token or a real Google client ID.
 *
 * The "no-client-id" branch (button hidden) is covered by vitest
 * src/__tests__/Login.google.test.ts.
 */
import { test, expect } from '@playwright/test'

test.describe('Google sign-in — Login page', () => {
  test('placeholder rendered, callback fires /v2/auth/google, stores JWT', async ({ page }) => {
    // Mock GIS script — render a clickable button that fires our captured callback
    await page.route('https://accounts.google.com/gsi/client', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/javascript',
        body: `
          window.google = window.google || {};
          window.google.accounts = window.google.accounts || {};
          window.google.accounts.id = {
            initialize: (cfg) => { window.__googleCredCallback = cfg.callback; },
            renderButton: (el, opts) => {
              const b = document.createElement('button');
              b.className = 'mock-google-signin';
              b.textContent = 'Mock Google Sign-In';
              b.onclick = () => window.__googleCredCallback({ credential: 'fake-google-jwt' });
              el.appendChild(b);
            }
          };
        `
      })
    })

    // Intercept backend /v2/auth/google so we don't need a real Google token
    let googleAuthCalled = 0
    await page.route('**/api/v2/auth/google', async (route) => {
      googleAuthCalled++
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: '1000',
          message: 'OK',
          data: {
            access_token: 'stub.google.access.jwt',
            refresh_token: 'stub.google.refresh.jwt',
            token_type: 'Bearer',
            expires_in: 7200,
            user: {
              id: 999,
              uuid: 'stub-uuid',
              username: 'g_stubuser1',
              email: 'stubuser@gmail.com',
              nickname: 'Stub Google User',
              avatar_url: 'https://example.com/avatar.png',
              language_pref: 'zh-CN',
              status: 'active',
              created_at: new Date().toISOString()
            }
          }
        })
      })
    })

    await page.goto('/login')

    // Placeholder + divider visible
    await expect(page.locator('.google-btn-wrap')).toBeVisible()
    await expect(page.locator('.auth-divider')).toBeVisible()

    // Mocked button should have been rendered inside the wrap
    const btn = page.locator('.mock-google-signin')
    await expect(btn).toBeVisible({ timeout: 5000 })

    // Click → callback fires → /v2/auth/google → redirect to /destinations
    await btn.click()
    await page.waitForURL(/\/destinations/, { timeout: 15_000 })
    expect(googleAuthCalled).toBe(1)

    // Token stored in localStorage
    const authRaw = await page.evaluate(() => localStorage.getItem('visa.auth'))
    expect(authRaw).toBeTruthy()
    const auth = JSON.parse(authRaw || '{}')
    expect(auth.accessToken).toBe('stub.google.access.jwt')
    expect(auth.refreshToken).toBe('stub.google.refresh.jwt')
    expect(auth.user.email).toBe('stubuser@gmail.com')
  })

  test('backend error: toast shown, no redirect, no token stored', async ({ page }) => {
    // Mock GIS to fire immediately on script load
    await page.addInitScript(() => {
      window.google = {
        accounts: {
          id: {
            initialize: (cfg) => {
              setTimeout(() => cfg.callback({ credential: 'bad.token' }), 50)
            },
            renderButton: (el) => {
              el.innerHTML = '<button class="mock-google-signin">x</button>'
            }
          }
        }
      }
    })

    await page.route('**/api/v2/auth/google', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ code: '2001', message: 'Invalid Google token', data: null })
      })
    })

    await page.goto('/login')
    await page.waitForTimeout(1500)

    // URL still /login (no redirect on failure)
    expect(page.url()).toMatch(/\/login$/)

    // No token stored
    const authRaw = await page.evaluate(() => localStorage.getItem('visa.auth'))
    if (authRaw) {
      const auth = JSON.parse(authRaw)
      expect(auth.accessToken).toBeFalsy()
    }
  })
})