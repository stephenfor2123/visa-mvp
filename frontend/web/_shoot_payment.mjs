/**
 * W14-10 PaymentResult screenshot script (verify-only retry).
 * Uses @playwright/test installed locally.
 * Bypasses vite build (macOS M-series hang).
 * Renders PaymentResult preview HTML served by python http.server on :5173.
 */
import { chromium } from '@playwright/test'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const OUT = '/Users/apple/.mavis/plans/plan_0dab473a/outputs/W14-10-payment-result/screenshots'
const BASE = 'http://127.0.0.1:5173/payment_preview.html'

const STATES = ['success', 'failed', 'pending']
const ORDER_ID = 'V2-20260614-009900'

const results = []

for (const status of STATES) {
  const browser = await chromium.launch({ headless: true, channel: 'chrome', timeout: 30000 })
  try {
    const ctx = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      deviceScaleFactor: 1
    })
    const page = await ctx.newPage()
    const url = `${BASE}?orderId=${ORDER_ID}&status=${status}`
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 })
    await page.waitForTimeout(2000)
    const fname = `payment_result_${status}.png`
    const fpath = path.join(OUT, fname)
    await page.screenshot({ path: fpath, fullPage: false })
    const buf = fs.readFileSync(fpath)
    const hash = crypto.createHash('sha256').update(buf).digest('hex')
    results.push({ status, file: fpath, hash, size: buf.length })
    console.log(`OK ${status} hash=${hash.slice(0, 16)} size=${buf.length}`)
  } catch (e) {
    console.error(`FAIL ${status}: ${e.message}`)
    results.push({ status, error: e.message })
  } finally {
    await browser.close()
  }
}

const hashes = results.filter(r => r.hash).map(r => r.hash)
const distinct = new Set(hashes)
console.log(`\n=== distinct ${distinct.size}/${hashes.length} ===`)
fs.writeFileSync(path.join(OUT, '_manifest.json'), JSON.stringify({
  total: results.length,
  distinct: distinct.size,
  items: results
}, null, 2))
if (distinct.size !== hashes.length) {
  console.error('FAIL: hash collision')
  process.exit(1)
}
console.log('Manifest written')
