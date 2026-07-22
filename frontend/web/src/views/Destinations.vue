<template>
  <div class="dest-page">
    <AppHeader scope="destinations" />
    <main class="dest-shell">
      <PageHero :title="t('dest.title')" :subtitle="t('dest.subtitle')" />

      <div v-if="loading" class="state-loading">⏳ {{ t('common.loading') }}</div>
      <div v-else-if="error" class="state-error">❌ {{ error }}</div>

      <div v-else class="dest-grid">
        <article
          v-for="d in cards"
          :key="d.id"
          class="country-card"
          :class="{ 'is-disabled': !d.enabled }"
          role="button"
          tabindex="0"
          :data-testid="`dest-card-${d.country_code}`"
          @click="d.enabled && onApply(d)"
          @keydown.enter="d.enabled && onApply(d)"
        >
          <div class="country-card__media">
            <img
              v-if="d.image"
              :src="d.image"
              :alt="d.country_name"
              loading="lazy"
              class="country-card__img"
              @error="onImgError(d.country_code)"
            />
            <div v-else class="country-card__media-fallback">{{ d.flag }}</div>
            <div class="country-card__media-overlay" />
          </div>

          <div class="country-card__top">
            <span class="country-card__flag">{{ d.flag }}</span>
            <span class="country-card__code">{{ d.codeLabel }}</span>
          </div>

          <div class="country-card__bottom">
            <h3 class="country-card__name">{{ d.country_name }}</h3>
            <p class="country-card__sub">{{ d.subLabel }}</p>

            <div class="country-card__attrs">
              <div class="country-card__attr">
                <span class="country-card__attr-label">{{ t('home.card.type') }}</span>
                <span class="country-card__attr-val">{{ d.visa_type_label }}</span>
              </div>
              <div class="country-card__attr">
                <span class="country-card__attr-label">{{ t('home.card.valid') }}</span>
                <span class="country-card__attr-val">{{ d.valid_label }}</span>
              </div>
              <div class="country-card__attr">
                <span class="country-card__attr-label">{{ t('home.card.fees') }}</span>
                <span class="country-card__attr-val">
                  <span class="country-card__price-from">FROM</span>
                  ${{ d.fee_usd }}
                </span>
              </div>
            </div>

            <div class="country-card__eta">
              <span aria-hidden="true">⏱</span>
              <span>{{ t('home.card.process_in_days', { n: d.process_days }) }}</span>
            </div>

            <div v-if="!d.enabled" class="country-card__lock">🔒 {{ t('dest.coming_soon') }}</div>
            <button
              v-else
              type="button"
              class="country-card__cta"
              :data-testid="`dest-apply-${d.country_code}`"
              @click.stop="onApply(d)"
            >{{ t('dest.apply_now') }} →</button>
          </div>
        </article>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { listDestinations } from '@/api/destinations'
import AppHeader from '@/components/AppHeader.vue'
import PageHero from '@/components/PageHero.vue'
import { countryCover, flagEmoji } from '@/utils/countryCovers'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const destinations = ref([])
const loading = ref(false)
const error = ref('')
const failedCovers = ref(new Set())

/** Fill gaps when DB row is incomplete (live UK currently has null meta). */
const META_DEFAULTS = {
  US: { fee_usd: 185, valid_days: 365, process_days: 15 },
  GB: { fee_usd: 155, valid_days: 180, process_days: 15 },
  UK: { fee_usd: 155, valid_days: 180, process_days: 15 },
  AU: { fee_usd: 145, valid_days: 365, process_days: 15 },
  // Schengen C: stay up to 90 days (not "6 months" validity)
  DE: { fee_usd: 90, valid_days: 90, process_days: 15 },
  FR: { fee_usd: 90, valid_days: 90, process_days: 15 },
}

