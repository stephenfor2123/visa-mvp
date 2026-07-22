<template>
  <div class="resources-curated-page">
    <AppHeader :scope="headerScope" />

    <main class="app-container app-page resources-main">
      <header class="resources-hero">
        <PageHero :title="titleText" :subtitle="introText" flush />

        <div class="resources-curated-tabs" role="tablist">
          <router-link
            v-for="t in tabs"
            :key="t.to"
            :to="t.to"
            class="resources-curated-tabs__btn"
            :class="{ 'is-active': t.section === section }"
            :data-testid="`curated-tab-${t.section}`"
          >
            <span class="resources-curated-tabs__num">{{ t.num }}</span>
            <span>{{ t.label }}</span>
          </router-link>
        </div>

        <div class="resources-curated-countries" role="tablist">
          <button
            v-for="cc in countryList"
            :key="cc.code"
            type="button"
            class="resources-curated-countries__btn"
            :class="{ 'is-active': cc.code === activeCountry }"
            :data-testid="`curated-country-${cc.code}`"
            @click="activeCountry = cc.code"
          >
            <span class="resources-curated-countries__flag">{{ cc.flag }}</span>
            <span>{{ cc.label }}</span>
          </button>
        </div>
      </header>

      <!-- 内容列表 -->
      <section class="resources-section">
      <h2 class="resources-section__title">{{ renderText(countryBlock?.title) || titleText }}</h2>
      <p v-if="countryBlock?.intro" class="resources-section__lead">{{ renderText(countryBlock.intro) }}</p>

        <!-- 顶部免责声明:以下解读为产品团队基于公开资料的补充说明,非移民局官方意见 -->
        <p v-if="items.length" class="resources-curated-disclaimer" data-testid="curated-disclaimer">
          {{ disclaimerText }}
        </p>

        <div class="resources-curated-list" v-if="items.length">
          <!-- 签证百科：材料清单作为首张内容卡片展示，视觉与百科条目一致。 -->
          <article
            v-if="section === 'wiki'"
            class="resources-curated-item resources-wiki-checklist-card"
            data-testid="wiki-materials-checklist"
          >
            <h3 class="resources-curated-item__title">{{ t('apply.checklist') }}</h3>
            <p class="resources-curated-item__desc">
              {{ t('resources.wiki_checklist_intro', '以下材料清单与「开始申请」页同源，来自官方资料整理。') }}
            </p>
            <div v-if="checklistExpanded" class="resources-wiki-checklist-card__body">
              <RagMaterialsChecklist :country-code="checklistApiCountry" />
            </div>
            <div class="resources-curated-item__meta">
              <button
                type="button"
                class="resources-curated-item__link resources-wiki-checklist-card__toggle"
                :aria-expanded="checklistExpanded"
                @click="checklistExpanded = !checklistExpanded"
              >
                {{ checklistExpanded
                  ? t('resources.wiki_checklist_collapse')
                  : t('resources.wiki_checklist_expand') }} {{ checklistExpanded ? '↑' : '↓' }}
              </button>
              <span v-if="verifiedAt" class="resources-curated-item__verified">
                {{ verifiedAtLabel.replace('{date}', verifiedAt) }}
              </span>
            </div>
          </article>

          <article
            v-for="(item, i) in items"
            :key="i"
            class="resources-curated-item"
            :data-testid="`curated-item-${i}`"
          >
            <h3 class="resources-curated-item__title">{{ renderText(item.title) }}</h3>
            <p class="resources-curated-item__desc">{{ renderText(item.desc) }}</p>
            <p v-if="renderText(item.notes)" class="resources-curated-item__notes" :data-testid="`curated-notes-${i}`">
              <span class="resources-curated-item__notes-prefix">{{ notesLabel }}</span>
              <span class="resources-curated-item__notes-body">{{ renderText(item.notes) }}</span>
            </p>
            <div class="resources-curated-item__meta">
              <a
                v-if="item.url"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
                class="resources-curated-item__link"
                :data-testid="`curated-link-${i}`"
              >
                {{ ctaOpenSource }} ↗
              </a>
              <span v-if="verifiedAt" class="resources-curated-item__verified">
                {{ verifiedAtLabel.replace('{date}', verifiedAt) }}
              </span>
            </div>
          </article>
        </div>

        <div v-else class="resources-curated-empty" data-testid="curated-empty">
          <p>{{ emptyCountry }}</p>
          <p class="resources-curated-empty__hint">{{ tryOtherCountry }}</p>
        </div>
      </section>

      <p class="resources-curated-back">
        <router-link to="/resources" class="resources-curated-back__link">
          ← {{ backToResources }}
        </router-link>
      </p>
    </main>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import PageHero from '@/components/PageHero.vue'
