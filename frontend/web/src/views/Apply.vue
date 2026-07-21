<template>
  <div class="apply-page">
    <AppHeader scope="apply" />

    <main class="app-container app-page apply-main">
      <!-- Step 1: 国家选 -->
      <section v-if="step === 1" class="apply-section" data-testid="apply-step-1">
        <h1 class="apply-section__title">{{ t('apply.step_country') }}</h1>
        <div class="apply-countries">
          <div
            v-for="(group, gKey) in groupedCountries"
            :key="gKey"
            class="apply-country-group"
            :data-testid="`apply-group-${gKey}`"
          >
            <h3 class="apply-country-group__title">
              {{ t(`common.country_group_${gKey}`) }}
              <span class="apply-country-group__count">{{ group.length }}</span>
            </h3>
            <div class="apply-country-group__grid">
              <button
                v-for="c in group"
                :key="c.country_code"
                type="button"
                class="apply-country"
                :class="{ 'is-selected': form.country_code === c.country_code }"
                :data-testid="`apply-country-${c.country_code}`"
                @click="selectCountry(c.country_code)"
              >
                <span class="apply-country__flag">{{ flagOf(c.country_code) }}</span>
                <span class="apply-country__name">{{ c.country_name }}</span>
                <span v-if="form.country_code === c.country_code" class="apply-country__badge">
                  <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">
                    <path d="M3 8 L7 12 L13 4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Step 2: 材料清单(RAG 拉出) -->
      <section v-else-if="step === 2" class="apply-section" data-testid="apply-step-2">
        <button class="apply-back" data-testid="apply-back" @click="step = 1">
          ← {{ t('apply.back') }}
        </button>
        <div class="apply-section__head">
          <h1 class="apply-section__title">
            <span class="apply-section__flag">{{ flagOf(form.country_code) }}</span>
            {{ selectedCountryName }} <span class="apply-section__sep">·</span> {{ t('apply.checklist') }}
          </h1>
          <p v-if="checklist" class="apply-section__sub">
            {{ t('apply.summary', { count: totalMaterialsCount, groups: groupedMaterials.length }) }}
          </p>
        </div>

        <div v-if="loading" class="apply-loading" data-testid="apply-loading">
          <div class="apply-spinner" />
          {{ t('apply.loading') }}
        </div>

        <template v-else-if="checklist">
          <!-- Meta: fee / time / validity -->
          <div v-if="checklist.fee || checklist.processing_time || checklist.validity" class="apply-meta">
            <div v-if="checklist.fee" class="apply-meta__cell">
              <div class="apply-meta__label">{{ t('apply.fee') }}</div>
              <div class="apply-meta__val">{{ metaHighlight(checklist.fee, 'fee') || cleanMeta(checklist.fee) }}</div>
              <div v-if="metaHighlight(checklist.fee, 'fee')" class="apply-meta__detail">{{ cleanMeta(checklist.fee) }}</div>
            </div>
            <div v-if="checklist.processing_time" class="apply-meta__cell">
              <div class="apply-meta__label">{{ t('apply.processing') }}</div>
              <div class="apply-meta__val">{{ metaHighlight(checklist.processing_time, 'processing') || cleanMeta(checklist.processing_time) }}</div>
              <div v-if="metaHighlight(checklist.processing_time, 'processing')" class="apply-meta__detail">{{ cleanMeta(checklist.processing_time) }}</div>
            </div>
            <div v-if="checklist.validity" class="apply-meta__cell">
              <div class="apply-meta__label">{{ t('apply.validity') }}</div>
              <div class="apply-meta__val">{{ metaHighlight(checklist.validity, 'validity') || cleanMeta(checklist.validity) }}</div>
              <div v-if="metaHighlight(checklist.validity, 'validity')" class="apply-meta__detail">{{ cleanMeta(checklist.validity) }}</div>
            </div>
          </div>

          <!-- Materials grouped by category -->
          <div v-if="groupedMaterials.length" class="apply-materials">
            <div v-for="(g, i) in groupedMaterials" :key="i" class="apply-material-group">
              <h3 class="apply-material-group__title">
                {{ t(`apply.cat_${g.key}`) }}
                <span class="apply-material-group__count">· {{ t('apply.item_count', { n: g.items.length }) }}</span>
              </h3>
              <ul class="apply-material-list">
                <li
                  v-for="(m, j) in g.items"
                  :key="j"
                  class="apply-material"
                  :data-testid="`apply-material-${g.key}-${j}`"
                >
                  <span class="apply-material__num">{{ j + 1 }}</span>
                  <span class="apply-material__body">
                    <span class="apply-material__name">{{ matName(m) }}</span>
                    <span v-if="matNote(m)" class="apply-material__note">{{ matNote(m) }}</span>
                  </span>
                  <span v-if="m.required === false" class="apply-material__optional">{{ t('apply.optional') }}</span>
                </li>
              </ul>
            </div>
          </div>

          <div v-else-if="!materialNotes.length" class="apply-empty">
            {{ t('apply.no_materials') }}
          </div>

          <!-- 提示 / 说明 — RAG 里以「重要/注意/提示」开头的条目不是要提交的材料,
               单独归到这里,不带编号/必交,避免混在材料清单里造成误解 -->
          <div v-if="materialNotes.length" class="apply-notes">
            <div class="apply-notes__title">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>
                <path d="M12 11v5M12 8h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              </svg>
              {{ t('apply.notes_title') }}
            </div>
            <ul class="apply-notes__list">
              <li v-for="(n, k) in materialNotes" :key="k">{{ stripNotePrefix(n.name) }}</li>
            </ul>
          </div>

          <div v-if="checklist.source_name" class="apply-source">
            <span class="apply-source__name">{{ checklist.source_name }}</span>
            <span v-if="checklist.last_refresh_at" class="apply-source__time">
              · {{ t('apply.source_updated_at') }} {{ formatChecklistTime(checklist.last_refresh_at) }}
            </span>
            <span
              v-if="checklist.review_status === 'pending_review'"
              class="apply-source__pill apply-source__pill--warn"
              :data-testid="`apply-source-pending-${checklist.country_code}`"
            >
              ⏳ {{ t('apply.source_pending_review') }}
            </span>
            <a v-if="checklist.source_url" :href="checklist.source_url" target="_blank" rel="noopener" class="apply-source__link">
              {{ t('apply.view_source') }} ↗
            </a>
          </div>

          <!-- 行动 -->
          <div class="apply-actions">
            <button type="button" class="apply-cta" data-testid="apply-cta" @click="goOrderNew">
              {{ t('apply.cta') }} →
            </button>
          </div>
        </template>

        <div v-else-if="error" class="apply-error" data-testid="apply-error">
          {{ error }}
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import { listDestinations } from '@/api/destinations'
import http from '@/api/http'
import { useToast } from '@/composables/useToast'
import { groupCountriesByVisaType } from '@/utils/countries'
import { track, Events, setEntrySource } from '@/api/analytics'

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const step = ref(1)
const countries = ref([])
const loading = ref(false)
const error = ref('')
const checklist = ref(null)

