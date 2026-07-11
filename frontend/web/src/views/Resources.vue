<template>
  <div class="resources-page">
    <AppHeader scope="resources" />

    <main class="app-container app-page resources-main">
      <header class="resources-hero">
        <h1 class="resources-hero__title">{{ t('resources.title') }}</h1>
        <p class="resources-hero__sub">{{ t('resources.sub') }}</p>
        <div class="resources-search">
          <svg class="resources-search__icon" width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/>
            <path d="M20 20 L16.5 16.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <input
            v-model="q"
            type="text"
            class="resources-search__input"
            :placeholder="t('resources.search_ph')"
            :aria-label="t('resources.search_ph')"
            data-testid="resources-search-input"
            @keydown.enter="onAsk"
          />
          <select v-model="country" class="resources-search__country" data-testid="resources-country">
            <option value="">{{ t('resources.all_countries') }}</option>
            <option v-for="c in countries" :key="c.country_code" :value="c.country_code">{{ c.country_name }}</option>
          </select>
          <button
            type="button"
            class="resources-search__btn"
            :disabled="!q.trim() || loading"
            data-testid="resources-ask-btn"
            @click="onAsk"
          >
            {{ loading ? t('resources.searching') : t('resources.ask') }}
          </button>
        </div>
      </header>

      <!-- W47d: 4 张子页入口卡片(签证百科/政策查询/材料模板/常见问答) -->
      <section class="resources-section resources-curated-entry">
        <div class="resources-curated-entry__grid">
          <router-link
            v-for="card in curatedEntries"
            :key="card.to"
            :to="card.to"
            class="resources-curated-entry__card"
            :data-testid="`resources-curated-${card.section}`"
          >
            <span class="resources-curated-entry__num">{{ card.num }}</span>
            <div class="resources-curated-entry__body">
              <div class="resources-curated-entry__title">{{ t(card.titleKey) }}</div>
              <div class="resources-curated-entry__desc">{{ t(card.descKey) }}</div>
            </div>
          </router-link>
        </div>
      </section>

      <!-- Curated 热门问题卡片 -->
      <section class="resources-section">
        <h2 class="resources-section__title">{{ t('resources.popular') }}</h2>
        <div class="resources-popular">
          <button
            v-for="(item, i) in popular"
            :key="i"
            class="resources-popular__card"
            :data-testid="`resources-popular-${i}`"
            @click="askPreset(item.q, item.cc)"
          >
            <span class="resources-popular__flag" :data-cc="item.cc">{{ flagOf(item.cc) }}</span>
            <div>
              <div class="resources-popular__q">{{ item.q }}</div>
              <div class="resources-popular__meta">{{ item.tag }}</div>
            </div>
          </button>
        </div>
      </section>

      <!-- 答案区 -->
      <section v-if="answer" class="resources-section resources-answer" data-testid="resources-answer">
        <h2 class="resources-section__title">{{ t('resources.answer') }}</h2>
        <div class="resources-answer__body">
          <div v-for="(line, i) in answerLines" :key="i" class="resources-answer__line" v-html="line" />
        </div>
        <details v-if="chunks.length" class="resources-answer__sources">
          <summary>{{ t('resources.sources') }} ({{ chunks.length }})</summary>
          <div v-for="c in chunks" :key="c.chunk_id" class="resources-answer__source">
            <span class="resources-answer__source-name">{{ c.source_name }}</span>
            <span class="resources-answer__source-score">score {{ c.score }}</span>
            <div class="resources-answer__source-snippet">{{ c.snippet }}</div>
          </div>
        </details>
      </section>

      <div v-if="error" class="resources-error" data-testid="resources-error">
        {{ error }}
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import { listDestinations } from '@/api/destinations'
import http from '@/api/http'

const { t, tm, locale } = useI18n()
const q = ref('')
const country = ref('')
const loading = ref(false)
const answer = ref('')
const chunks = ref([])
const error = ref('')
const countries = ref([])

