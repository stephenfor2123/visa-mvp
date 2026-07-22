<!-- PricingSection — interactive pricing comparison -->
<template>
  <section class="pricing" :class="{ 'pricing--standalone': standalone }" data-testid="home-pricing">
    <header class="pricing__head">
      <span class="pricing__eyebrow">HTEX · TRANSPARENT PRICING</span>
      <component :is="standalone ? 'h1' : 'h2'" class="pricing__title">
        {{ t('home.pricing.title') }}
      </component>
      <p class="pricing__sub">{{ t('home.pricing.sub') }}</p>
    </header>

    <div class="pricing__country-picker" role="group" :aria-label="t('home.pricing.col_country')">
      <button
        v-for="row in ROWS"
        :key="row.code"
        type="button"
        class="pricing__country-button"
        :class="{ 'is-active': selectedCode === row.code }"
        :aria-pressed="selectedCode === row.code"
        @click="selectedCode = row.code"
      >
        <span aria-hidden="true">{{ row.flag }}</span>
        <span>{{ t(`country.${row.code}`) }}</span>
      </button>
    </div>

    <!-- Flowbite-inspired decision panel; values remain driven by our own pricing API. -->
    <div class="pricing__decision">
      <article class="pricing__plan pricing__plan--official">
        <div class="pricing__plan-kicker">
          <span class="pricing__plan-icon" aria-hidden="true">{{ selectedRow.flag }}</span>
          {{ t('home.pricing.col_consulate') }}
        </div>
        <div class="pricing__price">
          <span>{{ selectedRow.symbol }}</span>{{ selectedRow.amount.toLocaleString() }}
        </div>
        <p>{{ t(`home.pricing.consulate_note_${selectedRow.currency.toLowerCase()}`) }}</p>
        <div class="pricing__status pricing__status--neutral">
          <span aria-hidden="true">×</span>{{ t('home.pricing.refund_no') }}
        </div>
      </article>

      <article class="pricing__plan pricing__plan--featured">
        <span v-if="isPromo" class="pricing__ribbon">{{ t('home.pricing.promo_tag') }}</span>
        <div class="pricing__plan-kicker">
          <span class="pricing__brand-mark" aria-hidden="true">H</span>
          {{ t('home.pricing.col_service') }}
        </div>
        <div class="pricing__price pricing__price--brand">
          <span>{{ symbol }}</span>{{ formatUsd(displayPrice) }}
        </div>
        <div v-if="isPromo" class="pricing__was">
          {{ symbol }} {{ formatUsd(listPrice) }}
        </div>
        <p>{{ t('home.pricing.service_note') }}</p>
        <div class="pricing__status pricing__status--ok">
          <span aria-hidden="true">✓</span>{{ t('home.pricing.service_refund_title') }}
        </div>
      </article>

      <article class="pricing__plan pricing__plan--promise">
        <div class="pricing__plan-kicker">
          <span class="pricing__shield" aria-hidden="true">✓</span>
          {{ t('home.pricing.col_refund') }}
        </div>
        <div class="pricing__promise-title">{{ t('home.pricing.service_refund_title') }}</div>
        <p>{{ t('home.pricing.service_refund_desc') }}</p>
        <div class="pricing__status pricing__status--link">
          {{ t('home.pricing.total_label') }} <span aria-hidden="true">→</span>
        </div>
      </article>
    </div>

    <div class="pricing__summary">
      <span class="pricing__summary-dot" aria-hidden="true"></span>
      <strong>{{ t('home.pricing.total_label') }}</strong>
      <span>{{ t('home.pricing.total_note') }}</span>
    </div>

    <div class="pricing__table-wrap">
      <table class="pricing__table" aria-label="签证费用对比">
        <thead>
          <tr>
            <th scope="col">{{ t('home.pricing.col_country') }}</th>
            <th scope="col">{{ t('home.pricing.col_consulate') }}</th>
            <th scope="col">{{ t('home.pricing.col_service') }}</th>
            <th scope="col">{{ t('home.pricing.col_refund') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in ROWS"
            :key="row.code"
            :class="{ 'is-selected': selectedCode === row.code }"
            :style="{ '--row-delay': `${index * 55}ms` }"
            @click="selectedCode = row.code"
          >
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
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePlatformPricing } from '@/composables/usePlatformPricing'

defineProps({ standalone: { type: Boolean, default: false } })

const { t } = useI18n()
const { isPromo, displayPrice, listPrice, symbol, load, formatUsd } = usePlatformPricing()
const selectedCode = ref('us')

const ROWS = [
  { code: 'us', flag: '🇺🇸', currency: 'USD', symbol: '$', amount: 185 },
  { code: 'gb', flag: '🇬🇧', currency: 'GBP', symbol: '£', amount: 127 },
  { code: 'fr', flag: '🇫🇷', currency: 'EUR', symbol: '€', amount: 90 },
  { code: 'au', flag: '🇦🇺', currency: 'AUD', symbol: 'A$', amount: 215 },
]

const selectedRow = computed(() => ROWS.find(row => row.code === selectedCode.value) || ROWS[0])

onMounted(() => { load() })
</script>

<style scoped>
.pricing {
  margin-top: 64px;
  padding: 64px 28px 68px;
  overflow: hidden;
  color: #101828;
  background:
    radial-gradient(circle at 50% -20%, rgba(37, 99, 235, .09), transparent 36%),
    linear-gradient(180deg, #fff 0%, #f8fafc 100%);
  border: 1px solid #e4e7ec;
  border-radius: 24px;
}
.pricing--standalone { margin-top: 22px; border: 0; background-color: transparent; }
.pricing__head { max-width: 720px; margin: 0 auto 28px; text-align: center; animation: pricing-rise .55s ease both; }
.pricing__eyebrow { display: inline-block; margin-bottom: 12px; color: #2563eb; font-size: 11px; font-weight: 800; letter-spacing: .13em; }
.pricing__title { margin: 0 0 12px; color: #0f172a; font-size: clamp(30px, 4vw, 44px); line-height: 1.1; letter-spacing: -.045em; }
.pricing__sub { margin: 0; color: #667085; font-size: 15px; line-height: 1.65; }

.pricing__country-picker { display: flex; width: fit-content; max-width: 100%; margin: 0 auto 22px; padding: 5px; gap: 4px; overflow-x: auto; border: 1px solid #e4e7ec; border-radius: 999px; background: rgba(255,255,255,.88); box-shadow: 0 5px 18px rgba(16,24,40,.05); }
.pricing__country-button { display: flex; align-items: center; gap: 7px; min-width: max-content; padding: 8px 14px; border: 0; border-radius: 999px; color: #667085; background: transparent; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; transition: color .2s, background .2s, box-shadow .2s, transform .2s; }
.pricing__country-button:hover { color: #1d4ed8; transform: translateY(-1px); }
.pricing__country-button.is-active { color: #fff; background: #2563eb; box-shadow: 0 5px 12px rgba(37,99,235,.25); }

.pricing__decision { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); max-width: 1120px; margin: 0 auto; overflow: hidden; border: 1px solid #e4e7ec; border-radius: 20px 20px 0 0; background: #f9fafb; box-shadow: 0 24px 55px rgba(16,24,40,.09); animation: pricing-rise .6s .08s ease both; }
.pricing__plan { position: relative; min-height: 310px; padding: 34px 34px 28px; border-right: 1px solid #e4e7ec; transition: background .25s, transform .25s, box-shadow .25s; }
.pricing__plan:last-child { border-right: 0; }
.pricing__plan:hover { z-index: 2; background: #fff; box-shadow: 0 18px 35px rgba(16,24,40,.09); transform: translateY(-4px); }
.pricing__plan--featured { background: #fff; }
.pricing__plan--featured::before { position: absolute; inset: 0 0 auto; height: 4px; content: ''; background: linear-gradient(90deg, #2563eb, #7c3aed); }
.pricing__ribbon { position: absolute; top: 18px; right: 18px; padding: 5px 9px; border-radius: 999px; color: #b45309; background: #fffbeb; font-size: 10px; font-weight: 800; letter-spacing: .04em; }
.pricing__plan-kicker { display: flex; align-items: center; gap: 9px; min-height: 28px; color: #101828; font-size: 17px; font-weight: 750; }
.pricing__plan-icon { font-size: 24px; }
.pricing__brand-mark, .pricing__shield { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 8px; color: #fff; background: linear-gradient(135deg, #2563eb, #7c3aed); font-size: 14px; font-weight: 900; box-shadow: 0 6px 14px rgba(37,99,235,.2); }
.pricing__shield { border-radius: 50%; background: #12b76a; }
.pricing__price { margin: 22px 0 18px; color: #101828; font-size: clamp(38px, 4vw, 52px); font-weight: 800; line-height: 1; letter-spacing: -.045em; font-variant-numeric: tabular-nums; }
.pricing__price span { margin-right: 4px; font-size: .55em; vertical-align: 8px; }
.pricing__price--brand { color: #1d4ed8; }
.pricing__was { margin: -12px 0 10px; color: #98a2b3; font-size: 14px; font-weight: 650; text-decoration: line-through; }
.pricing__plan p { min-height: 52px; margin: 0; color: #667085; font-size: 14px; line-height: 1.55; }
.pricing__promise-title { margin: 24px 0 14px; color: #101828; font-size: 26px; font-weight: 780; line-height: 1.14; letter-spacing: -.035em; }
.pricing__status { display: flex; align-items: center; width: 100%; min-height: 46px; margin-top: 22px; padding: 0 15px; gap: 9px; border: 1px solid #d0d5dd; border-radius: 9px; color: #344054; background: #fff; font-size: 13px; font-weight: 700; transition: transform .2s, box-shadow .2s; }
.pricing__status span { font-size: 18px; }
.pricing__status--ok { border: 0; color: #fff; background: linear-gradient(90deg, #2563eb, #4f46e5); box-shadow: 0 8px 20px rgba(37,99,235,.2); }
.pricing__status--ok:hover { transform: translateY(-2px); box-shadow: 0 12px 25px rgba(37,99,235,.3); }
.pricing__status--neutral span { color: #f04438; }
.pricing__status--link { padding: 0; border: 0; color: #7c3aed; background: transparent; }
.pricing__status--link span { transition: transform .2s; }
.pricing__plan:hover .pricing__status--link span { transform: translateX(5px); }

.pricing__summary { display: flex; align-items: center; max-width: 1120px; min-height: 64px; margin: 0 auto; padding: 14px 22px; gap: 10px; border: 1px solid #e4e7ec; border-top: 0; border-radius: 0 0 20px 20px; color: #667085; background: #f2f4f7; font-size: 12.5px; line-height: 1.5; }
.pricing__summary strong { flex: 0 0 auto; color: #344054; }
.pricing__summary-dot { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; background: #12b76a; box-shadow: 0 0 0 5px rgba(18,183,106,.12); animation: pricing-pulse 2s infinite; }

.pricing__table-wrap { max-width: 1120px; margin: 34px auto 0; overflow-x: auto; border: 1px solid #e4e7ec; border-radius: 15px; background: #fff; }
.pricing__table { width: 100%; min-width: 720px; border-collapse: collapse; table-layout: fixed; font-size: 13px; }
.pricing__table th, .pricing__table td { padding: 16px 20px; border-bottom: 1px solid #eaecf0; text-align: left; }
.pricing__table thead th { color: #667085; background: #f9fafb; font-size: 11px; font-weight: 750; letter-spacing: .06em; text-transform: uppercase; }
.pricing__table tbody tr { cursor: pointer; animation: pricing-rise .45s var(--row-delay) ease both; transition: background .18s, box-shadow .18s; }
.pricing__table tbody tr:last-child th, .pricing__table tbody tr:last-child td { border-bottom: 0; }
.pricing__table tbody tr:hover, .pricing__table tbody tr.is-selected { background: #f5f8ff; box-shadow: inset 3px 0 #2563eb; }
.pricing__flag { margin-right: 9px; font-size: 20px; vertical-align: middle; }
.pricing__list-price { margin-right: 7px; color: #98a2b3; text-decoration: line-through; }
.pricing__service-price { color: #2563eb; }
.pricing__check { display: inline-grid; width: 20px; height: 20px; margin-right: 8px; place-items: center; border-radius: 50%; color: #fff; background: #12b76a; font-size: 11px; font-weight: 900; }

@keyframes pricing-rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
@keyframes pricing-pulse { 50% { box-shadow: 0 0 0 9px rgba(18,183,106,0); } }
@media (prefers-reduced-motion: reduce) { .pricing *, .pricing *::before, .pricing *::after { animation: none !important; transition: none !important; } }
@media (max-width: 840px) {
  .pricing { padding: 46px 16px 52px; border-radius: 18px; }
  .pricing__decision { grid-template-columns: 1fr; }
  .pricing__plan { min-height: auto; border-right: 0; border-bottom: 1px solid #e4e7ec; }
  .pricing__plan:last-child { border-bottom: 0; }
  .pricing__plan p { min-height: 0; }
  .pricing__summary { align-items: flex-start; flex-wrap: wrap; }
}
@media (max-width: 520px) {
  .pricing__country-picker { width: 100%; justify-content: flex-start; border-radius: 14px; }
  .pricing__plan { padding: 28px 22px 24px; }
  .pricing__title { font-size: 30px; }
}
</style>
