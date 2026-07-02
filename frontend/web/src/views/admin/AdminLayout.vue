<template>
  <div class="admin-layout">
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

    <router-view />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'

const { t } = useI18n()
const router = useRouter()
const admin = useAdminStore()

const navItems = computed(() => {
  const items = [
    { path: '/admin/dashboard', label: 'admin.menu_overview', perm: 'dashboard' },
    { path: '/admin/orders', label: 'admin.menu_orders', perm: 'orders' },
    { path: '/admin/payments', label: 'admin.menu_payments', perm: 'payments' },
  ]
  if (admin.hasPermission('users')) {
    items.push({ path: '/admin/users', label: 'admin.menu_users', perm: 'users' })
    items.push({ path: '/admin/c-users', label: 'admin.menu_c_users', perm: 'users' })
  }
  if (admin.hasPermission('countries')) items.push({ path: '/admin/countries', label: 'admin.menu_countries', perm: 'countries' })
  if (admin.hasPermission('settings')) {
    items.push({ path: '/admin/rate-limit', label: 'admin.menu_settings', perm: 'settings' })
    items.push({ path: '/admin/ai-rules', label: 'admin.menu_ai_rules', perm: 'settings' })
    items.push({ path: '/admin/rpa-strategy', label: 'admin.menu_rpa_strategy', perm: 'settings' })
    items.push({ path: '/admin/i18n', label: 'admin.menu_i18n', perm: 'settings' })
    items.push({ path: '/admin/cleanup', label: 'admin.menu_cleanup', perm: 'settings' })
  }
  if (admin.hasPermission('dashboard')) items.push({ path: '/admin/logs', label: 'admin.menu_logs', perm: 'dashboard' })
  return items
})

function onLogout() {
  admin.logout()
  router.replace('/admin/login')
}

onMounted(() => {
  admin.hydrate()
  if (!admin.profile) admin.refreshProfile()
})
</script>

<style scoped lang="scss">
.admin-layout {
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
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
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
  flex-shrink: 0;
}

.admin-sidebar__nav {
  display: flex;
  flex-direction: column;
  padding: 12px 8px;
  gap: 2px;
  flex: 1;
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
</style>
