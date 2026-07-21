// useMaterialWizard — 分大类、强校验的材料收集向导
//
// 5 大类：身份证件 → 在职/工作证明 → 财力证明 → 行程住宿 → 信息表单。
// 大类内的子项可以自由顺序上传；大类内所有必填子项收集完后调用后端
// /materials/diagnose 做跨材料校验（护照有效期、材料完整性等），有 error/critical
// 级别问题时阻断，不允许进入下一大类。
import { computed, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  processMaterial,
  diagnoseMaterials,
  generateItineraryAttractions,
} from '@/api/materials'
import i18n from '@/i18n'
import {
  OCR_CACHE_KEY,
  TRAVEL_PLAN_KEY,
  WIZARD_TTL_MS,
  loadWithExpiry,
  saveWithExpiry,
} from '@/utils/localPrivacyStorage'

const STORAGE_PREFIX = 'visa.wizard.'

// 把后端拼出来的绝对 download URL 砍成同源相对路径。
// 后端在生成 signed URL 时会用 request.base_url 拼出 http://127.0.0.1:8000/...
// 这种绝对地址,在 dev 模式下:
//   - <img> / 普通 fetch 会走 vite proxy(同源) → OK
//   - <iframe src> 不会走 proxy,直接打 127.0.0.1:8000 → 拒连
// 解决:把 absolute URL 砍成 pathname + search,变成 /api/... 的相对地址,
// iframe / img / fetch 都走当前页面的同源(dev 走 proxy,prod 同源部署)就都能访问。
// 输入是 null/相对路径/同源绝对路径时都原样返回。
function toRelativeUrl(url) {
  if (!url) return null
  try {
    // 同源(protocol+host+port 跟当前页面一样)直接砍掉 prefix 也安全,但保持绝对也无害
    const u = new URL(url, window.location.origin)
    if (u.origin === window.location.origin) return u.pathname + u.search + u.hash
    // 跨源:提取 pathname 起头(比如 http://127.0.0.1:8000/api/v2/materials/... → /api/v2/materials/...)
    return u.pathname + u.search + u.hash
  } catch {
    return url
  }
}