const flagMap = {
  US: '🇺🇸', JP: '🇯🇵', KR: '🇰🇷', SG: '🇸🇬', GB: '🇬🇧', FR: '🇫🇷',
  ID: '🇮🇩', VN: '🇻🇳', TH: '🇹🇭', DE: '🇩🇪', AU: '🇦🇺', CA: '🇨🇦',
  NZ: '🇳🇿', SCHENGEN: '🇪🇺', EU: '🇪🇺',
}
function flagOf(cc) { return flagMap[cc] || '🌐' }

// 4 个产品线:欧洲(GB) / 申根(FR 代理) / 美国(US) / 澳洲(AU)
// 文案从 i18n 读,跟着 locale 切换 (4 国语言)
// 用 tm() 拿原始 message 数组 (t() 会做 message format 编译,数组会被强制转字符串)
const popular = computed(() => tm('resources.popular_questions') || [])

// W47d: 4 张子页入口 — wiki / policy / templates / faq
const curatedEntries = [
  { num: 1, section: 'wiki',      to: '/resources/wiki',      titleKey: 'nav.mega.resources_i1', descKey: 'nav.mega.resources_i1_d' },
  { num: 2, section: 'policy',    to: '/resources/policy',    titleKey: 'nav.mega.resources_i2', descKey: 'nav.mega.resources_i2_d' },
  { num: 3, section: 'templates', to: '/resources/templates', titleKey: 'nav.mega.resources_i3', descKey: 'nav.mega.resources_i3_d' },
  { num: 4, section: 'faq',       to: '/resources/faq',       titleKey: 'nav.mega.resources_i4', descKey: 'nav.mega.resources_i4_d' },
]

// 把 country_code 映射为产品线标签 (前端展示用)
const REGION_LABEL = {
  GB: '欧洲',
  FR: '申根',
  US: '美国',
  AU: '澳洲',
}

const answerLines = computed(() => {
  if (!answer.value) return []
  // 把 "(来源/Sumber/Nguồn/Source：xxx)" 包到独立 span,加 muted 样式
  // 同时把后端 RAG 答案里 matched keywords 的 **markdown** 解析成 <strong>
  return answer.value.split('\n').filter(Boolean).map((line) => {
    const escaped = line
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return escaped
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(
        /\((来源|Sumber|Nguồn|Source)[::\s]+([^)]+)\)/g,
        '<span class="resources-answer__cite">（来源：$2）</span>'
      )
  })
})

async function loadCountries() {
  try {
    const all = await listDestinations({ lang: locale.value })
    // W31: 只显示 4 个产品线,FR 重命名为"申根 (法国)"
    const REGION_CODES = ['GB', 'FR', 'US', 'AU']
    const filtered = all
      .filter((c) => REGION_CODES.includes(c.country_code))
      .map((c) =>
        c.country_code === 'FR'
          ? { ...c, country_name: '申根 (以法国为例 · 26 国)' }
          : c
      )
    countries.value = filtered
  } catch (e) {
    console.warn('[resources] load countries failed', e)
    countries.value = []
  }
}

async function onAsk() {
  const query = q.value.trim()
  if (!query) return
  await ask(query, country.value)
}

async function askPreset(query, cc) {
  country.value = cc
  q.value = query
  await ask(query, cc)
}

async function ask(query, cc) {
  loading.value = true
  error.value = ''
  answer.value = ''
  chunks.value = []
  try {
    const env = await http.post('/v2/rag/query', {
      query,
      country_code: cc || null,
      user_lang: locale.value,
      top_k: 3,
    })
    if (env.code !== '1000') throw new Error(env.message || 'query failed')
    answer.value = env.data?.answer || t('resources.no_answer')
    chunks.value = env.data?.chunks || []
  } catch (e) {
    error.value = e?.message || t('resources.err_network')
  } finally {
    loading.value = false
  }
}

onMounted(loadCountries)
// W48 fix: 用户在主页切语言后再进 /resources,countries.value 还是旧 locale 翻译
watch(locale, () => { loadCountries() })
</script>

<style scoped lang="scss">
.resources-page {
  min-height: 100vh;
  background: #fff;
  display: flex;
  flex-direction: column;
}

