<!--
  PricingSection.vue — 首页定价透明区块 (W54)

  设计:
  - 标题 + 一句话核心承诺
  - 4 国对比表 (国家 / 使馆费 / 平台服务费 / 退款规则)
  - 退款规则说明 block (重点突出: 平台服务费拒签可退 / 使馆费不退)
  - 合规说明 bullet (退费流程 / 工作时间 / 客服)

  i18n: 全文案走 key — 'home.pricing.*'
  数据: 4 国固化在组件, 服务费统一 99 元 (按产品定价), 退款规则文案化由 i18n 控制
-->
<template>
  <section class="pricing" :class="{ 'pricing--standalone': standalone }" data-testid="home-pricing">
    <header class="pricing__head">
      <component :is="standalone ? 'h1' : 'h2'" class="pricing__title">
        {{ t('home.pricing.title') }}
      </component>
      <p class="pricing__sub">{{ t('home.pricing.sub') }}</p>
    </header>

    <!-- 对比表格: 4 国核心收费 -->
    <div class="pricing__table-wrap">
      <table class="pricing__table" role="table" aria-label="签证费用对比">
        <colgroup>
          <col class="pricing__col-country" />
          <col class="pricing__col-consulate" />
          <col class="pricing__col-service" />
          <col class="pricing__col-refund" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">{{ t('home.pricing.col_country') }}</th>
            <th scope="col">{{ t('home.pricing.col_consulate') }}</th>
            <th scope="col">{{ t('home.pricing.col_service') }}</th>
            <th scope="col">{{ t('home.pricing.col_refund') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in ROWS" :key="row.code">
            <th scope="row" class="pricing__country">
              <span class="pricing__flag" aria-hidden="true">{{ row.flag }}</span>
              <span>{{ t(`country.${row.code}`) }}</span>
            </th>
            <td>
              <span class="pricing__amount">{{ row.symbol }} {{ row.amount.toLocaleString() }}</span>
              <span class="pricing__note">{{ t(`home.pricing.consulate_note_${row.currency.toLowerCase()}`) }}</span>
            </td>
            <td>
              <div class="pricing__svc-cell">
                <span v-if="isPromo" class="pricing__amount pricing__amount--list">
                  {{ symbol }} {{ formatUsd(listPrice) }}
                </span>
                <span class="pricing__amount pricing__amount--svc">
                  {{ symbol }} {{ formatUsd(displayPrice) }}
                </span>
                <span v-if="isPromo" class="pricing__promo-tag">{{ t('home.pricing.promo_tag') }}</span>
              </div>
              <span class="pricing__note">{{ t('home.pricing.service_note') }}</span>
            </td>
            <td class="pricing__refund">
              <span class="pricing__pill pricing__pill--no">{{ t('home.pricing.refund_no') }}</span>
              <span class="pricing__note">{{ t('home.pricing.refund_consulate_note') }}</span>
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" class="pricing__total-label">
              {{ t('home.pricing.total_label') }}
            </th>
            <td class="pricing__total-cell" :colspan="3">
              {{ t('home.pricing.total_note') }}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePlatformPricing } from '@/composables/usePlatformPricing'

defineProps({
  standalone: {
    type: Boolean,
    default: false,
  },
})

const { t } = useI18n()
const { isPromo, displayPrice, listPrice, symbol, load, formatUsd } = usePlatformPricing()

onMounted(() => { load() })

  const ROWS = [
    { code: 'us', flag: '🇺🇸', currency: 'USD', symbol: '$',  amount: 185 },
    { code: 'gb', flag: '🇬🇧', currency: 'GBP', symbol: '£', amount: 127 },
    { code: 'fr', flag: '🇫🇷', currency: 'EUR', symbol: '€', amount: 90 },
    { code: 'au', flag: '🇦🇺', currency: 'AUD', symbol: 'A$', amount: 215 },
  ]
</script>

<style scoped>
.pricing {
  margin-top: 64px;
  padding: 56px 24px 64px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-radius: 16px;
  border: 1px solid #e2e8f0;
}

/* W58: 独立页模式 — 去掉外层卡片框 / 渐变 / 圆角 / 顶部间距,
   让定价区块在 /pricing 页面里直接铺到主区背景上 */
.pricing--standalone {
  margin-top: 32px;
  padding: 32px 0 24px;
  background: transparent;
  border-radius: 0;
  border: 0;
}

/* 标题区 */
.pricing__head { text-align: center; margin-bottom: 36px; }
.pricing__title {
  font-size: 28px; font-weight: 700; color: #0f172a;
  margin: 0 0 10px; letter-spacing: -0.5px;
}
.pricing__sub {
  font-size: 15px; color: #64748b; margin: 0; line-height: 1.6;
  max-width: 620px; margin-left: auto; margin-right: auto;
}

/* 表格容器 */
.pricing__table-wrap {
  max-width: 920px; margin: 0 auto 36px;
  overflow-x: auto;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #fff;
}
.pricing__table {
  width: 100%; border-collapse: collapse;
  font-size: 14px;
  table-layout: fixed;
}
.pricing__col-country   { width: 22%; }
.pricing__col-consulate { width: 26%; }
.pricing__col-service   { width: 22%; }
.pricing__col-refund    { width: 30%; }
.pricing__table thead th {
  text-align: left; padding: 14px 18px;
  background: #f1f5f9;
  color: #475569; font-weight: 600; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.5px;
  border-bottom: 1px solid #e2e8f0;
}
.pricing__table tbody td,
.pricing__table tbody th,
.pricing__table tfoot td,
.pricing__table tfoot th {
  padding: 16px 18px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
  color: #1e293b;
}
.pricing__table tbody tr:last-child td,
.pricing__table tbody tr:last-child th {
  border-bottom: 1px solid #f1f5f9;
}
.pricing__country {
  display: flex; align-items: center; gap: 8px;
  font-weight: 600; color: #0f172a;
}
.pricing__flag {
  font-size: 22px; line-height: 1; flex-shrink: 0;
}
.pricing__amount {
  font-size: 17px; font-weight: 700; color: #0f172a;
  font-variant-numeric: tabular-nums;
}
.pricing__amount--svc { color: #2563eb; }
.pricing__amount--list {
  font-size: 14px; font-weight: 600; color: #94a3b8;
  text-decoration: line-through; margin-right: 6px;
}
.pricing__svc-cell { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px; }
.pricing__promo-tag {
  font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 999px;
  background: #fef3c7; color: #b45309; margin-left: 4px;
}
.pricing__note {
  display: block; margin-top: 4px;
  font-size: 11px; color: #94a3b8; line-height: 1.5;
}
.pricing__refund { /* no min-width — let table-layout: fixed govern */ }
.pricing__pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
}
.pricing__pill--ok { background: #dcfce7; color: #15803d; }
.pricing__pill--no { background: #fef3c7; color: #b45309; }

/* tfoot — 总说明 */
.pricing__table tfoot th { font-weight: 600; color: #475569; background: #f8fafc; }
.pricing__table tfoot td { font-size: 12.5px; color: #64748b; }

/* 退款双卡 */
.pricing__rules {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  max-width: 920px; margin: 0 auto 32px;
}
.pricing__rule {
  display: flex; gap: 14px; align-items: flex-start;
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px solid;
}
.pricing__rule--ok {
  background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%);
  border-color: #bbf7d0;
}
.pricing__rule--no {
  background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%);
  border-color: #fde68a;
}
.pricing__rule-icon {
  width: 28px; height: 28px;
  border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700;
  flex-shrink: 0;
}
.pricing__rule--ok .pricing__rule-icon { background: #16a34a; color: #fff; }
.pricing__rule--no .pricing__rule-icon { background: #f59e0b; color: #fff; }
.pricing__rule-title {
  margin: 0 0 6px;
  font-size: 15px; font-weight: 700; color: #0f172a;
}
.pricing__rule-desc {
  margin: 0; font-size: 13px; color: #475569; line-height: 1.6;
}

/* 合规性 bullet */
.pricing__notes {
  list-style: none; padding: 0;
  max-width: 920px; margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}
.pricing__notes li {
  position: relative; padding: 8px 12px 8px 28px;
  font-size: 12.5px; color: #64748b; line-height: 1.6;
}
.pricing__notes li::before {
  content: '·';
  position: absolute; left: 12px; top: 4px;
  font-size: 22px; color: #cbd5e1; line-height: 1;
}

/* 响应式 */
@media (max-width: 768px) {
  .pricing { padding: 40px 16px 48px; }
  .pricing__title { font-size: 24px; }
  .pricing__rules { grid-template-columns: 1fr; }
  .pricing__notes { grid-template-columns: 1fr; }
}
</style>