import RagMaterialsChecklist from '@/components/RagMaterialsChecklist.vue'
import { resolveChecklistCountry } from '@/utils/ragChecklist'

// Curated payload files — one per locale, kept under @shared/i18n/_curated_payloads/.
// Imported once per build, scoped by file name. Render-time resolution: when the
// user switches language we re-read by locale tag, no LLM call, no DB round-trip.
import curatedZhCN from '@shared/i18n/_curated_payloads/resources_curated.zh-CN.json'
import curatedEn   from '@shared/i18n/_curated_payloads/resources_curated.en.json'
import curatedID   from '@shared/i18n/_curated_payloads/resources_curated.id.json'
import curatedVi   from '@shared/i18n/_curated_payloads/resources_curated.vi.json'

const CURATED_BY_FILE = {
  'zh-CN': curatedZhCN,
  'en':    curatedEn,
  'id-ID': curatedID,
  'vi-VN': curatedVi,
}

const props = defineProps({
  section: { type: String, required: true }  // 'wiki' | 'policy' | 'templates' | 'faq'
})

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const activeCountry = ref('US')
const checklistExpanded = ref(false)

const headerScope = 'resources'

const checklistApiCountry = computed(() => resolveChecklistCountry(activeCountry.value))

// 4 个子页 tab
const tabs = computed(() => [
  { num: 1, section: 'wiki',      to: '/resources/wiki',      label: t('nav.mega.resources_i1') },
  { num: 2, section: 'policy',    to: '/resources/policy',    label: t('nav.mega.resources_i2') },
  { num: 3, section: 'templates', to: '/resources/templates', label: t('nav.mega.resources_i3') },
  { num: 4, section: 'faq',       to: '/resources/faq',       label: t('nav.mega.resources_i4') },
])

// 国家 tab 标签:从 curated payload (按语言分文件) 里读,而不是 t() 主 i18n
// 因为 curated 数据本身已经按 zh-CN / en / id / vi 4 份分文件维护,
// 主 i18n 不应再重复一份
const countryList = computed(() => {
  const c = curatedRoot.value?.country || {}
  return [
    { code: 'US',       flag: '🇺🇸', label: c.us       || 'US' },
    { code: 'GB',       flag: '🇬🇧', label: c.gb       || 'GB' },
    { code: 'AU',       flag: '🇦🇺', label: c.au       || 'AU' },
    { code: 'schengen', flag: '🇪🇺', label: c.schengen || 'Schengen' },
  ]
})

// 资源列表内的元文案(CTA / 核验时间 / 返回链接 / 空态提示)从 curated payload 读
const ctaOpenSource = computed(() => curatedRoot.value?.cta_open_source || '')
const verifiedAtLabel = computed(() => curatedRoot.value?.verified_at_label || '')
const emptyCountry = computed(() => curatedRoot.value?.empty_country || '')
const tryOtherCountry = computed(() => curatedRoot.value?.try_other_country || '')
const backToResources = computed(() => curatedRoot.value?.back_to_resources || '')

