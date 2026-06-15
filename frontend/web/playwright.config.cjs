'use strict'
const { defineConfig, devices } = require('@playwright/test')

/**
 * Playwright config — S1 Web 注册端到端
 *
 * 假设后端 FastAPI 已在 http://127.0.0.1:8000 跑着(由 B Agent 起)。
 * globalSetup 在测试前先起 vite dev server,测试结束后关掉。
 *
 * 跑法:
 *   cd frontend/web
 *   npx playwright test                    # 全跑
 *   npx playwright test register.spec.js   # 只跑注册
 *   npx playwright test --headed           # 有头模式(调试用)
 */
module.exports = defineConfig({
  testDir: './tests/e2e',
  // 注册流程涉及 DB 状态,串行更稳;happy path 用随机手机号避免冲突
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }]
  ],
  globalSetup: './tests/e2e/global-setup.cjs',
  globalTeardown: './tests/e2e/global-teardown.cjs',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 30_000
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ]
})