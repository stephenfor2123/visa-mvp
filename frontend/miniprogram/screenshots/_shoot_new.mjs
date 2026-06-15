// _shoot_new.mjs - W8-2 截 4 张新页 mobile preview (1 页 1 语种固定)
// 复用 frontend/web/node_modules/playwright 1.60 + chromium-1223 缓存
import { chromium } from '/Users/stephen/Desktop/签证项目/frontend/web/node_modules/playwright/index.mjs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourceDir = path.join(__dirname, 'source')
const outDir = __dirname

// 4 张:order(中文) / payment(英文) / forgot(印尼) / agreement(越南)
const JOBS = [
  { name: 'order_zh',     file: 'order.html',     lang: 'zh-CN' },
  { name: 'payment_en',   file: 'payment.html',   lang: 'en'     },
  { name: 'forgot_id',    file: 'forgot.html',    lang: 'id'     },
  { name: 'agreement_vi', file: 'agreement.html', lang: 'vi'     }
]

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({
  viewport: { width: 375, height: 812 },
  deviceScaleFactor: 2
})
const page = await ctx.newPage()

const results = []
for (const job of JOBS) {
  const url = 'file://' + path.join(sourceDir, job.file) + '?lang=' + job.lang
  await page.goto(url, { waitUntil: 'networkidle' })
  await page.waitForTimeout(200)
  const out = path.join(outDir, `${job.name}.png`)
  await page.screenshot({ path: out, fullPage: false, omitBackground: false })
  const buf = fs.readFileSync(out)
  const sha = createHash('sha256').update(buf).digest('hex')
  results.push({ name: job.name, file: job.file, lang: job.lang, out, bytes: buf.length, sha256: sha })
  console.log(`[shot] ${job.name}.png  ${buf.length} bytes  sha256=${sha.slice(0, 16)}...`)
}

await browser.close()

// distinct 校验
const shaSet = new Set(results.map(r => r.sha256))
console.log('---')
console.log('distinct sha256: ' + shaSet.size + '/' + results.length + (shaSet.size === results.length ? ' PASS' : ' FAIL'))
console.log('done')

// 把 sha 写进 results.json 便于 deliverable.md 引用
fs.writeFileSync(path.join(outDir, 'screenshots_results.json'), JSON.stringify(results, null, 2), 'utf8')
process.exit(shaSet.size === results.length ? 0 : 1)
