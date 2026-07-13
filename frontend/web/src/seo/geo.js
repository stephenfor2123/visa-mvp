/**
 * GEO helpers — structured data and route-specific schemas for AI/search systems.
 * Complements SEO meta tags; does not replace crawlable public content.
 */
import { siteOrigin, SITE_NAME } from './config.js'
import { seoPageKeyForRoute } from './routeSeo.js'
import curatedZhCN from '@shared/i18n/_curated_payloads/resources_curated.zh-CN.json'
import curatedEn from '@shared/i18n/_curated_payloads/resources_curated.en.json'
import curatedID from '@shared/i18n/_curated_payloads/resources_curated.id.json'
import curatedVi from '@shared/i18n/_curated_payloads/resources_curated.vi.json'

const CURATED_BY_LOCALE = {
  'zh-CN': curatedZhCN,
  en: curatedEn,
  'id-ID': curatedID,
  'vi-VN': curatedVi,
}

function tOr(i18n, key, fallback = '') {
  try {
    const v = i18n.global.t(key)
    if (!v || v === key) return fallback
    return v
  } catch {
    return fallback
  }
}

function curatedForLocale(locale) {
  return CURATED_BY_LOCALE[locale] || curatedEn
}

/** FAQ items from curated FAQ section (US block) for FAQPage schema. */
export function faqItemsFromCurated(locale, limit = 8) {
  const root = curatedForLocale(locale)
  const items = root?.faq?.us?.items
  if (!Array.isArray(items)) return []
  return items.slice(0, limit).map((item) => ({
    question: String(item.title || '').trim(),
    answer: String(item.desc || '').trim(),
  })).filter((x) => x.question && x.answer)
}

export function buildFaqPageSchema(items, pageUrl) {
  if (!items.length) return null
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map(({ question, answer }) => ({
      '@type': 'Question',
      name: question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: answer,
      },
    })),
    url: pageUrl,
  }
}

export function buildGeoOrganizationSchema(origin, i18n) {
  const description = tOr(i18n, 'seo.default_description', '')
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: SITE_NAME,
    url: origin,
    logo: `${origin}/icons/icon-512.png`,
    description: description || undefined,
    knowsAbout: [
      'United States B1/B2 visa',
      'United Kingdom Standard Visitor visa',
      'Australia visitor visa',
      'Schengen visa',
      'DS-160',
      'Visa document preparation',
    ],
    areaServed: {
      '@type': 'Place',
      name: 'Worldwide',
    },
  }
}

export function buildGeoWebSiteSchema(origin, i18n) {
  const description = tOr(i18n, 'seo.default_description', '')
  const locale = i18n.global.locale.value || 'en'
  const inLanguage = locale === 'zh-CN' ? 'zh-CN' : locale
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE_NAME,
    url: origin,
    description: description || undefined,
    inLanguage,
    publisher: {
      '@type': 'Organization',
      name: SITE_NAME,
      url: origin,
    },
  }
}

export function buildSoftwareApplicationSchema(origin, i18n) {
  const description = tOr(i18n, 'seo.default_description', '')
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: SITE_NAME,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    url: origin,
    description: description || undefined,
    offers: {
      '@type': 'Offer',
      price: '19.90',
      priceCurrency: 'USD',
      description: 'Promo USD 19.90 Jul 15–Aug 15, 2026 (regular 99.90). Charged only after visa approval; refunded if denied. Embassy visa fees non-refundable.',
    },
  }
}

export function buildWebPageSchema({ origin, canonical, title, description, i18n }) {
  const locale = i18n.global.locale.value || 'en'
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: title,
    description: description || undefined,
    url: canonical,
    inLanguage: locale === 'zh-CN' ? 'zh-CN' : locale,
    isPartOf: {
      '@type': 'WebSite',
      name: SITE_NAME,
      url: origin,
    },
  }
}

/**
 * Extra JSON-LD blocks for indexable routes (GEO).
 * Returns array of schema objects.
 */
export function buildGeoSchemas(route, i18n, { canonical, title, pageDesc }) {
  const origin = siteOrigin()
  const locale = i18n.global.locale.value || 'en'
  const schemas = [
    buildGeoOrganizationSchema(origin, i18n),
    buildGeoWebSiteSchema(origin, i18n),
    buildSoftwareApplicationSchema(origin, i18n),
    buildWebPageSchema({
      origin,
      canonical,
      title,
      description: pageDesc,
      i18n,
    }),
  ]

  const pageKey = seoPageKeyForRoute(route)
  if (route.name === 'ResourcesFaq' || route.name === 'Resources') {
    const faq = buildFaqPageSchema(faqItemsFromCurated(locale), canonical)
    if (faq) schemas.push(faq)
  }

  if (pageKey === 'resources_wiki') {
    const wikiIntro = curatedForLocale(locale)?.wiki?.intro
    if (wikiIntro) {
      schemas.push({
        '@context': 'https://schema.org',
        '@type': 'Article',
        headline: title,
        description: wikiIntro,
        url: canonical,
        publisher: { '@type': 'Organization', name: SITE_NAME },
      })
    }
  }

  return schemas.filter(Boolean)
}
