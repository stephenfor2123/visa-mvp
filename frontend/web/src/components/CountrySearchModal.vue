<!-- CountrySearchModal.vue — W28 P2 全屏国家搜索弹窗
     借鉴 atlys: 头部搜索 icon → 全屏 modal → 国家网格 + 搜索框 + 国旗预览
     支持中英文 / 国家代码搜索,选中后跳 /orders/new?country=XX -->
<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="cs-modal"
      role="dialog"
      aria-modal="true"
      :data-testid="`country-search-modal`"
      @click.self="close"
      @keydown.esc="close"
    >
      <div class="cs-modal__panel" @click.stop>
        <!-- 顶部搜索栏 -->
        <div class="cs-modal__head">
          <div class="cs-modal__search">
            <svg class="cs-modal__search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/>
              <path d="M20 20 L16.5 16.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              class="cs-modal__search-input"
              :placeholder="t('cs.search_placeholder') || 'Search by country name or code…'"
              autocomplete="off"
              spellcheck="false"
              :data-testid="`cs-search-input`"
              @input="onQueryChange"
            />
            <button
              v-if="query"
              class="cs-modal__clear"
              :aria-label="t('cs.clear') || 'Clear'"
              @click="clearQuery"
            >✕</button>
          </div>
          <button class="cs-modal__close" :aria-label="t('common.close') || 'Close'" @click="close">✕</button>
        </div>

        <!-- 分类标签(US / AU / GB / SCHENGEN) -->
        <div class="cs-modal__tabs">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="cs-modal__tab"
            :class="{ 'is-active': activeTab === tab.key }"
            :data-testid="`cs-tab-${tab.key}`"
            @click="activeTab = tab.key"
          >
            <span class="cs-modal__tab-flag">{{ tab.flag }}</span>
            <span>{{ tab.label }}</span>
          </button>
        </div>

        <!-- 列表主体 -->
        <div class="cs-modal__body">
          <div v-if="loading" class="cs-modal__loading">
            <div class="cs-modal__spinner"></div>
          </div>
          <div v-else-if="!filtered.length" class="cs-modal__empty">
            <p>{{ t('cs.no_results') || 'No countries found.' }}</p>
          </div>
          <div v-else class="cs-modal__grid">
            <button
              v-for="c in filtered"
              :key="c.country_code"
              class="cs-card"
              :class="{ 'is-disabled': !c.enabled }"
              :disabled="!c.enabled"
              :data-testid="`cs-card-${c.country_code}`"
              @click="onPick(c)"
            >
              <span class="cs-card__flag">{{ flagEmoji(c.country_code) }}</span>
              <span class="cs-card__name">{{ c.country_name }}</span>
              <span class="cs-card__code">{{ c.country_code }}</span>
              <span v-if="!c.enabled" class="cs-card__soon">{{ t('cs.coming_soon') || 'Coming soon' }}</span>
              <span v-else class="cs-card__arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import http from '@/api/http'

const { locale } = useI18n()
async function fetchDestinationsDirect() {
  // search modal 需要 i18n 后的国家名; listDestinations wrapper 默认 MOCK_MODE
  // 返回的是 fallback (含 country_name),但我们要的是 API 的真数据;
  // 直接调 http 拿真实列表(支持 lang 参数)
  const lang = (locale.value || 'zh-CN').startsWith('en') ? 'en'
            : (locale.value || 'zh-CN').startsWith('id') ? 'id'
            : (locale.value || 'zh-CN').startsWith('vi') ? 'vi'
            : 'zh-CN'
  const env = await http.get('/v2/destinations', { params: { lang }, __silent: true })
  if (env.code !== '1000') throw new Error(env.message || 'destinations fetch failed')
  return env.data || []
}

