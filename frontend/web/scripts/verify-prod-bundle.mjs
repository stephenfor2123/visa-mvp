#!/usr/bin/env node
/**
 * Post-build verification of production artifacts.
 * Run after `vite build` / `vercel build` before deploy.
 *
 * Fails if Google Client ID or API base did not bake into the bundle.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

function findAssetRoots() {
  const candidates = [
    path.join(root, '.vercel', 'output', 'static', 'assets'),
    path.join(root, 'dist', 'assets'),
  ]
  return candidates.filter((p) => fs.existsSync(p))
}

function readEnv(key) {
  for (const file of ['.env.production', '.env']) {
    const p = path.join(root, file)
    if (!fs.existsSync(p)) continue
    for (const line of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
      if (line.startsWith(`${key}=`)) {
        return line.slice(key.length + 1).trim().replace(/^['"]|['"]$/g, '')
      }
    }
  }
  return (process.env[key] || '').trim()
}

const googleId = readEnv('VITE_GOOGLE_CLIENT_ID')
const apiBase = readEnv('VITE_API_BASE')
const roots = findAssetRoots()

if (!roots.length) {
  console.error('verify-prod-bundle: no dist/.vercel assets found — build first')
  process.exit(1)
}

let blob = ''
for (const dir of roots) {
  for (const name of fs.readdirSync(dir)) {
    if (!/\.(js|mjs|css)$/.test(name)) continue
    blob += fs.readFileSync(path.join(dir, name), 'utf8')
  }
}

const failures = []
if (googleId && !blob.includes(googleId)) {
  failures.push(`bundle missing VITE_GOOGLE_CLIENT_ID value (Google button will hide)`)
}
if (apiBase && !blob.includes(apiBase) && !blob.includes('api.htexvisa.com')) {
  failures.push(`bundle missing API base / api.htexvisa.com`)
}
if (/\btrue\b/.test(String(process.env.VITE_MOCK)) && blob.includes('mock.access')) {
  failures.push('bundle looks like MOCK mode was enabled')
}

if (failures.length) {
  console.error('verify-prod-bundle FAILED:')
  for (const f of failures) console.error('  - ' + f)
  process.exit(1)
}

console.log('verify-prod-bundle passed (assets in', roots.join(', '), ')')
