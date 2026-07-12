<!-- Agreement.vue — W12 Story: 服务协议页 -->
<template>
  <div class="agreement-page">
    <AppHeader scope="agreement" />
    <main class="app-container app-page agreement-shell">
      <div class="page-header">
        <h1 class="page-title">{{ t('agreement.page_title') }}</h1>
        <p class="page-sub">{{ t('agreement.page_subtitle') }}</p>
        <p class="agreement-disclaimer">{{ t('agreement.beta_disclaimer') }}</p>
      </div>

      <!-- Tabs -->
      <div class="tab-nav" data-testid="agreement-tabs">
        <button
          class="tab-nav__btn"
          :class="{ 'is-active': activeTab === 'terms' }"
          @click="activeTab = 'terms'"
          data-testid="tab-terms"
        >
          {{ t('agreement.tab_terms') }}
        </button>
        <button
          class="tab-nav__btn"
          :class="{ 'is-active': activeTab === 'privacy' }"
          @click="activeTab = 'privacy'"
          data-testid="tab-privacy"
        >
          {{ t('agreement.tab_privacy') }}
        </button>
      </div>

      <!-- Terms -->
      <div v-if="activeTab === 'terms'" class="agreement-content" data-testid="agreement-terms">
        <h2 class="agreement-content__title">{{ t('agreement.terms_title') }}</h2>
        <p class="agreement-content__effective">{{ t('agreement.terms_effective') }}</p>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.terms_section_1_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.terms_section_1_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.terms_section_2_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.terms_section_2_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.terms_section_3_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.terms_section_3_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.terms_section_4_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.terms_section_4_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.terms_section_5_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.terms_section_5_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.terms_section_6_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.terms_section_6_body') }}</p>
        </section>
      </div>

      <!-- Privacy -->
      <div v-if="activeTab === 'privacy'" class="agreement-content" data-testid="agreement-privacy">
        <h2 class="agreement-content__title">{{ t('agreement.privacy_title') }}</h2>
        <p class="agreement-content__effective">{{ t('agreement.privacy_effective') }}</p>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.privacy_section_1_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.privacy_section_1_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.privacy_section_2_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.privacy_section_2_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.privacy_section_3_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.privacy_section_3_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.privacy_section_4_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.privacy_section_4_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.privacy_section_5_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.privacy_section_5_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.privacy_section_6_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.privacy_section_6_body') }}</p>
        </section>

        <section class="agreement-section">
          <h3 class="agreement-section__title">{{ t('agreement.privacy_section_7_title') }}</h3>
          <p class="agreement-section__body">{{ t('agreement.privacy_section_7_body', { email: t('agreement.privacy_contact_email') }) }}</p>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
// LEGAL_TODO: 正式上线前须法务/本地律师签字 — 见 docs/LEGAL_REVIEW_NOTES.md §3
// 当前 4 语种为 v1.1-gdpr-draft（产品自助合规草稿，已按 GDPR Ch.V / Art.8 对齐）
// 法务审核通过后删除本注释，并移除 i18n 中的 __legal_review_pending__
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LangSwitch from '@/components/LangSwitch.vue'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const route = useRoute()
const activeTab = ref(route.query.tab === 'privacy' ? 'privacy' : 'terms')

onMounted(() => {
  if (route.query.tab === 'privacy' || route.query.tab === 'terms') {
    activeTab.value = route.query.tab
  }
})
</script>

<style scoped>
.agreement-page {
  min-height: 100vh;
  background: #FFFFFF;
}
.agreement-shell {
  padding-top: 24px;
  padding-bottom: 64px;
  max-width: 720px;
}
.page-header {
  margin-bottom: 24px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 6px;
}
.page-sub {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}
.agreement-disclaimer {
  margin: 12px 0 0;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
}
.tab-nav {
  display: flex;
  gap: 4px;
  background: #fff;
  border-radius: 12px;
  padding: 6px;
  margin-bottom: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.tab-nav__btn {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  cursor: pointer;
  transition: all .15s;
}
.tab-nav__btn.is-active {
  background: var(--color-primary, #3b6ef5);
  color: #fff;
}
.agreement-content {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.agreement-content__title {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 8px;
}
.agreement-content__effective {
  font-size: 12px;
  color: #9ca3af;
  margin: 0 0 24px;
}
.agreement-section {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid #f0f0f0;
}
.agreement-section:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}
.agreement-section__title {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 8px;
}
.agreement-section__body {
  font-size: 14px;
  line-height: 1.7;
  color: #4b5563;
  margin: 0;
}
</style>