const props = defineProps({
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const { t } = useI18n()
const router = useRouter()

const inputRef = ref(null)
const query = ref('')
const activeTab = ref('all')
const allCountries = ref([])
const loading = ref(false)

const tabs = computed(() => [
  { key: 'all',     flag: '🌐', label: t('cs.tab_all')     || 'All' },
  { key: 'US',      flag: '🇺🇸', label: 'US' },
  { key: 'AU',      flag: '🇦🇺', label: 'AU' },
  { key: 'GB',      flag: '🇬🇧', label: 'GB' },
  { key: 'SCHENGEN',flag: '🇪🇺', label: t('cs.tab_schengen') || 'Schengen' },
])

const filtered = computed(() => {
  let rows = allCountries.value
  if (activeTab.value !== 'all' && activeTab.value !== 'SCHENGEN') {
    rows = rows.filter(c => c.country_code === activeTab.value)
  }
  if (activeTab.value === 'SCHENGEN') {
    rows = rows.filter(c => SCHENGEN_CODES.has(c.country_code))
  }
  const q = query.value.trim().toLowerCase()
  if (q) {
    rows = rows.filter(c =>
      c.country_name.toLowerCase().includes(q) ||
      c.country_code.toLowerCase().includes(q)
    )
  }
  return rows
})

const SCHENGEN_CODES = new Set([
  'AT','BE','HR','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IT','LV',
  'LI','LT','LU','MT','NL','NO','PL','PT','SK','SI','ES','SE'
])

async function loadCountries() {
  loading.value = true
  try {
    allCountries.value = await fetchDestinationsDirect()
  } catch (_) {
    allCountries.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.open, async (val) => {
  if (val) {
    query.value = ''
    activeTab.value = 'all'
    await loadCountries()
    await nextTick()
    inputRef.value?.focus()
    document.addEventListener('keydown', onEsc)
  } else {
    document.removeEventListener('keydown', onEsc)
  }
})

function onEsc(e) {
  if (e.key === 'Escape') close()
}

function close() {
  emit('close')
}
function clearQuery() { query.value = '' }
function onQueryChange() { /* reactive via computed */ }

function flagEmoji(code) {
  if (!code || code === 'SCHENGEN') return '🇪🇺'
  // convert 2-letter ISO to regional indicators
  return code.toUpperCase().split('').map(ch => String.fromCodePoint(0x1F1E6 + ch.charCodeAt(0) - 65)).join('')
}

function onPick(c) {
  if (!c.enabled) return
  close()
  if (c.country_code === 'SCHENGEN' || SCHENGEN_CODES.has(c.country_code)) {
    // 申根国 → 跳 SchengenCountries 让用户选具体国
    router.push({ name: 'SchengenCountries' })
  } else {
    router.push({ path: '/orders/new', query: { country: c.country_code, visa_type: 'tourism' } })
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onEsc)
})
</script>

<style scoped lang="scss">
.cs-modal {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(15, 23, 42, .55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 60px 20px 20px;
  animation: csIn .18s ease-out;
}
@keyframes csIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
.cs-modal__panel {
  width: 100%;
  max-width: 880px;
  max-height: calc(100vh - 100px);
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, .25), 0 4px 12px rgba(15, 23, 42, .1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: csPanelIn .25s cubic-bezier(.2,.8,.2,1);
}
@keyframes csPanelIn {
  from { opacity: 0; transform: translateY(-12px) scale(.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.cs-modal__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border, #E2E8F0);
}
.cs-modal__search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  height: 44px;
  background: var(--bg-alt, #F8FAFC);
  border: 1.5px solid transparent;
  border-radius: 12px;
  transition: border-color .15s ease, background .15s ease;
}
.cs-modal__search:focus-within {
  border-color: var(--el-color-primary, #3B6EF5);
  background: #fff;
}
.cs-modal__search-icon { color: var(--ink-3, #64748B); flex-shrink: 0; }
.cs-modal__search-input {
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 15px;
  color: var(--ink-1, #0F172A);
  font-family: inherit;
}
.cs-modal__search-input::placeholder { color: var(--ink-3, #94A3B8); }
.cs-modal__clear {
  border: 0;
  background: transparent;
  color: var(--ink-3, #94A3B8);
  cursor: pointer;
  font-size: 14px;
  padding: 4px 6px;
  border-radius: 6px;
}
.cs-modal__clear:hover { background: rgba(15, 23, 42, .06); color: var(--ink-1, #0F172A); }
.cs-modal__close {
  border: 0;
  background: transparent;
  color: var(--ink-3, #64748B);
  cursor: pointer;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 16px;
  transition: background .15s ease, color .15s ease;
}
.cs-modal__close:hover { background: var(--bg-alt, #F1F5F9); color: var(--ink-1, #0F172A); }

.cs-modal__tabs {
  display: flex;
  gap: 6px;
  padding: 12px 20px 0;
  overflow-x: auto;
}
.cs-modal__tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 0;
  background: transparent;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2, #334155);
  cursor: pointer;
  transition: background .15s ease, color .15s ease;
  white-space: nowrap;
  font-family: inherit;
}
.cs-modal__tab:hover { background: var(--bg-alt, #F1F5F9); }
.cs-modal__tab.is-active {
  background: var(--el-color-primary, #3B6EF5);
  color: #fff;
}
.cs-modal__tab-flag { font-size: 14px; line-height: 1; }

.cs-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 24px;
}
.cs-modal__loading,
.cs-modal__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--ink-3, #64748B);
  font-size: 14px;
}
.cs-modal__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border, #E2E8F0);
  border-top-color: var(--el-color-primary, #3B6EF5);
  border-radius: 50%;
  animation: csSpin .8s linear infinite;
}
@keyframes csSpin { to { transform: rotate(360deg); } }

.cs-modal__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.cs-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  grid-template-rows: auto auto;
  gap: 4px 10px;
  padding: 14px 14px;
  background: #fff;
  border: 1.5px solid var(--border, #E2E8F0);
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: border-color .15s ease, background .15s ease, transform .15s ease;
}
.cs-card:hover:not(:disabled) {
  border-color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .04);
  transform: translateY(-2px);
}
.cs-card:focus-visible {
  outline: 2px solid var(--el-color-primary, #3B6EF5);
  outline-offset: 2px;
}
.cs-card.is-disabled {
  opacity: .55;
  cursor: not-allowed;
  background: var(--bg-alt, #F8FAFC);
}
.cs-card__flag {
  grid-row: 1 / 3;
  font-size: 28px;
  align-self: center;
}
.cs-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-1, #0F172A);
  line-height: 1.2;
}
.cs-card__code {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .8px;
  color: var(--ink-3, #94A3B8);
  font-family: ui-monospace, SFMono-Regular, monospace;
}
.cs-card__arrow {
  grid-row: 1 / 3;
  align-self: center;
  color: var(--el-color-primary, #3B6EF5);
  font-size: 16px;
  font-weight: 600;
}
.cs-card__soon {
  grid-row: 1 / 3;
  align-self: center;
  font-size: 11px;
  color: var(--ink-3, #64748B);
  font-weight: 600;
}

@media (max-width: 600px) {
  .cs-modal { padding: 30px 12px 12px; }
  .cs-modal__panel { max-height: calc(100vh - 50px); }
  .cs-modal__grid { grid-template-columns: 1fr; }
}
</style>