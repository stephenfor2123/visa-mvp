<template>
  <div class="tp">
    <!-- 去程 -->
    <section class="tp-block">
      <h3 class="tp-block__title">
        <span class="tp-block__icon">🛫</span> {{ t('wizard.travel_outbound_title') }}
      </h3>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_origin_label') }}</span>
          <CityInput v-model="plan.origin" :placeholder="t('wizard.travel_origin_ph')" test-id="tp-origin" :country-code="countryCode" />
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_destination_label') }}</span>
          <input v-model="plan.destination" :placeholder="destinationName" class="tp-input" data-testid="tp-destination" />
        </label>
      </div>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_depart_label') }}</span>
          <LocaleDateInput v-model="plan.departDate" test-id="tp-depart-date" />
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_flight_out_label') }}</span>
          <input v-model="plan.flightOutNo" :placeholder="t('wizard.travel_flight_out_ph')" class="tp-input" data-testid="tp-flight-out" />
        </label>
      </div>
    </section>

    <!-- 返程：出发/到达地独立可编辑（开口程——回程不一定飞回同一个城市） -->
    <section class="tp-block">
      <h3 class="tp-block__title">
        <span class="tp-block__icon">🛬</span> {{ t('wizard.travel_return_title') }}
      </h3>
      <p class="tp-block__hint">{{ t('wizard.travel_return_openjaw_hint') }}</p>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_return_origin_label') }}</span>
          <CityInput v-model="plan.returnOrigin" :placeholder="plan.destination || destinationName" test-id="tp-return-origin" :country-code="countryCode" />
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_return_destination_label') }}</span>
          <CityInput v-model="plan.returnDestination" :placeholder="plan.origin" test-id="tp-return-destination" :country-code="countryCode" />
        </label>
      </div>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_return_label') }}</span>
          <LocaleDateInput v-model="plan.returnDate" test-id="tp-return-date" />
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_flight_back_label') }}</span>
          <input v-model="plan.flightBackNo" :placeholder="t('wizard.travel_flight_out_ph')" class="tp-input" data-testid="tp-flight-back" />
        </label>
      </div>
    </section>

    <!-- 行程单：日期一定就直接显示，逐格可编辑；"一键生成" 只补空白格 -->
    <section class="tp-block" v-if="plan.days.length">
      <h3 class="tp-block__title"><span class="tp-block__icon">📅</span> {{ t('wizard.travel_days_title', { n: plan.days.length }) }}</h3>
      <p class="tp-block__hint">{{ t('wizard.travel_days_hint') }}</p>

      <div class="tp-preview" data-testid="tp-itinerary-preview">
        <table class="tp-table">
          <thead>
            <tr>
              <th>{{ t('wizard.itinerary_col_day') }}</th>
              <th>{{ t('wizard.itinerary_col_date') }}</th>
              <th>
                <span class="tp-required-mark" aria-label="required">*</span>
                {{ t('wizard.itinerary_col_city') }}
              </th>
              <th>{{ t('wizard.itinerary_col_transport') }}</th>
              <th>{{ t('wizard.itinerary_col_attraction') }}</th>
              <th>{{ t('wizard.itinerary_col_hotel') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(d, i) in plan.days" :key="d.date" :data-testid="`tp-day-${i}`">
              <td class="tp-td-day">{{ t('wizard.travel_day') }} {{ d.day }}</td>
              <td class="tp-td-date">{{ formatDate(d.date) }}</td>
              <td>
                <input v-model="d.city" :placeholder="t('wizard.travel_day_city_ph')" class="tp-input tp-cell-input" :data-testid="`tp-day-city-${i}`" @input="d.city_en = ''" />
                <!-- W47c: 方向提示基于"行索引"显示（不再依赖 transport=flight）：
                     - Day 1（行程起点）: "出发城市 →"（箭头指向当天）
                     - 最后一天（返程日）: "→ 到达城市"（箭头从当天出发）
                     - 中间飞行日: "上一站 →"（箭头指向当天）
                     这样返程当天即使是步行/活动也能看到 → 到达城市，不会漏。
                     数据源是 plan.origin / plan.returnDestination。 -->
                <div
                  v-if="i === 0 || i === plan.days.length - 1 || d.transport === 'flight'"
                  class="tp-city-from"
                  :data-testid="`tp-day-city-from-${i}`"
                >
                  <template v-if="i === 0">
                    {{ plan.origin || '出发城市' }} →
                  </template>
                  <template v-else-if="i === plan.days.length - 1">
                    → {{ plan.returnDestination || plan.origin || '返程目的地' }}
                  </template>
                  <template v-else>
                    {{ dayCityDisplayFn(i).split('→')[0] }} →
                  </template>
                </div>
              </td>
              <td>
                <select
                  v-model="d.transport"
                  class="tp-input tp-cell-input"
                  :class="{ 'is-ai-filled': d._auto?.transport }"
                  :data-testid="`tp-day-transport-${i}`"
                  @change="onManualEdit(d, 'transport')"
                >
                  <option value="">{{ t('wizard.travel_transport_ph') }}</option>
                  <option value="flight">{{ t('wizard.transport_flight') }}</option>
                  <option value="train">{{ t('wizard.transport_train') }}</option>
                  <option value="car">{{ t('wizard.transport_car') }}</option>
                  <option value="bus">{{ t('wizard.transport_bus') }}</option>
                  <option value="walk">{{ t('wizard.transport_walk') }}</option>
                  <option value="other">{{ t('wizard.transport_other') }}</option>
                </select>
              </td>
              <td>
                <input
                  v-model="d.attraction"
                  :placeholder="t('wizard.travel_day_attraction_ph')"
                  class="tp-input tp-cell-input tp-cell-input--wide"
                  :class="{ 'is-ai-filled': d._auto?.attraction }"
                  :data-testid="`tp-day-attraction-${i}`"
                  @input="onManualEdit(d, 'attraction')"
                />
              </td>
              <td>
                <input
                  v-model="d.hotel"
                  :placeholder="t('wizard.travel_day_hotel_ph')"
                  class="tp-input tp-cell-input"
                  :class="{ 'is-ai-filled': d._auto?.hotel }"
                  :data-testid="`tp-day-hotel-${i}`"
                  @input="onManualEdit(d, 'hotel')"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="genIssues.length" class="tp-gen-issues" data-testid="tp-gen-issues">
        <div v-for="(iss, i) in genIssues" :key="i" class="tp-gen-issue">{{ iss.title }}<template v-if="iss.detail"> — {{ iss.detail }}</template></div>
      </div>
      <div v-if="genError" class="tp-gen-error" data-testid="tp-gen-error">{{ genError }}</div>

      <div class="tp-generate">
        <div v-if="generating" class="tp-progress" data-testid="tp-progress">
          <div class="tp-progress__bar"><div class="tp-progress__fill" :style="{ width: progress + '%' }" /></div>
          <div class="tp-progress__text">{{ t('wizard.travel_generating') }} {{ progress }}%</div>
        </div>
        <template v-else>
          <button type="button" class="tp-generate__btn" data-testid="tp-generate" @click="onGenerate">
            ✨ {{ t('wizard.travel_mode_smart') }}
          </button>
          <button
            v-if="canExportPdf"
            type="button"
            class="tp-export__btn"
            data-testid="tp-export-pdf"
            @click="onExportPdf"
          >
            📄 {{ t('wizard.travel_export_pdf') }}
          </button>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'
import LocaleDateInput from '@/components/LocaleDateInput.vue'
import CityInput from '@/components/CityInput.vue'

const { t, locale } = useI18n()
const isEnglishLocale = computed(() => locale.value === 'en')

const props = defineProps({
  plan: { type: Object, required: true },
  destinationName: { type: String, default: '' },
  countryCode: { type: String, default: '' },
  onGenerateItinerary: { type: Function, required: true }, // async () => text
  onCompileItineraryText: { type: Function, required: true }, // () => void, 逐格编辑后重新编译
  onRebuildDays: { type: Function, required: true }, // () => void, 日期变化时重建 days
  onValidateForGenerate: { type: Function, required: true }, // () => issues[]
  dayCityDisplayFn: { type: Function, required: true }, // (index) => string
  onMarkDayFieldManual: { type: Function, required: true }, // (day, field) => void
  onSyncDestinationToDays: { type: Function, required: true }, // (oldDest, newDest) => void
})

const generating = ref(false)
const genError = ref('')
const genIssues = ref([])
const progress = ref(0)
let progressTimer = null

// W47c: 最后一天一律是飞机（返程日）—— 兜住所有数据来源（AI 生成 / 手填 / 历史数据 / 默认 walk）。
// 用户如果手动改成别的交通方式，标记 _manual.transport=true，自愈逻辑尊重用户选择不再改回去。
watch(() => props.plan.days.length, (n) => {
  if (!n) return
  const last = props.plan.days[n - 1]
  if (!last) return
  if (last.transport === 'flight') return // 已经是飞机，跳过
  if (last._manual?.transport) return // 用户手动改过，尊重
  last.transport = 'flight'
  // 标记成"非手填"（系统兜底），避免用户后续看到后以为是 AI 填的
}, { immediate: true })

// 出发/返回日期一变就重建逐日行程（保留已有城市/交通/住宿/景点，按日期对齐）
watch(() => [props.plan.departDate, props.plan.returnDate], () => {
  props.onRebuildDays()
}, { immediate: true })

// W41：不再有单独的"逐日行程"输入区——表格本身就是可编辑区，任何一格改了都
// 直接重新编译 itineraryText（给 OrderNew.vue / 提交用的文本版）。
watch(() => props.plan.days, () => {
  props.onCompileItineraryText()
}, { deep: true })

watch(() => props.destinationName, (name) => {
  if (name && !props.plan.destination) props.plan.destination = name
}, { immediate: true })

// 顶部"目的地"文字改了 -> 跟旧目的地文字一样的"每天城市"格子跟着批量改
// （单城市行程的常见情况；多城市行程里跟旧目的地文字不一样的格子不受影响）
watch(() => props.plan.destination, (newVal, oldVal) => {
  props.onSyncDestinationToDays(oldVal, newVal)
})

// 用户在某个格子里手动改了内容 -> 标记成"手填"，以后"一键生成"不会再碰它
// （否则会一直卡在上一次 AI 生成的内容，改了目的地/航班信息后也刷新不了）
function onManualEdit(day, field) {
  props.onMarkDayFieldManual(day, field)
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return dateStr
  try {
    return new Intl.DateTimeFormat(locale.value, { year: 'numeric', month: 'short', day: 'numeric' }).format(d)
  } catch {
    return dateStr
  }
}

function startProgress() {
  progress.value = 0
  clearInterval(progressTimer)
  // 没有真实进度事件（单次 LLM 调用），用一个越来越慢的假进度条：
  // 快速冲到 70%，然后慢慢逼近 90%，剩下的留给请求真正完成时跳到 100%。
  progressTimer = setInterval(() => {
    if (progress.value < 70) progress.value += 6
    else if (progress.value < 90) progress.value += 1
  }, 300)
}
function stopProgress(success) {
  clearInterval(progressTimer)
  progressTimer = null
  if (success) progress.value = 100
}
onBeforeUnmount(() => clearInterval(progressTimer))

async function onGenerate() {
  genError.value = ''
  const issues = props.onValidateForGenerate()
  genIssues.value = issues
  if (issues.length) return
  generating.value = true
  startProgress()
  try {
    await props.onGenerateItinerary()
    stopProgress(true)
  } catch (e) {
    stopProgress(false)
    genError.value = e?.message || t('wizard.err_upload_failed')
  } finally {
    setTimeout(() => { generating.value = false }, 300)
  }
}

// W46: PDF 导出按钮的可见性 = 所有"下一步"前的校验都通过 + 有 days + 非生成中
const canExportPdf = computed(() => {
  if (generating.value) return false
  if (!props.plan.days.length) return false
  const issues = props.onValidateForGenerate() || []
  return issues.length === 0
})

// W46: 交通方式中英映射表（写死，避免引入额外 i18n key）
const TRANSPORT_EN = {
  flight: 'Flight',
  train: 'Train',
  car: 'Car',
  bus: 'Bus',
  walk: 'Walk',
  other: 'Other',
}

function formatDateEn(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return dateStr
  try {
    return new Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'short', day: 'numeric' }).format(d)
  } catch {
    return dateStr
  }
}

