#!/usr/bin/env node
/**
 * Production release preflight for the Vite frontend.
 *
 * Catches the class of bugs that silently ship broken UX:
 *  - missing VITE_GOOGLE_CLIENT_ID → Google login button disappears
 *  - empty VITE_API_BASE → API calls hit Vercel SPA and 405
 *  - VITE_MOCK left on → mock responses in production
 *
 * Usage:
 *   node scripts/preflight-prod.mjs
 *   npm run preflight:prod
 *
 * Env sources (first wins): process.env, then .env.production, then .env
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {}
  const out = {}
  for (const raw of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const i = line.indexOf('=')
    if (i <= 0) continue
    const key = line.slice(0, i).trim()
    let val = line.slice(i + 1).trim()
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1)
    }
    out[key] = val
  }
  return out
}

const fileEnv = {
  ...parseEnvFile(path.join(root, '.env')),
  ...parseEnvFile(path.join(root, '.env.production')),
}

function get(key) {
  const fromProc = process.env[key]
  if (fromProc !== undefined && String(fromProc).trim() !== '') return String(fromProc).trim()
  const fromFile = fileEnv[key]
  if (fromFile !== undefined && String(fromFile).trim() !== '') return String(fromFile).trim()
  return ''
}

const required = [
  {
    key: 'VITE_API_BASE',
    check: (v) => v.startsWith('https://') && v.includes('/api'),
    hint: 'must be absolute https://api…/api (empty → SPA 405 on /api)',
  },
  {
    key: 'VITE_GOOGLE_CLIENT_ID',
    check: (v) => v.includes('.apps.googleusercontent.com'),
    hint: 'missing → Google login button is hidden in production',
  },
  {
    key: 'VITE_WS_URL',
    check: (v) => v.startsWith('wss://') || v.startsWith('ws://'),
    hint: 'order realtime websocket base',
  },
]

const forbidden = [
  {
    key: 'VITE_MOCK',
    bad: (v) => ['1', 'true', 'yes', 'on'].includes(v.toLowerCase()),
    hint: 'must be false/empty in production builds',
  },
]

const failures = []
const notes = []

for (const rule of required) {
  const v = get(rule.key)
  if (!v) {
    failures.push(`${rule.key} is empty — ${rule.hint}`)
  } else if (!rule.check(v)) {
    failures.push(`${rule.key}="${v}" failed check — ${rule.hint}`)
  } else {
    notes.push(`OK ${rule.key}`)
  }
}

for (const rule of forbidden) {
  const v = get(rule.key)
  if (v && rule.bad(v)) {
    failures.push(`${rule.key}="${v}" — ${rule.hint}`)
  } else {
    notes.push(`OK ${rule.key || '(flag)'}=${v || '(unset)'}`)
  }
}

// Warn (non-fatal) if Stripe publishable key missing — payments may be mock-only.
const stripe = get('VITE_STRIPE_PUBLISHABLE_KEY')
if (!stripe) {
  notes.push('WARN VITE_STRIPE_PUBLISHABLE_KEY unset (ok if PAYMENT_CHANNEL=mock)')
}

console.log('preflight-prod:')
for (const n of notes) console.log('  ' + n)

if (failures.length) {
  console.error('\npreflight-prod FAILED:')
  for (const f of failures) console.error('  - ' + f)
  console.error('\nFix: set vars in Vercel Production env AND local .env.production,')
  console.error('then rebuild. Do not use bare `vercel build --prod` without these.')
  process.exit(1)
}

console.log('\npreflight-prod passed')
