<template>
  <header class="app-header app-container">
    <router-link to="/home" class="app-header__brand">
      <HtexLogo :size="28" />
    </router-link>
    <nav class="app-header__nav">
      <!-- 我的申请 - 下拉子菜单(仅登录后显示) -->
      <div
        v-if="auth.isLoggedIn"
        ref="ordersMenuRef"
        class="orders-menu"
        :class="{ 'is-open': ordersMenuOpen }"
      >
        <button
          type="button"
          class="orders-menu__trigger"
          :aria-expanded="ordersMenuOpen"
          aria-haspopup="menu"
          :aria-label="t('nav.orders')"
          :data-testid="`${props.scope}-orders-trigger`"
          @click="toggleOrdersMenu"
          @keydown.esc="closeOrdersMenu"
        >
          <span>{{ t('nav.orders') }}</span>
          <svg
            class="orders-menu__chevron"
            :class="{ 'is-open': ordersMenuOpen }"
            width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true"
          >
            <path d="M2 4.5 L6 8.5 L10 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <div
          v-show="ordersMenuOpen"
          class="orders-menu__panel"
          role="menu"
          :data-testid="`${props.scope}-orders-panel`"
        >
          <router-link
            to="/orders"
            class="orders-menu__item"
            role="menuitem"
            :data-testid="`${props.scope}-orders-all`"
            @click="closeOrdersMenu"
          >
            <svg class="orders-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 6h18M3 12h18M3 18h12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            <span>{{ t('nav.orders_menu.all') }}</span>
          </router-link>
          <router-link
            to="/orders/new"
            class="orders-menu__item"
            role="menuitem"
            :data-testid="`${props.scope}-orders-new`"
            @click="closeOrdersMenu"
          >
            <svg class="orders-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            <span>{{ t('nav.orders_menu.new_order') }}</span>
          </router-link>
          <div class="orders-menu__divider" role="separator" />
          <router-link
            to="/profile"
            class="orders-menu__item"
            role="menuitem"
            :data-testid="`${props.scope}-orders-profile`"
            @click="closeOrdersMenu"
          >
            <svg class="orders-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.8"/>
              <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            <span>{{ t('nav.orders_menu.profile') }}</span>
          </router-link>
          <router-link
            to="/materials"
            class="orders-menu__item"
            role="menuitem"
            :data-testid="`${props.scope}-orders-materials`"
            @click="closeOrdersMenu"
          >
            <svg class="orders-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 4h11l3 3v13H5z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
              <path d="M9 10h8M9 14h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            <span>{{ t('nav.orders_menu.materials') }}</span>
          </router-link>
        </div>
      </div>
    </nav>
    <div class="app-header__right">
      <ThemeToggle />
      <LangSwitch />
      <router-link
        to="/profile"
        class="app-header__profile-link"
        :title="t('nav.profile')"
        :aria-label="t('nav.profile')"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.8"/>
          <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      </router-link>
      <AppButton
        v-if="!auth.isLoggedIn"
        variant="primary"
        size="sm"
        :data-testid="loginTestId"
        @click="onLogin"
      >
        {{ t('nav.login') }}
      </AppButton>
      <AppButton
        v-else
        variant="outline"
        size="sm"
        :data-testid="logoutTestId"
        @click="onLogout"
      >
        {{ t('nav.logout') }}
      </AppButton>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import HtexLogo from '@/components/HtexLogo.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  /**
   * Page-specific testid suffix so multiple pages can each have their own
   * login/logout button locator in e2e specs (e.g. "home-login" vs "orders-login").
   * Falls back to "header" if no context is provided.
   */
  scope: { type: String, default: 'header' },
})

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

// ============== 我的申请 下拉子菜单 ==============
const ordersMenuOpen = ref(false)
const ordersMenuRef = ref(null)

function toggleOrdersMenu() {
  ordersMenuOpen.value = !ordersMenuOpen.value
}
function closeOrdersMenu() {
  ordersMenuOpen.value = false
}
function onDocClick(e) {
  if (!ordersMenuOpen.value) return
  const root = ordersMenuRef.value
  if (root && !root.contains(e.target)) closeOrdersMenu()
}
function onDocKey(e) {
  if (e.key === 'Escape' && ordersMenuOpen.value) closeOrdersMenu()
}

// Re-hydrate from localStorage in case the parent view didn't (e.g. when this
// is the first component to mount on a hard reload). Idempotent — `hydrate`
// short-circuits if `user.value` is already set.
onMounted(() => {
  try { auth.hydrate() } catch (_) {}
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onDocKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKey)
})

const loginTestId = computed(() => `${props.scope}-login`)
const logoutTestId = computed(() => `${props.scope}-logout`)

function onLogin() {
  router.push({ name: 'Login' })
}

function onLogout() {
  auth.logout()
  try { toast.success(t('toast.logout_success')) } catch (_) {}
  router.push('/home')
}
</script>

