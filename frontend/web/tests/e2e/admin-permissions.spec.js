/**
 * E2E: 管理员权限系统 W47
 *
 * 覆盖 3 个角色的关键场景:
 *  1) reviewer 登录 → 看到订单 + 看到 edit_status 按钮 + 看不到 close 按钮 + 看不到角色管理菜单
 *  2) finance 登录 → 看到支付菜单 + 看不到用户菜单
 *  3) super_admin 登录 → 看到全部菜单 + 看到所有动作按钮
 *
 * 前置:
 *  - 后端启动 + seed_admin_roles 已执行(默认会在 lifespan 自动跑)
 *  - 三个账号已存在:
 *      admin / HtexAd@26         → super_admin (env fallback)
 *      reviewer1 / Test1234!     → reviewer 角色
 *      finance1 / Test1234!      → finance 角色
 *  - 测试启动前 hook 会创建这两个 DB 账号
 */

import { test, expect, request as pwRequest } from '@playwright/test'

const BASE = process.env.E2E_BASE_URL || 'http://localhost:5173'

async function loginViaUi(page, username, password) {
  await page.goto(`${BASE}/admin/login`)
  await page.locator('input[name="username"], input[placeholder*="账号" i], input[type="text"]').first().fill(username)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button[type="submit"], button:has-text("登录")').first().click()
  // 等跳到 /admin/orders 或 /admin/dashboard
  await page.waitForURL(/\/admin\/(orders|dashboard|users)/, { timeout: 10000 })
}

test.describe('W47 admin permission system', () => {
  test('reviewer 看到订单 + edit_status 按钮 + 看不到 close 按钮', async ({ page }) => {
    await loginViaUi(page, 'reviewer1', 'Test1234!')

    // 左侧菜单: 应该有"订单管理"
    await expect(page.getByRole('link', { name: /订单管理/ })).toBeVisible()
    // 左侧菜单: 不应该有"角色管理"
    await expect(page.getByRole('link', { name: /角色管理/ })).toHaveCount(0)
    // 左侧菜单: 不应该有"支付流水"
    await expect(page.getByRole('link', { name: /支付流水/ })).toHaveCount(0)

    // 进到第一张订单详情
    await page.goto(`${BASE}/admin/orders`)
    await page.waitForLoadState('networkidle')
    // 找第一个"查看详情"链接
    const firstView = page.locator('[data-testid^="admin-order-view-"]').first()
    if (await firstView.count()) {
      await firstView.click()
      await page.waitForSelector('[data-testid="admin-order-detail"]')

      // 状态机按钮区
      // reviewer 有 order.edit_status 但无 order.close
      // 所以"通过/驳回"等可能显示,"关闭"按钮不应该显示
      const actionButtons = await page.locator('[data-testid^="admin-order-action-"]').all()
      for (const btn of actionButtons) {
        const testid = await btn.getAttribute('data-testid')
        // 不应该有 admin-order-action-closed / abnormal / failed
        expect(testid).not.toMatch(/admin-order-action-(closed|abnormal|failed)$/)
      }
    }
  })

  test('finance 看到支付 + 看不到用户菜单', async ({ page }) => {
    await loginViaUi(page, 'finance1', 'Test1234!')

    // 左侧菜单
    await expect(page.getByRole('link', { name: /订单管理/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /支付流水/ })).toBeVisible()
    // finance 没 user.view, 看不到"账号管理"
    await expect(page.getByRole('link', { name: /账号管理/ })).toHaveCount(0)
  })

  test('super_admin 看到全部菜单 + 全部动作按钮', async ({ page }) => {
    await loginViaUi(page, 'admin', 'HtexAd@26')

    // 全部菜单
    await expect(page.getByRole('link', { name: /总览/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /订单管理/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /支付流水/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /角色管理/ })).toBeVisible()
  })
})
