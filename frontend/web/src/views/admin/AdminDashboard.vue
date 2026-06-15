<!--
  AdminDashboard.vue — W14-11
  Minimal admin home / overview placeholder. Shows logged-in profile,
  a small navigation list, and a logout button. Subsequent stories
  (W14-12+) will fill in real metrics and CRUD pages.
-->
<template>
  <div class="admin-dashboard">
    <aside class="admin-sidebar">
      <div class="admin-sidebar__brand">
        <span class="admin-sidebar__mark">A</span>
        <span>{{ t('admin.dashboard') }}</span>
      </div>
      <nav class="admin-sidebar__nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="admin-sidebar__link"
          active-class="is-active"
        >
          {{ t(item.label) }}
        </router-link>
      </nav>
      <div class="admin-sidebar__foot">
        <button class="admin-sidebar__logout" @click="onLogout" data-testid="admin-logout">
          {{ t('admin.logout') }}
        </button>
      </div>
    </aside>

    <main class="admin-main">
      <header class="admin-main__head">
        <h1>{{ t('admin.dashboard') }}</h1>
        <p class="admin-main__hello">
          {{ profile?.display_name || profile?.username || username || 'admin' }}
        </p>
      </header>

      <section class="admin-cards">
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.revenue_month') }}</div>
          <div class="admin-card__value">¥128,460</div>
          <div class="admin-card__delta">+12.4%</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.menu_orders') }}</div>
          <div class="admin-card__value">236</div>
          <div class="admin-card__delta">+8 today</div>
        </AppCard>
        <AppCard class="admin-card">
          <div class="admin-card__label">{{ t('admin.menu_users') }}</div>
          <div class="admin-card__value">1,204</div>
          <div class="admin-card__delta">+34 this week</div>
        </AppCard>
      </section>

      <AppCard class="admin-panel">
        <template #header>
          <h3>{{ t('admin.menu_overview') }}</h3>
        </template>
        <p class="admin-panel__placeholder">
          <!-- placeholder copy — real KPIs/charts arrive in W14-12 -->
          Welcome, <b>{{ profile?.username || username }}</b>. This dashboard will surface orders, users, and RPA health in upcoming stories.
        </p>
        <ul class="admin-panel__links">
          <li><router-link to="/admin/rate-limit">{{ t('admin.menu_settings') }} →</router-link></li>
        </ul>
      </AppCard>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppCard from '@/components/AppCard.vue'
import { useAdminStore } from '@/stores/admin'

const { t } = useI18n()
const router = useRouter()
const admin = useAdminStore()

const profile = computed(() => admin.profile)
const username = computed(() => admin.username)

const navItems = [
  { path: '/admin/dashboard', label: 'admin.menu_overview' },
  { path: '/admin/rate-limit', label: 'admin.menu_settings' }
]

function onLogout() {
  admin.logout()
  router.replace('/admin/login')
}

onMounted(async () => {
  admin.hydrate()
  if (!admin.profile) {
    await admin.refreshProfile()
  }
})
</script>

<style scoped lang="scss">
.admin-dashboard {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 220px 1fr;
  background: #F1F5F9;
}

.admin-sidebar {
  background: #0F172A;
  color: #CBD5E1;
  display: flex;
  flex-direction: column;
  padding: 20px 0;
}

.admin-sidebar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, .06);
  font-weight: 600;
  font-size: 15px;
  color: #F8FAFC;
}

.admin-sidebar__mark {
  width: 28px;
  height: 28px;
  background: #3B6EF5;
  color: #fff;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
}

.admin-sidebar__nav {
  display: flex;
  flex-direction: column;
  padding: 12px 8px;
  gap: 2px;
}

.admin-sidebar__link {
  display: block;
  padding: 9px 14px;
  font-size: 14px;
  color: #CBD5E1;
  text-decoration: none;
  border-radius: 6px;
  transition: background .15s, color .15s;
}

.admin-sidebar__link:hover {
  background: rgba(255, 255, 255, .06);
  color: #F8FAFC;
}

.admin-sidebar__link.is-active {
  background: #3B6EF5;
  color: #fff;
}

.admin-sidebar__foot {
  margin-top: auto;
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, .06);
}

.admin-sidebar__logout {
  width: 100%;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, .15);
  color: #CBD5E1;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all .15s;
}

.admin-sidebar__logout:hover {
  background: rgba(220, 38, 38, .15);
  border-color: rgba(220, 38, 38, .6);
  color: #FCA5A5;
}

.admin-main {
  padding: 28px 32px;
  overflow-y: auto;
}

.admin-main__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 20px;
}

.admin-main__head h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0F172A;
}

.admin-main__hello {
  margin: 0;
  font-size: 13px;
  color: #64748B;
}

.admin-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 22px;
}

.admin-card {
  padding: 16px 18px;
}

.admin-card__label {
  font-size: 12px;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: .5px;
}

.admin-card__value {
  font-size: 26px;
  font-weight: 700;
  color: #0F172A;
  margin: 6px 0 4px;
}

.admin-card__delta {
  font-size: 12px;
  color: #16A34A;
}

.admin-panel__placeholder {
  margin: 0 0 12px;
  font-size: 14px;
  color: #475569;
}

.admin-panel__links {
  margin: 0;
  padding: 0;
  list-style: none;
}

.admin-panel__links a {
  color: #3B6EF5;
  text-decoration: none;
  font-size: 14px;
}

.admin-panel__links a:hover { text-decoration: underline; }
</style>