const form = reactive({
  country_code: '',
})

const CATEGORY_ORDER = ['identity', 'financial', 'work', 'travel', 'form', 'base']
const flagMap = {
  US: '🇺🇸', JP: '🇯🇵', KR: '🇰🇷', SG: '🇸🇬', GB: '🇬🇧', FR: '🇫🇷',
  ID: '🇮🇩', VN: '🇻🇳', TH: '🇹🇭', DE: '🇩🇪', AU: '🇦🇺', CA: '🇨🇦',
  NZ: '🇳🇿', SCHENGEN: '🇪🇺', EU: '🇪🇺',
  // 申根成员国 (W35: 26国全部可选，之前只有 DE/FR 有旗帜)
  AT: '🇦🇹', BE: '🇧🇪', HR: '🇭🇷', CZ: '🇨🇿', DK: '🇩🇰', EE: '🇪🇪',
  FI: '🇫🇮', GR: '🇬🇷', HU: '🇭🇺', IS: '🇮🇸', IT: '🇮🇹', LV: '🇱🇻',
  LI: '🇱🇮', LT: '🇱🇹', LU: '🇱🇺', MT: '🇲🇹', NL: '🇳🇱', NO: '🇳🇴',
  PL: '🇵🇱', PT: '🇵🇹', SK: '🇸🇰', SI: '🇸🇮', ES: '🇪🇸', SE: '🇸🇪',
  CH: '🇨🇭',
}
function flagOf(cc) { return flagMap[cc] || '🌐' }

