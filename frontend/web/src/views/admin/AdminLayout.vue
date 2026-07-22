<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <div class="admin-sidebar__brand">
        <HtexLogo :size="22" color="#F8FAFC" />
      </div>
      <nav class="admin-sidebar__nav">
        <section v-for="group in navGroups" :key="group.key" class="admin-sidebar__group">
          <div class="admin-sidebar__group-title">{{ group.label }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="admin-sidebar__link"
            active-class="is-active"
          >
            {{ t(item.label) }}
          </router-link>
        </section>
      </nav>
      <div class="admin-sidebar__foot">
        <div class="admin-sidebar__profile">
          <strong>{{ admin.profile?.username || admin.username || '管理员' }}</strong>
          <span>{{ admin.role || '—' }}</span>
        </div>
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
import HtexLogo from '@/components/HtexLogo.vue'

const { t } = useI18n()
const router = useRouter()
const admin = useAdminStore()

const navItems = computed(() => {
  // W63: navItems 计算前先 hydrate,避免刷新页面时 token 还没回到 store,
  // permissions=[],hasPermission 全 false,菜单短暂没显示又被 push 的闪烁。
  if (!admin.token) admin.hydrate()

  // 调试日志: 第一次算菜单时打印,确认 perm 链路
  if (!navItems.__logged) {
    navItems.__logged = true
    // eslint-disable-next-line no-console
    console.log('[admin-nav] token present?', !!admin.token,
      '| username:', admin.username,
      '| role:', admin.role,
      '| isSuperAdmin:', admin.isSuperAdmin,
      '| perms count:', admin.permissions?.length,
      '| perms:', admin.permissions)
  }

  const items = [
    { path: '/admin/dashboard', label: 'admin.menu_overview', perm: 'dashboard.view' },
    { path: '/admin/analytics', label: 'admin.menu_analytics', perm: 'dashboard.view' },
    { path: '/admin/orders', label: 'admin.menu_orders', perm: 'order.view' },
    { path: '/admin/payments', label: 'admin.menu_payments', perm: 'payment.view' },
  ]
  if (admin.hasPermission('user.view')) {
    items.push({ path: '/admin/users', label: 'admin.menu_users', perm: 'user.view' })
  }
  if (admin.hasPermission('country.manage')) items.push({ path: '/admin/countries', label: 'admin.menu_countries', perm: 'country.manage' })
  if (admin.hasPermission('pricing.manage') || admin.hasPermission('settings')) {
    items.push({ path: '/admin/pricing', label: 'admin.menu_pricing', perm: 'pricing.manage' })
  }
  if (admin.hasPermission('settings')) items.push({ path: '/admin/rate-limit', label: 'admin.menu_settings', perm: 'settings' })
  if (admin.hasPermission('ai_rules.edit')) items.push({ path: '/admin/ai-rules', label: 'admin.menu_ai_rules', perm: 'ai_rules.edit' })
  if (admin.hasPermission('rag.review')) items.push({ path: '/admin/rag-review', label: 'admin.menu_rag_review', perm: 'rag.review' })
  // 文件清理不进后台菜单 — 由定时任务 / 运维脚本处理（见 scripts/backup.py + cleanup cron）
  if (admin.hasPermission('role.manage')) items.push({ path: '/admin/roles', label: 'admin.menu_roles', perm: 'role.manage' })
  if (admin.hasPermission('dashboard.view')) items.push({ path: '/admin/logs', label: 'admin.menu_logs', perm: 'dashboard.view' })
  return items
})

const navGroups = computed(() => {
  const groups = [
    { key: 'operations', label: '运营', paths: ['/admin/dashboard', '/admin/orders', '/admin/payments', '/admin/users'] },
    { key: 'catalog', label: '商品与内容', paths: ['/admin/countries', '/admin/pricing', '/admin/ai-rules', '/admin/rag-review'] },
    { key: 'data', label: '数据', paths: ['/admin/analytics', '/admin/logs'] },
    { key: 'system', label: '系统', paths: ['/admin/rate-limit', '/admin/roles'] },
  ]
  return groups.map(group => ({
    ...group,
    items: navItems.value.filter(item => group.paths.includes(item.path)),
  })).filter(group => group.items.length)
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
  letter-spacing: -.5px;
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
.admin-sidebar__group + .admin-sidebar__group { margin-top: 12px; }
.admin-sidebar__group-title {
  padding: 0 14px 5px;
  color: #64748B;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
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
.admin-sidebar__profile { display: flex; flex-direction: column; gap: 2px; margin-bottom: 10px; }
.admin-sidebar__profile strong { color: #F8FAFC; font-size: 13px; }
.admin-sidebar__profile span { color: #94A3B8; font-size: 11px; }

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
