<!-- SchengenCountries.vue — 申根热门 5 国(封面图) + 全部 26 国(可展开) -->
<template>
  <div class="sch-page">
    <AppHeader scope="schengen" />
    <main class="sch-shell">
      <button class="sch-back" @click="$router.push('/home')" data-testid="sch-back">
        ← {{ t('common.back') || '返回' }}
      </button>

      <h1 class="page-title">{{ t('sch.title') }}</h1>
      <p class="page-sub">{{ t('sch.subtitle') }}</p>

      <!-- Top 5 popular — big cover cards -->
      <h2 class="sch-section">{{ t('sch.popular') || '热门国家' }}</h2>
      <div class="sch-top-grid">
        <button
          v-for="c in top5"
          :key="c.code"
          class="sch-top-card"
          :data-testid="`sch-top-${c.code}`"
          @click="onPick(c)"
        >
          <img class="sch-top-card__cover" :src="c.cover" :alt="c.name" loading="lazy" />
          <div class="sch-top-card__overlay" />
          <div class="sch-top-card__body">
            <span class="sch-top-card__flag">{{ c.flag }}</span>
            <span class="sch-top-card__name">{{ c.name }}</span>
            <span class="sch-top-card__cta">{{ t('sch.apply_through') || '通过此国申请 →' }}</span>
          </div>
        </button>
      </div>

      <!-- Toggle all 26 -->
      <div class="sch-all-toggle">
        <button
          class="sch-all-toggle__btn"
          :class="{ 'is-open': showAll }"
          :data-testid="sch-toggle-all"
          @click="showAll = !showAll"
        >
          {{ showAll ? t('sch.hide_all') : t('sch.show_all') }}
          <span class="sch-all-toggle__chev">{{ showAll ? '▲' : '▼' }}</span>
        </button>
      </div>

      <!-- All 26 (expanded) — flag emoji grid -->
      <section v-if="showAll" class="sch-all">
        <h2 class="sch-section">{{ t('sch.all_26') || '全部 26 个申根成员国' }}</h2>
        <div class="sch-all-grid">
          <button
            v-for="c in all26"
            :key="c.code"
            class="sch-tile"
            :data-testid="`sch-tile-${c.code}`"
            @click="onPick(c)"
          >
            <span class="sch-tile__flag">{{ c.flag }}</span>
            <span class="sch-tile__code">{{ c.code }}</span>
            <span class="sch-tile__name">{{ c.name }}</span>
          </button>
        </div>
      </section>

      <p class="sch-foot">
        <span class="sch-foot__hint">ℹ️</span>
        {{ t('sch.foot_hint') }}
      </p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const router = useRouter()
const showAll = ref(false)

// Top 5 by visa demand — each with a real cover image
const top5 = [
  { code: 'FR', flag: '🇫🇷', name: 'France',      cover: '/countries/fr_eiffel.jpg' },
  { code: 'DE', flag: '🇩🇪', name: 'Germany',     cover: '/countries/de_brandenburg.jpg' },
  { code: 'IT', flag: '🇮🇹', name: 'Italy',       cover: '/countries/it_colosseum.jpg' },
  { code: 'ES', flag: '🇪🇸', name: 'Spain',       cover: '/countries/es_sagrada.jpg' },
  { code: 'NL', flag: '🇳🇱', name: 'Netherlands', cover: '/countries/nl_tulips.jpg' },
]

// All 26 schengen (alphabetical) — top 5 marked separately above
const rest21 = [
  { code: 'AT', flag: '🇦🇹', name: 'Austria' },
  { code: 'BE', flag: '🇧🇪', name: 'Belgium' },
  { code: 'HR', flag: '🇭🇷', name: 'Croatia' },
  { code: 'CZ', flag: '🇨🇿', name: 'Czechia' },
  { code: 'DK', flag: '🇩🇰', name: 'Denmark' },
  { code: 'EE', flag: '🇪🇪', name: 'Estonia' },
  { code: 'FI', flag: '🇫🇮', name: 'Finland' },
  { code: 'GR', flag: '🇬🇷', name: 'Greece' },
  { code: 'HU', flag: '🇭🇺', name: 'Hungary' },
  { code: 'IS', flag: '🇮🇸', name: 'Iceland' },
  { code: 'LV', flag: '🇱🇻', name: 'Latvia' },
  { code: 'LI', flag: '🇱🇮', name: 'Liechtenstein' },
  { code: 'LT', flag: '🇱🇹', name: 'Lithuania' },
  { code: 'LU', flag: '🇱🇺', name: 'Luxembourg' },
  { code: 'MT', flag: '🇲🇹', name: 'Malta' },
  { code: 'NO', flag: '🇳🇴', name: 'Norway' },
  { code: 'PL', flag: '🇵🇱', name: 'Poland' },
  { code: 'PT', flag: '🇵🇹', name: 'Portugal' },
  { code: 'SK', flag: '🇸🇰', name: 'Slovakia' },
  { code: 'SI', flag: '🇸🇮', name: 'Slovenia' },
  { code: 'SE', flag: '🇸🇪', name: 'Sweden' },
]
const all26 = computed(() => [...top5, ...rest21])

