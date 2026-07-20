import { readFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const dist = join(root, 'dist')
const origin = (process.env.VITE_SITE_URL || 'https://htexvisa.com').replace(/\/$/, '')
const failures = []

const read = (path) => readFile(path, 'utf8')
const count = (text, pattern) => [...text.matchAll(pattern)].length
const value = (text, pattern) => text.match(pattern)?.[1]?.trim() || ''

const sitemap = await read(join(dist, 'sitemap.xml'))
const urls = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1])
const titles = new Map()

for (const absoluteUrl of urls) {
  const url = new URL(absoluteUrl)
  const pathname = url.pathname
  const target = pathname === '/'
    ? join(dist, 'index.html')
    : join(dist, pathname.replace(/^\/|\/$/g, ''), 'index.html')

  let html
  try {
    html = await read(target)
  } catch {
    failures.push(`${pathname}: missing generated HTML`)
    continue
  }

  const title = value(html, /<title>(.*?)<\/title>/s)
  const canonical = value(html, /<link[^>]+rel="canonical"[^>]+href="([^"]+)"/)
  const description = value(html, /<meta[^>]+name="description"[^>]+content="([^"]+)"/)
  const robots = value(html, /<meta[^>]+name="robots"[^>]+content="([^"]+)"/)

  if (!title) failures.push(`${pathname}: missing title`)
  if (title.length > 70) failures.push(`${pathname}: title exceeds 70 characters`)
  if (!description || description.length < 25) failures.push(`${pathname}: description is missing or too short`)
  if (canonical !== `${origin}${pathname}`) failures.push(`${pathname}: canonical mismatch (${canonical})`)
  if (!robots.includes('index')) failures.push(`${pathname}: page is not indexable`)
  if (count(html, /<h1(?:\s|>)/g) !== 1) failures.push(`${pathname}: expected exactly one h1`)
  if (!html.includes('application/ld+json')) failures.push(`${pathname}: missing JSON-LD`)

  if (pathname.includes('/visa-guides/')) {
    if (count(html, /hreflang="(?:en|vi|id|zh-CN)"/g) !== 4) failures.push(`${pathname}: incomplete hreflang cluster`)
    if (!html.includes('hreflang="x-default"')) failures.push(`${pathname}: missing x-default hreflang`)
    if (!pathname.endsWith('/visa-guides/')) {
      if (!html.includes('"BreadcrumbList"')) failures.push(`${pathname}: missing BreadcrumbList schema`)
      if (!html.includes('"FAQPage"')) failures.push(`${pathname}: missing FAQPage schema`)
      if (!html.includes('rel="noopener"')) failures.push(`${pathname}: missing official outbound sources`)
    }
  }

  if (title) {
    const duplicate = titles.get(title)
    if (duplicate && !['/', '/home'].includes(pathname)) failures.push(`${pathname}: duplicate title also used by ${duplicate}`)
    else titles.set(title, pathname)
  }
}

for (const asset of ['robots.txt', 'sitemap.xml', 'llms.txt', 'llms-full.txt', 'ai-index.json', 'feed.xml']) {
  try {
    const body = await read(join(dist, asset))
    if (!body.trim()) failures.push(`${asset}: empty`)
  } catch {
    failures.push(`${asset}: missing`)
  }
}

const aiIndex = JSON.parse(await read(join(dist, 'ai-index.json')))
if (aiIndex.pages.length !== 20) failures.push(`ai-index.json: expected 20 article records, got ${aiIndex.pages.length}`)
if (urls.length !== 38) failures.push(`sitemap.xml: expected 38 URLs, got ${urls.length}`)

if (failures.length) {
  console.error(`SEO audit failed with ${failures.length} issue(s):`)
  failures.forEach((failure) => console.error(`- ${failure}`))
  process.exit(1)
}

console.log(`SEO audit passed: ${urls.length} indexable URLs, ${aiIndex.pages.length} localized articles, 0 blocking issues`)
