import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const siteOrigin = (process.env.VITE_SITE_URL || 'https://htexvisa.com').replace(/\/$/, '')
const key = process.env.INDEXNOW_KEY

if (!key) {
  console.error('INDEXNOW_KEY is required. Generate a key in Bing Webmaster Tools and expose its .txt file at the site root.')
  process.exit(1)
}

const sitemapPath = resolve(import.meta.dirname, '../dist/sitemap.xml')
const sitemap = await readFile(sitemapPath, 'utf8')
const urlList = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1])

const response = await fetch('https://api.indexnow.org/indexnow', {
  method: 'POST',
  headers: { 'content-type': 'application/json; charset=utf-8' },
  body: JSON.stringify({
    host: new URL(siteOrigin).host,
    key,
    keyLocation: `${siteOrigin}/${key}.txt`,
    urlList,
  }),
})

if (!response.ok) {
  throw new Error(`IndexNow submission failed: ${response.status} ${await response.text()}`)
}

console.log(`Submitted ${urlList.length} URLs to IndexNow.`)
