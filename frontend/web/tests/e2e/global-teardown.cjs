'use strict'
/* eslint-disable no-console */
/**
 * Playwright global teardown — kill the vite dev server we started in global-setup.
 */
module.exports = async function globalTeardown() {
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