<template>
  <div class="benefits">
    <div class="benefits__head">
      <p class="benefits__title">{{ t('payment.checkout_cmp_title') }}</p>
      <p class="benefits__desc">{{ t('payment.checkout_cmp_desc') }}</p>
      <div class="benefits__legend">
        <span class="benefits__legend-item benefits__legend-item--free">{{ t('payment.checkout_legend_free') }}</span>
        <span class="benefits__legend-item benefits__legend-item--paid">{{ t('payment.checkout_legend_paid') }}</span>
      </div>
    </div>

    <table class="benefits__table" :aria-label="t('payment.checkout_cmp_aria')">
      <thead>
        <tr>
          <th class="benefits__col-feat">{{ t('payment.checkout_col_feat') }}</th>
          <th class="benefits__col-free">{{ t('payment.checkout_col_free') }}</th>
          <th class="benefits__col-paid">
            {{ t('payment.checkout_col_paid') }}
            <span class="benefits__badge">{{ t('payment.checkout_badge_recommended') }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <template v-for="group in groups" :key="group.sectionKey">
          <tr class="benefits__section">
            <td colspan="3">{{ t(group.sectionKey) }}</td>
          </tr>
          <tr
            v-for="row in group.rows"
            :key="row.key"
            :class="{ 'benefits__row--highlight': row.highlight }"
          >
            <td class="benefits__feat">
              {{ t(`payment.checkout_feat_${row.key}`) }}
              <span>{{ t(`payment.checkout_feat_${row.key}_hint`) }}</span>
            </td>
            <td class="benefits__cell" :class="cellClass(row.free)">{{ cellText(row.free) }}</td>
            <td class="benefits__cell benefits__cell--paid" :class="cellClass(row.paid)">{{ cellText(row.paid) }}</td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const groups = [
  {
    sectionKey: 'payment.checkout_section_basic',
    rows: [
      { key: 'checklist', free: 'yes', paid: 'yes' },
      { key: 'ocr', free: 'yes', paid: 'yes' },
      { key: 'assess', free: 'yes', paid: 'yes' },
    ],
  },
  {
    sectionKey: 'payment.checkout_section_paid',
    rows: [
      { key: 'template', free: 'preview', paid: 'download', highlight: true },
      { key: 'report', free: 'summary', paid: 'full', highlight: true },
      { key: 'issues', free: 'no', paid: 'yes', highlight: true },
      { key: 'consistency', free: 'no', paid: 'yes', highlight: true },
      { key: 'rerun', free: 'no', paid: 'yes' },
    ],
  },
  {
    sectionKey: 'payment.checkout_section_browser',
    rows: [
      { key: 'fill', free: 'no', paid: 'yes', highlight: true },
      { key: 'submit', free: 'no', paid: 'yes', highlight: true },
    ],
  },
]

function cellClass(kind) {
  if (kind === 'yes') return 'benefits__cell--yes'
  if (kind === 'no') return 'benefits__cell--no'
  return 'benefits__cell--partial'
}

function cellText(kind) {
  if (kind === 'yes') return '✓'
  if (kind === 'no') return '—'
  return t(`payment.checkout_cell_${kind}`)
}
</script>

<style scoped lang="scss">
.benefits__head {
  margin-bottom: 12px;
  padding: 14px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.benefits__title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.benefits__desc {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}
.benefits__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-top: 10px;
  font-size: 12px;
  color: #475569;
}
.benefits__legend-item::before {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 6px;
  content: '';
  vertical-align: middle;
}
.benefits__legend-item--free::before { background: #94a3b8; }
.benefits__legend-item--paid::before { background: #3b6ef5; }

.benefits__table {
  width: 100%;
  border-collapse: collapse;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 20px;
  background: #fff;
}
.benefits__table th,
.benefits__table td {
  padding: 11px 12px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}
.benefits__table thead th {
  background: #f1f5f9;
  font-size: 13px;
  font-weight: 700;
  color: #475569;
}
.benefits__col-free,
.benefits__col-paid {
  width: 22%;
  text-align: center;
}
.benefits__col-paid {
  background: #3b6ef5;
  color: #fff;
}
.benefits__col-feat { text-align: left; }

.benefits__section td {
  background: #f8fafc;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #64748b;
  padding: 8px 12px;
  border-bottom: 1px solid #e2e8f0;
}
.benefits__feat {
  font-weight: 600;
  color: #0f172a;
}
.benefits__feat span {
  display: block;
  font-weight: 400;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}
.benefits__cell {
  text-align: center;
  font-size: 13px;
  color: #64748b;
}
.benefits__cell--paid { background: #f0f5ff; }
.benefits__row--highlight .benefits__cell--paid {
  background: #eaf0fe;
  font-weight: 700;
  color: #1d4ed8;
}
.benefits__cell--yes { color: #047857; font-weight: 800; font-size: 15px; }
.benefits__cell--no { color: #cbd5e1; font-weight: 700; }
.benefits__cell--partial {
  color: #b45309;
  font-weight: 600;
  font-size: 12px;
  line-height: 1.35;
  white-space: pre-line;
}
.benefits__badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 4px;
  background: rgba(255, 255, 255, 0.25);
}
.benefits__table tbody tr:last-child td { border-bottom: 0; }
</style>
