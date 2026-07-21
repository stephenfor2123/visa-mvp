<template>
  <div class="contact-page">
    <AppHeader />

    <main class="app-container app-page contact-page__main">
      <header class="contact-page__head">
        <h1 class="contact-page__title">{{ t('contact.title') }}</h1>
      </header>

    <ul class="contact-page__list" aria-label="Contact options">
      <li class="contact-page__row" data-testid="contact-row-email">
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.email') }}</div>
          <a class="contact-page__row-value" :href="`mailto:${CONTACT.support}`" data-testid="contact-email-value">{{ CONTACT.support }}</a>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          :data-testid="`contact-copy-email`"
          :class="{ 'is-copied': copyState === 'email' }"
          @click="copyToClipboard('email', CONTACT.support)"
        >
          {{ copyState === 'email' ? t('contact.copied') : t('contact.copy') }}
        </button>
      </li>

      <li class="contact-page__row" data-testid="contact-row-privacy">
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.privacy_label') }}</div>
          <a class="contact-page__row-value" :href="`mailto:${CONTACT.privacy}`" data-testid="contact-privacy-value">{{ CONTACT.privacy }}</a>
          <div class="contact-page__row-note">{{ t('contact.privacy_note') }}</div>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          data-testid="contact-copy-privacy"
          :class="{ 'is-copied': copyState === 'privacy' }"
          @click="copyToClipboard('privacy', CONTACT.privacy)"
        >
          {{ copyState === 'privacy' ? t('contact.copied') : t('contact.copy') }}
        </button>
      </li>

      <li class="contact-page__row" :class="{ 'is-focused': focusPartner }" data-testid="contact-row-partner">
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.partner_label') }}</div>
          <a class="contact-page__row-value" :href="`mailto:${CONTACT.business}?subject=${encodeURIComponent(t('contact.partner_subject'))}`" data-testid="contact-partner-value">{{ CONTACT.business }}</a>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          :data-testid="`contact-copy-partner`"
          :class="{ 'is-copied': copyState === 'partner' }"
          @click="copyToClipboard('partner', CONTACT.business)"
        >
          {{ copyState === 'partner' ? t('contact.copied') : t('contact.copy') }}
        </button>
      </li>
    </ul>

    <!-- W47d+ : 删 footer 工作时间。W54 决策: 全部走邮件,无需展示"工作时间"
         (回邮件没有"工作时间"概念) -->
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const route = useRoute()

const focusPartner = computed(() => route.query.focus === 'partner')

// W31: 联系信息(品牌统一,可后续改为后端配置)
// W54: 只保留邮件渠道 — 电话/微信/WhatsApp 已被产品决策下线。
const CONTACT = {
  support: 'support@htexvisa.com',
  privacy: 'privacy@htex.app',
  business: 'business@htexvisa.com',
}

// 复制到剪贴板
const copyState = ref('')
async function copyToClipboard(key, value) {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(value)
    } else {
      const ta = document.createElement('textarea')
      ta.value = value
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copyState.value = key
    setTimeout(() => { if (copyState.value === key) copyState.value = '' }, 1500)
  } catch (e) {
    console.warn('[contact] copy failed', e)
  }
}
</script>

<style scoped lang="scss">
.contact-page {
  min-height: 100vh;
  background: #fff;
  display: flex;
  flex-direction: column;

  &__main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 56px 24px 96px;
  }
  &__head {
    width: 100%;
    max-width: 1200px;
    margin: 0 auto 36px;
    text-align: center;
  }
  &__title {
    font-size: clamp(36px, 4vw, 52px);
    line-height: 1.1;
    font-weight: 700;
    color: #101828;
    margin: 0;
    letter-spacing: -.04em;
  }
  &__intro {
    max-width: 480px;
    margin: 16px auto 0;
    color: #667085;
    font-size: 16px;
    line-height: 1.6;
  }
  &__list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
  }
  &__row {
    display: flex;
    align-items: center;
    gap: 18px;
    min-height: 140px;
    padding: clamp(24px, 3vw, 34px);
    border: 1px solid #e3e8f2;
    border-radius: 20px;
    background: rgba(255, 255, 255, .94);
    box-shadow: 0 8px 24px rgba(22, 48, 92, .06);
    transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
    &:hover {
      transform: translateY(-3px);
      border-color: #cbd8ff;
      box-shadow: 0 16px 34px rgba(31, 73, 161, .12);
    }
    &.is-focused { border-color: #9bb2ff; box-shadow: 0 0 0 3px rgba(78, 111, 228, .10); }
  }
  &__row-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  &__row-label {
    font-size: clamp(18px, 2vw, 24px);
    color: #101828;
    font-weight: 700;
    letter-spacing: -.02em;
  }
  &__row-value {
    font-size: clamp(15px, 1.6vw, 18px);
    font-weight: 400;
    color: #7b8494;
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    letter-spacing: -.01em;
    &:hover { color: #4567db; }
  }
  &__row-note {
    font-size: 12px;
    color: #7b8494;
    line-height: 1.4;
  }
  &__copy {
    align-self: flex-start;
    background: #4c6ee4;
    border: 1px solid #4c6ee4;
    border-radius: 999px;
    padding: 10px 18px;
    font-size: 13px;
    color: #fff;
    cursor: pointer;
    flex-shrink: 0;
    transition: all .15s;
    font-weight: 500;
    &:hover { background: #3858c8; border-color: #3858c8; }
    &.is-copied {
      background: #16a34a;
      border-color: #16a34a;
      color: #fff;
    }
  }

  @media (max-width: 760px) {
    &__main { padding: 42px 16px 64px; }
    &__head { margin-bottom: 28px; }
    &__title { font-size: 36px; }
    &__intro { margin-top: 14px; font-size: 15px; }
    &__list { grid-template-columns: 1fr; }
    &__row {
      min-height: 120px;
      padding: 24px 18px;
      gap: 16px;
    }
    &__copy { padding: 9px 14px; }
  }
}
</style>
