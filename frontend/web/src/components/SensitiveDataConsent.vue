<!-- SensitiveDataConsent — 上传护照/照片/银行流水前的明示同意 -->
<template>
  <Transition name="fade">
    <div v-if="open" class="sdc-overlay" role="dialog" aria-modal="true" data-testid="sensitive-consent">
      <div class="sdc-modal">
        <h2 class="sdc-modal__title">{{ t('privacy_consent.title') }}</h2>
        <p class="sdc-modal__body">{{ t('privacy_consent.body') }}</p>
        <ul class="sdc-modal__list">
          <li>{{ t('privacy_consent.item_passport') }}</li>
          <li>{{ t('privacy_consent.item_photo') }}</li>
          <li>{{ t('privacy_consent.item_financial') }}</li>
        </ul>
        <p class="sdc-modal__note">
          {{ t('privacy_consent.privacy_link_prefix') }}
          <router-link to="/agreement?tab=privacy" @click="onPrivacyClick">
            {{ t('privacy_consent.privacy_link') }}
          </router-link>
        </p>
        <div class="sdc-modal__actions">
          <button class="sdc-btn sdc-btn--ghost" type="button" @click="$emit('cancel')">
            {{ t('privacy_consent.cancel') }}
          </button>
          <button class="sdc-btn sdc-btn--primary" type="button" data-testid="sensitive-consent-accept" @click="$emit('accept')">
            {{ t('privacy_consent.accept') }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['accept', 'cancel'])
const { t } = useI18n()

function onPrivacyClick() {
  emit('cancel')
}
</script>

<style scoped>
.sdc-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.sdc-modal {
  background: #fff;
  border-radius: 12px;
  max-width: 440px;
  width: 100%;
  padding: 24px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.18);
}
.sdc-modal__title {
  margin: 0 0 12px;
  font-size: 17px;
  font-weight: 700;
  color: #1a1a2e;
}
.sdc-modal__body {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.6;
  color: #4b5563;
}
.sdc-modal__list {
  margin: 0 0 12px;
  padding-left: 20px;
  font-size: 13px;
  color: #4b5563;
  line-height: 1.7;
}
.sdc-modal__note {
  margin: 0 0 20px;
  font-size: 12px;
  color: #6b7280;
}
.sdc-modal__note a {
  color: var(--color-primary, #3b6ef5);
}
.sdc-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.sdc-btn {
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
}
.sdc-btn--ghost {
  background: #f3f4f6;
  color: #374151;
}
.sdc-btn--primary {
  background: var(--color-primary, #3b6ef5);
  color: #fff;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
