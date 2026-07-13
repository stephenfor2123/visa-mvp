import { SITE_NAME, siteOrigin, defaultOgImage } from './config.js'
import { isRouteIndexable, seoPageKeyForRoute } from './routeSeo.js'
import { buildGeoSchemas } from './geo.js'

const MANAGED = 'data-seo-managed'

function tOr(i18n, key, fallback = '') {
  if (!key) return fallback
  try {
    const v = i18n.global.t(key)
    if (!v || v === key || v.startsWith('seo.')) return fallback
    return v
  } catch {
    return fallback
  }
}

function upsertMeta(attr, key, content) {
  if (content == null || content === '') return
  let el = document.head.querySelector(`meta[${attr}="${key}"][${MANAGED}]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    el.setAttribute(MANAGED, '')
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function upsertLink(rel, href, extra = {}) {
  if (!href) return
  let el = document.head.querySelector(`link[rel="${rel}"][${MANAGED}]`)
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    el.setAttribute(MANAGED, '')
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
  for (const [k, v] of Object.entries(extra)) {
    if (v != null) el.setAttribute(k, v)
  }
}

function upsertJsonLd(id, data) {
  let el = document.getElementById(id)
  if (!data) {
    el?.remove()
    return
  }
  if (!el) {
    el = document.createElement('script')
    el.type = 'application/ld+json'
    el.id = id
    el.setAttribute(MANAGED, '')
    document.head.appendChild(el)
  }
  el.textContent = JSON.stringify(data)
}

function canonicalUrl(route) {
  const origin = siteOrigin()
  const path = route.path || '/'
  // Drop query/hash for canonical (locale is client-side, not separate URLs yet).
  return `${origin}${path}`
}

function upsertJsonLdGraph(id, schemas) {
  if (!schemas?.length) {
    document.getElementById(id)?.remove()
    return
  }
  upsertJsonLd(id, {
    '@context': 'https://schema.org',
    '@graph': schemas,
  })
}

/**
 * Apply document title + meta tags for the current route.
 * Called from router.afterEach and on locale change.
 */
export function applyRouteSeo(route, i18n) {
  if (typeof document === 'undefined') return

  const indexable = isRouteIndexable(route)
  const pageKey = seoPageKeyForRoute(route)
  const origin = siteOrigin()
  const canonical = canonicalUrl(route)

  const pageTitle = pageKey
    ? tOr(i18n, `seo.pages.${pageKey}.title`, '')
    : (route.meta?.title ? tOr(i18n, route.meta.title, '') : '')

  const defaultDesc = tOr(i18n, 'seo.default_description', '')
  const pageDesc = pageKey
    ? tOr(i18n, `seo.pages.${pageKey}.description`, defaultDesc)
    : defaultDesc

  const title = pageTitle
    ? `${SITE_NAME} · ${pageTitle}`
    : (() => {
        const slogan = tOr(i18n, 'common.app_slogan', '')
        return slogan ? `${SITE_NAME} · ${slogan}` : SITE_NAME
      })()

  document.title = title

  const locale = i18n.global.locale.value || 'en'
  const htmlLang = locale === 'zh-CN' ? 'zh-CN' : locale
  document.documentElement.lang = htmlLang

  upsertLink('canonical', canonical)

  const robots = indexable ? 'index,follow' : 'noindex,nofollow'
  upsertMeta('name', 'robots', robots)
  upsertMeta('name', 'description', pageDesc)

  upsertMeta('property', 'og:site_name', SITE_NAME)
  upsertMeta('property', 'og:title', title)
  upsertMeta('property', 'og:description', pageDesc)
  upsertMeta('property', 'og:url', canonical)
  upsertMeta('property', 'og:type', 'website')
  upsertMeta('property', 'og:locale', htmlLang.replace('-', '_'))
  upsertMeta('property', 'og:image', defaultOgImage())

  upsertMeta('name', 'twitter:card', 'summary')
  upsertMeta('name', 'twitter:title', title)
  upsertMeta('name', 'twitter:description', pageDesc)
  upsertMeta('name', 'twitter:image', defaultOgImage())

  // GEO: machine-readable site brief for LLM crawlers (also linked from index.html).
  upsertLink('alternate', `${origin}/llms.txt`, { type: 'text/plain', title: 'LLM site summary' })

  if (indexable) {
    const geoSchemas = buildGeoSchemas(route, i18n, { canonical, title, pageDesc })
    upsertJsonLdGraph('seo-geo-jsonld', geoSchemas)
    // Legacy single-schema ids kept empty — graph supersedes.
    upsertJsonLd('seo-org-jsonld', null)
    upsertJsonLd('seo-website-jsonld', null)
  } else {
    upsertJsonLdGraph('seo-geo-jsonld', null)
    upsertJsonLd('seo-org-jsonld', null)
    upsertJsonLd('seo-website-jsonld', null)
  }
}

/** Last applied route — re-run SEO when only locale changes. */
let _lastRoute = null

export function rememberRouteForSeo(route) {
  _lastRoute = route
}

export function reapplySeoForLastRoute(i18n) {
  if (_lastRoute) applyRouteSeo(_lastRoute, i18n)
}
