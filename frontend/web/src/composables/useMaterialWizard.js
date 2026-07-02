// useMaterialWizard — 分大类、强校验的材料收集向导
//
// 6 大类，按顺序解锁：身份证件 → 财力证明 → 在职/工作证明 → 行程住宿 → 旅行保险 → 信息表单。
// 大类内的子项可以自由顺序上传；大类内所有必填子项收集完后调用后端
// /materials/diagnose 做跨材料校验（护照有效期、材料完整性等），有 error/critical
// 级别问题时阻断，不允许进入下一大类。旅行保险大类允许"稍后上传"跳过。
import { computed, reactive, watch } from 'vue'
import {
  uploadMaterialWithProgress,
  deleteMaterial,
  diagnoseMaterials,
  generateItineraryAttractions,
} from '@/api/materials'
import http from '@/api/http'
import i18n from '@/i18n'

const STORAGE_PREFIX = 'visa.wizard.'
const OCR_CACHE_KEY = 'visa.wizard.ocrCache' // materialId -> ocr fields，供 OrderNew.vue 自动带入用
const TRAVEL_PLAN_KEY = 'visa.wizard.travelPlan'

// W39: /materials/diagnose 是后端接口，返回的 title/detail 是服务端拼好的 zh-CN
// 字符串（不管前端选了什么语言）。后端在 W39 里给每条 issue 附带了 params
// （拼字符串用到的原始数值），这里按 code 把 title/detail 换成前端 i18n 的翻译，
// 认不出的 code 才回退用后端原文，保证多语言下这块也能跟着切换。
function translateDiagnoseIssue(issue) {
  const t = i18n.global.t
  const p = issue.params || {}
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
      title: t('wizard.diag_no_suspicious_title'),
      detail: t('wizard.diag_no_suspicious_detail', { passportNo: p.passport_no }),
    }),
    'photo.bg_uncertain': () => ({
      title: t('wizard.diag_bg_uncertain_title'),
      detail: t('wizard.diag_bg_uncertain_detail'),
    }),
    'ocr.failed': () => ({
      title: t('wizard.diag_ocr_failed_title', { materialType: t(`materials.type_${p.material_type}`) }),
      detail: t('wizard.diag_ocr_failed_detail'),
    }),
  }
  const translated = table[code]?.()
  if (!translated) return issue // 不认识的 code：原样透传后端文案
  return { ...issue, title: translated.title, detail: translated.detail }
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
      { key: 'household', labelKey: 'wizard.item_household_label', materialType: 'household', ocr: true, hintKey: 'wizard.item_household_hint' },
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
    key: 'work',
    labelKey: 'apply.cat_work',
    icon: 'work',
    items: [
      { key: 'employment', labelKey: 'wizard.item_employment_label', materialType: 'employment', ocr: false, hintKey: 'wizard.item_employment_hint' },
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
    key: 'insurance',
    labelKey: 'apply.cat_insurance',
    icon: 'insurance',
    skippable: true,
    items: [
      { key: 'insurance', labelKey: 'wizard.item_insurance_label', materialType: 'insurance', ocr: false, optional: true, hintKey: 'wizard.item_insurance_hint' },
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
    materialId: null,
    fileName: null,
    thumbUrl: null,
    ocrFields: null,
    isBlurry: false,
    isComplete: true,
    error: null,
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
      : { day, date: dateStr, city: '', transport: '', hotel: '', attraction: '' })
  }
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
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function saveOcrField(materialId, fields) {
  if (!materialId || !fields) return
  const cache = loadCache(OCR_CACHE_KEY, {})
  cache[materialId] = fields
  try { localStorage.setItem(OCR_CACHE_KEY, JSON.stringify(cache)) } catch {}
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
  const state = reactive(loaded)

  watch(state, (v) => {
    try { localStorage.setItem(key, JSON.stringify(v)) } catch {}
  }, { deep: true })

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
    return catDef.items
      .filter((it) => !it.optional && !it.auto)
      .every((it) => c.items[it.key]?.collected)
  }

  const activeCategoryReady = computed(() => {
    const def = activeCategoryDef.value
    if (def.isFormStep) return true
    if (def.isTravelPlanner) return !!state.categories.travel.items.itinerary?.collected
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
  async function uploadItem(catKey, itemKey, file, onProgress) {
    const catDef = categoryList.find((c) => c.key === catKey)
    const itemDef = catDef.items.find((i) => i.key === itemKey)
    const rec = state.categories[catKey].items[itemKey]
    rec.error = null

    let material
    try {
      material = await uploadMaterialWithProgress(file, itemDef.materialType, null, onProgress)
    } catch (e) {
      rec.error = e?.message || i18n.global.t('wizard.err_upload_failed')
      throw e
    }

    rec.materialId = material.id || material.material_id
    rec.fileName = material.file_name || file.name
    rec.thumbUrl = material.thumbnail_url || null
    rec.isBlurry = false
    rec.isComplete = true
    rec.ocrFields = null
    rec.collected = true

    // OCR-capable 子项：调用 /{id}/ocr 识别并把结果落到 Material 记录上
    // （不是 /ocr/recognize 那种一次性识别——那个接口不写库，diagnose 接口读的
    // 是 Material.ocr_result，两边对不上会导致强校验永远读不到 OCR 结果）。
    if (itemDef.ocr) {
      try {
        const form = new FormData()
        form.append('lang', 'en')
        const resp = await http.post(`/v2/materials/${rec.materialId}/ocr`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 60000,
        })
        const fields = resp?.data?.fields || {}
        rec.ocrFields = fields
        rec.isBlurry = !!resp?.data?.is_blurry
        rec.isComplete = resp?.data?.is_complete !== false
        saveOcrField(rec.materialId, fields)

        if (itemDef.checkExpiry) {
          const expiry = fields.expiry || fields.date_of_expiry || fields.passport_expiry
          const months = monthsUntil(expiry)
          if (expiry && months !== null && months < PASSPORT_MIN_VALIDITY_MONTHS) {
            rec.error = i18n.global.t('wizard.err_expiry_short', { months: PASSPORT_MIN_VALIDITY_MONTHS, remain: months })
            rec.collected = false
          } else if (!expiry) {
            // fields.is_passport_doc === false：OCR 引擎压根没从图里认出任何护照
            // 特征（连一个字都没识别到，或者没有 PASSPORT/护照/MRZ 关键字），跟"识别到
            // 护照但读不出有效期"是两码事，用更准确的提示，不然用户会一直以为自己
            // 传的是护照、纳闷"明明有有效期怎么还报缺失"。
            rec.error = fields.is_passport_doc === false
              ? i18n.global.t('wizard.err_not_passport_detected')
              : i18n.global.t('wizard.err_expiry_missing')
            rec.collected = false
          }
        }
      } catch (e) {
        // OCR 失败不阻断上传本身，只是拿不到结构化字段/清晰度提示
        rec.ocrFields = null
      }
    }

    return rec
  }

  async function removeItem(catKey, itemKey) {
    const rec = state.categories[catKey].items[itemKey]
    if (rec.materialId) {
      try { await deleteMaterial(rec.materialId) } catch { /* best-effort */ }
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

    const ids = allMaterialIds.value
    if (!ids.length) {
      c.validated = true
      return c
    }

    try {
      const out = await diagnoseMaterials({
        material_ids: ids,
        country_code: state.countryCode,
        visa_type: state.visaType,
      })
      const materialIdsInCategory = new Set(
        catDef.items.map((it) => c.items[it.key]?.materialId).filter(Boolean)
      )
      const relevant = (out.issues || [])
        .filter((iss) => materialIdsInCategory.has(iss.related_material_id))
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
    if (dep < today) issues.push({ severity: 'error', title: t('wizard.issue_depart_past_title'), detail: plan.departDate })
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
    if (plan.days.some((d) => !d.hotel || !d.hotel.trim())) {
      issues.push({ severity: 'error', title: t('wizard.issue_hotel_missing_title'), detail: t('wizard.issue_hotel_missing_detail') })
    }
    if (!plan.itineraryText) {
      issues.push({ severity: 'error', title: t('wizard.issue_itinerary_missing_title'), detail: t('wizard.issue_itinerary_missing_detail') })
    }
    return issues
  }

  // 把 day 行的 transport==='flight' 渲染成"出发地 → 到达地"；day1 的出发地是
  // plan.origin，之后每天的出发地是前一天的 city（同城多日不是 flight 就不受影响）。
  function dayCityDisplay(plan, index) {
    const d = plan.days[index]
    if (!d) return ''
    if (d.transport !== 'flight') return d.city || ''
    const from = index === 0 ? (plan.origin || '') : (plan.days[index - 1]?.city || '')
    return from ? `${from} → ${d.city || ''}` : (d.city || '')
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
    const allFilled = p.days.length > 0 && p.days.every((d) => d.city && d.hotel)
    rec.collected = allFilled && !!p.departDate && !!p.returnDate
    rec.error = rec.collected ? null : t('wizard.itinerary_incomplete_error')

    try {
      localStorage.setItem(TRAVEL_PLAN_KEY, JSON.stringify({
        hotel_name: [...new Set(p.days.map((d) => d.hotel).filter(Boolean))].join(', '),
        flight_no: p.flightOutNo,
        arrival_date: p.departDate,
        departure_date: p.returnDate,
        itinerary_text: text,
      }))
    } catch {}

    return text
  }

  // 用户在某天格子里手动打字 → 标记这个字段是"手填"，以后一键生成不会再碰它。
  // city 永远是手填字段（就没有 _auto 这一说），不在这里管。
  // W47: 用户手动改过 hotel/attraction 后，之前 LLM 给的英文镜像就过期了，
  // 清掉对应的 *_en，PDF 那格会回退成只显示当前语言（而不是错的英文）。
  function markDayFieldManual(day, field) {
    day._auto = { ...(day._auto || {}), [field]: false }
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
    return compileItineraryText(p)
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
    // 只能跳到已完成的大类，或紧接着的下一个未完成大类
    const firstIncomplete = categoryList.findIndex((c) => !categoryDone(c.key))
    if (idx <= firstIncomplete) state.activeCategory = catKey
  }

  return {
    CATEGORIES: categoryList,
    state,
    activeIndex,
    activeCategoryDef,
    activeCategoryReady,
    overallPercent,
    allMaterialIds,
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
