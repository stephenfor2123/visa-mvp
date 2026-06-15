// _shoot.mjs - 用 playwright 截 5 张 mobile 设计稿
// 用前端项目自带的 playwright (v1.60, 匹配 chromium-1223 缓存)
import { chromium } from '/Users/stephen/Desktop/签证项目/frontend/web/node_modules/playwright/index.mjs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourceDir = path.join(__dirname, 'source')
const outDir = __dirname

const PAGES = ['login', 'register', 'destinations', 'home', 'profile']

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({
  viewport: { width: 375, height: 812 },
  deviceScaleFactor: 2
})
const page = await ctx.newPage()

for (const name of PAGES) {
  const url = 'file://' + path.join(sourceDir, `${name}.html`)
  await page.goto(url, { waitUntil: 'networkidle' })
  await page.waitForTimeout(200)  // 字体稳定
  const out = path.join(outDir, `${name}.png`)
  await page.screenshot({ path: out, fullPage: false, omitBackground: false })
  console.log(`[shot] ${name}.png saved`)
}

await browser.close()
console.log('done')
