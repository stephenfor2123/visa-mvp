<template>
  <div class="dest-page">
    <AppHeader scope="destinations" />
    <main class="dest-shell">
      <h1 class="page-title">{{ t('dest.title') }}</h1>
      <p class="page-sub">{{ t('dest.subtitle') }}</p>

      <div v-if="loading" class="state-loading">⏳ {{ t('common.loading') }}</div>
      <div v-else-if="error" class="state-error">❌ {{ error }}</div>

      <div v-else class="dest-grid">
        <article
          v-for="d in destinations"
          :key="d.id"
          class="dest-card"
          :class="{ 'is-disabled': !d.enabled, 'has-cover': getCover(d.country_code) }"
          :data-testid="`dest-card-${d.country_code}`"
        >
          <!-- Cover image (zigzag bottom edge) -->
          <div class="dest-card__cover">
            <img
              v-if="getCover(d.country_code)"
              :src="getCover(d.country_code)"
              :alt="d.country_name"
              loading="lazy"
              @error="onImgError(d.country_code)"
            />
            <div v-else class="dest-card__cover-fallback">
              <span class="dest-card__flag-big">{{ flagEmoji(d.country_code) }}</span>
            </div>
            <div class="dest-card__cover-overlay" />
            <div class="dest-card__cover-flag">{{ flagEmoji(d.country_code) }}</div>
          </div>

          <!-- Body -->
          <div class="dest-card__body">
            <div class="dest-card__name">{{ d.country_name }}</div>
            <div class="dest-card__types">
              <span v-for="type in d.visa_types" :key="type" class="tag" :class="`tag--${type}`">
                {{ visaTypeLabel(type) }}
              </span>
            </div>
            <div v-if="!d.enabled" class="dest-card__lock">🔒 {{ t('dest.coming_soon') }}</div>
            <button
              v-if="d.enabled"
              class="btn primary"
              :data-testid="`dest-apply-${d.country_code}`"
              @click="onApply(d)"
            >{{ t('dest.apply_now') }} →</button>
          </div>
        </article>
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
import AppHeader from '@/components/AppHeader.vue'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const destinations = ref([])
const loading = ref(false)
const error = ref('')
// Track which countries failed to load cover so we can fall back
const failedCovers = ref(new Set())

// Country cover mapping — serves from /public/countries/*.jpg
// Add new covers here as we acquire them
const COVER_MAP = {
  FR: '/countries/fr_eiffel.jpg',      // Eiffel Tower (Wikimedia Commons)
  // Add more here as needed:
  // US: '/countries/us_liberty.jpg',
  // GB: '/countries/gb_london.jpg',
  // JP: '/countries/jp_fuji.jpg',
}

function getCover(cc) {
  if (failedCovers.value.has(cc)) return null
  return COVER_MAP[cc] || null
}

function onImgError(cc) {
  // mark as failed so vue doesn't keep trying
  const next = new Set(failedCovers.value)
  next.add(cc)
  failedCovers.value = next
}

function flagEmoji(cc) {
  if (!cc || cc.length !== 2) return '🌐'
  const codePoints = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65))
  return String.fromCodePoint(...codePoints)
}

// W45 fix: visa type label maps to its own i18n key; fall back to raw type
// (uppercase) if the locale doesn't ship a translation for an uncommon type.
function visaTypeLabel(type) {
  const key = `dest.${type}`
  const label = t(key)
  // t() returns the raw key when messages aren't loaded or when missing;
  // compare against the dotted form so we don't show "dest.work" as a label.
  if (label && label !== key) return label
  return String(type).toUpperCase()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await listDestinations({ lang: locale.value || 'zh-CN' })
    destinations.value = res
  } catch (e) {
    error.value = e?.message || t('common.network_error')
  } finally {
    loading.value = false
  }
}

function onApply(d) {
  // W38 fix: 老的 'Materials' 页是废弃原型（假上传、没有多语言接入），
  // 真正接入后端的流程是材料收集向导 MaterialWizard。
  router.push({ name: 'MaterialWizard', query: { country: d.country_code, visa_type: 'tourism' } })
}

onMounted(() => {
  auth.hydrate()
  load()
})
</script>

<style scoped lang="scss">
/* ============================================================
   Htex Destinations — 触感设计 (zigzag 拉链边缘 + cover 沉浸)
   ============================================================ */