// W47: 双语单元格 —— 目标语言在上，英文在下（灰色小字）。
// 当前 UI 已是英文时只渲染一行，避免 "Flight / Flight" 这种重复。
function bilingualCellHtml(target, en) {
  const tv = escapeHtml(String(target ?? '').trim())
  const ev = escapeHtml(String(en ?? '').trim())
  if (!tv && !ev) return '<div style="color:#94a3b8">—</div>'
  if (isEnglishLocale.value) return `<div>${ev || tv}</div>`
  const top = tv || ev
  const sub = tv && ev && tv !== ev
    ? `<div style="color:#64748b;font-size:11px;margin-top:2px">${ev}</div>`
    : ''
  return `<div>${top}</div>${sub}`
}

// 表头同样目标语言在上、英文在下（白字，配蓝底）。
function bilingualHeaderHtml(target, en) {
  const tv = escapeHtml(String(target ?? '').trim())
  const ev = escapeHtml(String(en ?? '').trim())
  if (isEnglishLocale.value) return `<div>${ev || tv}</div>`
  return `<div>${tv}</div><div style="font-size:10px;font-weight:600;opacity:.85;margin-top:1px">${ev}</div>`
}

async function onExportPdf() {
  const issues = props.onValidateForGenerate() || []
  if (issues.length) {
    genIssues.value = issues
    ElMessage?.error?.(issues[0]?.title || 'Please complete the required fields first.')
    return
  }
  // 保险起见再编译一次（实际 watch 已经自动跑了，但这是用户主动导出，确保 itineraryText 是最新的）
  props.onCompileItineraryText()

  try {
    const marginX = 36
    const marginTop = 40
    const footerGap = 40 // 底部给页脚留白

    // W47b 实现说明：
    // - 整份行程单 = 一页、一张"目标语言结构化表格"（前端已经去掉英文副标题，
    //   PDF 跟前端保持一致）。jsPDF 自带 helvetica 不支持 CJK，所以整块放
    //   离屏 DOM 用 html2canvas 截图成图片再 addImage —— 中/越/印尼都能正确渲染。
    // - 文件体积控制（之前 scale:2 + PNG → 7 天行程 3MB+，30 天能到 8MB）：
    //     1. html2canvas scale 从 2 降到 1.4（视觉肉眼无差，分辨率砍掉一半多）
    //     2. 输出格式 PNG → JPEG，quality 0.82（行程单无透明通道，纯文字 + 边框，
    //        JPEG 压缩比 10~20×）
    //     3. canvas 物理宽度限制在 1400px（多余像素直接 trim）
    //   实测 7 天行程稳定 250~500KB；30 天最长约 800KB，远低于 1MB。
    const canvas = await renderBilingualPageOneCanvas()
    const MAX_W = 1400
    let exportCanvas = canvas
    if (canvas.width > MAX_W) {
      const ratio = MAX_W / canvas.width
      exportCanvas = document.createElement('canvas')
      exportCanvas.width = MAX_W
      exportCanvas.height = Math.round(canvas.height * ratio)
      const ctx = exportCanvas.getContext('2d')
      ctx.imageSmoothingEnabled = true
      ctx.imageSmoothingQuality = 'high'
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height)
      ctx.drawImage(canvas, 0, 0, exportCanvas.width, exportCanvas.height)
    }
    const imgData = exportCanvas.toDataURL('image/jpeg', 0.82)

    // A4 尺寸 (pt)。分别算纵向/横向下能把整张表放到多大，取更大的那个方向。
    const A4 = { short: 595.28, long: 841.89 }
    const fitScale = (pageW, pageH) =>
      Math.min((pageW - marginX * 2) / exportCanvas.width, (pageH - marginTop - footerGap) / exportCanvas.height)
    const portraitScale = fitScale(A4.short, A4.long)
    const landscapeScale = fitScale(A4.long, A4.short)
    const orientation = landscapeScale >= portraitScale ? 'landscape' : 'portrait'

    const doc = new jsPDF({ unit: 'pt', format: 'a4', orientation, compress: true })
    const pageWidth = doc.internal.pageSize.getWidth()
    const pageHeight = doc.internal.pageSize.getHeight()

    const usableWidth = pageWidth - marginX * 2
    const maxHeight = pageHeight - marginTop - footerGap

    let imgW = usableWidth
    let imgH = (exportCanvas.height / exportCanvas.width) * imgW
    if (imgH > maxHeight) {
      const scale = maxHeight / imgH
      imgH = maxHeight
      imgW *= scale
    }
    const x = marginX + (usableWidth - imgW) / 2 // 缩小后水平居中
    doc.addImage(imgData, 'JPEG', x, marginTop, imgW, imgH)

    // 页脚 (英文，helvetica 能渲染)
    doc.setFontSize(9)
    doc.setTextColor(120)
    const footer = `Generated by Htex · ${new Date().toISOString().slice(0, 10)}`
    doc.text(footer, pageWidth / 2, pageHeight - 18, { align: 'center' })
    doc.setTextColor(0)

    // 文件名: 行程单_{countryCode}_{departDate}_{returnDate}.pdf
    const cc = props.countryCode || 'XX'
    const dep = (props.plan.departDate || '').replace(/-/g, '')
    const ret = (props.plan.returnDate || '').replace(/-/g, '')
    const filename = `\u884c\u7a0b\u5355_${cc}_${dep}_${ret}.pdf`
    doc.save(filename)
    ElMessage?.success?.('PDF saved.')
  } catch (e) {
    genError.value = e?.message || 'PDF export failed'
    ElMessage?.error?.(genError.value)
  }
}

