'use strict'
/* eslint-disable no-console */
/**
 * Playwright global setup — S1
 *
 * 后端由 B Agent 在外部起(127.0.0.1:8000),这里只起 vite dev server。
 * 这样 spec 跑得更快也更隔离(后端可复用,不被反复重启)。
 */
const { spawn } = require('node:child_process')
const path = require('node:path')

const FRONTEND_DIR = path.resolve(__dirname, '..', '..')
const PORT = 5173
const READY_TIMEOUT_MS = 30_000

function waitForServer(url, timeoutMs) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = async () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error(`Server at ${url} not ready within ${timeoutMs}ms`))
        return
      }
      try {
        const res = await fetch(url, { method: 'GET' })
        if (res.status < 500) {
          resolve()
          return
        }
      } catch (_) {
        // not yet listening
      }
      setTimeout(tick, 500)
    }
    tick()
  })
}

async function globalSetup() {
  console.log('[global-setup] starting vite dev server...')

  const proc = spawn('npx', ['vite', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: FRONTEND_DIR,
    env: { ...process.env, FORCE_COLOR: '0' },
    stdio: ['ignore', 'pipe', 'pipe']
  })

  proc.stdout.on('data', (d) => process.stdout.write(`[vite] ${d}`))
  proc.stderr.on('data', (d) => process.stderr.write(`[vite] ${d}`))
  proc.on('exit', (code) => {
    if (code !== 0 && code !== null) {
      console.log(`[vite] exited with code=${code}`)
    }
  })

  // Save pid on globalThis so global-teardown can kill it
  globalThis.__viteProc = proc

  try {
    await waitForServer(`http://127.0.0.1:${PORT}/`, READY_TIMEOUT_MS)
    console.log(`[global-setup] vite ready on http://127.0.0.1:${PORT}`)
  } catch (e) {
    try { proc.kill('SIGTERM') } catch (_) {}
    throw e
  }
}

async function globalTeardown() {
  const proc = globalThis.__viteProc
  if (proc && !proc.killed) {
    console.log(`[global-teardown] killing vite pid=${proc.pid}`)
    try {
      proc.kill('SIGTERM')
      await new Promise((r) => setTimeout(r, 500))
      if (!proc.killed) proc.kill('SIGKILL')
    } catch (e) {
      console.warn(`[global-teardown] kill failed: ${e.message}`)
    }
  }
}

module.exports = globalSetup
module.exports.teardown = globalTeardown