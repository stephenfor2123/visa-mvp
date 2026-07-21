/**
 * Site-wide SEO constants.
 * Public content URLs in sitemap must be approved before adding new paths.
 */

export const SITE_NAME = 'Htex'

/** Canonical origin — override via VITE_SITE_URL in production. */
export function siteOrigin() {
  const fromEnv = typeof import.meta !== 'undefined' && import.meta.env?.VITE_SITE_URL
  const base = (fromEnv || 'https://htexvisa.com').replace(/\/$/, '')
  return base
}

/** Default OG/Twitter image (square app icon). */
export function defaultOgImage() {
  return `${siteOrigin()}/icons/icon-512.png`
}

/**
 * Paths allowed in sitemap.xml — only existing public routes.
 * Add new guide URLs here only after content owner sign-off.
 */
export const SITEMAP_PATHS = [
  '/',
  '/home',
  '/destinations',
  '/schengen-countries',
  '/apply',
  '/diagnose',
  '/resources',
  '/resources/wiki',
  '/resources/policy',
  '/resources/templates',
  '/resources/faq',
  '/contact',
  '/about',
  '/pricing',
  '/agreement',
]

/** Route names that may be indexed; all others get noindex,nofollow. */
export const INDEXABLE_ROUTE_NAMES = new Set([
  'Home',
  'Destinations',
  'SchengenCountries',
  'Apply',
  'Diagnose',
  'Resources',
  'ResourcesWiki',
  'ResourcesPolicy',
  'ResourcesTemplates',
  'ResourcesFaq',
  'Contact',
  'About',
  'Pricing',
  'Agreement',
])