const SCHENGEN_CODES = new Set(['DE', 'FR', 'IT', 'ES', 'NL', 'AT', 'BE', 'GR', 'PT', 'CZ', 'DK', 'FI', 'HU', 'IS', 'LU', 'NO', 'PL', 'SE', 'CH', 'SCHENGEN'])

const STICKER = new Set([
  'US', 'FR', 'DE', 'IT', 'ES', 'NL', 'AT', 'BE', 'GR', 'PT', 'CZ', 'DK',
  'FI', 'HU', 'IS', 'LU', 'NO', 'PL', 'SE', 'CH', 'SCHENGEN',
])

function normalizeCode(cc) {
  const c = String(cc || '').toUpperCase()
  return c === 'UK' ? 'GB' : c
}

function onImgError(cc) {
  const next = new Set(failedCovers.value)
  next.add(normalizeCode(cc))
  failedCovers.value = next
}

function formatValid(days) {
  if (!days) return '—'
  if (days % 365 === 0) {
    const y = days / 365
    return y === 1 ? '1 YEAR' : `${y} YEARS`
  }
  if (days % 30 === 0) {
    const mo = days / 30
    return mo === 1 ? '1 MONTH' : `${mo} MONTHS`
  }
  return `${days} DAYS`
}

const cards = computed(() =>
  destinations.value.map((d) => {
    const cc = normalizeCode(d.country_code)
    const defaults = META_DEFAULTS[cc] || META_DEFAULTS[d.country_code] || {}
    const cover = failedCovers.value.has(cc) ? null : countryCover(cc)
    const feeCents = d.visa_fee_usd != null
      ? d.visa_fee_usd
      : (defaults.fee_usd != null ? defaults.fee_usd * 100 : null)
    const fee = feeCents != null ? Math.round(feeCents / 100) : defaults.fee_usd
    // API currently stores 180 for DE/FR (the 90/180 window), which reads as
    // "6 MONTHS" on the card — wrong. Tourism Schengen stay is 90 days.
    let validDays = d.valid_days ?? defaults.valid_days
    if (SCHENGEN_CODES.has(cc)) validDays = 90
    // Prefer API process_days; if missing use default. Soften ultra-aggressive
    // marketing values for display (still days, not a calendar deadline).
    let processDays = d.process_days ?? defaults.process_days ?? 15
    if (processDays < 10) processDays = 10

    return {
      ...d,
      country_code: cc,
      flag: flagEmoji(cc),
      image: cover,
      codeLabel: cc,
      subLabel: t('dest.tourism'),
      fee_usd: fee,
      visa_type_label: STICKER.has(cc) ? t('home.card.type_sticker') : t('home.card.type_evisa'),
      // Keep "90 DAYS" (not "3 MONTHS") for Schengen stay clarity
      valid_label: SCHENGEN_CODES.has(cc) ? '90 DAYS' : formatValid(validDays),
      process_days: processDays,
    }
  }),
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    destinations.value = await listDestinations({ lang: locale.value || 'zh-CN' })
  } catch (e) {
    error.value = e?.message || t('common.network_error')
  } finally {
    loading.value = false
  }
}

function onApply(d) {
  router.push({ name: 'MaterialWizard', query: { country: d.country_code, visa_type: 'tourism' } })
}

onMounted(() => {
  auth.hydrate()
  load()
})
</script>