/* W47d: 4 张子页入口卡片(签证百科/政策查询/材料模板/常见问答) */
.resources-curated-entry {
  border-top: 1px solid #f3f4f6;
  padding-top: 24px;
  margin-top: 16px;
}
.resources-curated-entry__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.resources-curated-entry__card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 20px 18px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  text-decoration: none;
  color: inherit;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, .06);
    border-color: #93c5fd;
  }
}
.resources-curated-entry__num {
  flex: 0 0 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #111827;
  color: #fff;
  border-radius: 999px;
  font-weight: 700;
  font-size: 13px;
  margin-top: 2px;
}
.resources-curated-entry__body { flex: 1; min-width: 0; }
.resources-curated-entry__title { font-size: 16px; font-weight: 600; color: #111827; margin: 0 0 4px; }
.resources-curated-entry__desc  { font-size: 13px; color: #6b7280; line-height: 1.5; margin: 0; }
@media (max-width: 768px) {
  .resources-curated-entry__grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .resources-curated-entry__grid { grid-template-columns: 1fr; }
}
.resources-main {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px 80px;
}
.resources-hero {
  text-align: center;
  margin-bottom: 36px;
  &__title {
    font-size: 32px;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 8px;
    letter-spacing: -.5px;
  }
  &__sub {
    font-size: 15px;
    color: #64748b;
    margin: 0 0 24px;
  }
}
.resources-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 6px 8px 6px 14px;
  box-shadow: 0 4px 12px -2px rgba(15, 23, 42, .04);
  &__icon { color: #94a3b8; flex-shrink: 0; }
  &__input {
    flex: 1;
    border: 0;
    outline: none;
    font-size: 15px;
    padding: 10px 0;
    color: #0f172a;
    background: transparent;
    min-width: 0;
  }
  &__country {
    border: 0;
    background: #f1f5f9;
    color: #475569;
    font-size: 13px;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    outline: none;
  }
  &__btn {
    background: #3b6ef5;
    color: #fff;
    border: 0;
    padding: 10px 18px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background .15s ease;
    &:hover { background: #2553d6; }
    &:disabled { background: #cbd5e1; cursor: not-allowed; }
  }
}
.resources-section {
  margin-bottom: 32px;
  &__title {
    font-size: 18px;
    font-weight: 600;
    color: #0f172a;
    margin: 0 0 14px;
  }
}
.resources-popular {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  @media (max-width: 640px) {
    grid-template-columns: 1fr;
  }
  &__card {
    display: flex;
    align-items: center;
    gap: 12px;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 16px;
    text-align: left;
    cursor: pointer;
    transition: border-color .15s ease, transform .15s ease;
    &:hover { border-color: #3b6ef5; transform: translateY(-1px); }
  }
  &__flag { font-size: 22px; line-height: 1; }
  &__q {
    font-size: 14px;
    font-weight: 500;
    color: #0f172a;
    margin-bottom: 2px;
  }
  &__meta {
    font-size: 11.5px;
    color: #94a3b8;
  }
}
.resources-answer {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 20px 24px;
  &__body {
    font-size: 14.5px;
    line-height: 1.7;
    color: #1e293b;
    white-space: pre-wrap;
  }
  &__line { margin-bottom: 6px; }
  :deep(&__cite) { color: #64748b; font-size: 12.5px; margin-left: 4px; }
  &__sources {
    margin-top: 16px;
    border-top: 1px solid #f1f5f9;
    padding-top: 12px;
    summary {
      cursor: pointer;
      font-size: 13px;
      color: #3b6ef5;
      font-weight: 500;
    }
  }
  &__source {
    margin-top: 10px;
    padding: 10px 12px;
    background: #f8fafc;
    border-radius: 8px;
    &-name { font-size: 12px; font-weight: 600; color: #475569; margin-right: 8px; }
    &-score { font-size: 11px; color: #94a3b8; }
    &-snippet {
      font-size: 12px;
      color: #64748b;
      margin-top: 4px;
      line-height: 1.5;
    }
  }
}
.resources-error {
  text-align: center;
  color: #b91c1c;
  font-size: 13px;
  padding: 12px;
  background: #fef2f2;
  border-radius: 10px;
  margin-top: 16px;
}
</style>
