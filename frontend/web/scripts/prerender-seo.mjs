import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const dist = join(root, 'dist')
const origin = process.env.PRERENDER_ORIGIN || 'http://127.0.0.1:4173'
const publicOrigin = (process.env.VITE_SITE_URL || 'https://htexvisa.com').replace(/\/$/, '')
const paths = [
  '/home',
  '/destinations',
  '/schengen-countries',
  '/apply',
  '/diagnose',
  '/resources',
  '/resources/wiki',
  '/resources/policy',
  '/resources/templates',
  '/resources/faq',
  '/contact',
  '/pricing',
  '/agreement',
  // Render the fallback shell last because this overwrites dist/index.html.
  '/',
]

function waitForServer(url, timeoutMs = 20_000) {
  const started = Date.now()
  return new Promise((resolveReady, reject) => {
    const attempt = async () => {
      try {
        const response = await fetch(url)
        if (response.ok) return resolveReady()
      } catch {}
      if (Date.now() - started > timeoutMs) {
        return reject(new Error(`Preview server did not become ready at ${url}`))
      }
      setTimeout(attempt, 200)
    }
    attempt()
  })
}

function outputFileFor(pathname) {
  return pathname === '/' ? join(dist, 'index.html') : join(dist, pathname.slice(1), 'index.html')
}

const preview = spawn(
  process.execPath,
  [join(root, 'node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', '4173'],
  { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] },
)

let browser
try {
  await waitForServer(origin)
  browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()

  for (const pathname of paths) {
    await page.goto(`${origin}${pathname}`, { waitUntil: 'networkidle', timeout: 30_000 })
    await page.waitForSelector('#app main, #app .page, #app [class*="page"]', { timeout: 10_000 })

    await page.evaluate(({ canonical, siteOrigin }) => {
      document.querySelectorAll(
        'meta[name="description"]:not([data-seo-managed]), meta[name="robots"]:not([data-seo-managed]), ' +
        'meta[property^="og:"]:not([data-seo-managed]), meta[name^="twitter:"]:not([data-seo-managed]), ' +
        'link[rel="canonical"]:not([data-seo-managed]), script[type="application/ld+json"]:not([data-seo-managed])',
      ).forEach((node) => node.remove())

      document.querySelectorAll('[data-seo-managed]').forEach((node) => node.removeAttribute('data-seo-managed'))
      document.querySelectorAll('link[href], script[src], img[src]').forEach((node) => {
        for (const attr of ['href', 'src']) {
          const value = node.getAttribute(attr)
          if (value?.startsWith('/')) node.setAttribute(attr, `${siteOrigin}${value}`)
        }
      })

      const canonicalNode = document.querySelector('link[rel="canonical"]')
      if (canonicalNode) canonicalNode.href = canonical
    }, { canonical: `${publicOrigin}${pathname}`, siteOrigin: publicOrigin })

    const html = `<!DOCTYPE html>\n${await page.locator('html').evaluate((el) => el.outerHTML)}\n`
    const target = outputFileFor(pathname)
    await mkdir(dirname(target), { recursive: true })
    await writeFile(target, html, 'utf8')
    console.log(`prerendered ${pathname}`)
  }

  const rootHtml = await readFile(join(dist, 'index.html'), 'utf8')
  if (!rootHtml.includes('<h1') || !rootHtml.includes('application/ld+json')) {
    throw new Error('Prerender validation failed: root HTML is missing crawlable content or JSON-LD')
  }
} finally {
  await browser?.close()
  preview.kill('SIGTERM')
}
