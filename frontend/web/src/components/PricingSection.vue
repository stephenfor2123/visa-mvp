<!-- PricingSection — title + comparison table + refund / fee-scope notes -->
<template>
  <section class="pricing" :class="{ 'pricing--standalone': standalone }" data-testid="home-pricing">
    <header class="pricing__head">
      <PageHero
        :heading="standalone ? 'h1' : 'h2'"
        :title="t('home.pricing.title')"
        :subtitle="t('home.pricing.sub')"
      />
    </header>

    <div class="pricing__table-wrap">
      <table class="pricing__table" :aria-label="t('home.pricing.title')">
        <thead>
          <tr>
            <th scope="col">{{ t('home.pricing.col_country') }}</th>
            <th scope="col">{{ t('home.pricing.col_consulate') }}</th>
            <th scope="col">{{ t('home.pricing.col_service') }}</th>
            <th scope="col">{{ t('home.pricing.col_refund') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in ROWS" :key="row.code" :style="{ '--row-delay': `${index * 55}ms` }">
            <th scope="row"><span class="pricing__flag">{{ row.flag }}</span>{{ t(`country.${row.code}`) }}</th>
            <td><strong>{{ row.symbol }} {{ row.amount.toLocaleString() }}</strong></td>
            <td>
              <span v-if="isPromo" class="pricing__list-price">{{ symbol }} {{ formatUsd(listPrice) }}</span>
              <strong class="pricing__service-price">{{ symbol }} {{ formatUsd(displayPrice) }}</strong>
            </td>
            <td><span class="pricing__check">✓</span>{{ t('home.pricing.service_note') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pricing__notes" data-testid="pricing-notes">
      <article class="pricing__note">
        <h3>{{ t('home.pricing.fee_scope_title') }}</h3>
        <p>{{ t('home.pricing.fee_scope_body') }}</p>
      </article>
      <article class="pricing__note">
        <h3>{{ t('home.pricing.refund_flow_title') }}</h3>
        <ol>
          <li>{{ t('home.pricing.refund_flow_1') }}</li>
          <li>{{ t('home.pricing.refund_flow_2') }}</li>
          <li>{{ t('home.pricing.refund_flow_3') }}</li>
        </ol>
      </article>
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePlatformPricing } from '@/composables/usePlatformPricing'
import PageHero from '@/components/PageHero.vue'

defineProps({ standalone: { type: Boolean, default: false } })

const { t } = useI18n()
const { isPromo, displayPrice, listPrice, symbol, load, formatUsd } = usePlatformPricing()

const ROWS = [
  { code: 'us', flag: '🇺🇸', currency: 'USD', symbol: '$', amount: 185 },
  { code: 'gb', flag: '🇬🇧', currency: 'GBP', symbol: '£', amount: 127 },
  { code: 'fr', flag: '🇫🇷', currency: 'EUR', symbol: '€', amount: 90 },
  { code: 'au', flag: '🇦🇺', currency: 'AUD', symbol: 'A$', amount: 215 },
]

onMounted(() => { load() })
</script>

<style scoped>
.pricing {
  margin-top: 64px;
  padding: 40px 0 64px;
  overflow: hidden;
  color: #101828;
  background: #fff;
}
.pricing--standalone { margin-top: 0; }
.pricing__head {
  max-width: 720px;
  margin: 0 0 28px;
  text-align: left;
}
.pricing__table-wrap {
  max-width: 1120px;
  margin: 0 auto;
  overflow-x: auto;
  border: 1px solid #e4e7ec;
  border-radius: 15px;
  background: #fff;
}
.pricing__table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}
.pricing__table th,
.pricing__table td {
  padding: 16px 20px;
  border-bottom: 1px solid #eaecf0;
  text-align: left;
}
.pricing__table thead th {
  color: #667085;
  background: #f9fafb;
  font-size: 11px;
  font-weight: 750;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.pricing__table tbody tr { transition: background .18s; }
.pricing__table tbody tr:last-child th,
.pricing__table tbody tr:last-child td { border-bottom: 0; }
.pricing__table tbody tr:hover { background: #f8fafc; }
.pricing__flag { margin-right: 9px; font-size: 20px; vertical-align: middle; }
.pricing__list-price { margin-right: 7px; color: #98a2b3; text-decoration: line-through; }
.pricing__service-price { color: #2563eb; }
.pricing__check {
  display: inline-grid;
  width: 20px;
  height: 20px;
  margin-right: 8px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: #12b76a;
  font-size: 11px;
  font-weight: 900;
}

.pricing__notes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  max-width: 1120px;
  margin: 22px auto 0;
}
.pricing__note {
  padding: 22px 24px;
  border: 1px solid #e4e7ec;
  border-radius: 15px;
  background: #fff;
}
.pricing__note h3 {
  margin: 0 0 10px;
  color: #101828;
  font-size: 16px;
  font-weight: 750;
  letter-spacing: -.02em;
}
.pricing__note p,
.pricing__note ol {
  margin: 0;
  color: #667085;
  font-size: 14px;
  line-height: 1.65;
}
.pricing__note ol {
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

@media (max-width: 900px) {
  .pricing { padding: 28px 0 48px; }
  .pricing__table { min-width: 640px; }
  .pricing__notes { grid-template-columns: 1fr; }
}
</style>
