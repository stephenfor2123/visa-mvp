#!/usr/bin/env node
/**
 * Optional SEO post-build pipeline (Playwright prerender + guides + audit).
 * Set SKIP_SEO=1 to skip (recommended for CI/Vercel when browsers are unavailable).
 */
import { spawnSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

if (process.env.SKIP_SEO === '1') {
  console.log('run-seo-pipeline: SKIP_SEO=1 — skipping prerender/guides/audit')
  process.exit(0)
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const steps = ['prerender-seo.mjs', 'generate-seo-guides.mjs', 'audit-seo.mjs']

for (const script of steps) {
  const result = spawnSync(process.execPath, [resolve(root, 'scripts', script)], {
    cwd: root,
    stdio: 'inherit',
    env: process.env,
  })
  if (result.status !== 0) {
    console.error(`run-seo-pipeline: ${script} failed (exit ${result.status})`)
    process.exit(result.status || 1)
  }
}