// W48c: 后端 checklist.materials[].name 里后端已经拼好了全局序号 ("1. xxx", "2. yyy")。
// 现在改成按分类从 1 重排,所以把后端写在 name 前面的 "N. " / "N、" / "N " 前缀剔掉,
// 再由模板的 j+1 / padStart 渲染分类内编号。
function stripLeadingNumber(name) {
  if (typeof name !== 'string') return String(name ?? '')
  return name.replace(/^\s*\d+\s*[.、)）]\s*/, '').trim()
}

// W59: RAG 解析出的材料名把规格/说明也塞进了 name (例
// "白底彩色证件照 1 张（51mm×51mm，6 个月内近照）")。展示时把末尾的
// 括号补充说明拆成下方小字 note,主标题只留材料本体,读起来更清爽。
// 仅剥「末尾一段」括号,句中的正常括号不动。
function splitNameNote(name) {
  const base = stripLeadingNumber(name)
  const m = base.match(/^(.+?)\s*[（(]([^（）()]+)[)）]\s*$/)
  if (m && m[1].trim().length >= 2) {
    return { name: m[1].trim(), note: m[2].trim() }
  }
  return { name: base, note: '' }
}
function matName(m) { return splitNameNote(m?.name).name }
function matNote(m) {
  // 后端 note 优先;没有则用从 name 里拆出来的括号说明。
  return (m?.note && String(m.note).trim()) || splitNameNote(m?.name).note
}

// W59: 部分 meta 值把字段标签也带进了正文 (中文 "审理时间：根据…",
// 英文 "Validity: B-1/B-2 …")。label 已经在左侧展示,这里剥掉正文开头
// 重复的「标签：」前缀,避免同一个词出现两次。
function cleanMeta(val) {
  if (typeof val !== 'string') return String(val ?? '')
  // 开头 ≤20 字符、无句末标点、后接全/半角冒号 → 视为重复标签,剥掉。
  return val.replace(/^\s*[^：:。.\n]{1,20}[：:]\s*/, '').trim() || val.trim()
}

// W59: RAG 抽出的 fee/processing/validity 常是整段话,而用户只想一眼看到
// 核心数值 (185 美元 / 5-15 个工作日 / 6 个月以上)。按 meta 类型抽出关键
// 数字+单位作为加粗大字,完整原句降级成下方小字。抽不到就返回空串,模板
// 回退到显示完整原句。多语言单位都覆盖 (zh/en/vi/id)。
const _META_HIGHLIGHT = {
  fee: [
    /(?:USD|EUR|GBP|AUD|RMB|CNY|IDR|VND|Rp|¥|\$|€|£)\s?\d[\d,]*(?:\.\d+)?/i,
    /\d[\d,]*(?:\.\d+)?\s*(?:美元|元|欧元|英镑|澳元|人民币|越南盾|盾|卢比|rupiah|đồng|USD|EUR|GBP|AUD)/i,
  ],
  processing: [
    /\d+\s*[-–~至到]\s*\d+\s*(?:个)?\s*(?:工作日|工作天|个工作日|工作周|周|天|日|business\s*days?|working\s*days?|weeks?|days?|hari\s*kerja|hari|ngày\s*làm\s*việc|ngày|tuần)/i,
    /\d+\s*(?:个)?\s*(?:工作日|工作天|个工作日|工作周|周|天|日|business\s*days?|working\s*days?|weeks?|days?|hari\s*kerja|hari|ngày\s*làm\s*việc|ngày|tuần)/i,
  ],
  validity: [
    // English often uses adjectival durations: "10-year multiple-entry visa"
    // or "2-year, 5-year and 10-year options". Capture the concise duration
    // as the dark emphasis and leave the policy sentence as muted detail.
    /(?:\d+\s*[-–]\s*(?:years?|months?|days?))(?:\s*,\s*\d+\s*[-–]\s*(?:years?|months?|days?))*(?:\s+(?:and|or)\s+\d+\s*[-–]\s*(?:years?|months?|days?))?(?:\s+multiple[-\s]entry\s+visa)?/i,
    /\d+\s*(?:个)?\s*(?:月|年|天|日|months?|years?|days?|tháng|năm|bulan|tahun)\s*(?:以上|以内|or\s*more|trở\s*lên)?/i,
  ],
}
function metaHighlight(val, type) {
  const s = cleanMeta(val)
  if (!s) return ''
  for (const re of (_META_HIGHLIGHT[type] || [])) {
    const m = s.match(re)
    if (m) return m[0].replace(/\s+/g, ' ').trim()
  }
  // Some official wording has no fixed number ("decided by the department",
  // "within a few weeks"). Keep the same two-level visual hierarchy in every
  // locale: a concise dark summary plus the original policy in muted text.
  return t('apply.meta_official_assessment')
}