// W39: /materials/diagnose 是后端接口，返回的 title/detail 是服务端拼好的 zh-CN
// 字符串（不管前端选了什么语言）。后端在 W39 里给每条 issue 附带了 params
// （拼字符串用到的原始数值），这里按 code 把 title/detail 换成前端 i18n 的翻译，
// 认不出的 code 才回退用后端原文，保证多语言下这块也能跟着切换。
function translateDiagnoseIssue(issue) {
  const t = i18n.global.t
  const p = issue.params || {}
  // W67+: i18n 字符串里要显示国家名(美国 / United States / Hoa Kỳ / Amerika Serikat),
  // 不能裸用 country code ('US')。后端 params 只给 code,前端按当前 locale 补一个
  // country_name — 4 国都已经在 i18n 里有 country_us / country_gb / country_au ...
  // 找不到时退回 code,避免空字符串(后端 diagnose 截图里"目的国 要求"中间的空白就是这个 bug)。
  const cc = (p.country || '').toLowerCase()
  const countryName = cc && t(`country_${cc}`) !== `country_${cc}` ? t(`country_${cc}`) : (cc ? cc.toUpperCase() : '')
  const pRender = { ...p, country_name: countryName }
  let code = issue.code || ''
  if (code.startsWith('ocr.failed.')) code = 'ocr.failed' // 动态后缀 (ocr.failed.<material_type>)
  const table = {
    'passport.expiry_missing': () => ({
      title: t('wizard.diag_expiry_missing_title'),
      detail: t('wizard.diag_expiry_missing_detail'),
    }),
    'passport.not_detected': () => ({
      title: t('wizard.diag_not_detected_title'),
      detail: t('wizard.diag_not_detected_detail'),
    }),
    'passport.expiry_short': () => ({
      title: t('wizard.diag_expiry_short_title', { minMonths: p.min_months }),
      detail: t('wizard.diag_expiry_short_detail', { expiry: p.expiry, monthsLeft: p.months_left, minMonths: p.min_months }),
    }),
    'passport.no_suspicious': () => ({
      title: t('diagnose.passport_no_suspicious_title'),
      detail: t('diagnose.passport_no_suspicious_detail', { passport_no: p.passport_no }),
    }),
    'photo.bg_uncertain': () => ({
      // W67+: 后端 visa_diagnoser 一直把这条 issue 的 code 写成 'photo.bg_uncertain',
      // 但 title_key / detail_key 都用 'photo_bg_country_*', 意思是"按目的国规格确认"。
      // 之前路由表里走的是 'diag_bg_uncertain_*' 泛提示 ("多数国家白底,部分东南亚蓝底"),
      // 用户反馈太泛,改成 country-aware 文案(用 {country_name} 拿到按 locale 翻译的国家名)。
      title: t('diagnose.photo_bg_country_title', pRender),
      detail: t('diagnose.photo_bg_country_detail', pRender),
    }),
    // W62/W63: 后端 visa_diagnoser 在 W62/W63 改后吐这两种 photo 背景色 issue,
    // 之前路由表里没 → 漏翻译,直接透传后端 zh-CN 字符串。
    // key 路径是 diagnose.photo_bg_country_* (W62 当时就加在了 diagnose 命名空间,不是 wizard)。
    'photo.bg_country': () => ({
      title: t('diagnose.photo_bg_country_title', pRender),
      detail: t('diagnose.photo_bg_country_detail', pRender),
    }),
    'photo.bg_mismatch': () => ({
      title: t('diagnose.photo_bg_mismatch_title', pRender),
      detail: t('diagnose.photo_bg_mismatch_detail', pRender),
    }),
    'ocr.failed': () => ({
      title: t('wizard.diag_ocr_failed_title', { materialType: t(`materials.type_${p.material_type}`) }),
      detail: t('wizard.diag_ocr_failed_detail'),
    }),
    // W67+: 银行流水类 issue 后端 code 命名 (visa_diagnoser.py:382-774), 之前路由表没 →
    // 漏翻译,直接透传后端 zh-CN 字符串, 即使 UI 切到 en/vi/id 也显示中文。
    'bank.unparseable': () => ({
      title: t('diagnose.bank_unparseable_title'),
      detail: t('diagnose.bank_unparseable_detail'),
    }),
    'bank.coverage_short': () => ({
      title: t('diagnose.bank_coverage_short_title', { months: p.months }),
      detail: t('diagnose.bank_coverage_short_detail', { months: p.months }),
    }),
    'bank.income_low': () => ({
      title: t('diagnose.bank_income_low_title'),
      detail: t('diagnose.bank_income_low_detail', { monthly_income: p.monthly_income }),
    }),
    'bank.large_inflow': () => ({
      title: t('diagnose.bank_large_inflow_title', { count: p.count }),
      detail: t('diagnose.bank_large_inflow_detail', { count: p.count }),
    }),
    'bank.income_gap': () => ({
      title: t('diagnose.bank_income_gap_title', { gap_months: p.gap_months }),
      detail: t('diagnose.bank_income_gap_detail', {
        gap_months: p.gap_months, start_month: p.start_month, end_month: p.end_month, gap_count: p.gap_count,
      }),
    }),
    'bank.months_missing': () => ({
      title: t('diagnose.bank_months_missing_title', { n: (p.missing_months || []).length }),
      detail: t('diagnose.bank_months_missing_detail', { missing_months: (p.missing_months || []).join(', ') }),
    }),
    'bank.sudden_inflow': () => ({
      title: t('diagnose.bank_sudden_inflow_title', { n: p.count }),
      detail: t('diagnose.bank_sudden_inflow_detail', {
        top_date: p.top_date, top_amount: p.top_amount, top_severity: p.top_severity,
      }),
    }),
    'bank.balance_below_threshold': () => ({
      title: t('diagnose.bank_balance_threshold_title', { country: countryName }),
      detail: t('diagnose.bank_balance_threshold_detail', {
        country: countryName,
        ending_balance_src: p.ending_balance_src,
        ending_balance_dest: p.ending_balance_dest,
        daily_min_dest: p.daily_min_dest,
        min_coverage_months: p.min_coverage_months,
        hard_block: p.hard_block,
      }),
    }),
    'bank.balance_coverage': () => ({
      title: t('diagnose.bank_balance_coverage_title'),
      detail: t('diagnose.bank_balance_coverage_detail', {
        ending_balance: p.ending_balance, budget_total: p.budget_total, stay_days: p.stay_days,
      }),
    }),
    'fields.travel_date_missing': () => ({
      title: t('diagnose.travel_date_missing_title'),
      detail: t('diagnose.travel_date_missing_detail'),
    }),
    'fields.purpose_missing': () => ({
      title: t('diagnose.purpose_missing_title'),
      detail: t('diagnose.purpose_missing_detail'),
    }),
  }
  const translated = table[code]?.()
  if (!translated) return issue // 不认识的 code：原样透传后端文案
  // W58: 用 code 前缀推断 itemKey（passport.* → 'passport' / photo.* → 'photo'），
  // 前端按 itemKey 把 issue 路由到对应 tab，不再把所有提示堆在页面底部。
  const itemKey = code.split('.')[0]
  // W67: i18n 兜底 — 如果 t() 因为 messages 加载未完成 / locale alias 失配 / 任何原因
  // 返回的字符串等于 i18n key 本身(t() 找不到 key 的 fallback 行为),
  // 就降级到后端给的 zh 字面值(issue.title / issue.detail,后端永远有 zh-CN 兜底)。
  // 同时记一行 warn 帮我们 track 哪些 i18n key 在哪些 locale 下失效。
  const rawTitle = translated.title
  const rawDetail = translated.detail
  const titleLooksUnresolved = typeof rawTitle === 'string'
    && /^[a-z_]+\.[a-z_0-9.]+_[a-z]+$/.test(rawTitle)
  const detailLooksUnresolved = typeof rawDetail === 'string'
    && /^[a-z_]+\.[a-z_0-9.]+_[a-z]+$/.test(rawDetail)
  const finalTitle = titleLooksUnresolved && issue.title ? issue.title : rawTitle
  const finalDetail = detailLooksUnresolved && issue.detail ? issue.detail : rawDetail
  if (titleLooksUnresolved || detailLooksUnresolved) {
    try {
      // eslint-disable-next-line no-console
      console.warn(`[w67-i18n-missing] code=${code} locale=${i18n.global.locale.value}`,
        { titleRaw: rawTitle, detailRaw: rawDetail, fallbackUsed: { title: !!issue.title, detail: !!issue.detail } })
    } catch {}
  }
  return { ...issue, title: finalTitle, detail: finalDetail, itemKey }
}

