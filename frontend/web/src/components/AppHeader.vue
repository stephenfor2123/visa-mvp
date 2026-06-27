<template>
  <header class="app-header app-container">
    <router-link to="/home" class="app-header__brand">
      <HtexLogo :size="28" />
    </router-link>
    <nav class="app-header__nav">
      <!-- W31: 3 个产品级 mega menu(deel.com 风格: trigger + 宽 panel) -->
      <div
        v-for="m in megaMenus"
        :key="m.id"
        ref="megaRefs"
        class="mega-menu"
        :class="{ 'is-open': openMega === m.id }"
        @mouseleave="onMegaHoverLeave(m.id)"
      >
        <button
          type="button"
          class="mega-menu__trigger"
          :aria-expanded="openMega === m.id"
          aria-haspopup="menu"
          :aria-label="t(m.triggerKey)"
          :data-testid="`${props.scope}-mega-${m.id}-trigger`"
          @click="toggleMega(m.id)"
          @mouseenter="onMegaHover(m.id)"
          @keydown.esc="closeMega"
        >
          <span>{{ t(m.triggerKey) }}</span>
          <svg
            class="mega-menu__chevron"
            :class="{ 'is-open': openMega === m.id }"
            width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true"
          >
            <path d="M2 4.5 L6 8.5 L10 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <div
          v-show="openMega === m.id"
          class="mega-menu__panel"
          role="menu"
          :data-testid="`${props.scope}-mega-${m.id}-panel`"
        >
          <div class="mega-menu__intro">
            <h3 class="mega-menu__title">{{ t(m.titleKey) }}</h3>
            <p class="mega-menu__desc">{{ t(m.descKey) }}</p>
          </div>
          <div class="mega-menu__grid">
            <router-link
              v-for="(item, i) in m.items"
              :key="i"
              :to="item.to"
              class="mega-menu__item"
              role="menuitem"
              :data-testid="`${props.scope}-mega-${m.id}-item-${i}`"
              @click="closeMega"
            >
              <div class="mega-menu__icon" :class="`mega-menu__icon--${item.tone}`" v-html="item.icon" />
              <div class="mega-menu__item-body">
                <div class="mega-menu__item-name">{{ t(item.nameKey) }}</div>
                <div class="mega-menu__item-desc">{{ t(item.descKey) }}</div>
              </div>
            </router-link>
          </div>
        </div>
      </div>
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
      <!-- W28 P2: 全屏国家搜索弹窗 trigger -->
      <button
        type="button"
        class="search-trigger"
        :title="t('cs.open_search') || 'Search a country'"
        :aria-label="t('cs.open_search') || 'Search a country'"
        :data-testid="`${props.scope}-search-trigger`"
        @click="openSearchModal"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/>
          <path d="M20 20 L16.5 16.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
      <!-- W28: On Time Guaranteed 蓝色盾牌徽章(借鉴 atlys 信任徽章) -->
      <div
        class="trust-badge"
        :title="t('trust.on_time_tip')"
        :data-testid="`${props.scope}-trust-badge`"
      >
        <svg class="trust-badge__shield" viewBox="0 0 24 28" width="18" height="22" aria-hidden="true">
          <defs>
            <linearGradient id="trust-shield-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stop-color="#3B6EF5"/>
              <stop offset="100%" stop-color="#2553D6"/>
            </linearGradient>
          </defs>
          <path d="M12 1 L22 5 V13 C22 19.5 17.5 24.5 12 27 C6.5 24.5 2 19.5 2 13 V5 Z"
                fill="url(#trust-shield-grad)" stroke="#1E40AF" stroke-width=".6"/>
          <path d="M7.5 14 L11 17.5 L17 11.5" fill="none" stroke="#fff" stroke-width="2.4"
                stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="trust-badge__text">{{ t('trust.on_time') }}</span>
      </div>
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
  <CountrySearchModal :open="searchModalOpen" @close="closeSearchModal" />
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import HtexLogo from '@/components/HtexLogo.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import AppButton from '@/components/AppButton.vue'
import CountrySearchModal from '@/components/CountrySearchModal.vue'
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
  document.addEventListener('click', onMegaDocClick)
  document.addEventListener('keydown', onMegaDocKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKey)
  document.removeEventListener('click', onMegaDocClick)
  document.removeEventListener('keydown', onMegaDocKey)
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