const selectedCountryName = computed(() => {
  const c = countries.value.find(x => x.country_code === form.country_code)
  return c?.country_name || form.country_code
})

// 按签证体系分组 (W27): 国别签证 / 申根签证
// W37: 过滤掉 enabled=false 的国家 — 申根 26 国里大部分是 disabled
// (产品当前只在做 DE/FR 两个代表国), 之前没过滤 → /apply 页会显示一堆灰色国家.
const groupedCountries = computed(() => {
  const visible = countries.value.filter((c) => c.enabled !== false)
  const g = groupCountriesByVisaType(visible)
  return { national: g.national, schengen: g.schengen }
})

// W60: RAG 会把「重要：xxx」这类建议/说明也解析成材料条目 (例
// "重要：美国 B1/B2 签证申请不需要邀请函…")。它不是要提交的材料,却被归到
// 某个分类里还挂了「必交」,很容易误解。这里按开头前缀识别出「提示型」条目,
// 从材料清单里剔除,单独归到页面下方的「提示」区。
const _NOTE_PREFIX = /^\s*(重要|注意|提示|温馨提示|特别提醒|须知|说明|备注|tips?|note|important|please\s*note|catatan|penting|lưu\s*ý|quan\s*trọng)\s*[:：、\.\-]/i
function isNoteItem(m) {
  return _NOTE_PREFIX.test(stripLeadingNumber(m?.name || ''))
}
// 提示区展示时把开头的「重要：」前缀去掉,正文更干净。
function stripNotePrefix(name) {
  return stripLeadingNumber(name || '').replace(_NOTE_PREFIX, '').trim()
}

const materialItems = computed(() =>
  (checklist.value?.materials || []).filter(m => !isNoteItem(m))
)
const materialNotes = computed(() =>
  (checklist.value?.materials || []).filter(isNoteItem)
)

const groupedMaterials = computed(() => {
  const buckets = {}
  for (const m of materialItems.value) {
    const cat = m.category || 'base'
    if (!buckets[cat]) buckets[cat] = []
    buckets[cat].push(m)
  }
  return CATEGORY_ORDER
    .filter(k => buckets[k])
    .map(k => ({ key: k, items: buckets[k] }))
})

const totalMaterialsCount = computed(() => materialItems.value.length)

function selectCountry(cc) {
  form.country_code = cc
  step.value = 2
  setEntrySource('apply')
  track(Events.COUNTRY_SELECTED, { country_code: cc, entry_source: 'apply' })
  loadChecklist()
}

// W47c: 切换语言后重新拉 checklist, 否则 fee/processing/validity 还显示
// 旧语言的内容(i18n 文案会自动切,但 checklist 是后端按 lang 返回的 chunk,
// 必须重新请求才能拿到新语言版本)。
watch(locale, () => {
  if (step.value === 2 && form.country_code) loadChecklist()
})

// W58: 切换语言后重新拉国家列表, 否则 step 1 / step 2 标题里国家名还是
// 旧语言的硬编码 ("美国" / "英国" 等),在 ID/VI/EN 下显示错乱
// 跟 W57 (Diagnose.vue) 同模式。
watch(locale, () => {
  loadCountries()
})

async function loadChecklist() {
  loading.value = true
  error.value = ''
  checklist.value = null
  try {
    // Map Vue i18n locale → backend language bucket.
    //   en     → 'en'
    //   id-ID  → 'id'
    //   vi-VN  → 'vi'
    //   zh-CN / anything else → 'zh-CN'
    const rawLocale = (locale.value || 'zh-CN').toString().toLowerCase()
    let lang = 'zh-CN'
    if (rawLocale.startsWith('en')) lang = 'en'
    else if (rawLocale.startsWith('id')) lang = 'id'
    else if (rawLocale.startsWith('vi')) lang = 'vi'
    const env = await http.get('/v2/rag/checklist', { params: { country_code: form.country_code, lang } })
    if (env.code !== '1000') throw new Error(env.message || 'checklist failed')
    checklist.value = env.data
  } catch (e) {
    error.value = e?.message || t('apply.err_network')
  } finally {
    loading.value = false
  }
}

function formatChecklistTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = Date.now()
    const diffSec = Math.floor((now - d.getTime()) / 1000)
    if (diffSec < 60) return t('apply.time_just_now')
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} ${t('apply.time_min_ago')}`
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} ${t('apply.time_hour_ago')}`
    if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)} ${t('apply.time_day_ago')}`
    return d.toLocaleDateString()
  } catch { return iso }
}

function goOrderNew() {
  if (!form.country_code) return
  // W36: 先进材料收集向导（分大类强校验），完成后向导会带着 material_ids 跳 OrderNew
  setEntrySource('apply')
  track(Events.WIZARD_STARTED, { country_code: form.country_code, entry_source: 'apply' })
  router.push({
    name: 'MaterialWizard',
    query: { country: form.country_code, visa_type: 'tourism' },
  })
}

async function loadCountries() {
  try {
    countries.value = await listDestinations({ lang: locale.value })
  } catch (e) {
    countries.value = []
  }
}

onMounted(loadCountries)
</script>

<style scoped lang="scss">
.apply-page { min-height: 100vh; background: #ffffff; display: flex; flex-direction: column; }
.apply-main {
  flex: 1; max-width: 1200px; width: 100%;
  margin: 0 auto; padding: 32px 24px 80px;
}
.apply-section {
  background: #fff; border: 1px solid #e9edf5; border-radius: 20px;
  padding: 32px 34px; margin-bottom: 18px;
  box-shadow: 0 8px 28px rgba(15, 23, 42, .06);
}
.apply-section__head { margin-bottom: 22px; }
.apply-section__title {
  font-size: 21px; font-weight: 800; color: #0f172a; margin: 0;
  letter-spacing: -.3px;
}
.apply-section__sub {
  font-size: 13px; color: #64748b; margin: 6px 0 0;
}
.apply-section__sep { color: #cbd5e1; font-weight: 500; }
.apply-section__flag { font-size: 20px; line-height: 1; margin-right: 2px; }
.apply-back {
  background: transparent; border: 0; color: #64748b; font-size: 13px;
  padding: 0 0 14px; cursor: pointer; font-weight: 500;
  &:hover { color: #3b6ef5; }
}
.apply-loading {
  text-align: center; padding: 60px 0; color: #64748b; font-size: 14px;
}
.apply-spinner {
  display: inline-block; width: 24px; height: 24px;
  border: 3px solid #e2e8f0; border-top-color: #3b6ef5;
  border-radius: 50%; animation: spin .8s linear infinite;
  margin-right: 8px; vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }
.apply-countries {
  display: flex; flex-direction: column; gap: 22px;
}
.apply-country-group {
  display: flex; flex-direction: column; gap: 12px;
  &__title {
    font-size: 13px; font-weight: 700; color: #475569;
    margin: 0; letter-spacing: .3px; text-transform: uppercase;
    display: flex; align-items: center; gap: 8px;
  }
  &__count {
    font-size: 11px; color: #94a3b8; font-weight: 600;
    background: #f1f5f9; padding: 2px 8px; border-radius: 999px;
  }
  &__grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px;
  }
}
.apply-country {
  position: relative;
  display: flex; align-items: center; gap: 10px;
  background: #FFFFFF; border: 1.5px solid #e9edf5; border-radius: 14px;
  padding: 15px 16px; cursor: pointer;
  transition: transform .18s cubic-bezier(.2,.8,.2,1), box-shadow .18s ease, border-color .18s ease, background .18s ease;
  font-size: 14px; color: #0f172a;
  &:hover { border-color: #93b4fb; background: #FFFFFF; transform: translateY(-2px); box-shadow: 0 10px 22px rgba(59,110,245,.12); }
  &.is-selected {
    background: #FFFFFF;
    border-color: #3b6ef5;
    box-shadow: 0 8px 20px rgba(59,110,245,.16);
  }
  &__flag { font-size: 23px; }
  &__name { font-weight: 600; }
  &__badge {
    position: absolute; top: -7px; right: -7px;
    width: 18px; height: 18px; border-radius: 50%;
    background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
    color: #fff; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 6px rgba(59,110,245,.4);
  }
}
.apply-meta {
  display: flex; padding: 16px 0; margin-bottom: 24px;
  border-top: 1px solid #eef1f6; border-bottom: 1px solid #eef1f6;
  &__cell {
    flex: 1; padding-left: 20px;
    &:first-child { padding-left: 0; }
    & + & { border-left: 1px solid #eef1f6; }
  }
  &__label { font-size: 12px; color: #94a3b8; margin-bottom: 3px; }
  &__val { font-size: 16px; color: #0f172a; line-height: 1.35; font-weight: 700; }
  &__detail { font-size: 12px; color: #94a3b8; line-height: 1.5; margin-top: 4px; }
}
.apply-materials { display: flex; flex-direction: column; gap: 26px; margin-bottom: 20px; }
.apply-material-group {
  &__title {
    font-size: 13px; font-weight: 700; color: #334155; letter-spacing: .2px;
    margin: 0 0 14px;
  }
  &__count { color: #94a3b8; font-weight: 500; }
}
.apply-material-list {
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 14px;
}
.apply-material {
  display: flex; align-items: flex-start; gap: 12px;
  &__num {
    flex-shrink: 0;
    width: 26px; height: 26px;
    border-radius: 50%;
    background: #0f172a;
    color: #fff;
    font-size: 12px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    font-variant-numeric: tabular-nums;
  }
  &__body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  &__name { font-size: 14px; color: #0f172a; line-height: 1.5; font-weight: 700; }
  &__note { font-size: 12px; color: #94a3b8; line-height: 1.5; margin-top: 2px; }
  &__optional {
    flex-shrink: 0;
    font-size: 11px; font-weight: 600; color: #64748b;
    white-space: nowrap;
    background: #f1f5f9; border-radius: 999px;
    padding: 2px 9px;
    line-height: 1.5;
    align-self: flex-start;
  }
}
.apply-empty {
  text-align: center; padding: 40px 20px; color: #94a3b8; font-size: 13.5px;
}
/* W60: 提示区 — RAG 里的「重要/注意」类说明单独归集,跟材料清单区分开 */
.apply-notes {
  margin-top: 24px;
  background: #f8fafc;
  border: 1px solid #eef1f6;
  border-radius: 14px;
  padding: 16px 18px;
  &__title {
    display: flex; align-items: center; gap: 7px;
    font-size: 13px; font-weight: 700; color: #475569; margin-bottom: 10px;
    svg { color: #94a3b8; }
  }
  &__list {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-direction: column; gap: 8px;
    li {
      position: relative; padding-left: 16px;
      font-size: 13px; color: #475569; line-height: 1.6;
      &::before {
        content: ''; position: absolute; left: 2px; top: 9px;
        width: 4px; height: 4px; border-radius: 50%; background: #cbd5e1;
      }
    }
  }
}
.apply-source {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  a { color: #3b6ef5; margin-left: 4px; text-decoration: none; }
}
.apply-source__tag {
  background: #EEF2FF;
  color: #4338CA;
  font-weight: 600;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: .02em;
}
.apply-source__name { color: #475569; font-weight: 500; }
.apply-source__time { color: #94a3b8; font-size: 11px; }
.apply-source__link { color: #3B6EF5; font-weight: 500; }
.apply-source__link:hover { text-decoration: underline; }
.apply-source__pill {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 999px;
  letter-spacing: .03em;
  margin-left: 4px;
}
.apply-source__pill--warn {
  background: #FEF3C7;
  color: #B45309;
  animation: apply-pulse 1.8s ease-in-out infinite;
}
@keyframes apply-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .65; }
}
.apply-actions {
  position: relative;
  z-index: 2;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #eef1f6;
}
.apply-cta {
  width: 100%;
  background: #0f172a; color: #fff; border: 0; padding: 15px;
  border-radius: 12px; font-size: 15px; font-weight: 700; cursor: pointer;
  transition: background .15s ease;
  &:hover { background: #1e293b; }
}
.apply-error {
  text-align: center; color: #b91c1c; font-size: 13px;
  padding: 12px; background: #fef2f2; border-radius: 10px; margin-top: 16px;
}
</style>