// 顶部免责声明 + 「非官方解读」小标签
const disclaimerText = computed(() => curatedRoot.value?.disclaimer || '')
const notesLabel = computed(() => curatedRoot.value?.notes_label || '')

// Curated payload for the active locale (re-resolved when language changes).
// Empty object if the locale file isn't registered — UI gracefully shows
// the empty state with a "TODO" hint.
const curatedRoot = computed(() => {
  const file = CURATED_BY_FILE[locale.value]
  return file || curatedEn  // fallback to en so the page never breaks
})

// 每个 section 的 title / intro
const titleText = computed(() => curatedRoot.value?.[props.section]?.title || t(`resources_curated.${props.section}.title`))
const introText = computed(() => curatedRoot.value?.[props.section]?.intro || t(`resources_curated.${props.section}.intro`))

// 当前国家块:resources_curated.{section}.{country}.{title,intro,items[],_verified_at}
// JSON keys are lowercase ("us" / "gb" / "au" / "schengen"); UI labels & URL are
// mixed case. Normalize via COUNTRY_KEY so we don't get a lookup miss.
const COUNTRY_KEY = { US: 'us', GB: 'gb', AU: 'au', SCHENGEN: 'schengen' }

const countryBlock = computed(() => {
  const sec = curatedRoot.value?.[props.section]
  const key = COUNTRY_KEY[activeCountry.value] || activeCountry.value.toLowerCase()
  return sec?.[key] || null
})

const items = computed(() => Array.isArray(countryBlock.value?.items) ? countryBlock.value.items : [])

function renderText(s) {
  return typeof s === 'string' ? s : ''
}

const verifiedAt = computed(() => {
  return typeof countryBlock.value?._verified_at === 'string'
    ? countryBlock.value._verified_at
    : null
})

onMounted(() => {
  window.scrollTo({ top: 0, behavior: 'instant' })
  const q = String(route.query.country || '').trim()
  if (q) {
    const upper = q.toUpperCase()
    if (upper === 'FR' || upper === 'SCHENGEN' || q.toLowerCase() === 'schengen') {
      activeCountry.value = 'schengen'
    } else if (['US', 'GB', 'AU'].includes(upper)) {
      activeCountry.value = upper
    }
  }
  // debug expose for browser-side introspection during W47d dev — no production impact
  if (typeof window !== 'undefined') {
    window.__curatedDebug = { locale: locale.value, section: props.section, country: activeCountry.value, hasRoot: !!curatedRoot.value, hasSec: !!curatedRoot.value?.[props.section], hasCountry: !!curatedRoot.value?.[props.section]?.[activeCountry.value], secKeys: Object.keys(curatedRoot.value || {}), rootKeys: Object.keys(curatedRoot.value?.[props.section] || {}) }
  }
})

watch(activeCountry, (cc) => {
  checklistExpanded.value = false
  if (props.section === 'wiki') {
    router.replace({ path: route.path, query: { ...route.query, country: cc } })
  }
})
</script>

