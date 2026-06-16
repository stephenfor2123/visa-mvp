'use strict'
/**
 * W19 fast config: 跑 flows/ 下的跨页/a11y/compat 测试
 *  - baseURL 直接指向 4176 反代 (main dist), 不起 vite dev
 *  - 用系统 Chrome 替代 chromium
 *  - 单 worker, 串行跑
 *
 * 用法:
 *   cd frontend/web
 *   PW_NO_GLOBAL_SETUP=1 PW_BASE_URL=http://127.0.0.1:4176 \
 *     npx playwright test --config=tests/e2e/flows/_fast.config.cjs tests/e2e/flows/10-cross.spec.js ...
 */
const path = require('path')
const { defineConfig, devices } = require('@playwright/test')

module.exports = defineConfig({
  testDir: path.resolve(__dirname),
  testMatch: /10-cross|11-a11y|12-compat/,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4176',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000
  },
  projects: [
    {
      name: 'chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' }
    }
  ]
})
