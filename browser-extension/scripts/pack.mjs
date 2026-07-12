#!/usr/bin/env node
// Pack extension as zip for sideloading (excludes node_modules, tests)
import { execSync } from 'node:child_process'
import { existsSync, readFileSync, unlinkSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const manifest = JSON.parse(readFileSync(resolve(ROOT, 'manifest.json'), 'utf8'))
const VERSION = manifest.version || '0.0.0'
const OUT = resolve(ROOT, `htex-ds160-extension-v${VERSION}.zip`)

if (existsSync(OUT)) unlinkSync(OUT)

execSync(
  `cd "${ROOT}" && zip -r "${OUT}" . ` +
  `-x "node_modules/*" -x "test/*" -x "scripts/*" -x "*.zip" ` +
  `-x "package-lock.json" -x "ux-preview-v0.2.html"`,
  { stdio: 'inherit' }
)

console.log('✅ Packed:', OUT)