function onPick(c) {
  // W47: 选完国家 → 直接进 MaterialWizard,材料收集 + 表格填写在同一页完成
  router.push({ name: 'MaterialWizard', query: { country: c.code, visa_type: 'tourism' } })
}
</script>

<style scoped lang="scss">
.sch-page { min-height: 100vh; background: #fff; }
.sch-shell { max-width: 1200px; margin: 0 auto; padding: 24px 24px 80px; }

.sch-back {
  background: transparent; border: 0;
  color: var(--ink-3, #64748B); font-size: 13px;
  cursor: pointer; padding: 6px 0; margin-bottom: 16px;
  transition: color .15s;
}
.sch-back:hover { color: var(--el-color-primary, #3B6EF5); }

.page-title {
  font-size: 30px; font-weight: 700; color: var(--ink-1, #0F172A);
  margin: 0 0 6px; letter-spacing: -0.5px;
}
.page-sub {
  color: var(--ink-3, #64748B); font-size: 15px; margin: 0 0 32px;
}

.sch-section {
  font-size: 16px; font-weight: 700; color: var(--ink-1, #0F172A);
  margin: 8px 0 16px; letter-spacing: 0;
}

/* ── Top 5: large cover cards (like Home cards) ── */
.sch-top-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
.sch-top-card {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  border: 0;
  padding: 0;
  cursor: pointer;
  aspect-ratio: 3 / 4;
  background: #0F172A;
  transition: transform .25s ease, box-shadow .25s ease;
  box-shadow: 0 2px 8px rgba(15,23,42,0.08);
}
.sch-top-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(15,23,42,0.18);
}
.sch-top-card__cover {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: cover;
  transition: transform .5s ease;
}
.sch-top-card:hover .sch-top-card__cover { transform: scale(1.06); }
.sch-top-card__overlay {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 30%, rgba(0,0,0,0.78) 100%);
}
.sch-top-card__body {
  position: absolute; left: 0; right: 0; bottom: 0;
  padding: 18px 16px 16px;
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
  text-align: left;
  color: #fff;
}
.sch-top-card__flag { font-size: 22px; line-height: 1; }
.sch-top-card__name {
  font-size: 18px; font-weight: 700; letter-spacing: -0.2px;
  margin-top: 2px;
}
.sch-top-card__cta {
  font-size: 12px; font-weight: 500; opacity: 0.85; margin-top: 4px;
}

/* ── Show all toggle ── */
.sch-all-toggle {
  display: flex; justify-content: center;
  margin: 8px 0 24px;
}
.sch-all-toggle__btn {
  background: transparent;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px;
  padding: 10px 22px;
  font-size: 14px; font-weight: 600;
  color: var(--ink-1, #0F172A);
  cursor: pointer;
  transition: all .15s;
  display: inline-flex; align-items: center; gap: 8px;
}
.sch-all-toggle__btn:hover {
  border-color: var(--el-color-primary, #3B6EF5);
  color: var(--el-color-primary, #3B6EF5);
}
.sch-all-toggle__btn.is-open {
  background: var(--el-color-primary, #3B6EF5);
  border-color: var(--el-color-primary, #3B6EF5);
  color: #fff;
}
.sch-all-toggle__chev { font-size: 10px; opacity: 0.7; }

/* ── All 26 grid ── */
.sch-all-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}
.sch-tile {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  padding: 16px 10px 14px;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 10px;
  cursor: pointer;
  transition: all .15s;
  text-align: center;
  min-height: 110px;
}
.sch-tile:hover {
  border-color: var(--el-color-primary, #3B6EF5);
  background: rgba(59,110,245,.04);
  transform: translateY(-2px);
}
.sch-tile__flag { font-size: 32px; line-height: 1; margin-bottom: 2px; }
.sch-tile__code {
  font-size: 10px; font-weight: 700;
  color: var(--ink-3, #64748B); letter-spacing: 1px;
  text-transform: uppercase;
}
.sch-tile__name { font-size: 12px; font-weight: 600; color: var(--ink-1, #0F172A); }

.sch-foot {
  margin-top: 32px; font-size: 12px;
  color: var(--ink-3, #64748B);
  display: flex; align-items: center; gap: 6px;
}
.sch-foot__hint { font-size: 14px; }

@media (max-width: 600px) {
  .sch-top-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .sch-all-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 8px; }
  .sch-tile { min-height: 95px; padding: 12px 8px 10px; }
  .sch-tile__flag { font-size: 26px; }
  .page-title { font-size: 22px; }
}
</style>