// W63-f: 纯重译函数 — 给一个已存的 issue,按当前 locale 重新生成 title/detail。
// 不修改 code/severity/itemKey/related_material_id/params,只覆盖可翻译字段。
function retranslateIssue(issue) {
  const t = i18n.global.t
  const p = issue.params || {}
  // 同 translateDiagnoseIssue — 补 country_name(按当前 locale 翻译)
  const cc = (p.country || '').toLowerCase()
  const countryName = cc && t(`country_${cc}`) !== `country_${cc}` ? t(`country_${cc}`) : (cc ? cc.toUpperCase() : '')
  const pRender = { ...p, country_name: countryName }
  let code = issue.code || ''
  if (code.startsWith('ocr.failed.')) code = 'ocr.failed'
  const table = {
    'passport.expiry_missing': () => ({ title: t('wizard.diag_expiry_missing_title'), detail: t('wizard.diag_expiry_missing_detail') }),
    'passport.not_detected':  () => ({ title: t('wizard.diag_not_detected_title'),  detail: t('wizard.diag_not_detected_detail') }),
    'passport.expiry_short':   () => ({ title: t('wizard.diag_expiry_short_title', { minMonths: p.min_months }), detail: t('wizard.diag_expiry_short_detail', { expiry: p.expiry, monthsLeft: p.months_left, minMonths: p.min_months }) }),
    'passport.no_suspicious':  () => ({ title: t('diagnose.passport_no_suspicious_title'), detail: t('diagnose.passport_no_suspicious_detail', { passport_no: p.passport_no }) }),
    'photo.bg_uncertain':      () => ({ title: t('diagnose.photo_bg_country_title', pRender), detail: t('diagnose.photo_bg_country_detail', pRender) }),
    'photo.bg_country':        () => ({ title: t('diagnose.photo_bg_country_title', pRender), detail: t('diagnose.photo_bg_country_detail', pRender) }),
    'photo.bg_mismatch':       () => ({ title: t('diagnose.photo_bg_mismatch_title', pRender), detail: t('diagnose.photo_bg_mismatch_detail', pRender) }),
    'ocr.failed':              () => ({ title: t('wizard.diag_ocr_failed_title', { materialType: t(`materials.type_${p.material_type}`) }), detail: t('wizard.diag_ocr_failed_detail') }),
    'bank.unparseable':        () => ({ title: t('diagnose.bank_unparseable_title'), detail: t('diagnose.bank_unparseable_detail') }),
    'bank.coverage_short':     () => ({ title: t('diagnose.bank_coverage_short_title', { months: p.months }), detail: t('diagnose.bank_coverage_short_detail', { months: p.months }) }),
    'bank.income_low':         () => ({ title: t('diagnose.bank_income_low_title'), detail: t('diagnose.bank_income_low_detail', { monthly_income: p.monthly_income }) }),
    'bank.large_inflow':       () => ({ title: t('diagnose.bank_large_inflow_title', { count: p.count }), detail: t('diagnose.bank_large_inflow_detail', { count: p.count }) }),
    'bank.income_gap':         () => ({ title: t('diagnose.bank_income_gap_title', { gap_months: p.gap_months }), detail: t('diagnose.bank_income_gap_detail', { gap_months: p.gap_months, start_month: p.start_month, end_month: p.end_month, gap_count: p.gap_count }) }),
    'bank.months_missing':     () => ({ title: t('diagnose.bank_months_missing_title', { n: (p.missing_months || []).length }), detail: t('diagnose.bank_months_missing_detail', { missing_months: (p.missing_months || []).join(', ') }) }),
    'bank.sudden_inflow':      () => ({ title: t('diagnose.bank_sudden_inflow_title', { n: p.count }), detail: t('diagnose.bank_sudden_inflow_detail', { top_date: p.top_date, top_amount: p.top_amount, top_severity: p.top_severity }) }),
    'bank.balance_below_threshold': () => ({ title: t('diagnose.bank_balance_threshold_title', { country: countryName }), detail: t('diagnose.bank_balance_threshold_detail', { country: countryName, ending_balance_src: p.ending_balance_src, ending_balance_dest: p.ending_balance_dest, daily_min_dest: p.daily_min_dest, min_coverage_months: p.min_coverage_months, hard_block: p.hard_block }) }),
    'bank.balance_coverage':   () => ({ title: t('diagnose.bank_balance_coverage_title'), detail: t('diagnose.bank_balance_coverage_detail', { ending_balance: p.ending_balance, budget_total: p.budget_total, stay_days: p.stay_days }) }),
    'fields.travel_date_missing': () => ({ title: t('diagnose.travel_date_missing_title'), detail: t('diagnose.travel_date_missing_detail') }),
    'fields.purpose_missing':  () => ({ title: t('diagnose.purpose_missing_title'), detail: t('diagnose.purpose_missing_detail') }),
  }
  const r = table[code]?.()
  if (!r) return {}
  // W67: 跟 translateDiagnoseIssue 同样的 i18n 兜底 — t() 失败时降级到 issue 原 title/detail。
  const rawTitle = r.title
  const rawDetail = r.detail
  const titleLooksUnresolved = typeof rawTitle === 'string'
    && /^[a-z_]+\.[a-z_0-9.]+_[a-z]+$/.test(rawTitle)
  const detailLooksUnresolved = typeof rawDetail === 'string'
    && /^[a-z_]+\.[a-z_0-9.]+_[a-z]+$/.test(rawDetail)
  return {
    title: titleLooksUnresolved && issue.title ? issue.title : rawTitle,
    detail: detailLooksUnresolved && issue.detail ? issue.detail : rawDetail,
  }
}

// ------------------------------------------------------------------ //
// 大类 + 子项定义                                                       //
// ------------------------------------------------------------------ //
// W37: label/hint 换成 i18n key（labelKey/hintKey），不再是写死的中文字符串——
// 模板里用 t(item.labelKey) 取当前语言的文案。分类的 labelKey 复用 Apply.vue
// 已有的 apply.cat_* key，保持措辞一致；bank 子项的 labelKey 复用
// materials.type_bank（W36 之前就存在，本来就是给这个材料类型用的）。
export const CATEGORIES = [
  {
    key: 'identity',
    labelKey: 'apply.cat_identity',
    icon: 'identity',
    items: [
      { key: 'passport', labelKey: 'wizard.item_passport_label', materialType: 'passport', ocr: true, checkExpiry: true, hintKey: 'wizard.item_passport_hint' },
      { key: 'photo', labelKey: 'wizard.item_photo_label', materialType: 'photo', ocr: false, hintKey: 'wizard.item_photo_hint' },
      // W54: 户口本已下架 (用户不再上传户口本)。如使馆要求特殊场景可走"其他材料"兜底。
    ],
  },
  {
    key: 'work',
    labelKey: 'apply.cat_work',
    icon: 'work',
    items: [
      { key: 'employment', labelKey: 'wizard.item_employment_label', materialType: 'employment', ocr: false, hintKey: 'wizard.item_employment_hint' },
    ],
  },
  {
    key: 'financial',
    labelKey: 'apply.cat_financial',
    icon: 'financial',
    items: [
      { key: 'bank_statement', labelKey: 'materials.type_bank', materialType: 'bank', ocr: true, hintKey: 'wizard.item_bank_hint' },
    ],
  },
  {
    key: 'travel',
    labelKey: 'apply.cat_travel',
    icon: 'travel',
    isTravelPlanner: true,
    items: [
      { key: 'itinerary', labelKey: 'wizard.item_itinerary_label', auto: true },
    ],
  },
  {
    key: 'form',
    labelKey: 'apply.cat_form',
    icon: 'form',
    isFormStep: true,
    items: [],
  },
]