<style scoped lang="scss">
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid var(--border, #E2E8F0);
  background: #fff;
  gap: 24px;
}

.app-header__brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 18px;
  color: var(--ink-1, #0F172A);
  text-decoration: none;
}

.app-header__nav {
  display: flex;
  gap: 22px;
  font-size: 14px;
  color: var(--ink-2, #334155);
  flex: 1;
  margin-left: 32px;
}

.app-header__nav :deep(a) {
  color: var(--ink-2, #334155);
  text-decoration: none;
  transition: color .15s;
}
.app-header__nav :deep(a:hover) {
  color: var(--el-color-primary, #3B6EF5);
}
.app-header__nav :deep(a.router-link-active) {
  color: var(--el-color-primary, #3B6EF5);
  font-weight: 600;
}

/* ============== 我的申请 下拉子菜单 ============== */
.orders-menu {
  position: relative;
}
.orders-menu__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 4px;
  background: transparent;
  border: 0;
  color: var(--ink-2, #334155);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
  border-radius: 6px;
  transition: color .15s, background .15s;
}
.orders-menu__trigger:hover,
.orders-menu.is-open .orders-menu__trigger {
  color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .06);
}
.orders-menu__trigger:focus-visible {
  outline: 2px solid var(--el-color-primary, #3B6EF5);
  outline-offset: 2px;
}
.orders-menu__chevron {
  display: block;
  transition: transform .2s ease;
}
.orders-menu__chevron.is-open {
  transform: rotate(180deg);
}
.orders-menu__panel {
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  min-width: 220px;
  padding: 6px;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, .14), 0 2px 6px rgba(15, 23, 42, .06);
  z-index: 1000;
  animation: ordersMenuIn .18s ease-out;
}
@keyframes ordersMenuIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.orders-menu__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  color: var(--ink-1, #0F172A);
  text-decoration: none;
  font-size: 14px;
  transition: background .15s, color .15s;
  cursor: pointer;
}
.orders-menu__item:hover {
  background: rgba(59, 110, 245, .08);
  color: var(--el-color-primary, #3B6EF5);
}
.orders-menu__item.router-link-active {
  background: rgba(59, 110, 245, .12);
  color: var(--el-color-primary, #3B6EF5);
  font-weight: 600;
}
.orders-menu__item:focus-visible {
  outline: 2px solid var(--el-color-primary, #3B6EF5);
  outline-offset: -2px;
}
.orders-menu__icon {
  flex: 0 0 16px;
  color: var(--ink-3, #64748B);
  transition: color .15s;
}
.orders-menu__item:hover .orders-menu__icon,
.orders-menu__item.router-link-active .orders-menu__icon {
  color: var(--el-color-primary, #3B6EF5);
}
.orders-menu__divider {
  height: 1px;
  margin: 6px 4px;
  background: var(--border, #E2E8F0);
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__profile-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--border, #E2E8F0);
  color: var(--ink-2, #334155);
  text-decoration: none;
  background: #fff;
  transition: border-color .15s, color .15s, background .15s, box-shadow .15s;
}
.app-header__profile-link:hover {
  border-color: var(--el-color-primary, #3B6EF5);
  color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .06);
}
.app-header__profile-link.router-link-active {
  border-color: var(--el-color-primary, #3B6EF5);
  color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .08);
}
.app-header__profile-link svg { display: block; }

[data-theme="dark"] .app-header {
  background: var(--bg, #0F172A);
  border-bottom-color: var(--border, #1E293B);
}
[data-theme="dark"] .app-header__profile-link {
  background: transparent;
  color: var(--ink-2, #CBD5E1);
}

[data-theme="dark"] .orders-menu__trigger {
  color: var(--ink-2, #CBD5E1);
}
[data-theme="dark"] .orders-menu__trigger:hover,
[data-theme="dark"] .orders-menu.is-open .orders-menu__trigger {
  color: var(--el-color-primary, #6E59F0);
  background: rgba(110, 89, 240, .12);
}
[data-theme="dark"] .orders-menu__panel {
  background: var(--bg, #0F172A);
  border-color: var(--border, #1E293B);
  box-shadow: 0 12px 32px rgba(0, 0, 0, .4), 0 2px 6px rgba(0, 0, 0, .2);
}
[data-theme="dark"] .orders-menu__item {
  color: var(--ink-2, #CBD5E1);
}
[data-theme="dark"] .orders-menu__item:hover,
[data-theme="dark"] .orders-menu__item.router-link-active {
  background: rgba(110, 89, 240, .12);
  color: var(--el-color-primary, #A5B4FC);
}
[data-theme="dark"] .orders-menu__icon {
  color: var(--ink-3, #94A3B8);
}
[data-theme="dark"] .orders-menu__divider {
  background: var(--border, #1E293B);
}
</style>
