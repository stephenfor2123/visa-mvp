/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createI18n } from 'vue-i18n'
import en from '@shared/i18n/en.json'
import { applyRouteSeo } from '@/seo/applySeo.js'

vi.stubGlobal('import.meta', { env: { VITE_SITE_URL: 'https://htexvisa.com' } })

function makeI18n() {
  return createI18n({
    legacy: false,
    locale: 'en',
    messages: { en },
  })
}

describe('applyRouteSeo', () => {
  beforeEach(() => {
    document.head.innerHTML = '<title>Htex</title>'
    document.documentElement.lang = 'en'
  })

  it('sets indexable meta for Home', () => {
    const i18n = makeI18n()
    applyRouteSeo({ name: 'Home', path: '/home', meta: {} }, i18n)

    expect(document.title).toContain('Visa application assistant')
    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('index,follow')
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://htexvisa.com/home')
    expect(document.querySelector('meta[name="description"]')?.getAttribute('content')).toContain('$19.9')
    const geo = document.getElementById('seo-geo-jsonld')
    expect(geo).toBeTruthy()
    expect(geo.textContent).toContain('SoftwareApplication')
    expect(geo.textContent).toContain('Organization')
  })

  it('includes FAQPage schema on Resources FAQ route', () => {
    const i18n = makeI18n()
    applyRouteSeo({ name: 'ResourcesFaq', path: '/resources/faq', meta: {} }, i18n)
    const geo = document.getElementById('seo-geo-jsonld')
    expect(geo.textContent).toContain('FAQPage')
  })

  it('sets noindex for login', () => {
    const i18n = makeI18n()
    applyRouteSeo({ name: 'Login', path: '/login', meta: { title: 'nav.login' } }, i18n)

    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex,nofollow')
    expect(document.getElementById('seo-geo-jsonld')).toBeNull()
  })

  it('sets noindex for admin routes', () => {
    const i18n = makeI18n()
    applyRouteSeo({ name: 'AdminDashboard', path: '/admin/dashboard', meta: {} }, i18n)

    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex,nofollow')
  })

  it('does not duplicate canonical/alternate links on Agreement route', () => {
    // Simulate production index.html baseline tags.
    document.head.innerHTML = `
      <title>Htex</title>
      <link rel="canonical" href="https://htexvisa.com/" />
      <link rel="alternate" type="text/plain" href="https://htexvisa.com/llms.txt" title="LLM site summary" />
    `

    const i18n = makeI18n()
    applyRouteSeo({ name: 'Agreement', path: '/agreement', meta: {} }, i18n)

    expect(document.head.querySelectorAll('link[rel="canonical"]').length).toBe(1)
    expect(document.head.querySelectorAll('link[rel="alternate"]').length).toBe(1)
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://htexvisa.com/agreement')
    expect(document.querySelector('link[rel="alternate"]')?.getAttribute('href')).toBe('https://htexvisa.com/llms.txt')
  })
})