<style scoped lang="scss">
.dest-page {
  min-height: 100vh;
  background: #fff;
}
.dest-shell {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 80px;
}
.state-loading,
.state-error {
  padding: 60px;
  text-align: center;
  color: #9ca3af;
  font-size: 14px;
}
.state-error { color: #dc2626; }

.dest-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.country-card {
  position: relative;
  height: 420px;
  border-radius: 18px;
  overflow: hidden;
  cursor: pointer;
  transition: transform .35s cubic-bezier(.2, .8, .2, 1), box-shadow .35s ease;
  box-shadow: 0 6px 18px rgba(15, 23, 42, .08);
  background: #f8fafc;
  isolation: isolate;
}
.country-card:hover:not(.is-disabled) {
  transform: translateY(-6px) scale(1.015);
  box-shadow: 0 22px 48px rgba(15, 23, 42, .22);
}
.country-card.is-disabled {
  opacity: .55;
  filter: saturate(.4);
  cursor: not-allowed;
}
.country-card:focus-visible {
  outline: 3px solid #3b6ef5;
  outline-offset: 3px;
}

.country-card__media {
  position: absolute;
  inset: 0;
  z-index: 0;
}
.country-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform .6s cubic-bezier(.2, .8, .2, 1);
  filter: saturate(1.5) contrast(1.1);
}
.country-card:hover:not(.is-disabled) .country-card__img {
  transform: scale(1.08);
}
.country-card__media-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 100px;
  background: linear-gradient(135deg, #3b6ef5 0%, #6e59f0 100%);
}
.country-card__media-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0, 0, 0, .05) 0%, rgba(0, 0, 0, 0) 35%, rgba(0, 0, 0, .3) 100%);
  z-index: 2;
  pointer-events: none;
}

.country-card__top {
  position: absolute;
  top: 16px;
  left: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 3;
}
.country-card__flag {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, .25);
  border: 2px solid rgba(255, 255, 255, .8);
}
.country-card__code {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, .92);
  color: #1f2937;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, .15);
}

.country-card__bottom {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 18px 18px 16px;
  z-index: 3;
  color: #fff;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, .35) 40%, rgba(0, 0, 0, .78) 100%);
}
.country-card__name {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 800;
  line-height: 1.15;
  text-shadow: 0 2px 8px rgba(0, 0, 0, .4);
}
.country-card__sub {
  margin: 0 0 10px;
  font-size: 13px;
  opacity: .95;
  line-height: 1.35;
  text-shadow: 0 1px 4px rgba(0, 0, 0, .4);
}
.country-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 10px;
}
.country-card__tag {
  border: 1px solid transparent;
  color: #fff;
  cursor: pointer;
  font-family: inherit;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, .2);
  backdrop-filter: blur(6px);
}
.country-card__tag:hover,
.country-card__tag.is-selected {
  border-color: rgba(255, 255, 255, .9);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, .22);
}
.country-card__tag:not(.is-selected) { opacity: .72; }
.country-card__tag--tourism { background: rgba(59, 110, 245, .85); }
.country-card__tag--student { background: rgba(217, 119, 6, .85); }
.country-card__tag--business { background: rgba(21, 128, 61, .85); }

.country-card__attrs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 0 0 10px;
  padding: 10px 0;
  border-top: 1px solid rgba(255, 255, 255, .22);
  border-bottom: 1px solid rgba(255, 255, 255, .22);
}
.country-card__attr {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.country-card__attr-label {
  font-size: 10px;
  letter-spacing: 1.1px;
  font-weight: 700;
  color: rgba(255, 255, 255, .75);
  text-transform: uppercase;
}
.country-card__attr-val {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.country-card__price-from {
  font-size: 9px;
  opacity: .8;
  margin-right: 2px;
}
.country-card__eta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  font-size: 12px;
  opacity: .95;
}
.country-card__eta.is-empty { visibility: hidden; }
.country-card__lock {
  font-size: 12px;
  color: rgba(255, 255, 255, .85);
}
.country-card__cta {
  width: 100%;
  padding: 10px 16px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(135deg, #3b6ef5 0%, #6e59f0 100%);
  box-shadow: 0 2px 8px rgba(59, 110, 245, .35);
  transition: transform .15s, box-shadow .15s;
}
.country-card__cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(59, 110, 245, .45);
}

@media (max-width: 1100px) {
  .dest-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .dest-shell { padding: 16px 16px 60px; }
  .dest-grid { grid-template-columns: 1fr; gap: 14px; }
  .country-card { height: 380px; }
}
</style>
