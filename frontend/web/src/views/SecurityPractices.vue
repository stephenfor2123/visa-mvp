<template>
  <div class="security-page">
    <AppHeader scope="security" />
    <main>
      <section class="security-hero">
        <div class="security-hero__glow" aria-hidden="true" />
        <div class="security-shell security-hero__content">
          <PageHero
            on-dark
            flush
            :title="t('trust.page_title')"
            :subtitle="t('trust.page_intro')"
          />
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
            <h2>{{ t('trust.plain_title') }}</h2>
          </header>
          <div class="security-grid">
            <article v-for="(item, index) in practices" :key="item.title" class="security-card">
              <span class="security-card__number">0{{ index + 1 }}</span>
              <h3>{{ t(item.title) }}</h3>
              <p>{{ t(item.body) }}</p>
            </article>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import PageHero from '@/components/PageHero.vue'

const { t } = useI18n()
const practices = [
  { title: 'trust.local_title', body: 'trust.local_body' },
  { title: 'trust.encryption_title', body: 'trust.encryption_body' },
  { title: 'trust.minimal_title', body: 'trust.minimal_body' },
  { title: 'trust.control_title', body: 'trust.control_body' },
]
</script>

<style scoped lang="scss">
.security-page { min-height: 100vh; background: #fff; color: var(--ink-1, #0f172a); }
.security-shell { width: min(1160px, calc(100% - 40px)); margin: 0 auto; position: relative; }
.security-hero {
  position: relative; overflow: hidden; padding: 72px 0 68px; border-top: 1px solid #f1f5f9; border-bottom: 1px solid #f1f5f9;
  background: #fff;
  &__glow { display: none; }
  &__content { z-index: 1; }
  p { max-width: 650px; margin: 0; color: #475569; font-size: 16px; line-height: 1.75; }
  &__status { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; span { padding: 7px 12px; border: 1px solid #cbd5e1; border-radius: 999px; color: #334155; background: #fff; font-size: 12px; } span::before { content: '✓'; color: #3b6ef5; margin-right: 7px; font-weight: 700; } }
}
.security-body { padding: 64px 0 88px; background: #fff; }
.security-body__head {
  max-width: 680px; margin-bottom: 42px;
  h2 { margin: 0; font-size: 30px; letter-spacing: -.02em; }
}
.security-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.security-card {
  position: relative; min-height: 142px; padding: 22px 24px; overflow: hidden; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; box-shadow: 0 2px 8px rgba(15,23,42,.04); transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
  &:hover { transform: translateY(-2px); border-color: #a9c0ff; box-shadow: 0 8px 22px rgba(15,23,42,.08); }
  &__number { position: absolute; right: 22px; top: 18px; color: #cbd5e1; font-size: 12px; font-weight: 700; }
  h3 { margin: 0 0 9px; padding-right: 34px; font-size: 17px; }
  p { margin: 0; max-width: 430px; color: #64748b; line-height: 1.65; font-size: 14px; }
}
@media (max-width: 760px) {
  .security-shell { width: min(100% - 32px, 1120px); }
  .security-hero { padding: 52px 0 48px; &__glow { right: -220px; }  }
  .security-body { padding: 48px 0 64px; }
  .security-grid { grid-template-columns: 1fr; }
}
</style>
