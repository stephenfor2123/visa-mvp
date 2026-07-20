<template>
  <div class="security-page">
    <AppHeader scope="security" />
    <main>
      <section class="security-hero">
        <div class="security-hero__glow" aria-hidden="true" />
        <div class="security-shell security-hero__content">
          <div class="security-hero__eyebrow"><span class="security-hero__pulse" />{{ t('trust.eyebrow') }}</div>
          <h1>{{ t('trust.page_title') }}</h1>
          <p>{{ t('trust.page_intro') }}</p>
          <div class="security-hero__status">
            <span>{{ t('trust.status_local') }}</span>
            <span>{{ t('trust.status_encrypted') }}</span>
            <span>{{ t('trust.status_control') }}</span>
          </div>
        </div>
      </section>

      <section class="security-body">
        <div class="security-shell">
          <header class="security-body__head">
            <span>{{ t('trust.plain_label') }}</span>
            <h2>{{ t('trust.plain_title') }}</h2>
            <p>{{ t('trust.plain_intro') }}</p>
          </header>
          <div class="security-grid">
            <article v-for="(item, index) in practices" :key="item.title" class="security-card">
              <span class="security-card__number">0{{ index + 1 }}</span>
              <div class="security-card__icon" aria-hidden="true" v-html="item.icon" />
              <h3>{{ t(item.title) }}</h3>
              <p>{{ t(item.body) }}</p>
            </article>
          </div>
          <aside class="security-boundary">
            <div>
              <span class="security-boundary__label">{{ t('trust.boundary_label') }}</span>
              <h2>{{ t('trust.boundary_title') }}</h2>
            </div>
            <p>{{ t('trust.boundary_body') }}</p>
            <router-link to="/agreement?tab=privacy">{{ t('trust.privacy_link') }} <span aria-hidden="true">↗</span></router-link>
          </aside>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const practices = [
  { title: 'trust.local_title', body: 'trust.local_body', icon: '<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M8 21h8M12 18v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>' },
  { title: 'trust.encryption_title', body: 'trust.encryption_body', icon: '<svg viewBox="0 0 24 24" fill="none"><rect x="5" y="10" width="14" height="11" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M8 10V7a4 4 0 0 1 8 0v3" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="15" r="1.3" fill="currentColor"/></svg>' },
  { title: 'trust.minimal_title', body: 'trust.minimal_body', icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 3l8 4.5v5c0 5-3.4 8-8 9.5-4.6-1.5-8-4.5-8-9.5v-5L12 3z" stroke="currentColor" stroke-width="1.6"/><path d="M8.5 12l2.2 2.2 4.8-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>' },
  { title: 'trust.control_title', body: 'trust.control_body', icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M7 7l1 14h8l1-14M9 7V4h6v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M10 11v6M14 11v6" stroke="currentColor" stroke-width="1.6"/></svg>' },
]
</script>

<style scoped lang="scss">
.security-page { min-height: 100vh; background: #070a10; color: #f8fafc; }
.security-shell { width: min(1120px, calc(100% - 48px)); margin: 0 auto; position: relative; }
.security-hero {
  position: relative; overflow: hidden; padding: 116px 0 104px; border-bottom: 1px solid rgba(148, 163, 184, .14);
  background: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px), radial-gradient(circle at 75% 35%, rgba(59,110,245,.18), transparent 32%);
  background-size: 44px 44px, 44px 44px, auto;
  &__glow { position: absolute; width: 420px; height: 420px; right: 5%; top: 0; border: 1px solid rgba(96,165,250,.18); border-radius: 50%; box-shadow: 0 0 100px rgba(37,99,235,.16), inset 0 0 80px rgba(37,99,235,.08); }
  &__content { z-index: 1; }
  &__eyebrow { display: flex; align-items: center; gap: 10px; color: #93c5fd; font: 600 12px/1.2 monospace; letter-spacing: .14em; text-transform: uppercase; }
  &__pulse { width: 7px; height: 7px; border-radius: 50%; background: #60a5fa; box-shadow: 0 0 16px #3b82f6; }
  h1 { max-width: 760px; margin: 22px 0 20px; font-size: clamp(42px, 6vw, 72px); line-height: 1.05; letter-spacing: -.05em; }
  p { max-width: 690px; margin: 0; color: #a8b3c7; font-size: 18px; line-height: 1.8; }
  &__status { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 36px; span { padding: 8px 12px; border: 1px solid rgba(96,165,250,.24); border-radius: 999px; color: #cbd5e1; background: rgba(15,23,42,.58); font-size: 12px; } span::before { content: '✓'; color: #60a5fa; margin-right: 7px; } }
}
.security-body { padding: 92px 0 112px; background: linear-gradient(180deg, #080b12, #05070b); }
.security-body__head {
  max-width: 680px; margin-bottom: 42px;
  > span { color: #60a5fa; font: 600 12px/1 monospace; letter-spacing: .16em; text-transform: uppercase; }
  h2 { margin: 14px 0; font-size: 34px; letter-spacing: -.03em; }
  p { margin: 0; color: #8f9bad; line-height: 1.8; }
}
.security-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.security-card {
  position: relative; min-height: 230px; padding: 28px; overflow: hidden; border: 1px solid rgba(148,163,184,.14); border-radius: 18px; background: linear-gradient(145deg, rgba(17,24,39,.88), rgba(8,12,20,.96)); transition: transform .2s ease, border-color .2s ease;
  &:hover { transform: translateY(-3px); border-color: rgba(96,165,250,.4); }
  &__number { position: absolute; right: 22px; top: 18px; color: rgba(148,163,184,.28); font: 500 12px monospace; }
  &__icon { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; background: rgba(37,99,235,.12); color: #60a5fa; border: 1px solid rgba(96,165,250,.18); }
  &__icon :deep(svg) { width: 24px; height: 24px; }
  h3 { margin: 24px 0 10px; font-size: 19px; }
  p { margin: 0; max-width: 430px; color: #8f9bad; line-height: 1.75; font-size: 14px; }
}
.security-boundary {
  display: grid; grid-template-columns: 1.05fr 1.45fr auto; gap: 32px; align-items: center; margin-top: 20px; padding: 30px; border: 1px solid rgba(96,165,250,.22); border-radius: 18px; background: linear-gradient(100deg, rgba(37,99,235,.13), rgba(15,23,42,.45));
  &__label { color: #60a5fa; font: 600 11px monospace; letter-spacing: .13em; text-transform: uppercase; }
  h2 { margin: 9px 0 0; font-size: 20px; }
  p { margin: 0; color: #9aa6b8; line-height: 1.7; font-size: 14px; }
  a { white-space: nowrap; color: #bfdbfe; text-decoration: none; font-size: 13px; font-weight: 600; }
}
@media (max-width: 760px) {
  .security-shell { width: min(100% - 32px, 1120px); }
  .security-hero { padding: 76px 0 68px; &__glow { right: -220px; } h1 { font-size: 42px; } p { font-size: 16px; } }
  .security-body { padding: 64px 0 80px; }
  .security-grid { grid-template-columns: 1fr; }
  .security-boundary { grid-template-columns: 1fr; gap: 16px; }
}
</style>