<style scoped>
/* 子页骨架 — 顶部 tab + 国家切换 + 列表项 */
.resources-curated-page { background: #fff; min-height: 100vh; }
.resources-hero { padding: 0 0 8px; text-align: left; }
.resources-section__lead { color: #6b7280; margin-bottom: 24px; max-width: 720px; }
.resources-section__title { font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 16px; }

.resources-curated-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 24px;
}
.resources-curated-tabs__btn {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  color: #111827;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: border-color .15s, box-shadow .15s, transform .15s;
}
.resources-curated-tabs__btn:hover {
  border-color: #93c5fd;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.resources-curated-tabs__btn.is-active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}
.resources-curated-tabs__num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px;
  background: #111827;
  color: #fff;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.resources-curated-tabs__btn.is-active .resources-curated-tabs__num {
  background: #2563eb;
}

.resources-curated-countries {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
.resources-curated-countries__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  color: #374151;
  font-size: 14px;
  cursor: pointer;
  transition: all .15s;
}
.resources-curated-countries__btn:hover { border-color: #93c5fd; }
.resources-curated-countries__btn.is-active {
  background: #111827;
  color: #fff;
  border-color: #111827;
}
.resources-curated-countries__flag { font-size: 16px; }

.resources-curated-list {
  display: grid; grid-template-columns: 1fr; gap: 12px;
}
.resources-curated-item {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px 24px;
  transition: box-shadow .15s, border-color .15s;
}
.resources-curated-item:hover { box-shadow: 0 2px 12px rgba(0,0,0,.04); border-color: #93c5fd; }
.resources-curated-item__title {
  font-size: 16px; font-weight: 600; color: #111827; margin: 0 0 8px;
}
.resources-curated-item__desc {
  font-size: 14px; color: #4b5563; line-height: 1.6; margin: 0 0 12px;
}
.resources-curated-item__meta {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px;
  border-top: 1px solid #f3f4f6;
  padding-top: 12px;
}

/* 顶部免责声明:灰色小字,告诉用户下面解读非官方 */
.resources-curated-disclaimer {
  font-size: 12px;
  color: #6b7280;
  background: #f9fafb;
  border: 1px solid #f3f4f6;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 16px;
  line-height: 1.5;
}

/* 「— 解读」灰色 inline 注解块:无黄底/无橙边/无💡,
   用前导破折号代替色块,字体 italic + 灰色,跟 desc 视觉区分但不抢戏。
   也适配多语言(英文 "Editor's note" 等较长前缀,inline 排版不换行)。 */
.resources-curated-item__notes {
  font-size: 13px;
  line-height: 1.65;
  color: #6b7280;
  font-style: italic;
  margin: -2px 0 12px;
  /* 不换行换块,而是 inline 跟随文字流 */
  text-indent: 0;
}
.resources-curated-item__notes-prefix {
  color: #6b7280;
  font-weight: 500;
  font-style: normal;
  margin-right: 4px;
  /* 在 prefix 后加破折号"—— "作为视觉锚点,代替原来的色块/图标 */
}
.resources-curated-item__notes-prefix::after {
  content: " —";
  color: #9ca3af;
  font-weight: 400;
  margin: 0 2px 0 2px;
}
.resources-curated-item__notes-body {
  color: #6b7280;
}
.resources-curated-item__link {
  color: #2563eb; text-decoration: none; font-weight: 500;
}
.resources-curated-item__link:hover { text-decoration: underline; }
.resources-curated-item__verified { color: #9ca3af; }

.resources-curated-empty {
  background: #fff; border: 1px dashed #e5e7eb; border-radius: 12px;
  padding: 48px; text-align: center; color: #6b7280;
}
.resources-curated-empty__hint { font-size: 13px; margin-top: 8px; color: #9ca3af; }

.resources-curated-back { margin-top: 32px; text-align: center; }
.resources-curated-back__link {
  color: #6b7280; text-decoration: none; font-size: 14px;
}
.resources-curated-back__link:hover { color: #2563eb; }

.resources-wiki-checklist-card :deep(.rag-checklist) {
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
}
.resources-wiki-checklist-card__body {
  margin: 4px 0 16px;
}
.resources-wiki-checklist-card__toggle {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font: inherit;
}
.resources-wiki-checklist-card :deep(.rag-checklist__head),
.resources-wiki-checklist-card :deep(.rag-checklist__group-title) {
  display: none;
}
.resources-wiki-checklist-card :deep(.rag-checklist__group),
.resources-wiki-checklist-card :deep(.rag-checklist__notes) {
  margin-top: 8px;
}
.resources-wiki-checklist-card :deep(.rag-checklist__list) {
  gap: 6px;
}
.resources-wiki-checklist-card :deep(.rag-checklist__item) {
  min-height: 38px;
  padding: 8px 12px;
}

@media (max-width: 768px) {
  .resources-curated-tabs { grid-template-columns: repeat(2, 1fr); }
}
</style>
