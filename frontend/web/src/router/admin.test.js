import { describe, expect, it } from 'vitest'
import { adminRoutes } from './admin'

describe('admin routes', () => {
  it('keeps the admin root inside the admin namespace', () => {
    const root = adminRoutes.find(route => route.path === '/admin')
    const index = root.children.find(route => route.path === '')
    expect(index.redirect).toBe('/admin/dashboard')
  })
})