// 护照最短剩余有效期（月）— 与后端 VisaDiagnoser.PASSPORT_MIN_VALIDITY_MONTHS 保持一致
const PASSPORT_MIN_VALIDITY_MONTHS = 6

const _MONTHS = {
  JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6,
  JUL: 7, AUG: 8, SEP: 9, OCT: 10, NOV: 11, DEC: 12,
}

/** 尽量宽松地解析 OCR 抽取出来的日期字符串,返回 {y,m,d} 或 null。 */
function parseOcrDate(raw) {
  if (!raw) return null
  const s = String(raw).trim().toUpperCase()
  let m = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/)
  if (m) return { y: +m[1], m: +m[2], d: +m[3] }
  m = s.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/)
  if (m) return { y: +m[3], m: +m[2], d: +m[1] }
  m = s.match(/^(\d{1,2})\s+([A-Z]{3})\s+(\d{4})$/)
  if (m && _MONTHS[m[2]]) return { y: +m[3], m: _MONTHS[m[2]], d: +m[1] }
  return null
}

/** 距离今天的月数(向下取整),解析失败返回 null。 */
function monthsUntil(raw) {
  const d = parseOcrDate(raw)
  if (!d) return null
  const target = new Date(d.y, d.m - 1, d.d)
  const today = new Date()
  let months = (target.getFullYear() - today.getFullYear()) * 12 + (target.getMonth() - today.getMonth())
  if (target.getDate() < today.getDate()) months -= 1
  return months
}

function defaultItemState() {
  return {
    collected: false,
    localId: null,
    materialId: null,
    fileName: null,
    thumbUrl: null,
    fileUrl: null,   // 完整文件 URL(供 Lightbox 预览原图/PDF)
    fileType: null,  // image/* | application/pdf — 决定 Lightbox 用 <img> 还是 <iframe>
    ocrFields: null,
    isBlurry: false,
    isComplete: true,
    error: null,
    // W63+ 银行流水的非阻断性审核提示(后端 /ocr 端点 bank_analysis 字段)
    bankAnalysis: null,
    // W62+ 证件照片的非阻断性提示(后端 /v2/materials/photo/check 警告),
    // 比如"未检测到人脸,可能不是证件照"。允许上传但显示在卡片上提醒用户。
    photoWarnings: null,
  }
}

function defaultState(countryCode, visaType) {
  const categories = {}
  for (const cat of CATEGORIES) {
    const items = {}
    for (const it of cat.items) items[it.key] = defaultItemState()
    categories[cat.key] = { items, validated: false, skipped: false, issues: [] }
  }
  return {
    countryCode,
    visaType,
    activeCategory: CATEGORIES[0].key,
    categories,
    travelPlan: {
      origin: '', destination: '', departDate: '', returnDate: '',
      flightOutNo: '', flightBackNo: '',
      // W42: 回程独立可编辑（开口程 open-jaw：去哪个城市回程可以跟去程不是同一个
      // 城市）。留空时按 destination→origin 兜底（generateItinerary 里处理）。
      returnOrigin: '', returnDestination: '',
      days: [], // [{day, date, city, transport, hotel, attraction}] — W40
      itineraryText: '',
    },
  }
}

// W40/W41: 出发/返回日期确定后，按日期区间重建 days（每天一行）——只根据日期算
// 天数和每天日期，city/transport/hotel/attraction 全部留空，用户自己填或点
// "一键生成" 交给 AI。已有条目按日期复用，不会因为改日期清空已经填好的内容。
function rebuildTravelDays(plan) {
  if (!plan.departDate || !plan.returnDate) {
    plan.days = []
    return
  }
  const start = new Date(plan.departDate)
  const end = new Date(plan.returnDate)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    plan.days = []
    return
  }
  const byDate = new Map((plan.days || []).map((d) => [d.date, d]))
  const days = []
  let day = 1
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1), day += 1) {
    const dateStr = d.toISOString().slice(0, 10)
    const existing = byDate.get(dateStr)
    days.push(existing
      ? { ...existing, day }
      : { day, date: dateStr, city: '', transport: '', hotel: '', attraction: '', flightNo: '' })
  }
  // W66: 把 plan 级别的去程/返程航班号同步到首末天的 day.flightNo,
  // 这样 PDF 渲染只看 d.flightNo 就行,逻辑统一。
  // 只在 day.flightNo 为空时覆盖,尊重用户手填。
  if (days.length && plan.flightOutNo && !days[0].flightNo) days[0].flightNo = plan.flightOutNo
  if (days.length && plan.flightBackNo && !days[days.length - 1].flightNo) days[days.length - 1].flightNo = plan.flightBackNo
  plan.days = days
}

// 顶部"目的地"文字改了 → 把跟旧目的地文字一样的"每天城市"格子也批量改成新的
// （单城市行程的常见情况）；跟旧目的地文字不一样的格子（多城市行程）不动。
function syncDestinationToDays(plan, oldDestination, newDestination) {
  if (!oldDestination || oldDestination === newDestination) return
  for (const d of plan.days || []) {
    if (d.city === oldDestination) {
      d.city = newDestination
      d.city_en = '' // W47: 城市变了，旧的英文镜像作废
    }
  }
}

function storageKey(countryCode, visaType) {
  return `${STORAGE_PREFIX}${countryCode || 'na'}.${visaType || 'na'}`
}

function loadCache(key, fallback) {
  return loadWithExpiry(key, fallback, WIZARD_TTL_MS)
}

function saveCache(key, data) {
  saveWithExpiry(key, data, WIZARD_TTL_MS)
}

function saveOcrField(localId, fields) {
  if (!localId || !fields) return
  const cache = loadCache(OCR_CACHE_KEY, {})
  cache[localId] = fields
  saveCache(OCR_CACHE_KEY, cache)
}

export function getOcrCache() {
  return loadCache(OCR_CACHE_KEY, {})
}

export function getTravelPlanCache() {
  return loadCache(TRAVEL_PLAN_KEY, null)
}

