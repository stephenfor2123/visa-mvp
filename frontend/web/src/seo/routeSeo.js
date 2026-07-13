import { INDEXABLE_ROUTE_NAMES } from './config.js'

/**
 * Per-route SEO copy keys (i18n: seo.pages.<key>).
 * Routes not listed here are noindex unless in INDEXABLE_ROUTE_NAMES with defaults.
 */
export const ROUTE_SEO_KEYS = {
  Home: 'home',
  Destinations: 'destinations',
  SchengenCountries: 'schengen',
  Apply: 'apply',
  Diagnose: 'diagnose',
  Resources: 'resources',
  ResourcesWiki: 'resources_wiki',
  ResourcesPolicy: 'resources_policy',
  ResourcesTemplates: 'resources_templates',
  ResourcesFaq: 'resources_faq',
  Contact: 'contact',
  Pricing: 'pricing',
  Agreement: 'agreement',
}

export function isRouteIndexable(route) {
  if (!route?.name) return false
  if (route.path?.startsWith('/admin')) return false
  if (route.meta?.seoIndex === false) return false
  if (route.meta?.seoIndex === true) return true
  return INDEXABLE_ROUTE_NAMES.has(route.name)
}

export function seoPageKeyForRoute(route) {
  if (!route?.name) return null
  return ROUTE_SEO_KEYS[route.name] || null
}