.dest-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #F5F7FB 0%, #EEF2F8 100%);
}
.dest-shell { max-width: 1200px; margin: 0 auto; padding: 32px 24px 80px; }
.page-title { font-size: 32px; font-weight: 700; margin: 0 0 6px; color: #0F172A; letter-spacing: -0.5px; }
.page-sub { color: #64748B; margin: 0 0 32px; font-size: 15px; }

.state-loading, .state-error {
  padding: 60px; text-align: center; color: #9CA3AF; font-size: 14px;
}
.state-error { color: #DC2626; }

.dest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
}

/* ── Card shell ── */
.dest-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;     /* clip the zigzag inside */
  position: relative;
  transition: transform .25s ease, box-shadow .25s ease;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  /* tactile: subtle texture via gradient */
  background-image:
    repeating-linear-gradient(45deg, transparent 0, transparent 4px, rgba(15, 23, 42, 0.008) 4px, rgba(15, 23, 42, 0.008) 5px);
}

.dest-card:not(.is-disabled):hover {
  transform: translateY(-4px) rotate(-0.3deg);
  box-shadow:
    0 12px 32px rgba(15, 23, 42, 0.14),
    0 4px 8px rgba(15, 23, 42, 0.06);
}

.dest-card.is-disabled { opacity: 0.55; filter: saturate(0.4); }

/* ── Cover image (with zigzag BOTTOM edge) ── */
.dest-card__cover {
  position: relative;
  width: 100%;
  height: 200px;
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
  overflow: hidden;
}

.dest-card__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform .4s ease;
}

.dest-card:not(.is-disabled):hover .dest-card__cover img {
  transform: scale(1.05);
}

/* Zigzag bottom edge — gives the cover a "torn paper / stamp" feel.
   8 teeth across, 10px deep. Works regardless of card width. */
.dest-card__cover::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 14px;
  background: #fff;
  /* 16-point zigzag — teeth pointing UP into the image */
  clip-path: polygon(
    0% 100%, 0% 30%,
    6.25% 0%, 12.5% 30%,
    18.75% 0%, 25% 30%,
    31.25% 0%, 37.5% 30%,
    43.75% 0%, 50% 30%,
    56.25% 0%, 62.5% 30%,
    68.75% 0%, 75% 30%,
    81.25% 0%, 87.5% 30%,
    93.75% 0%, 100% 30%,
    100% 100%
  );
}

/* Card body sits behind the zigzag */
.dest-card__body {
  position: relative;
  padding: 20px 18px 22px;
  text-align: center;
}

/* ── Cover flag (small badge in corner) ── */
.dest-card__cover-flag {
  position: absolute;
  top: 12px;
  right: 12px;
  font-size: 22px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 50%;
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  backdrop-filter: blur(4px);
}

/* ── Big fallback flag (for countries without a cover image) ── */
.dest-card__cover-fallback {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1E293B 0%, #475569 100%);
}
.dest-card__flag-big { font-size: 80px; }

/* Subtle bottom-of-cover darken for legibility on the flag badge */
.dest-card__cover-overlay {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.18) 0%, transparent 30%, transparent 70%, rgba(0,0,0,0.05) 100%);
  pointer-events: none;
}

/* ── Body content ── */
.dest-card__name {
  font-size: 17px;
  font-weight: 700;
  color: #0F172A;
  margin-bottom: 10px;
  letter-spacing: -0.2px;
}

.dest-card__types {
  display: flex;
  gap: 6px;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
  min-height: 22px;
}

.tag {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2px;
}
.tag--tourism { background: linear-gradient(135deg, #EEF2FF, #DBEAFE); color: #4338CA; }
.tag--student { background: linear-gradient(135deg, #FEF3C7, #FDE68A); color: #B45309; }
.tag--business { background: linear-gradient(135deg, #DCFCE7, #BBF7D0); color: #15803D; }
.tag--work { background: linear-gradient(135deg, #FCE7F3, #FBCFE8); color: #BE185D; }

.dest-card__lock {
  font-size: 12px;
  color: #94A3B8;
  margin-bottom: 10px;
}

.btn {
  padding: 10px 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  width: 100%;
  transition: all .15s;
  letter-spacing: 0.2px;
}
.btn.primary {
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
  color: #FFF;
  box-shadow: 0 2px 4px rgba(59, 110, 245, 0.25);
}
.btn.primary:hover {
  box-shadow: 0 6px 16px rgba(59, 110, 245, 0.4);
  transform: translateY(-1px);
}
.btn.primary:active { transform: translateY(0); }

/* ── Tactile micro-interaction: when a card has a cover, add a
   subtle "peel" hint via a diagonal sheen line at top-right ── */
.dest-card.has-cover .dest-card__cover::before {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 60px; height: 60px;
  background: linear-gradient(225deg, rgba(255,255,255,0.4) 0%, transparent 50%);
  pointer-events: none;
  z-index: 1;
}

@media (max-width: 600px) {
  .dest-shell { padding: 16px; }
  .dest-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; }
  .dest-card__cover { height: 140px; }
  .page-title { font-size: 24px; }
}
</style>