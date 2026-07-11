<template>
  <div class="ipt" data-testid="itinerary-preview-table">
    <table class="ipt__table">
      <thead>
        <tr>
          <th v-for="(h, i) in headers" :key="i" :class="`ipt-th ipt-th--${h.key}`">
            <div class="ipt-th__zh">{{ h.zh }}</div>
            <div class="ipt-th__en">{{ h.en }}</div>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="i" data-testid="ipt-row">
          <td class="ipt-td ipt-td--day">
            <div class="ipt-cell__zh">Day {{ row.day }}</div>
          </td>
          <td class="ipt-td ipt-td--date">
            <div class="ipt-cell__zh">{{ formatDate(row.date) }}</div>
            <div v-if="formatDateEn(row.date) && formatDateEn(row.date) !== formatDate(row.date)" class="ipt-cell__en">
              {{ formatDateEn(row.date) }}
            </div>
          </td>
          <td class="ipt-td ipt-td--city">
            <div class="ipt-cell__zh">{{ cityDisplay(i) }}</div>
            <div v-if="row.city_en && row.city_en !== cityDisplay(i)" class="ipt-cell__en">
              {{ row.city_en }}
            </div>
          </td>
          <td class="ipt-td ipt-td--transport">
            <div class="ipt-cell__zh">{{ transportLabel(row.transport) }}</div>
            <div v-if="TRANSPORT_EN[row.transport] && TRANSPORT_EN[row.transport] !== transportLabel(row.transport)" class="ipt-cell__en">
              {{ TRANSPORT_EN[row.transport] }}
            </div>
          </td>
          <td class="ipt-td ipt-td--attraction">
            <div class="ipt-cell__zh">{{ row.attraction || '—' }}</div>
            <div v-if="row.attraction_en && row.attraction_en !== row.attraction" class="ipt-cell__en">
              {{ row.attraction_en }}
            </div>
          </td>
          <td class="ipt-td ipt-td--hotel">
            <div class="ipt-cell__zh">{{ row.hotel || '—' }}</div>
            <div v-if="row.hotel_en && row.hotel_en !== row.hotel" class="ipt-cell__en">
              {{ row.hotel_en }}
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
// W47c: 给"材料收集向导提交后"的页面(wizard form 预览 + OrderNew 审核页)
// 渲染一个跟 TravelPlanner 编辑页一致的中英双语结构化表格。
// 之前是 pipe 分隔的 <pre> 文本,既丑又不能用表格样式。
//
// Props.days 是 wizard compileItineraryText 写进 localStorage 的结构化 days
// (不是 in-memory state 的 _auto 字段版本). 字段名跟 TravelPlanner 一致,
// 所以这里可以共享 TRANSPORT_EN / formatDate / dayCityDisplay 逻辑.
import { computed, unref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  days: { type: Array, required: true },
  // 以下三字段是 dayCityDisplay 算返程用的:
  origin: { type: String, default: '' },
  destination: { type: String, default: '' },
  returnOrigin: { type: String, default: '' },
  returnDestination: { type: String, default: '' },
})

const { t, locale } = useI18n()

const TRANSPORT_EN = {
  flight: 'Flight', train: 'Train', car: 'Car', bus: 'Bus', walk: 'Walk', other: 'Other',
}

const headers = computed(() => [
  { key: 'day', zh: t('wizard.itinerary_col_day', '天数'), en: 'Day' },
  { key: 'date', zh: t('wizard.itinerary_col_date', '日期'), en: 'Date' },
  { key: 'city', zh: t('wizard.itinerary_col_city', '城市'), en: 'City' },
  { key: 'transport', zh: t('wizard.itinerary_col_transport', '交通方式'), en: 'Transport' },
  { key: 'attraction', zh: t('wizard.itinerary_col_attraction', '行程/景点'), en: 'Itinerary' },
  { key: 'hotel', zh: t('wizard.itinerary_col_hotel', '住宿'), en: 'Hotel' },
])

const rows = computed(() => (unref(props.days) || []).map((d, i) => ({
  day: d.day,
  date: d.date,
  city: d.city,
  city_en: d.city_en,
  transport: d.transport,
  hotel: d.hotel,
  hotel_en: d.hotel_en,
  attraction: d.attraction,
  attraction_en: d.attraction_en,
  __i: i,
})))

function transportLabel(key) {
  if (!key) return '—'
  return t(`wizard.transport_${key}`, key)
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return dateStr
  try {
    return new Intl.DateTimeFormat(locale.value, { year: 'numeric', month: 'short', day: 'numeric' }).format(d)
  } catch { return dateStr }
}
function formatDateEn(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return dateStr
  try {
    return new Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'short', day: 'numeric' }).format(d)
  } catch { return dateStr }
}

// 跟 useMaterialWizard.js dayCityDisplay 同一逻辑:返程日显示
// "当前城市 → 返回城市",中间日显示 "上一日城市 → 当前城市",首日
// 显示 "origin → 当前城市".
function cityDisplay(index) {
  const d = unref(props.days) || []
  const cur = d[index]
  if (!cur) return ''
  if (cur.transport !== 'flight') return cur.city || ''
  const isLast = index === d.length - 1
  if (isLast) {
    const to = props.returnDestination || props.origin || ''
    return to ? `${cur.city || ''} → ${to}` : (cur.city || '')
  }
  const from = index === 0 ? (props.origin || '') : (d[index - 1]?.city || '')
  return from ? `${from} → ${cur.city || ''}` : (cur.city || '')
}
</script>

<style scoped lang="scss">
.ipt {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  overflow-x: auto;
}
.ipt__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  color: #0f172a;
  table-layout: fixed;

  th, td {
    border: 1px solid #e2e8f0;
    padding: 8px 10px;
    text-align: left;
    vertical-align: top;
  }
}
.ipt-th {
  background: #f1f5f9;
  font-weight: 700;
  white-space: nowrap;
  &__zh { font-size: 12.5px; color: #0f172a; }
  &__en { font-size: 11px; color: #64748b; font-weight: 600; margin-top: 1px; }
  &--day { width: 64px; }
  &--date { width: 110px; }
  &--city { width: 150px; }
  &--transport { width: 100px; }
  &--attraction { width: 30%; }
  &--hotel { width: 24%; }
}
.ipt-td {
  &--day { font-weight: 700; color: #475569; white-space: nowrap; }
  &--date { white-space: nowrap; color: #475569; }
  &--city { color: #0f172a; font-weight: 600; }
}
.ipt-cell__zh { font-size: 12.5px; line-height: 1.45; color: #0f172a; }
.ipt-cell__en { font-size: 11px; line-height: 1.4; color: #94a3b8; margin-top: 2px; }
</style>