<!--
  Shared RAG materials checklist renderer.
  Used by Resources (hot questions) and ResourcesCuratedView (签证百科).
-->
<template>
  <div class="rag-checklist" data-testid="rag-materials-checklist">
    <div v-if="loading" class="rag-checklist__loading">{{ loadingText }}</div>
    <div v-else-if="error" class="rag-checklist__error">{{ error }}</div>
    <template v-else-if="hasMaterials">
      <header class="rag-checklist__head">
        <h3 class="rag-checklist__title">{{ title }}</h3>
        <p v-if="summary" class="rag-checklist__summary">{{ summary }}</p>
        <div v-if="metaBits.length" class="rag-checklist__meta">
          <span v-for="(bit, i) in metaBits" :key="i" class="rag-checklist__meta-chip">{{ bit }}</span>
        </div>
      </header>

      <div
        v-for="group in grouped"
        :key="group.key"
        class="rag-checklist__group"
      >
        <h4 class="rag-checklist__group-title">{{ categoryLabel(group.key) }}</h4>
        <ul class="rag-checklist__list">
          <li
            v-for="(m, i) in group.items"
            :key="i"
            class="rag-checklist__item"
          >
            <span class="rag-checklist__name">{{ stripLeadingNumber(m.name) }}</span>
            <span v-if="m.required" class="rag-checklist__badge">{{ requiredLabel }}</span>
          </li>
        </ul>
      </div>

      <div v-if="notes.length" class="rag-checklist__notes">
        <h4 class="rag-checklist__group-title">{{ notesTitle }}</h4>
        <ul class="rag-checklist__list rag-checklist__list--notes">
          <li v-for="(m, i) in notes" :key="i" class="rag-checklist__item rag-checklist__item--note">
            {{ stripNotePrefix(m.name) }}
          </li>
        </ul>
      </div>

      <footer v-if="sourceLine" class="rag-checklist__source">
        <template v-if="sourceUrl">
          <a :href="sourceUrl" target="_blank" rel="noopener noreferrer">{{ sourceLine }}</a>
        </template>
        <template v-else>{{ sourceLine }}</template>
      </footer>
    </template>
    <div v-else class="rag-checklist__empty">{{ emptyText }}</div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import { resolveChecklistCountry } from '@/utils/ragChecklist'

const props = defineProps({
  /** ISO country code: US / GB / AU / FR (Schengen proxy) */
  countryCode: { type: String, required: true },
  /** Optional override title; defaults to apply.checklist */
  title: { type: String, default: '' },
})

const emit = defineEmits(['loaded', 'error'])

const { t, locale } = useI18n()

const loading = ref(false)
const error = ref('')
const checklist = ref(null)

const CATEGORY_ORDER = ['identity', 'form', 'financial', 'travel', 'work', 'base']
const _NOTE_PREFIX = /^\s*(重要|注意|提示|温馨提示|特别提醒|须知|说明|备注|tips?|note|important|please\s*note|catatan|penting|lưu\s*ý|quan\s*trọng)\s*[:：、.\-]/i

function stripLeadingNumber(name) {
  return String(name || '').replace(/^\s*\d+[\.、\)\]\s]+/, '').trim()
}
function isNoteItem(m) {
  return _NOTE_PREFIX.test(stripLeadingNumber(m?.name || ''))
}
function stripNotePrefix(name) {
  return stripLeadingNumber(name || '').replace(_NOTE_PREFIX, '').trim()
}

function localeToLang(loc) {
  const raw = (loc || 'zh-CN').toString().toLowerCase()
  if (raw.startsWith('en')) return 'en'
  if (raw.startsWith('id')) return 'id'
  if (raw.startsWith('vi')) return 'vi'
  return 'zh-CN'
}

const title = computed(() => props.title || t('apply.checklist'))
const loadingText = computed(() => t('apply.loading'))
const emptyText = computed(() => t('apply.no_materials'))
const requiredLabel = computed(() => t('apply.required'))
const notesTitle = computed(() => t('apply.notes_title'))

