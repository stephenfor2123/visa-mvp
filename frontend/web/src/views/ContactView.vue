<template>
  <div class="contact-page">
    <AppHeader />

    <main class="app-container app-page contact-page__main">
      <header class="contact-page__head">
        <h1 class="contact-page__title">{{ t('contact.title') }}</h1>
        <!-- W47d+ : 副标题 "邮件咨询 1 小时内回复..." 划掉,产品决定页面只
             保留主标题 + 卡片,信息密度更聚焦 -->
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

      <!-- W57: 商业合作 — 共用 hello@htex.com, 文案区分用途。 -->
      <li class="contact-page__row contact-page__row--partner" data-testid="contact-row-partner">
        <span class="contact-page__chip contact-page__chip--indigo" v-html="SVG_BRIEFCASE" />
        <div class="contact-page__row-body">
          <div class="contact-page__row-label">{{ t('contact.partner_label') }}</div>
          <a class="contact-page__row-value" :href="`mailto:${CONTACT.email}?subject=${encodeURIComponent(t('contact.partner_subject'))}`" data-testid="contact-partner-value">{{ CONTACT.email }}</a>
        </div>
        <button
          type="button"
          class="contact-page__copy"
          :data-testid="`contact-copy-partner`"
          :class="{ 'is-copied': copyState === 'partner' }"
          @click="copyToClipboard('partner', CONTACT.email)"
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
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()

// W31: 联系信息(品牌统一,可后续改为后端配置)
// W54: 只保留邮件渠道 — 电话/微信/WhatsApp 已被产品决策下线。
const CONTACT = {
  email: 'hello@htex.com',
}

const SVG_MAIL = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M3 7l9 6 9-6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`
// W57: 商业合作 — 共用 hello@htex.com,但视觉与文案区分。
const SVG_BRIEFCASE = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="7" width="18" height="13" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M3 12h18" stroke="currentColor" stroke-width="1.6"/></svg>`

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
  background: var(--bg, #f9fafb);
  display: flex;
  flex-direction: column;

  &__main {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 72px 24px 80px;
  }
  &__head {
    text-align: center;
    margin-bottom: 32px;
    max-width: 520px;
  }
  &__title {
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 4px;
    letter-spacing: -.3px;
  }
  // 副标题已删 (W47d+),保留空选择器避免外部 override 失效
  &__list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
    width: 100%;
    max-width: 880px;
  }
  &__row {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 18px 20px;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    background: #fff;
    box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
    transition: all .2s ease;
    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(15, 23, 42, .08);
    }
    &--email {
      background: linear-gradient(135deg, #eff6ff 0%, #ffffff 60%);
      border-color: #bfdbfe;
    }
    &--partner {
      background: linear-gradient(135deg, #eef2ff 0%, #ffffff 60%);
      border-color: #c7d2fe;
    }
  }
  &__chip {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    svg { width: 24px; height: 24px; }
    &--blue    { background: #dbeafe; color: #2563eb; }
    &--indigo  { background: #e0e7ff; color: #4f46e5; }
  }
  &__row-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  &__row-label {
    font-size: 12px;
    color: #64748b;
    font-weight: 500;
    letter-spacing: .3px;
  }
  &__row-value {
    font-size: 17px;
    font-weight: 600;
    color: #0f172a;
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    letter-spacing: -.2px;
    &:hover { color: #3b6ef5; }
  }
  &__copy {
    background: #fff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12px;
    color: #475569;
    cursor: pointer;
    flex-shrink: 0;
    transition: all .15s;
    font-weight: 500;
    &:hover { background: #3b6ef5; border-color: #3b6ef5; color: #fff; }
    &.is-copied {
      background: #16a34a;
      border-color: #16a34a;
      color: #fff;
    }
  }
  // 页脚已删 (W47d+)
}
</style>