// ============== W28 P2: Country search modal ==============
const searchModalOpen = ref(false)
function openSearchModal() { searchModalOpen.value = true }
function closeSearchModal() { searchModalOpen.value = false }

// ============== W31: 3 个产品级 mega menu (deel.com 风格) ==============
// 1. 签证办理 — 选国家 → RAG 拉材料清单 → 上传/OCR → 跳 OrderNew
// 2. 数据诊断 — 选国家 → 个人条件表单 → 签率综合判断
// 3. 资源中心 — RAG FAQ + 政策查询 + 材料模板
const SVG_DOC = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 3h11l4 4v14H5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M16 3v4h4" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 12h7M9 16h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`
const SVG_CHART = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 20V8M10 20V4M16 20v-9M22 20H2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`
const SVG_UPLOAD = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 18v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`
const SVG_SCAN = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M3 10h18M8 5V3M16 5V3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="12" cy="14.5" r="2.4" stroke="currentColor" stroke-width="1.6"/></svg>`
const SVG_BOOK = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 4h12a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3V4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M4 17a3 3 0 0 1 3-3h12" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`
const SVG_PULSE = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 12h4l2-7 4 14 2-7h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`
const SVG_USERS = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="9" cy="9" r="3.4" stroke="currentColor" stroke-width="1.6"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="17" cy="8" r="2.6" stroke="currentColor" stroke-width="1.6"/><path d="M15 14.5c2.5 0 4.5 1.8 4.5 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`
const SVG_QUESTION = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6"/><path d="M9.5 9a2.5 2.5 0 0 1 5 .2c0 1.5-2.5 2-2.5 3.3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="12" cy="16.5" r="1" fill="currentColor"/></svg>`
const SVG_GLOBE = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" stroke="currentColor" stroke-width="1.6"/></svg>`
const SVG_FILE = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 2h9l5 5v15H6z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M14 2v6h6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 14h7M9 18h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`

// W31: contact icons
const SVG_MAIL = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M3 7l9 6 9-6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`
const SVG_PHONE = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 4h3l2 5-2 1a11 11 0 0 0 6 6l1-2 5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`
const SVG_WECHAT = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 4C5 4 2 6.7 2 10c0 1.7.8 3.3 2 4.3l-.5 2 2.2-1.1c.7.2 1.4.3 2.3.3.3 0 .5 0 .8-.1a5.4 5.4 0 0 1 5.4-5.4c.3 0 .6 0 .9.1C14.5 6.5 12 4 9 4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="6.5" cy="9" r="0.8" fill="currentColor"/><circle cx="10" cy="9" r="0.8" fill="currentColor"/><path d="M22 14.5c0-2.8-2.5-5-5.5-5s-5.5 2.2-5.5 5 2.5 5 5.5 5c.6 0 1.2-.1 1.7-.2l1.8.9-.4-1.6c1.4-.9 2.4-2.4 2.4-4.1z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="14.5" cy="14" r="0.7" fill="currentColor"/><circle cx="17.5" cy="14" r="0.7" fill="currentColor"/></svg>`
const SVG_WHATSAPP = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3.5 20.5l1-3.6A8.5 8.5 0 1 1 7 19.5l-3.5 1z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 9.5c.5-.5 1-.5 1.4 0l.7 1c.4.5.4.8 0 1.2l-.4.4c.5 1 1.3 1.8 2.3 2.3l.4-.4c.4-.4.7-.4 1.2 0l1 .7c.5.4.5.9 0 1.4l-.5.5c-.7.7-2 .5-3.5-.5-2-1.3-3.4-2.8-3.7-3.7-.4-1.2-.5-2.3 0-3z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`

const megaMenus = [
  {
    id: 'apply',
    triggerKey: 'nav.mega.apply',
    titleKey: 'nav.mega.apply_title',
    descKey: 'nav.mega.apply_desc',
    items: [
      { to: '/apply',           nameKey: 'nav.mega.apply_i1', descKey: 'nav.mega.apply_i1_d', icon: SVG_DOC,     tone: 'blue' },
      { to: '/apply?step=ocr',  nameKey: 'nav.mega.apply_i2', descKey: 'nav.mega.apply_i2_d', icon: SVG_SCAN,    tone: 'indigo' },
      { to: '/apply?step=upload', nameKey: 'nav.mega.apply_i3', descKey: 'nav.mega.apply_i3_d', icon: SVG_UPLOAD,  tone: 'cyan' },
    ],
  },
  {
    id: 'diagnose',
    triggerKey: 'nav.mega.diagnose',
    titleKey: 'nav.mega.diagnose_title',
    descKey: 'nav.mega.diagnose_desc',
    items: [
      { to: '/diagnose',        nameKey: 'nav.mega.diagnose_i1', descKey: 'nav.mega.diagnose_i1_d', icon: SVG_PULSE,  tone: 'green' },
      { to: '/diagnose?focus=income',  nameKey: 'nav.mega.diagnose_i2', descKey: 'nav.mega.diagnose_i2_d', icon: SVG_CHART,  tone: 'emerald' },
      { to: '/diagnose?focus=history', nameKey: 'nav.mega.diagnose_i3', descKey: 'nav.mega.diagnose_i3_d', icon: SVG_USERS,  tone: 'teal' },
    ],
  },
  {
    id: 'resources',
    triggerKey: 'nav.mega.resources',
    titleKey: 'nav.mega.resources_title',
    descKey: 'nav.mega.resources_desc',
    items: [
      { to: '/resources',       nameKey: 'nav.mega.resources_i1', descKey: 'nav.mega.resources_i1_d', icon: SVG_BOOK,     tone: 'amber' },
      { to: '/resources?focus=policy',  nameKey: 'nav.mega.resources_i2', descKey: 'nav.mega.resources_i2_d', icon: SVG_GLOBE,    tone: 'orange' },
      { to: '/resources?focus=template', nameKey: 'nav.mega.resources_i3', descKey: 'nav.mega.resources_i3_d', icon: SVG_FILE,    tone: 'rose' },
      { to: '/resources?focus=faq',     nameKey: 'nav.mega.resources_i4', descKey: 'nav.mega.resources_i4_d', icon: SVG_QUESTION, tone: 'pink' },
    ],
  },
  {
    id: 'contact',
    triggerKey: 'nav.mega.contact',
    titleKey: 'nav.mega.contact_title',
    descKey: 'nav.mega.contact_desc',
    items: [
      { to: '/contact',         nameKey: 'nav.mega.contact_i1', descKey: 'nav.mega.contact_i1_d', icon: SVG_MAIL,     tone: 'blue' },
      { to: '/contact?focus=phone',    nameKey: 'nav.mega.contact_i2', descKey: 'nav.mega.contact_i2_d', icon: SVG_PHONE,    tone: 'emerald' },
      { to: '/contact?focus=wechat',   nameKey: 'nav.mega.contact_i3', descKey: 'nav.mega.contact_i3_d', icon: SVG_WECHAT,   tone: 'green' },
      { to: '/contact?focus=whatsapp', nameKey: 'nav.mega.contact_i4', descKey: 'nav.mega.contact_i4_d', icon: SVG_WHATSAPP, tone: 'teal' },
    ],
  },
]

const openMega = ref(null)  // 当前打开的 mega menu id
function toggleMega(id) {
  openMega.value = openMega.value === id ? null : id
}
function closeMega() {
  openMega.value = null
}
function onMegaHover(id) {
  // desktop 上 hover 展开, 离开后保留 click 状态 — 用 setTimeout 延迟 close 防止 jitter
  openMega.value = id
}
let _leaveTimer = null
function onMegaHoverLeave(id) {
  if (_leaveTimer) clearTimeout(_leaveTimer)
  _leaveTimer = setTimeout(() => {
    if (openMega.value === id) closeMega()
  }, 180)
}
function onMegaDocClick(e) {
  if (!openMega.value) return
  // 关掉所有非自身内的点击
  const roots = document.querySelectorAll('.mega-menu.is-open')
  for (const r of roots) {
    if (r.contains(e.target)) return
  }
  closeMega()
}
function onMegaDocKey(e) {
  if (e.key === 'Escape' && openMega.value) closeMega()
}

</script>

<style scoped lang="scss">
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  background: #fff;
  gap: 24px;
  position: relative;
}

// ============== W31: Mega menu (deel.com 风格) ==============
.mega-menu {
  position: relative;
  &__trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: 0;
    color: #0f172a;
    font-size: 14px;
    font-weight: 500;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: background .15s ease;
    &:hover { background: #f1f5f9; }
  }
  &__chevron {
    transition: transform .2s ease;
    color: #64748b;
    &.is-open { transform: rotate(180deg); }
  }
  &__panel {
    position: absolute;
    top: calc(100% + 8px);
    left: -16px;
    min-width: 480px;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    box-shadow: 0 24px 48px -16px rgba(15, 23, 42, .14), 0 4px 12px rgba(15, 23, 42, .04);
    padding: 20px 22px;
    z-index: 50;
    animation: megaIn .18s ease-out;
  }
  &__intro {
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid #f1f5f9;
  }
  &__title {
    font-size: 15px;
    font-weight: 600;
    margin: 0 0 4px;
    color: #0f172a;
  }
  &__desc {
    font-size: 12px;
    color: #64748b;
    margin: 0;
    line-height: 1.5;
  }
  &__grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
  }
  &__item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 10px;
    border-radius: 10px;
    text-decoration: none;
    color: inherit;
    transition: background .12s ease;
    &:hover { background: #f8fafc; }
  }
  &__icon {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #eef2ff;
    color: #3b6ef5;
    :deep(svg) { width: 18px; height: 18px; }
    &--blue    { background: #eef2ff; color: #3b6ef5; }
    &--indigo  { background: #e0e7ff; color: #4f46e5; }
    &--cyan    { background: #cffafe; color: #0891b2; }
    &--green   { background: #dcfce7; color: #16a34a; }
    &--emerald { background: #d1fae5; color: #059669; }
    &--teal    { background: #ccfbf1; color: #0d9488; }
    &--amber   { background: #fef3c7; color: #d97706; }
    &--orange  { background: #ffedd5; color: #ea580c; }
    &--rose    { background: #ffe4e6; color: #e11d48; }
    &--pink    { background: #fce7f3; color: #db2777; }
  }
  &__item-body {
    min-width: 0;
    flex: 1;
  }
  &__item-name {
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 2px;
  }
  &__item-desc {
    font-size: 11.5px;
    color: #64748b;
    line-height: 1.45;
  }
}
@keyframes megaIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
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

/* ============== Search trigger (W28 P2) ============== */
.search-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--border, #E2E8F0);
  color: var(--ink-2, #334155);
  background: #fff;
  cursor: pointer;
  transition: border-color .15s, color .15s, background .15s, box-shadow .15s;
}
.search-trigger:hover {
  border-color: var(--el-color-primary, #3B6EF5);
  color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .06);
  box-shadow: 0 2px 8px rgba(59, 110, 245, .12);
}
.search-trigger:focus-visible {
  outline: 2px solid var(--el-color-primary, #3B6EF5);
  outline-offset: 2px;
}
.search-trigger svg { display: block; }

/* ============== On Time Guaranteed 信任徽章(W28) ============== */
.trust-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px 6px 8px;
  background: linear-gradient(135deg, #EFF4FF 0%, #DBE6FE 100%);
  border: 1px solid #BFD3FE;
  border-radius: 999px;
  color: #1E40AF;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: .2px;
  white-space: nowrap;
  box-shadow: 0 1px 3px rgba(30, 64, 175, .08);
  transition: transform .15s ease, box-shadow .15s ease;
}
.trust-badge:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(30, 64, 175, .16);
}
.trust-badge__shield {
  flex: 0 0 18px;
  display: block;
  filter: drop-shadow(0 1px 1px rgba(30, 64, 175, .25));
}
.trust-badge__text {
  font-feature-settings: 'tnum';
}
@media (max-width: 768px) {
  .trust-badge { padding: 5px 8px; }
  .trust-badge__text { display: none; }  /* 小屏只显示盾牌 icon,省空间 */
}
@media (max-width: 480px) {
  .trust-badge { display: none; }  /* 超小屏整组隐藏 */
}
</style>
