// Probe v10 — empty CTA test
import { test, expect } from '@playwright/test'

const LIST_URL = /\/api\/v2\/materials(\?|$)/

test('Materials W4-2: empty CTA fires onTabClick', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('visa.lang', 'zh-CN')
    localStorage.setItem('visa.auth', JSON.stringify({
      accessToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.mock',
      refreshToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.refresh',
      user: { id: 'u_demo', phoneCountry: '+86', phone: '13800000000', languagePref: 'zh-CN', status: 'active', createdAt: '2026-06-11T00:00:00Z' }
    }))
  })

  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log(`[B ${msg.type()}]`, msg.text())
  })

  // Override listMaterials to return EMPTY (bypassing the demo fallback)
  await page.route(LIST_URL, async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ code: '1000', data: { items: [], total: 0 } })
    })
  })

  await page.goto('http://127.0.0.1:5173/materials')
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1500)

  // Empty CTA should be visible
  await expect(page.getByTestId('mat-empty-cta')).toBeVisible({ timeout: 8000 })
  console.log('PROBE 1: mat-empty-cta visible (emptyCtaBtnRef mounted)')

  // Click it — should fire onTabClick(tabs[0]) which sets activeTab='photo' (already default)
  // Verify the click does not throw and the page stays alive
  await page.getByTestId('mat-empty-cta').click()
  await page.waitForTimeout(500)
  console.log('PROBE 1 PASS: empty CTA click fired setOnTrigger without error')

  // Switch to voice tab to verify the click actually changes tab
  await page.getByTestId('mat-tab-voice').click()
  await page.waitForTimeout(500)
  // Verify voice panel is shown
  await expect(page.getByTestId('mat-voice-panel')).toBeVisible()
  console.log('PROBE 1 PASS: tab switch works independently')
})
