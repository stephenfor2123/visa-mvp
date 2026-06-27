<template>
  <div class="contact-page">
    <header class="contact-page__head">
      <h1 class="contact-page__title">{{ t('contact.title') }}</h1>
      <p class="contact-page__sub">{{ t('contact.sub') }}</p>
    </header>

    <ul class="contact-page__list">
      <li class="contact-page__row contact-page__row--email" data-testid="contact-row-email">
        <span class="contact-page__chip contact-page__chip--blue" v-html="SVG_MAIL" />
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.email') }}</div>
          <a class="contact-page__row-value" :href="`mailto:${CONTACT.email}`" data-testid="contact-email-value">{{ CONTACT.email }}</a>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          :data-testid="`contact-copy-email`"
          :class="{ 'is-copied': copyState === 'email' }"
          @click="copyToClipboard('email', CONTACT.email)"
        >
          {{ copyState === 'email' ? t('contact.copied') : t('contact.copy') }}
        </button>
      </li>

      <li class="contact-page__row" data-testid="contact-row-phone">
        <span class="contact-page__chip contact-page__chip--emerald" v-html="SVG_PHONE" />
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.phone') }}</div>
          <a class="contact-page__row-value" :href="`tel:${CONTACT.phone}`">{{ CONTACT.phone }}</a>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          :data-testid="`contact-copy-phone`"
          :class="{ 'is-copied': copyState === 'phone' }"
          @click="copyToClipboard('phone', CONTACT.phone)"
        >
          {{ copyState === 'phone' ? t('contact.copied') : t('contact.copy') }}
        </button>
      </li>

      <li class="contact-page__row" data-testid="contact-row-wechat">
        <span class="contact-page__chip contact-page__chip--green" v-html="SVG_WECHAT" />
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.wechat') }}</div>
          <span class="contact-page__row-value">{{ CONTACT.wechat }}</span>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          :data-testid="`contact-copy-wechat`"
          :class="{ 'is-copied': copyState === 'wechat' }"
          @click="copyToClipboard('wechat', CONTACT.wechat)"
        >
          {{ copyState === 'wechat' ? t('contact.copied') : t('contact.copy') }}
        </button>
      </li>

      <li class="contact-page__row" data-testid="contact-row-whatsapp">
        <span class="contact-page__chip contact-page__chip--teal" v-html="SVG_WHATSAPP" />
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.whatsapp') }}</div>
          <a
            class="contact-page__row-value"
            :href="`https://wa.me/${CONTACT.whatsapp.replace(/[^\d]/g, '')}`"
            target="_blank"
            rel="noopener"
          >{{ CONTACT.whatsapp }}</a>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          :data-testid="`contact-copy-whatsapp`"
          :class="{ 'is-copied': copyState === 'whatsapp' }"
          @click="copyToClipboard('whatsapp', CONTACT.whatsapp)"
        >
          {{ copyState === 'whatsapp' ? t('contact.copied') : t('contact.copy') }}
        </button>
      </li>
    </ul>

    <footer class="contact-page__foot">
      <span class="contact-page__hours-label">{{ t('contact.hours') }}</span>
      <span class="contact-page__hours-value">{{ t('contact.hours_days') }} · {{ t('contact.hours_time') }}</span>
    </footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// W31: 联系信息(品牌统一,可后续改为后端配置)
const CONTACT = {
  email: 'hello@htex.com',
  phone: '400-888-1234',
  wechat: 'Htex_visa',
  whatsapp: '+86 138-0013-8000',
}

const SVG_MAIL = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M3 7l9 6 9-6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`
const SVG_PHONE = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 4h3l2 5-2 1a11 11 0 0 0 6 6l1-2 5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`
const SVG_WECHAT = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 4C5 4 2 6.7 2 10c0 1.7.8 3.3 2 4.3l-.5 2 2.2-1.1c.7.2 1.4.3 2.3.3.3 0 .5 0 .8-.1a5.4 5.4 0 0 1 5.4-5.4c.3 0 .6 0 .9.1C14.5 6.5 12 4 9 4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="6.5" cy="9" r="0.8" fill="currentColor"/><circle cx="10" cy="9" r="0.8" fill="currentColor"/><path d="M22 14.5c0-2.8-2.5-5-5.5-5s-5.5 2.2-5.5 5 2.5 5 5.5 5c.6 0 1.2-.1 1.7-.2l1.8.9-.4-1.6c1.4-.9 2.4-2.4 2.4-4.1z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="14.5" cy="14" r="0.7" fill="currentColor"/><circle cx="17.5" cy="14" r="0.7" fill="currentColor"/></svg>`
const SVG_WHATSAPP = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3.5 20.5l1-3.6A8.5 8.5 0 1 1 7 19.5l-3.5 1z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 9.5c.5-.5 1-.5 1.4 0l.7 1c.4.5.4.8 0 1.2l-.4.4c.5 1 1.3 1.8 2.3 2.3l.4-.4c.4-.4.7-.4 1.2 0l1 .7c.5.4.5.9 0 1.4l-.5.5c-.7.7-2 .5-3.5-.5-2-1.3-3.4-2.8-3.7-3.7-.4-1.2-.5-2.3 0-3z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`

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
  align-items: center;
  padding: 64px 24px 80px;
  &__head {
    text-align: center;
    margin-bottom: 36px;
    max-width: 520px;
  }
  &__title {
    font-size: 32px;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 8px;
  }
  &__sub {
    font-size: 14px;
    color: #64748b;
    margin: 0;
    line-height: 1.6;
  }
  &__list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    max-width: 560px;
  }
  &__row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px 18px;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    background: #f8fafc;
    transition: background 0.15s;
    &:hover { background: #f1f5f9; }
    &--email {
      background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
      border-color: #bfdbfe;
    }
  }
  &__chip {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    svg { width: 22px; height: 22px; }
    &--blue    { background: #dbeafe; color: #2563eb; }
    &--emerald { background: #d1fae5; color: #059669; }
    &--green   { background: #dcfce7; color: #16a34a; }
    &--teal    { background: #ccfbf1; color: #0d9488; }
  }
  &__row-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  &__row-label { font-size: 12px; color: #64748b; }
  &__row-value {
    font-size: 16px;
    font-weight: 500;
    color: #0f172a;
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    &:hover { color: #3b6ef5; text-decoration: underline; }
  }
  &__copy {
    background: #fff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
    color: #475569;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s;
    font-weight: 500;
    &:hover { background: #3b6ef5; border-color: #3b6ef5; color: #fff; }
    &.is-copied {
      background: #16a34a;
      border-color: #16a34a;
      color: #fff;
    }
  }
  &__foot {
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid #f1f5f9;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    width: 100%;
    max-width: 560px;
    justify-content: center;
  }
  &__hours-label { color: #64748b; }
  &__hours-value { color: #0f172a; font-weight: 500; }
}
</style>
