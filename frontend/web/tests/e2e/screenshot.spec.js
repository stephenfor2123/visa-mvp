/**
 * S1 截图脚本 — 启动前端 + 后端,截 /register 页
 * 需先确保后端在 8000 端口运行(已在) + Playwright 全局 setup 会起 vite
 */
import { test, expect } from '@playwright/test'

test('screenshot register page 1440x900', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/register')
  await expect(page.getByTestId('reg-submit')).toBeVisible()
  // 等待字体/样式稳定
  await page.waitForTimeout(500)
  await page.screenshot({
    path: 'screenshots/register.png',
    fullPage: false
  })
})
