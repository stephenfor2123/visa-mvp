import { describe, it, expect } from 'vitest'
import { faqItemsFromCurated, buildFaqPageSchema } from '@/seo/geo.js'

describe('geo', () => {
  it('reads FAQ items from curated payload', () => {
    const items = faqItemsFromCurated('en', 3)
    expect(items.length).toBe(3)
    expect(items[0].question).toBeTruthy()
    expect(items[0].answer).toBeTruthy()
  })

  it('builds FAQPage schema', () => {
    const schema = buildFaqPageSchema(
      [{ question: 'Q?', answer: 'A.' }],
      'https://htexvisa.com/resources/faq',
    )
    expect(schema['@type']).toBe('FAQPage')
    expect(schema.mainEntity).toHaveLength(1)
  })
})
