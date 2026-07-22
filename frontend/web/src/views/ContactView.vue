<template>
  <div class="contact-page">
    <AppHeader scope="contact" />

    <main class="app-container contact-page__main">
      <section class="contact-hero">
        <div class="contact-hero__main">
          <span class="contact-hero__status">
            <i aria-hidden="true" />{{ t('contact.online') }}
          </span>
          <h1>{{ t('contact.hero_title') }}</h1>
          <p>{{ t('contact.hero_lead') }}</p>
        </div>
        <aside class="contact-hero__tip">
          <strong>{{ t('contact.email_tip_title') }}</strong>
          <span>{{ t('contact.email_tip_text') }}</span>
        </aside>
      </section>

      <section class="contact-grid" :aria-label="t('contact.title')">
        <article class="contact-card contact-card--support">
          <h2>{{ t('contact.support_title') }}</h2>
          <p class="contact-card__desc">{{ t('contact.support_desc') }}</p>
          <div class="contact-card__topics">
            <span>{{ t('contact.topic_application') }}</span>
            <span>{{ t('contact.topic_order') }}</span>
            <span>{{ t('contact.topic_account') }}</span>
            <span>{{ t('contact.topic_privacy') }}</span>
          </div>
          <a class="contact-card__email" :href="supportMailto">{{ CONTACT.support }}</a>
          <div class="contact-card__actions">
            <a class="contact-card__send" :href="supportMailto">{{ t('contact.send_email') }} →</a>
            <button
              type="button"
              class="contact-card__copy"
              :class="{ 'is-copied': copyState === 'support' }"
              @click="copyToClipboard('support', CONTACT.support)"
            >
              {{ copyState === 'support' ? t('contact.copied') : t('contact.copy_address') }}
            </button>
          </div>
        </article>

        <article class="contact-card" :class="{ 'is-focused': focusPartner }">
          <h2>{{ t('contact.partner_label') }}</h2>
          <p class="contact-card__desc">{{ t('contact.partner_note') }}</p>
          <div class="contact-card__topics">
            <span>{{ t('contact.topic_brand') }}</span>
            <span>{{ t('contact.topic_channel') }}</span>
          </div>
          <a class="contact-card__email" :href="businessMailto">{{ CONTACT.business }}</a>
          <div class="contact-card__actions">
            <a class="contact-card__send" :href="businessMailto">{{ t('contact.send_email') }} →</a>
            <button
              type="button"
              class="contact-card__copy"
              :class="{ 'is-copied': copyState === 'business' }"
              @click="copyToClipboard('business', CONTACT.business)"
            >
              {{ copyState === 'business' ? t('contact.copied') : t('contact.copy_address') }}
            </button>
          </div>
        </article>
      </section>

      <aside class="contact-security">
        <span><strong>{{ t('contact.security_prefix') }}</strong>{{ t('contact.security_text') }}</span>
        <router-link to="/security">{{ t('contact.security_link') }} →</router-link>
      </aside>
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

const CONTACT = {
  support: 'support@htexvisa.com',
  business: 'business@htexvisa.com',
}

const focusPartner = computed(() => route.query.focus === 'partner')
const supportMailto = computed(() => `mailto:${CONTACT.support}?subject=${encodeURIComponent(t('contact.support_subject'))}`)
const businessMailto = computed(() => `mailto:${CONTACT.business}?subject=${encodeURIComponent(t('contact.partner_subject'))}`)

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
.contact-page { min-height: 100vh; background: #fff; }
.contact-page__main { padding-top: 64px; padding-bottom: 96px; }

.contact-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(260px, .82fr);
  align-items: end;
  gap: 48px;
  margin-bottom: 54px;
}
.contact-hero__status {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 7px 11px;
  border-radius: 999px;
  color: var(--el-color-primary, #3B6EF5);
  background: var(--primary-bg, #EAF0FE);
  font-size: 13px;
  font-weight: 700;
  i {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #35b878;
    box-shadow: 0 0 0 4px rgba(53, 184, 120, .12);
  }
}
.contact-hero h1 {
  max-width: 700px;
  margin: 20px 0;
  color: var(--ink-1, #0F172A);
  font-size: clamp(40px, 4vw, 56px);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -.035em;
  white-space: pre-line;
}
.contact-hero__main > p {
  max-width: 650px;
  margin: 0;
  color: var(--ink-3, #64748B);
  font-size: 16px;
  line-height: 1.65;
}
.contact-hero__tip {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 7px 0 7px 28px;
  border-left: 1px solid #e4e9f2;
  color: #66748e;
  line-height: 1.65;
  strong { color: #09142b; font-size: 15px; }
}

.contact-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  align-items: stretch;
}
.contact-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100%;
  padding: 34px;
  border: 1px solid #e4e9f2;
  border-radius: var(--radius-panel, 16px);
  background: #fff;
  transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
  &:hover {
    transform: translateY(-4px);
    border-color: #c9d7f4;
    box-shadow: var(--shadow-card-hover);
  }
  &--support { border-color: #cbd9f8; }
  &.is-focused { border-color: #9bb2ff; box-shadow: 0 0 0 3px rgba(78, 111, 228, .10); }
  h2 { margin: 0 0 8px; color: var(--ink-1, #0F172A); font-size: 22px; letter-spacing: -.02em; }
}
.contact-card__desc {
  min-height: 52px;
  margin: 0;
  color: var(--ink-3, #64748B);
  line-height: 1.65;
}
.contact-card__topics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 24px 0 28px;
  span {
    padding: 7px 10px;
    border: 1px solid #dce5f6;
    border-radius: 999px;
    color: #4d5e7a;
    background: #fff;
    font-size: 13px;
  }
}
.contact-card__email {
  display: block;
  margin-top: auto;
  margin-bottom: 16px;
  color: #09142b;
  font-size: 17px;
  font-weight: 750;
  overflow-wrap: anywhere;
  &:hover { color: #2459cf; text-decoration: none; }
}
.contact-card__actions { display: flex; gap: 10px; }
.contact-card__send,
.contact-card__copy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 45px;
  padding: 0 17px;
  border-radius: 11px;
  cursor: pointer;
  font-family: inherit;
  font-weight: 700;
}
.contact-card__send {
  border: 1px solid #2f6fed;
  color: #fff;
  background: #2f6fed;
  text-decoration: none;
  &:hover { background: #245ed2; text-decoration: none; }
}
.contact-card__copy {
  border: 1px solid #d9e0ea;
  color: #34435d;
  background: #fff;
  &.is-copied { color: #087a4f; border-color: #9bdcc4; background: #effbf6; }
}
.contact-security {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  margin-top: 22px;
  padding: 23px 26px;
  border: 1px solid #e4e9f2;
  border-radius: 18px;
  color: #66748e;
  strong { color: #09142b; }
  a { color: #2459cf; font-weight: 700; white-space: nowrap; }
}

@media (max-width: 900px) {
  .contact-hero, .contact-grid { grid-template-columns: 1fr; }
  .contact-hero { gap: 28px; }
  .contact-hero__tip { padding: 20px 0 0; border-top: 1px solid #e4e9f2; border-left: 0; }
}
@media (max-width: 680px) {
  .contact-page__main { padding-top: 48px; padding-bottom: 68px; }
  .contact-hero h1 { font-size: 42px; }
  .contact-card { padding: 25px; }
  .contact-card__actions, .contact-security { flex-direction: column; align-items: stretch; }
  .contact-card__send, .contact-card__copy { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  .contact-card { transition: none; }
}
</style>
