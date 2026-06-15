<template>
  <div class="profile-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <span class="app-header__brand-mark">V</span>
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <nav class="app-header__nav">
        <router-link to="/home">{{ t('nav.home') }}</router-link>
        <router-link to="/profile">{{ t('nav.profile') }}</router-link>
      </nav>
      <div class="app-header__right">
        <LangSwitch />
        <AppButton variant="outline" size="sm" @click="onLogout">{{ t('nav.logout') }}</AppButton>
      </div>
    </header>

    <main class="app-container app-page">
      <h1 class="section-title">{{ t('profile.page_title') }}</h1>
      <p class="section-sub">{{ t('profile.wip_notice') }}</p>

      <AppCard v-if="user">
        <template #header>
          <h3 style="margin:0;font-size:16px;font-weight:600">{{ user.nickname }}</h3>
          <p style="margin:4px 0 0;font-size:13px;color:var(--ink-3)">
            {{ user.phoneCountry }} {{ user.phone }}
          </p>
        </template>
        <dl class="info-list">
          <div class="info-list__row"><dt>{{ t('profile.user_id') }}</dt><dd>{{ user.id }}</dd></div>
          <div class="info-list__row"><dt>{{ t('profile.language_pref') }}</dt><dd>{{ user.languagePref }}</dd></div>
          <div class="info-list__row"><dt>{{ t('profile.registered_at') }}</dt><dd>{{ formatDate(user.createdAt) }}</dd></div>
          <div class="info-list__row"><dt>{{ t('profile.status') }}</dt><dd><span class="badge badge--success">{{ t('profile.active') }}</span></dd></div>
        </dl>
      </AppCard>
      <AppCard v-else>
        <p>{{ t('profile.no_user_info') }}</p>
        <AppButton variant="primary" size="md" @click="$router.push('/login')">{{ t('profile.go_login') }}</AppButton>
      </AppCard>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
auth.hydrate()
const user = computed(() => auth.user)
const toast = useToast()

function formatDate(s) {
  if (!s) return '-'
  try { return new Date(s).toLocaleString() } catch { return s }
}

function onLogout() {
  auth.logout()
  toast.success(t('toast.logout_success'))
  router.push('/login')
}
</script>

<style scoped lang="scss">
.info-list { margin: 0; padding: 0; }
.info-list__row {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--border);
  font-size: 14px;
}
.info-list__row:last-child { border-bottom: none; }
.info-list__row dt { color: var(--ink-3); margin: 0; }
.info-list__row dd { color: var(--ink-1); margin: 0; font-weight: 500; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}
.badge--success { background: #DCFCE7; color: #166534; }
</style>