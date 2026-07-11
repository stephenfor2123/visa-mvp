// tests/e2e/password-toggle.spec.js — W53: AppInput 密码可见性切换
//
// 验证:
//  1) 注册页 / 登录页 / 忘记密码页 — 密码输入框 type=password 初始,有点击眼睛按钮
//  2) 点击眼睛 → input.type 变 text + aria-pressed=true
//  3) 再点 → 切回 password
//  4) 不会影响 v-model 状态(切来切去密码内容不变)
import { test, expect } from '@playwright/test'

const PAGES = [
  {
    name: 'register',
    url: '/register',
    inputTestid: 'reg-password',
  },
  {
    name: 'forgot',
    url: '/forgot-password',
    inputTestid: 'forgot-new-pwd',
  },
  {
    name: 'login',
    url: '/login',
    inputTestid: 'login-password',
  },
]

for (const p of PAGES) {
  test(`[${p.name}] 眼睛按钮切换 input type=password ↔ text`, async ({ page, context }) => {
    await context.addInitScript(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          accessToken: 'fake-jwt',
          refreshToken: 'fake-refresh',
          user: { id: 1, email: 'demo@htex.com', name: 'Demo' },
        }))
      } catch {}
    })
    await page.goto(p.url)

    // 找到密码输入 + 它旁边的 toggle 按钮
    const input = page.locator(`[data-testid="${p.inputTestid}"] input`)
    const toggle = page.locator(`[data-testid="${p.inputTestid}-toggle"]`)

    await expect(input).toBeVisible({ timeout: 10000 })
    await expect(toggle).toBeVisible()

    // 初始 type=password
    await expect(input).toHaveAttribute('type', 'password')
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')

    // 填一个测试密码
    await input.fill('MySecret123!')
    await expect(input).toHaveValue('MySecret123!')

    // 点眼睛 → 切到 text
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'text')
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    // v-model 仍保持
    await expect(input).toHaveValue('MySecret123!')

    // 再点 → 切回 password
    await toggle.click()
    await expect(input).toHaveAttribute('type', 'password')
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await expect(input).toHaveValue('MySecret123!')
  })
}
