'use strict'
/**
 * QA E2E config — 独立于 frontend/web/playwright.config.cjs
 *
 * 用途:C 测试 agent 写的 E2E (qa/E2E/*.spec.js),需要复用:
 *   - vite dev server (5173) 启停:沿用 global-setup.cjs / global-teardown.cjs
 *   - baseURL / actionTimeout 等:与主 config 对齐
 *
 * 区别:
 *   - testDir 指向 qa/E2E/ 而不是 tests/e2e/
 *   - 不带 CI retries (单线程,跑 1 次出真实结果)
 *
 * 跑法:
 *   cd frontend/web
 *   npx playwright test --config qa/qa-playwright.config.cjs --reporter=list
 *   npx playwright test --config qa/qa-playwright.config.cjs qa/E2E/validation.spec.js
 */
const { defineConfig, devices } = require('@playwright/test')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '..')  // frontend/web/

module.exports = defineConfig({
  testDir: path.join(__dirname, 'E2E'),
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: path.join(ROOT, 'playwright-report') }]
  ],
  globalSetup: path.join(ROOT, 'tests', 'e2e', 'global-setup.cjs'),
  globalTeardown: path.join(ROOT, 'tests', 'e2e', 'global-teardown.cjs'),
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
