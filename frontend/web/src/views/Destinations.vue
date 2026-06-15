<template>
  <div class="dest-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <span class="app-header__brand-mark">V</span>
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <div class="app-header__right">
        <LangSwitch />
        <span class="app-header__user" v-if="auth.user">👋 {{ auth.user.nickname || auth.user.phone }}</span>
      </div>
    </header>

    <main class="dest-shell">
      <h1 class="page-title">{{ t('dest.title') }}</h1>
      <p class="page-sub">{{ t('dest.subtitle') }}</p>

      <div v-if="loading" class="state-loading">⏳ {{ t('common.loading') }}</div>
      <div v-else-if="error" class="state-error">❌ {{ error }}</div>

      <div v-else class="dest-grid">
        <div
          v-for="d in destinations"
          :key="d.id"
          class="dest-card"
          :class="{ 'is-disabled': !d.enabled }"
          :data-testid="`dest-card-${d.country_code}`"
        >
          <div class="dest-card__flag">{{ flagEmoji(d.country_code) }}</div>
          <div class="dest-card__name">{{ d.country_name }}</div>
          <div class="dest-card__types">
            <span v-for="type in d.visa_types" :key="type" class="tag" :class="`tag--${type}`">
              {{ type === 'tourism' ? t('dest.tourism') : t('dest.student') }}
            </span>
          </div>
          <div v-if="!d.enabled" class="dest-card__lock">🔒 {{ t('dest.coming_soon') }}</div>
          <button
            v-if="d.enabled"
            class="btn primary"
            :data-testid="`dest-apply-${d.country_code}`"
            @click="onApply(d)"
          >{{ t('dest.apply_now') }}</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { listDestinations } from '@/api/destinations'
import LangSwitch from '@/components/LangSwitch.vue'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const destinations = ref([])
const loading = ref(false)
const error = ref('')

function flagEmoji(cc) {
  if (!cc || cc.length !== 2) return '🌐'
  const codePoints = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65))
  return String.fromCodePoint(...codePoints)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await listDestinations({ lang: locale.value || 'zh-CN' })
    console.log('[DEBUG] destinations loaded:', res.length, res.slice(0, 2))
    destinations.value = res
  } catch (e) {
    console.log('[DEBUG] destinations ERROR:', e?.message, e)
    error.value = e?.message || t('common.network_error')
  } finally {
    loading.value = false
  }
}

function onApply(d) {
  // Jump to materials prep page (V3+ impl, here just routing placeholder)
  router.push({ name: 'Materials', query: { country: d.country_code, type: 'tourism' } })
}

onMounted(() => {
  auth.hydrate()
  load()
})
</script>

<style scoped lang="scss">
.dest-page { min-height: 100vh; background: var(--bg, #FAFBFC); }
.dest-shell { max-width: 1200px; margin: 0 auto; padding: 24px; }
.page-title { font-size: 28px; font-weight: 600; margin: 0 0 6px; color: var(--ink, #1A1D29); }
.page-sub { color: var(--ink-2, #5A5F6D); margin: 0 0 24px; }
.state-loading, .state-error { padding: 40px; text-align: center; color: var(--muted, #9CA3AF); font-size: 14px; }
.state-error { color: var(--accent, #DC2626); }
.dest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.dest-card {
  background: var(--surface, #FFF);
  border: 1px solid var(--line, #E5E7EB);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  transition: all 0.15s;
  position: relative;
}
.dest-card:not(.is-disabled):hover {
  border-color: var(--primary, #2D5BFF);
  box-shadow: 0 4px 16px rgba(45, 91, 255, 0.12);
  transform: translateY(-2px);
}
.dest-card.is-disabled { opacity: 0.6; }
.dest-card__flag { font-size: 40px; margin-bottom: 8px; }
.dest-card__name { font-size: 16px; font-weight: 600; color: var(--ink, #1A1D29); margin-bottom: 8px; }
.dest-card__types { display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; margin-bottom: 12px; }
.tag { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; }
.tag--tourism { background: #EAF0FE; color: #2D5BFF; }
.tag--student { background: #FEF3C7; color: #B45309; }
.dest-card__lock { font-size: 12px; color: var(--muted, #9CA3AF); margin-bottom: 8px; }
.btn { padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; }
.btn.primary { background: var(--primary, #2D5BFF); color: #FFF; width: 100%; }
.btn.primary:hover { background: var(--primary-hover, #1E47E0); }
</style>