// ------------------------------------------------------------------ //
// composable                                                          //
// ------------------------------------------------------------------ //
export function useMaterialWizard(countryCode, visaType = 'tourism') {
  const key = storageKey(countryCode, visaType)
  const loaded = loadCache(key, defaultState(countryCode, visaType))
  // W40 迁移兜底：老版本 localStorage 里的 travelPlan 是旧字段（attractions/
  // hotelName），没有 days/mode——缺字段就按新 defaultState 补上，避免 undefined。
  if (!loaded.travelPlan || !Array.isArray(loaded.travelPlan.days)) {
    loaded.travelPlan = { ...defaultState(countryCode, visaType).travelPlan, ...(loaded.travelPlan || {}), days: [] }
  }
  // W67: localStorage 里缓存的 c.issues 是后端硬编码中文 title/detail,
  // 之前从未经过 translateDiagnoseIssue 翻译 → 切到 en/vi/id UI 也显示中文。
  // 在 load 时统一 map 一次。issue 没 params/title_key 的(后端 issue 应该有),
  // map 失败时 issueFallbackText 会用 issue 原 title/detail(后端 zh-CN)兜底。
  if (loaded.categories) {
    for (const catKey of Object.keys(loaded.categories)) {
      const c = loaded.categories[catKey]
      if (c?.issues?.length) {
        c.issues = c.issues.map(translateDiagnoseIssue)
      }
    }
  }
  const state = reactive(loaded)

  watch(state, (v) => {
    saveCache(key, v)
  }, { deep: true })

  // W67: days 任何变化(AI 生成 / 日期重建 / 用户手改 city / 手改 transport)
  // 都触发一次同城自愈。跟 TravelPlanner.vue 里"最后一天兜底成飞机"的 watch 对称,
  // 只是这一条修的是"同城不能是飞机"的对立面。
  watch(() => state.travelPlan.days, (days) => {
    healIntraCityTransport({ days })
  }, { deep: true })

  // W63-f: 监听 UI 语言变化,重新翻译所有 c.issues 的 title/detail。
  // 之前 translateDiagnoseIssue 在 validateCategory 时跑一次,issue.title 是字符串,
  // 用户切语言后 c.issues 不会自动重译 → 越南/印尼用户看到"护照号格式异常"中文。
  // 重译逻辑:遍历每个 cat.issues,保留原 code/severity/itemKey/related_material_id,
  // 用当前 i18n locale 重新生成 title/detail + params。
  const { locale } = useI18n({ useScope: 'global' })
  watch(locale, () => {
    for (const catKey of Object.keys(state.categories || {})) {
      const c = state.categories[catKey]
      if (!c?.issues?.length) continue
      c.issues = c.issues.map((iss) => {
        // 如果 issue 没有 code(纯客户端补的),保持原样
        if (!iss.code) return iss
        return { ...iss, ...retranslateIssue(iss) }
      })
    }
  })

  const categoryList = CATEGORIES

  const activeIndex = computed(() => categoryList.findIndex((c) => c.key === state.activeCategory))
  const activeCategoryDef = computed(() => categoryList[activeIndex.value] || categoryList[0])

  function categoryDone(catKey) {
    const c = state.categories[catKey]
    if (!c) return false
    // Already-validated (user pressed Next, diagnose passed) or user-skipped —
    // these are the "approved" states. Once approved, keep showing as done.
    if (c.validated || c.skipped) return true
    // W45 fix: also count as done the moment every required item in the
    // category is collected, so the top progress bar climbs in real time as
    // the user uploads. Without this the bar stays at 0% until the user
    // clicks Next — which is what made W45 e2e testers think the bar was
    // broken. Validate-on-Next still runs the diagnose check; this only
    // affects the visual fill.
    const catDef = categoryList.find((x) => x.key === catKey)
    if (!catDef) return false
    if (catDef.isFormStep) return false
    if (catDef.isTravelPlanner) {
      // itinerary collected = all days have city + hotel
      return !!state.categories.travel.items.itinerary?.collected
    }
    return itemsRequiredCollected(catDef)
  }

  const overallPercent = computed(() => {
    const done = categoryList.filter((c) => categoryDone(c.key)).length
    return Math.round((done / categoryList.length) * 100)
  })

  function itemsRequiredCollected(catDef) {
    const c = state.categories[catDef.key]
    // W48: 修复 — 之前 `.filter(!it.optional)` 对全 optional 的分类(如 insurance)
    // 会得到空数组,`every` 在空数组上返回 true,导致旅行保险没填也显示绿色对勾。
    // 现在:必须至少有一项**非 optional** 才走 `every`;全 optional 分类返回 false
    // (除非用户显式点过 skip / validated)。
    const required = catDef.items.filter((it) => !it.optional && !it.auto)
    if (required.length === 0) return false
    return required.every((it) => c.items[it.key]?.collected)
  }

  const activeCategoryReady = computed(() => {
    const def = activeCategoryDef.value
    if (def.isFormStep) return true
    if (def.isTravelPlanner) {
      // W67: 不依赖 itinerary.collected 标志位(那是 onNext 时 compileItineraryText 才更新的,
      // 死锁)。直接算 days 是否填好: 每 day 有 city, 倒数第 1 天外还有 hotel,
      // 且有 depart/return date。
      const p = state.travelPlan
      if (!p.days.length) return false
      if (!p.departDate || !p.returnDate) return false
      const lastIdx = p.days.length - 1
      return p.days.every((d, i) => d.city && (i < lastIdx ? d.hotel : true))
    }
    return itemsRequiredCollected(def)
  })

  const allMaterialIds = computed(() => {
    const ids = []
    for (const cat of categoryList) {
      const c = state.categories[cat.key]
      for (const it of cat.items) {
        const rec = c.items[it.key]
        if (rec?.materialId) ids.push(rec.materialId)
      }
    }
    return ids
  })

  // -------------------------------------------------------------- //
  // 上传 / OCR                                                        //
  // -------------------------------------------------------------- //
  // W59: 客户端预校验 — 文件类型 + 大小,失败时直接落到 rec.error,不发请求。
  // 跟 UploadItemCard input[accept] 配合做双重兜底(用户从系统选择器能绕过 accept)。
  const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
  const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
  function validateFileClient(file) {
    if (!file) return i18n.global.t('wizard.err_file_missing')
    if (!ALLOWED_TYPES.includes(file.type)) {
      return i18n.global.t('wizard.err_file_type', { types: 'JPG / PNG / WebP / PDF' })
    }
    if (file.size > MAX_FILE_SIZE) {
      const mb = (file.size / 1024 / 1024).toFixed(1)
      return i18n.global.t('wizard.err_file_size', { size: mb, max: 10 })
    }
    return null
  }

  // 图片 → 生成 data URL 缩略图,不依赖后端 thumbnail_url;
  // 后端有返回时优先用后端的(更准确 / CDN 缓存),失败才退回 data URL。
  function readAsDataUrl(file) {
    return new Promise((resolve) => {
      const r = new FileReader()
      r.onload = () => resolve(r.result)
      r.onerror = () => resolve(null)
      r.readAsDataURL(file)
    })
  }

  function buildMaterialsSnapshot(catKey = null) {
    const snaps = []
    const cats = catKey
      ? categoryList.filter((c) => c.key === catKey)
      : categoryList
    for (const cat of cats) {
      const c = state.categories[cat.key]
      for (const it of cat.items) {
        const rec = c.items[it.key]
        if (!rec?.collected) continue
        snaps.push({
          item_key: it.key,
          material_type: it.materialType,
          ocr_result: rec.ocrFields || {},
        })
      }
    }
    return snaps
  }

  async function uploadItem(catKey, itemKey, file, onProgress) {
    const catDef = categoryList.find((c) => c.key === catKey)
    const itemDef = catDef.items.find((i) => i.key === itemKey)
    const rec = state.categories[catKey].items[itemKey]
    rec.error = null

    // W59: client-side pre-check
    const clientErr = validateFileClient(file)
    if (clientErr) {
      rec.error = clientErr
      throw new Error(clientErr)
    }

    rec.localId = `${catKey}:${itemKey}`
    rec.materialId = null

    let result
    try {
      if (onProgress) onProgress(5)
      result = await processMaterial(file, itemDef.materialType, {
        countryCode: state.countryCode,
        onProgress,
      })
      if (onProgress) onProgress(100)
    } catch (e) {
      rec.error = e?.message || i18n.global.t('wizard.err_upload_failed')
      throw e
    }

    rec.fileName = file.name
    rec.fileUrl = await readAsDataUrl(file)
    rec.fileType = (file.type || '').toLowerCase()
    if (file.type.startsWith('image/')) {
      rec.thumbUrl = rec.fileUrl
    } else {
      rec.thumbUrl = null
    }
    rec.isBlurry = false
    rec.isComplete = true
    rec.ocrFields = null
    rec.bankAnalysis = null
    rec.collected = true

    if (itemDef.ocr) {
      const fields = result?.fields || {}
      rec.ocrFields = fields
      rec.isBlurry = !!result?.is_blurry
      rec.isComplete = result?.is_complete !== false
      saveOcrField(rec.localId, fields)

      if (itemKey === 'bank_statement' && result?.bank_analysis) {
        rec.bankAnalysis = result.bank_analysis
      } else {
        rec.bankAnalysis = null
      }

      if (itemDef.checkExpiry) {
        const expiry = fields.expiry || fields.date_of_expiry || fields.passport_expiry
        const months = monthsUntil(expiry)
        if (expiry && months !== null && months < PASSPORT_MIN_VALIDITY_MONTHS) {
          rec.error = i18n.global.t('wizard.err_expiry_short', { months: PASSPORT_MIN_VALIDITY_MONTHS, remain: months })
          rec.collected = false
        } else if (!expiry) {
          rec.error = fields.is_passport_doc === false
            ? i18n.global.t('wizard.err_not_passport_detected')
            : i18n.global.t('wizard.err_expiry_missing')
          rec.collected = false
        }
      }
    }

    return rec
  }

  async function removeItem(catKey, itemKey) {
    const rec = state.categories[catKey].items[itemKey]
    if (rec.localId) {
      const cache = loadCache(OCR_CACHE_KEY, {})
      delete cache[rec.localId]
      saveCache(OCR_CACHE_KEY, cache)
    }
    state.categories[catKey].items[itemKey] = defaultItemState()
    state.categories[catKey].validated = false
  }

  // -------------------------------------------------------------- //
  // 跨材料校验（诊断接口）                                                //
  // -------------------------------------------------------------- //
  async function validateCategory(catKey) {
    const catDef = categoryList.find((c) => c.key === catKey)
    const c = state.categories[catKey]
    c.issues = []

    if (catDef.isTravelPlanner) {
      const issues = validateTravelPlan(state.travelPlan)
      c.issues = issues
      c.validated = issues.every((i) => i.severity !== 'error')
      return c
    }

    // 子项本身已标记 error（比如护照过期）→ 直接阻断，不用等诊断接口
    const hasItemError = catDef.items.some((it) => c.items[it.key]?.error)
    if (hasItemError) {
      c.issues = catDef.items
        .filter((it) => c.items[it.key]?.error)
        .map((it) => ({ severity: 'error', title: i18n.global.t(it.labelKey), detail: c.items[it.key].error, itemKey: it.key }))
      c.validated = false
      return c
    }

    const snaps = buildMaterialsSnapshot(catKey)
    if (!snaps.length) {
      c.validated = true
      return c
    }

    try {
      const out = await diagnoseMaterials({
        materials_snapshot: snaps,
        country_code: state.countryCode,
        visa_type: state.visaType,
      })
      const itemKeysInCategory = new Set(catDef.items.map((it) => it.key))
      const relevant = (out.issues || [])
        .filter((iss) => itemKeysInCategory.has(iss.related_item_key))
        .map(translateDiagnoseIssue)
      c.issues = relevant
      const blocked = relevant.some((iss) => iss.severity === 'error' || iss.severity === 'critical')
      c.validated = !blocked
    } catch (e) {
      // 诊断接口失败（网络抖动等）不阻断——已经通过了子项自身的清晰度/过期校验
      c.validated = true
    }
    return c
  }

  // 供"生成行程单"按钮点的前置校验：只检查日期 + 每天有没有填城市（LLM 补景点
  // 需要知道城市），不要求已经编译过 itineraryText——那是最终"下一步"用的更严格校验。
  function validateForGenerate(plan) {
    const t = i18n.global.t
    const issues = []
    if (!plan.departDate || !plan.returnDate) {
      issues.push({ severity: 'error', title: t('wizard.issue_travel_dates_title'), detail: t('wizard.issue_travel_dates_detail') })
      return issues
    }
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const dep = new Date(plan.departDate)
    const ret = new Date(plan.returnDate)
    // W67: 出发日期早于今天 — 警告不阻塞(PDF 导出允许导出已发生的行程)。
    if (dep < today) issues.push({ severity: 'warn', title: t('wizard.issue_depart_past_title'), detail: plan.departDate })
    if (ret <= dep) issues.push({ severity: 'error', title: t('wizard.issue_return_before_depart_title'), detail: `${plan.departDate} → ${plan.returnDate}` })
    if (!plan.days || plan.days.length === 0) {
      issues.push({ severity: 'error', title: t('wizard.issue_travel_dates_title'), detail: t('wizard.issue_travel_dates_detail') })
    } else if (plan.days.some((d) => !d.city || !d.city.trim())) {
      issues.push({ severity: 'error', title: t('wizard.issue_city_missing_title'), detail: t('wizard.issue_city_missing_detail') })
    }
    return issues
  }

  function validateTravelPlan(plan) {
    const t = i18n.global.t
    const issues = validateForGenerate(plan)
    if (issues.length) return issues
    // W67: 最后一天是返程日, hotel 被 clearLastDayHotel 强制清空, some() 跳过最后一天。
    const lastIdx = plan.days.length - 1
    if (plan.days.some((d, i) => i < lastIdx && (!d.hotel || !d.hotel.trim()))) {
      issues.push({ severity: 'error', title: t('wizard.issue_hotel_missing_title'), detail: t('wizard.issue_hotel_missing_detail') })
    }
    // W67: itineraryText 原本由 compileItineraryText 在 onNext 时填,
    // 但 onNext 不跑就不会填, 这里检查会死锁。
    // 改成现场算一个: 至少有一个 day 有 city + 至少 1 个非空 attraction 就算通过。
    const hasContent = plan.days.some((d) => d.city && d.city.trim() && (d.attraction || '').trim())
    if (!hasContent) {
      issues.push({ severity: 'error', title: t('wizard.issue_itinerary_missing_title'), detail: t('wizard.issue_itinerary_missing_detail') })
    }
    return issues
  }

  // 把 day 行的 transport==='flight' 渲染成"出发地 → 到达地"。
  // - Day 1（首日）: origin → 当天城市（出发的机场/城市）
  // - Day 2..N-1（中间飞行日）: 上一站 city → 当天 city
  // - Day N（最后一天，返程日）: 当天 city → returnDestination（不是"旧金山 → 旧金山"）
  // 中间非飞行日直接返回 d.city（不画箭头）。
  // W67: 同城检测 — 当 from === to 时（同城内活动，例芝加哥→芝加哥）,
  // 不画箭头，退化到单城市展示，避免视觉冗余（"芝加哥 → 芝加哥"看着像 bug）。
  function dayCityDisplay(plan, index) {
    const d = plan.days[index]
    if (!d) return ''
    if (d.transport !== 'flight') return d.city || ''
    const isLast = index === plan.days.length - 1
    const to = isLast
      ? (plan.returnDestination || plan.origin || '')
      : (d.city || '')
    const from = index === 0
      ? (plan.origin || '')
      : (plan.days[index - 1]?.city || '')
    // W67: 起点 = 终点 = 同城内活动，跳过箭头
    if (from && to && from === to) return d.city || ''
    if (from && to) return `${from} → ${to}`
    return d.city || ''
  }

  // W41: 逐日行程表随便怎么改都直接反映在预览表格上，不再区分"手动/自动模式"。
  // compileItineraryText 是纯同步函数——每次 days 变化就重新编译一次 itineraryText
  // （给 OrderNew.vue / 提交后端用的文本版），不调用 LLM。
  function compileItineraryText(plan) {
    const t = i18n.global.t
    const p = plan
    const rows = p.days.map((d, i) => ({
      day: d.day,
      date: d.date,
      city: dayCityDisplay(p, i),
      transport: d.transport ? t(`wizard.transport_${d.transport}`) : '—',
      attraction: d.attraction || '—',
      hotel: d.hotel || '—',
    }))
    const header = [
      `${t('wizard.itinerary_col_day')} Day`,
      `${t('wizard.itinerary_col_date')} Date`,
      `${t('wizard.itinerary_col_city')} City`,
      `${t('wizard.itinerary_col_transport')} Transport`,
      `${t('wizard.itinerary_col_attraction')} Itinerary`,
      `${t('wizard.itinerary_col_hotel')} Hotel`,
    ]
    const lines = [header.join(' | ')]
    lines.push(header.map(() => '---').join(' | '))
    for (const r of rows) {
      lines.push([`Day ${r.day}`, r.date, r.city, r.transport, r.attraction, r.hotel].join(' | '))
    }
    const text = p.days.length ? lines.join('\n') : ''
    p.itineraryText = text

    const rec = state.categories.travel.items.itinerary
    // W67: 最后一天是返程日, hotel 被 clearLastDayHotel 强制清空,
    // 所以 every 检查要跳过最后一天 (i < days.length - 1)。
    const lastIdx = p.days.length - 1
    const allFilled = p.days.length > 0 && p.days.every((d, i) => d.city && (i < lastIdx ? d.hotel : true))
    rec.collected = allFilled && !!p.departDate && !!p.returnDate
    rec.error = rec.collected ? null : t('wizard.itinerary_incomplete_error')

    try {
      localStorage.setItem(TRAVEL_PLAN_KEY, JSON.stringify({
        hotel_name: [...new Set(p.days.map((d) => d.hotel).filter(Boolean))].join(', '),
        flight_no: p.flightOutNo,
        arrival_date: p.departDate,
        departure_date: p.returnDate,
        itinerary_text: text,
        // W47c: 写完整 days 让提交页(OrderNew)/审核页可以直接渲染真表格预览,
        // 不用反向解析 pipe 文本. 仅持久化非 _auto 字段,避免 localStorage 膨胀.
        days: p.days.map((d) => ({
          day: d.day, date: d.date, city: d.city,
          transport: d.transport, hotel: d.hotel, attraction: d.attraction,
          city_en: d.city_en, hotel_en: d.hotel_en, attraction_en: d.attraction_en,
        })),
        origin: p.origin, destination: p.destination,
        return_origin: p.returnOrigin, return_destination: p.returnDestination,
      }))
    } catch {}

    return text
  }

  // 用户在某天格子里手动打字 → 标记这个字段是"手填"，以后一键生成不会再碰它。
  // city 永远是手填字段（就没有 _auto 这一说），不在这里管。
  // W47: 用户手动改过 hotel/attraction 后，之前 LLM 给的英文镜像就过期了，
  // 清掉对应的 *_en，PDF 那格会回退成只显示当前语言（而不是错的英文）。
  // W67: 同时设 _manual[field]=true，让下方的"最后一天兜底成飞机" /
  // "同城兜底成 walk"这些自愈逻辑真正尊重用户手填。
  function markDayFieldManual(day, field) {
    day._auto = { ...(day._auto || {}), [field]: false }
    day._manual = { ...(day._manual || {}), [field]: true }
    if (field === 'hotel') day.hotel_en = ''
    if (field === 'attraction') day.attraction_en = ''
  }

  // 一键生成：调用后端 LLM 接口补全 transport/hotel/attraction。
  // - 真正空白的字段：直接补。
  // - 上一轮"一键生成"自动填过、用户没再手动改过的字段（day._auto[field]===true）：
  //   这次也当作空白重新生成——否则改了目的地/航班信息后，已经生成过一次的
  //   格子会一直卡在旧内容，包括返程那天。
  // - 用户自己手填过的字段：永远保留，不会被覆盖。
  // city 永远是用户自己的字段，不参与生成。
  async function generateItinerary() {
    const p = state.travelPlan
    // _auto 是纯前端的字段来源标记，不是后端 schema 的一部分，发请求时去掉
    const requestDays = p.days.map((d) => ({
      day: d.day,
      date: d.date,
      city: d.city,
      transport: d._auto?.transport ? '' : d.transport,
      hotel: d._auto?.hotel ? '' : d.hotel,
      attraction: d._auto?.attraction ? '' : d.attraction,
    }))
    const { days } = await generateItineraryAttractions({
      countryName: p.destination || state.countryCode,
      lang: i18n.global.locale.value,
      days: requestDays,
      flight: {
        origin: p.origin,
        destination: p.destination,
        // 回程留空就按 destination→origin 兜底（W42：开口程可以自己填不一样的）
        return_origin: p.returnOrigin || p.destination,
        return_destination: p.returnDestination || p.origin,
        flight_out_no: p.flightOutNo,
        flight_back_no: p.flightBackNo,
        depart_date: p.departDate,
        return_date: p.returnDate,
      },
    })
    p.days = days.map((d, i) => {
      const auto = { ...(p.days[i]?._auto || {}) }
      for (const f of ['transport', 'hotel', 'attraction']) {
        if (!requestDays[i][f] && d[f]) auto[f] = true
      }
      return { ...d, _auto: auto }
    })
    // W67: 中间天同城自愈 — "芝加哥→芝加哥"不能是飞机,得改成市内交通 (walk)。
    // 对齐 TravelPlanner.vue 那条"最后一天兜底成飞机"的规则,互为对称。
    // 尊重 _manual.transport=true (用户手填过就别动)。
    //   - 中间天 (1 <= i < n-1): from = days[i-1].city, to = d.city
    //   - 首日 / 末日: 不动 (首日 = 去程出发是常态, 末日 = 用户改返程目的地 ≠ 出发点才合理)
    healIntraCityTransport(p)
    return compileItineraryText(p)
  }

  // W67: 中间天同城兜底 — transport=flight 但 from===to 时强制改成 walk,
  // 因为同城内不可能坐飞机,这条视觉上"芝加哥 → 芝加哥 ✈️"就是典型 AI 幻觉。
  // 只覆盖 AI 生成 (或重建) 时; 用户手填过的字段通过 _manual.transport 保护。
  function healIntraCityTransport(plan) {
    const days = plan.days
    if (!days || days.length < 3) return  // 1-2 天行程不可能有中间天
    for (let i = 1; i < days.length - 1; i += 1) {
      const d = days[i]
      if (!d) continue
      if (d.transport !== 'flight') continue
      if (d._manual?.transport) continue  // 用户手填过，尊重
      const from = days[i - 1]?.city || ''
      const to = d.city || ''
      if (from && to && from === to) {
        d.transport = 'walk'
      }
    }
  }

  function skipCategory(catKey) {
    const catDef = categoryList.find((c) => c.key === catKey)
    if (!catDef.skippable) return
    state.categories[catKey].skipped = true
    state.categories[catKey].validated = true
  }

  function goToNextCategory() {
    const idx = activeIndex.value
    if (idx < categoryList.length - 1) {
      state.activeCategory = categoryList[idx + 1].key
    }
  }

  function goToCategory(catKey) {
    const idx = categoryList.findIndex((c) => c.key === catKey)
    if (idx < 0) return
    // W47d+ : 5 大类材料并非串行依赖关系(身份证明/财务证明/工作在职/
    // 行程住宿/签证表格 是平行收集,不是必须先做完 A 才能填 B)。
    // 产品决策:tab 自由切换,用户点哪个就跳哪个。
    // (旧的"先做完才能切下一个"限制已去除,以匹配产品需求。)
    state.activeCategory = catKey
  }

  return {
    CATEGORIES: categoryList,
    state,
    activeIndex,
    activeCategoryDef,
    activeCategoryReady,
    overallPercent,
    allMaterialIds,
    buildMaterialsSnapshot,
    categoryDone,
    uploadItem,
    removeItem,
    validateCategory,
    skipCategory,
    generateItinerary,
    compileItineraryText: () => compileItineraryText(state.travelPlan),
    validateForGenerate: () => validateForGenerate(state.travelPlan),
    rebuildTravelDays: (plan) => rebuildTravelDays(plan ?? state.travelPlan),
    dayCityDisplay: (index) => dayCityDisplay(state.travelPlan, index),
    markDayFieldManual,
    syncDestinationToDays: (oldDestination, newDestination) => syncDestinationToDays(state.travelPlan, oldDestination, newDestination),
    goToNextCategory,
    goToCategory,
  }
}
