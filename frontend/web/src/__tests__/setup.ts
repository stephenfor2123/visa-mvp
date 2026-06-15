/**
 * src/__tests__/setup.ts
 * Vitest global setup — mocks and polyfills needed across all unit tests.
 */
import { config } from '@vue/test-utils'
import { beforeAll } from 'vitest'

// Mock Element Plus so components render without the full UI library
beforeAll(() => {
  config.global.config = {
    warnHandler: () => {},
    devtools: false
  }
})

// Suppress console.error in tests (Element Plus emits some during auto-import)
const _origError = console.error
console.error = (...args: unknown[]) => {
  if (
    typeof args[0] === 'string' &&
    (args[0].includes('[Vue warn]') || args[0].includes('AutoImport'))
  ) {
    return
  }
  _origError(...args)
}