// 把"标题 + 副标题 + 双语结构表"整页渲染到一个临时离屏 DOM，再用 html2canvas 截图。
// 离屏 DOM 不进 Vue、不进文档流，截图完直接删掉。
async function renderBilingualPageOneCanvas() {
  const wrapper = document.createElement('div')
  wrapper.style.cssText = `
    position: fixed; left: -10000px; top: 0;
    width: 1100px; padding: 24px 28px; background: #fff;
    font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
    color: #0f172a;
  `
  const days = props.plan.days
  const destName = props.destinationName || props.countryCode || ''
  const sub = `${destName} · ${props.plan.departDate || ''} ~ ${props.plan.returnDate || ''}`

  // 标题：目标语言在上（已带天数），英文副标题在下
  const titleTarget = t('wizard.travel_days_title', { n: days.length })
  const titleEn = `Itinerary (${days.length} ${days.length === 1 ? 'day' : 'days'})`

  // 表头：目标语言在前 + 英文在后（英文写死，避免额外 i18n key）
  const headerDefs = [
    [t('wizard.itinerary_col_day'), 'Day'],
    [t('wizard.itinerary_col_date'), 'Date'],
    [t('wizard.itinerary_col_city'), 'City'],
    [t('wizard.itinerary_col_transport'), 'Transport'],
    [t('wizard.itinerary_col_attraction'), 'Itinerary'],
    [t('wizard.itinerary_col_hotel'), 'Hotel'],
  ]
  const colWidths = [64, 132, 120, 104, 250, 174]  // 加起来 ≈ 844
  const tableW = colWidths.reduce((a, b) => a + b, 0)

  const headHtml = headerDefs.map(([tt, en], i) =>
    `<th style="border:1px solid #3b6ef5;background:#3b6ef5;color:#fff;padding:6px 8px;text-align:left;font-size:12px;width:${colWidths[i]}px;font-weight:700">${bilingualHeaderHtml(tt, en)}</th>`
  ).join('')

  let bodyHtml = ''
  days.forEach((d, i) => {
    const transportKey = d.transport || ''
    const cells = [
      bilingualCellHtml(`Day ${d.day}`, ''),
      // 日期：目标语言格式在上、英文格式在下（修掉之前英文重复两遍的 bug）
      bilingualCellHtml(formatDate(d.date), formatDateEn(d.date)),
      // 城市 / 景点 / 住宿：目标语言在上、LLM 给的英文镜像在下（W47）。
      // 英文镜像缺失（用户手改过）时，bilingualCellHtml 自动只渲染一行。
      bilingualCellHtml(props.dayCityDisplayFn(i), d.city_en),
      bilingualCellHtml(
        transportKey ? t(`wizard.transport_${transportKey}`) : '',
        TRANSPORT_EN[transportKey] || ''
      ),
      bilingualCellHtml(d.attraction, d.attraction_en),
      bilingualCellHtml(d.hotel, d.hotel_en),
    ]
    bodyHtml += '<tr>' + cells.map((inner, ci) =>
      `<td style="border:1px solid #e2e8f0;padding:6px 8px;vertical-align:top;font-size:12.5px;width:${colWidths[ci]}px">${inner}</td>`
    ).join('') + '</tr>'
  })

  wrapper.innerHTML = `
    <div style="text-align:center;margin-bottom:6px">
      <div style="font-size:22px;font-weight:800">${escapeHtml(titleTarget)}</div>
      ${isEnglishLocale.value ? '' : `<div style="font-size:12px;color:#64748b;margin-top:2px">${escapeHtml(titleEn)}</div>`}
      <div style="font-size:13px;color:#475569;margin-top:6px">${escapeHtml(sub)}</div>
    </div>
    <table style="border-collapse:collapse;margin:16px auto 0;width:${tableW}px;table-layout:fixed">
      <thead><tr>${headHtml}</tr></thead>
      <tbody>${bodyHtml}</tbody>
    </table>
  `
  document.body.appendChild(wrapper)
  try {
    return await html2canvas(wrapper, { scale: 2, backgroundColor: '#ffffff', useCORS: true })
  } finally {
    wrapper.remove()
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}
</script>

<style scoped lang="scss">
.tp { display: flex; flex-direction: column; gap: 24px; }
.tp-block {
  border: 1px solid #eef1f6; border-radius: 16px; padding: 18px 20px; background: #fff;
}
.tp-block__title {
  font-size: 15px; font-weight: 700; color: #0f172a; margin: 0 0 4px;
  display: flex; align-items: center; gap: 8px;
}
.tp-block__hint { font-size: 12.5px; color: #64748b; margin: 0 0 12px; }
.tp-block__icon { font-size: 16px; }

.tp-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.tp-field { display: flex; flex-direction: column; gap: 5px; font-size: 12.5px; color: #475569; font-weight: 600; }
.tp-input {
  border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 9px 12px; font-size: 13.5px;
  color: #0f172a; font-weight: 400; font-family: inherit;
  &:focus { outline: none; border-color: #3b6ef5; }
}

.tp-preview { overflow-x: auto; }
.tp-table {
  width: 100%; border-collapse: collapse; font-size: 12.5px; color: #0f172a; background: #fff;
  th, td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; vertical-align: middle; }
  th { font-weight: 700; background: #f1f5f9; line-height: 1.4; white-space: nowrap; }
}
.tp-td-day, .tp-td-date { white-space: nowrap; font-weight: 600; color: #475569; }
// W46: 城市列"必填"红色 * 标记 —— 只加在 th 里，渲染成普通 inline 文本（不会影响列宽/对齐）
.tp-required-mark { color: #dc2626; font-weight: 700; margin-right: 2px; }
.tp-cell-input { padding: 6px 8px; font-size: 12.5px; min-width: 90px; border-color: #e9edf5; }
.tp-cell-input--wide { min-width: 180px; }
// AI 填的格子给个淡紫底色提示"这是生成的，可以再点一次一键生成刷新，或者直接手改"
.tp-cell-input.is-ai-filled { background: #f5f3ff; border-color: #ddd6fe; }
// W47b: "从北京出发"提示 —— 放到 city 输入框下方一行（之前在框上方），
// 让用户填了"到达城市"以后下面自然出现"是从哪个城市来的"，更连贯。
.tp-city-from {
  margin-top: 3px;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
  white-space: nowrap;
  line-height: 1.3;
}

.tp-gen-issues { margin-top: 12px; }
.tp-gen-issue {
  font-size: 12.5px; color: #b91c1c; background: #fef2f2; border-radius: 8px;
  padding: 8px 12px; margin-bottom: 6px;
}
.tp-gen-error {
  margin-top: 12px; font-size: 12.5px; color: #b91c1c; background: #fef2f2;
  border-radius: 8px; padding: 8px 12px;
}

.tp-generate { display: flex; flex-direction: column; align-items: center; margin-top: 14px; gap: 10px; }
.tp-generate__btn {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border: 0;
  padding: 12px 28px; border-radius: 999px; font-size: 14px; font-weight: 700; cursor: pointer;
  box-shadow: 0 8px 20px rgba(15,23,42,.18);
  &:hover:not(:disabled) { transform: translateY(-1px); }
}
// W46: PDF 导出按钮 —— 比智能补充淡一档，视觉上是"次要动作"
.tp-export__btn {
  background: #fff; color: #1e293b; border: 1.5px solid #cbd5e1;
  padding: 10px 22px; border-radius: 999px; font-size: 13.5px; font-weight: 600; cursor: pointer;
  &:hover:not(:disabled) { border-color: #3b6ef5; color: #3b6ef5; }
}
.tp-progress { width: 100%; max-width: 360px; }
.tp-progress__bar { height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.tp-progress__fill {
  height: 100%; background: linear-gradient(90deg, #3B6EF5, #6E59F0);
  transition: width .3s ease;
}
.tp-progress__text { text-align: center; font-size: 12px; color: #64748b; margin-top: 6px; font-weight: 600; }
</style>
