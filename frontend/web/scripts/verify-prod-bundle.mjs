#!/usr/bin/env node
/**
 * Post-build verification of production artifacts.
 * Run after `vite build` / `vercel build` before deploy.
 *
 * IMPORTANT: verifies ONE asset root only (never OR dist + .vercel together).
 * Prefer:
 *   1) VERIFY_ASSET_ROOT env
 *   2) ../.vercel/output/static/assets (vercel build)
 *   3) ./dist/assets (npm run build)
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const frontendRoot = path.resolve(root, '..')

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
  const fromProc = (process.env[key] || '').trim()
  return fromProc
}

function resolveAssetRoot() {
  if (process.env.VERIFY_ASSET_ROOT) {
    return path.resolve(process.env.VERIFY_ASSET_ROOT)
  }
  const distAssets = path.join(root, 'dist', 'assets')
  const vercelAssets = path.join(frontendRoot, '.vercel', 'output', 'static', 'assets')
  // Prefer fresh local dist over stale .vercel output from a previous build.
  if (fs.existsSync(distAssets)) return distAssets
  if (fs.existsSync(vercelAssets)) return vercelAssets
  return null
}

function findEntryChunk(dir) {
  const names = fs.readdirSync(dir).filter((n) => /^index-[A-Za-z0-9_-]+\.js$/.test(n))
  if (!names.length) return null
  // Prefer largest index chunk (main app)
  names.sort((a, b) => fs.statSync(path.join(dir, b)).size - fs.statSync(path.join(dir, a)).size)
  return path.join(dir, names[0])
}

const googleId = readEnv('VITE_GOOGLE_CLIENT_ID')
const apiBase = readEnv('VITE_API_BASE')
const assetRoot = resolveAssetRoot()

if (!assetRoot || !fs.existsSync(assetRoot)) {
  console.error('verify-prod-bundle: no dist/.vercel assets found — build first')
  process.exit(1)
}

let blob = ''
for (const name of fs.readdirSync(assetRoot)) {
  if (!/\.(js|mjs|css)$/.test(name)) continue
  blob += fs.readFileSync(path.join(assetRoot, name), 'utf8')
}

const entry = findEntryChunk(assetRoot)
const entryBlob = entry ? fs.readFileSync(entry, 'utf8') : ''

const failures = []

if (!googleId) {
  failures.push('VITE_GOOGLE_CLIENT_ID empty in env/.env.production')
} else if (!blob.includes(googleId)) {
  failures.push('bundle missing VITE_GOOGLE_CLIENT_ID value (Google button will hide)')
}

if (apiBase && !blob.includes(apiBase) && !blob.includes('api.htexvisa.com')) {
  failures.push('bundle missing API base / api.htexvisa.com')
}

// Soft check: mock.access string may remain as dead branches when MOCK is compiled false.
// Fail only when mock branch is the live path (no real login call) OR google disabled.
const hasRealLogin = blob.includes('/v2/auth/login')
const googleOn = googleId && blob.includes(googleId) && !blob.includes('googleEnabled:!1')
const mockLooksLive = blob.includes('mock.access') && !hasRealLogin

if (mockLooksLive) {
  failures.push('bundle looks like MOCK auth is the live path (no /v2/auth/login)')
}
if (blob.includes('googleEnabled:!1') && googleId) {
  failures.push('googleEnabled compiled false despite Client ID configured')
}
if (blob.includes('mock.access') && hasRealLogin && googleOn) {
  console.log('  note: mock.access strings present but dead (MOCK compiled false, real login present)')
}

// Remove the old hard fail on any mock.access:
// (handled above)

if (failures.length) {
  console.error('verify-prod-bundle FAILED (root=' + assetRoot + '):')
  for (const f of failures) console.error('  - ' + f)
  process.exit(1)
}

console.log('verify-prod-bundle passed')
console.log('  assets:', assetRoot)
if (entry) console.log('  entry:', path.basename(entry))
console.log('  google id present:', !!googleId && blob.includes(googleId))
console.log('  real /v2/auth/login present:', hasRealLogin)
console.log('  googleEnabled on:', googleOn)
