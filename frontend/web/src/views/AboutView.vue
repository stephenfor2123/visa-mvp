<template>
  <div class="about-page">
    <AppHeader />

    <main class="about-page__main">
      <PageHero :title="t('about.title')" :subtitle="t('about.lead')" />

      <section class="about-page__content">
        <article v-for="(item, index) in sections" :key="item.title" class="about-page__row">
          <span class="about-page__number">{{ String(index + 1).padStart(2, '0') }}</span>
          <h2>{{ item.title }}</h2>
          <p>
            {{ item.prefix }}<strong>{{ item.highlight }}</strong>{{ item.suffix }}
            <span v-if="item.construction" class="about-page__badge">{{ t('about.construction') }}</span>
            {{ item.after }}
          </p>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import PageHero from '@/components/PageHero.vue'

const { t } = useI18n()

const sections = computed(() => [
  {
    title: t('about.who_title'),
    prefix: t('about.who_prefix'),
    highlight: t('about.who_highlight'),
    suffix: t('about.who_suffix'),
  },
  {
    title: t('about.global_title'),
    prefix: t('about.global_prefix'),
    highlight: t('about.global_highlight'),
    suffix: t('about.global_suffix'),
    construction: true,
    after: t('about.global_after'),
  },
  {
    title: t('about.advantage_title'),
    prefix: t('about.advantage_prefix'),
    highlight: t('about.advantage_highlight'),
    suffix: t('about.advantage_suffix'),
  },
])
</script>

<style scoped lang="scss">
.about-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #fff 0%, #fbfcff 100%);
  color: #0f172a;

  &__main {
    width: 100%;
    max-width: 980px;
    margin: 0 auto;
    padding: 48px 28px 100px;
  }
  &__title { /* PageHero */ }
  &__lead { /* PageHero */ margin: 0 0 40px; }
  &__content { border-top: 1px solid #cfd7e4; }
  &__row {
    display: grid;
    grid-template-columns: 44px 160px 1fr;
    gap: 24px;
    padding: 34px 0 36px;
    border-bottom: 1px solid #dbe1ea;

    h2 { margin: 0; font-size: 15px; font-weight: 680; }
    p { margin: 0; color: #59677c; font-size: 17px; line-height: 1.75; }
    strong { color: #111827; font-weight: 650; }
  }
  &__number {
    padding-top: 2px;
    color: #3b6ef5;
    font-size: 12px;
    font-weight: 750;
    letter-spacing: .08em;
  }
  &__badge {
    display: inline-flex;
    margin: 0 6px;
    padding: 3px 8px;
    border: 1px solid #d9e1ed;
    border-radius: 999px;
    background: #fff;
    color: #7b8799;
    font-size: 11px;
    line-height: 1.3;
    vertical-align: 2px;
  }

  @media (max-width: 760px) {
    &__main { padding: 72px 20px 96px; }
    &__title { font-size: 48px; }
    &__lead { margin-bottom: 48px; }
    &__row {
      grid-template-columns: 32px 1fr;
      gap: 12px 8px;
      p { grid-column: 2; font-size: 16px; }
    }
  }
}
</style>