const materialItems = computed(() =>
  (checklist.value?.materials || []).filter((m) => !isNoteItem(m)),
)
const notes = computed(() =>
  (checklist.value?.materials || []).filter((m) => isNoteItem(m)),
)
const hasMaterials = computed(() => materialItems.value.length > 0)

const grouped = computed(() => {
  const buckets = {}
  for (const m of materialItems.value) {
    const cat = m.category || 'base'
    if (!buckets[cat]) buckets[cat] = []
    buckets[cat].push(m)
  }
  return CATEGORY_ORDER
    .filter((k) => buckets[k])
    .map((k) => ({ key: k, items: buckets[k] }))
})

const summary = computed(() => {
  const n = materialItems.value.length
  if (!n) return ''
  return t('apply.summary', { count: n, groups: grouped.value.length })
})

const metaBits = computed(() => {
  const d = checklist.value
  if (!d) return []
  const bits = []
  if (d.fee) bits.push(`${t('apply.fee')}: ${d.fee}`)
  if (d.processing_time) bits.push(`${t('apply.processing')}: ${d.processing_time}`)
  if (d.validity) bits.push(`${t('apply.validity')}: ${d.validity}`)
  return bits
})

const sourceUrl = computed(() => checklist.value?.source_url || '')
const sourceLine = computed(() => {
  const name = checklist.value?.source_name
  if (!name) return ''
  return `${t('apply.source')}: ${name}`
})

function categoryLabel(key) {
  const map = {
    identity: t('apply.cat_identity', '身份证明'),
    form: t('apply.cat_form', '申请表格'),
    financial: t('apply.cat_financial', '经济材料'),
    travel: t('apply.cat_travel', '行程材料'),
    work: t('apply.cat_work', '工作材料'),
    base: t('apply.cat_base', '其他'),
  }
  return map[key] || key
}

async function load() {
  const cc = resolveChecklistCountry(props.countryCode)
  if (!cc) {
    checklist.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    const env = await http.get('/v2/rag/checklist', {
      params: { country_code: cc, lang: localeToLang(locale.value) },
    })
    if (env.code !== '1000') throw new Error(env.message || 'checklist failed')
    checklist.value = env.data
    emit('loaded', env.data)
  } catch (e) {
    error.value = e?.message || t('resources.err_network')
    checklist.value = null
    emit('error', error.value)
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.countryCode, locale.value],
  () => { load() },
  { immediate: true },
)

defineExpose({ reload: load })
</script>

<style scoped lang="scss">
.rag-checklist {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px 22px;
}
.rag-checklist__loading,
.rag-checklist__error,
.rag-checklist__empty {
  font-size: 14px;
  color: #64748b;
  padding: 8px 0;
}
.rag-checklist__error { color: #b91c1c; }
.rag-checklist__head { margin-bottom: 16px; }
.rag-checklist__title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}
.rag-checklist__summary {
  margin: 0 0 10px;
  font-size: 13px;
  color: #64748b;
}
.rag-checklist__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.rag-checklist__meta-chip {
  font-size: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  padding: 4px 10px;
  color: #334155;
}
.rag-checklist__group { margin-top: 14px; }
.rag-checklist__group-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #3b6ef5;
  letter-spacing: 0.02em;
}
.rag-checklist__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rag-checklist__item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  color: #0f172a;
  line-height: 1.45;
}
.rag-checklist__item--note {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}
.rag-checklist__badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  background: #fef3c7;
  border-radius: 4px;
  padding: 2px 6px;
}
.rag-checklist__source {
  margin-top: 16px;
  font-size: 12px;
  color: #64748b;
}
.rag-checklist__source a {
  color: #3b6ef5;
  text-decoration: none;
}
.rag-checklist__source a:hover { text-decoration: underline; }
</style>
