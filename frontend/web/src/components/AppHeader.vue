<template>
  <header ref="headerEl" class="app-header">
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
      </div>
    </nav>

    <!-- W47c: panel 用 Teleport 渲染到 body，避免污染 .app-header 的 flex 布局。
         原来把 panel 放到 .app-header 直接子元素，会被 flex 计入 item 数（即使 absolute 也会影响宽度计算），
         导致 home / apply 页面 header 看起来"差不多但有微小差异"。Teleport 到 body 后彻底脱流。
         用 inline style 实时同步 header 的 left/right（panel 视觉上仍跟着 header 左右边界走）。 -->
    <Teleport to="body">
      <div
        v-for="m in megaMenus"
        v-show="openMega === m.id"
        :key="`panel-${m.id}`"
        class="mega-menu__panel mega-menu__panel--teleported"
        role="menu"
        :data-testid="`${props.scope}-mega-${m.id}-panel`"
        :style="panelStyle"
        @mouseenter="onPanelEnter(m.id)"
      >
      <div class="mega-menu__intro">
        <h3 class="mega-menu__title">{{ t(m.titleKey) }}</h3>
        <p class="mega-menu__desc">{{ t(m.descKey) }}</p>
      </div>
      <div class="mega-menu__grid" :class="m.gridClass">
        <router-link
          v-for="(item, i) in m.items"
          :key="i"
          :to="item.to"
          class="mega-menu__item"
          role="menuitem"
          :data-testid="`${props.scope}-mega-${m.id}-item-${i}`"
          @click="closeMega"
        >
          <div class="mega-menu__item-body">
            <div class="mega-menu__item-name">
              <span class="mega-menu__item-num">{{ i + 1 }}</span>{{ t(item.nameKey) }}
            </div>
            <div class="mega-menu__item-desc">{{ t(item.descKey) }}</div>
          </div>
        </router-link>
      </div>
    </div>
    </Teleport>
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
      <!-- W57: 加密隐私保护徽章 — 点击弹出 popover(简化:仅大锁+标题+副标题+CTA,W57b) -->
      <TrustBadgePopover :scope="props.scope" learn-more-to="/security" />
      <LangSwitch />
      <!-- W47: 人物头像下拉菜单(整合"我的申请" + profile + 退出登录) -->
      <div
        v-if="auth.isLoggedIn"
        ref="userMenuRef"
        class="user-menu"
        :class="{ 'is-open': userMenuOpen }"
      >
        <button
          type="button"
          class="user-menu__trigger"
          :aria-expanded="userMenuOpen"
          aria-haspopup="menu"
          :aria-label="t('nav.profile')"
          :data-testid="`${props.scope}-user-trigger`"
          @click="toggleUserMenu"
          @keydown.esc="closeUserMenu"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.8"/>
            <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          <svg class="user-menu__chevron" :class="{ 'is-open': userMenuOpen }" width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M2 4.5 L6 8.5 L10 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <div
          v-show="userMenuOpen"
          class="user-menu__panel"
          role="menu"
          :data-testid="`${props.scope}-user-panel`"
        >
          <!-- 顶部申请人列表已挪到 /profile 个人中心(W59) — 弹窗只保留 4 个工具入口 -->

          <div class="user-menu__divider" role="separator" />

          <!-- 我的申请 子菜单 -->
          <router-link
            to="/orders"
            class="user-menu__item"
            role="menuitem"
            :data-testid="`${props.scope}-user-orders-all`"
            @click="closeUserMenu"
          >
            <svg class="user-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 6h18M3 12h18M3 18h12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            <span>{{ t('nav.orders_menu.all') }}</span>
          </router-link>
          <router-link
            to="/destinations"
            class="user-menu__item"
            role="menuitem"
            :data-testid="`${props.scope}-user-orders-new`"
            @click="closeUserMenu"
          >
            <svg class="user-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            <span>{{ t('nav.orders_menu.new_order') }}</span>
          </router-link>

          <div class="user-menu__divider" role="separator" />

          <router-link
            to="/profile"
            class="user-menu__item"
            role="menuitem"
            :data-testid="`${props.scope}-user-profile`"
            @click="closeUserMenu"
          >
            <svg class="user-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.8"/>
              <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
            <span>{{ t('nav.profile') }}</span>
          </router-link>
          <button
            type="button"
            class="user-menu__item user-menu__item--danger"
            role="menuitem"
            :data-testid="`${props.scope}-user-logout`"
            @click="onLogout"
          >
            <svg class="user-menu__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M14 4h-7a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              <path d="M16 8l4 4-4 4M20 12H9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>{{ t('nav.logout') }}</span>
          </button>
        </div>
      </div>
      <AppButton
        v-else
        variant="primary"
        size="sm"
        :data-testid="loginTestId"
        @click="onLogin"
      >
        {{ t('nav.login') }}
      </AppButton>
    </div>
  </header>
  <CountrySearchModal :open="searchModalOpen" @close="closeSearchModal" />
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import HtexLogo from '@/components/HtexLogo.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import AppButton from '@/components/AppButton.vue'
import CountrySearchModal from '@/components/CountrySearchModal.vue'
import TrustBadgePopover from '@/components/TrustBadgePopover.vue'
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

// ============== 用户菜单(W47:整合"我的申请" + profile + 退出登录) ==============
// W59: 顶部申请人列表已挪到 /profile 个人中心,弹窗只保留 4 个工具入口
const userMenuOpen = ref(false)
const userMenuRef = ref(null)

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}
function closeUserMenu() {
  userMenuOpen.value = false
}
function onDocClick(e) {
  if (!userMenuOpen.value) return
  const root = userMenuRef.value
  if (root && !root.contains(e.target)) closeUserMenu()
}
function onDocKey(e) {
  if (e.key === 'Escape' && userMenuOpen.value) closeUserMenu()
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

// ============== W47c: Teleport panel 跟随 header 位置 ==============
const headerEl = ref(null)
const scrollTick = ref(0)
const panelStyle = computed(() => {
  // scrollTick 让 scroll/resize 触发重算
  void scrollTick.value
  if (!headerEl.value) return {}
  const rect = headerEl.value.getBoundingClientRect()
  const headerBottom = rect.bottom + 8
  return {
    left: `${rect.left}px`,
    right: `${window.innerWidth - rect.right}px`,
    top: `${headerBottom}px`,
  }
})
function syncPanelOnScroll() {
  scrollTick.value++
}
onMounted(() => {
  window.addEventListener('scroll', syncPanelOnScroll, { passive: true })
  window.addEventListener('resize', syncPanelOnScroll)
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', syncPanelOnScroll)
  window.removeEventListener('resize', syncPanelOnScroll)
})

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

const SVG_MAIL = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M3 7l9 6 9-6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`

const megaMenus = [
  {
    id: 'apply',
    triggerKey: 'nav.mega.apply',
    titleKey: 'nav.mega.apply_title',
    descKey: 'nav.mega.apply_desc',
    // W55: 6 大产品卖点 3×2 布局 — 替代原 1-3 步流程
    gridClass: 'mega-menu__grid--3col',
    items: [
      // W55: 6 大产品卖点 — 替代原 1-3 步流程
      // 1. 材料清单(实时获取) 2. OCR 智能识别 3. 签证模版
      // 4. 一键生成行程单   5. 母语填写     6. 智能审核
      { to: '/destinations',   nameKey: 'nav.mega.apply_i1', descKey: 'nav.mega.apply_i1_d', icon: SVG_DOC,     tone: 'blue' },
      { to: '/apply?step=ocr',  nameKey: 'nav.mega.apply_i2', descKey: 'nav.mega.apply_i2_d', icon: SVG_SCAN,    tone: 'indigo' },
      { to: '/resources/templates', nameKey: 'nav.mega.apply_i3', descKey: 'nav.mega.apply_i3_d', icon: SVG_FILE, tone: 'cyan' },
      { to: '/apply?step=itinerary', nameKey: 'nav.mega.apply_i4', descKey: 'nav.mega.apply_i4_d', icon: SVG_GLOBE, tone: 'amber' },
      { to: '/apply?step=lang',      nameKey: 'nav.mega.apply_i5', descKey: 'nav.mega.apply_i5_d', icon: SVG_BOOK, tone: 'emerald' },
      { to: '/apply?step=review',    nameKey: 'nav.mega.apply_i6', descKey: 'nav.mega.apply_i6_d', icon: SVG_PULSE, tone: 'rose' },
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
      { to: '/resources/wiki',      nameKey: 'nav.mega.resources_i1', descKey: 'nav.mega.resources_i1_d', icon: SVG_BOOK,     tone: 'amber' },
      { to: '/resources/policy',    nameKey: 'nav.mega.resources_i2', descKey: 'nav.mega.resources_i2_d', icon: SVG_GLOBE,    tone: 'orange' },
      { to: '/resources/templates', nameKey: 'nav.mega.resources_i3', descKey: 'nav.mega.resources_i3_d', icon: SVG_FILE,    tone: 'rose' },
      { to: '/resources/faq',       nameKey: 'nav.mega.resources_i4', descKey: 'nav.mega.resources_i4_d', icon: SVG_QUESTION, tone: 'pink' },
    ],
  },
  {
    id: 'contact',
    triggerKey: 'nav.mega.contact',
    titleKey: 'nav.mega.contact_title',
    descKey: 'nav.mega.contact_desc',
    items: [
      // 联系菜单: 邮件 + 产品定价 + 关于我们（电话直拨已下线）
      { to: '/contact', nameKey: 'nav.mega.contact_i1', descKey: 'nav.mega.contact_i1_d', icon: SVG_MAIL, tone: 'blue' },
      { to: '/pricing', nameKey: 'nav.mega.contact_i2', descKey: 'nav.mega.contact_i2_d', icon: SVG_FILE, tone: 'amber' },
      { to: '/about', nameKey: 'nav.mega.contact_i3', descKey: 'nav.mega.contact_i3_d', icon: SVG_GLOBE, tone: 'indigo' },
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
  cancelMegaLeave()  // 鼠标重新进入 trigger 也取消待关闭 timer
  openMega.value = id
}
function onPanelEnter(id) {
  // 鼠标进入 panel — 取消即将关闭的 timer + 确保 openMega 是这个 panel
  cancelMegaLeave()
  openMega.value = id
}
let _leaveTimer = null
function onMegaHoverLeave(id) {
  if (_leaveTimer) clearTimeout(_leaveTimer)
  // W47c: 鼠标从 trigger 移到 panel 中间会经过 8px gap 触发 mouseleave,
  // 350ms 给用户足够时间跨过去; 同时 panel 的 mouseenter 会 cancel 这个 timer
  // (避免进入 panel 后面板还被关掉)。
  _leaveTimer = setTimeout(() => {
    if (openMega.value === id) closeMega()
  }, 350)
}
function cancelMegaLeave() {
  // W47c: panel mouseenter 调用 — 取消即将关闭面板的延迟 timer
  if (_leaveTimer) {
    clearTimeout(_leaveTimer)
    _leaveTimer = null
  }
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
  padding: 14px 20px;
  background: #fff;
  gap: 24px;
  position: relative;  // W47c: 给 mega-menu__panel 提供绝对定位的锚点
  // W48: 全站 header 统一 1200 居中（与 .app-container 对齐）.
  // width: 100% 强制 flex 容器不收缩到子元素总宽; max-width 限制到 1200;
  // margin: 0 auto 居中 — 避免 nav children 多的页面（登录后多"我的申请"下拉）
  // 把 header 撑窄.
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  flex-shrink: 0;
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
    // W47c: 跨整条导航条宽度（deel.com 风格 mega menu），
    // 而不只是比 trigger 宽一点 — 让 panel 视觉上"长在导航条下面"，
    // 而不是脱节的浮层。
    top: calc(100% + 8px);
    left: 0;
    right: 0;
    min-width: 480px;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    box-shadow: 0 24px 48px -16px rgba(15, 23, 42, .14), 0 4px 12px rgba(15, 23, 42, .04);
    padding: 20px 22px;
    z-index: 50;
    animation: megaIn .18s ease-out;
    // W47c: Teleport 到 body 后用 JS 算坐标（见 onMegaHover 中计算）。
    // 默认占位 — 真实定位由 .mega-menu__panel--teleported 覆盖
  }
  // W47c: Teleport 到 body 的 panel 用 fixed 定位，JS 计算 left/right/top
  &__panel--teleported {
    position: fixed;
    z-index: 1000;
    // 默认值，JS 会动态更新
    top: 60px;
    left: 0;
    right: 0;
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
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 4px;
  }
  // W55: 6 条产品卖点专用 3 列布局 (3×2) — 只对 apply mega 生效
  // 其它 mega (diagnose 3 / resources 4 / contact 2) 继续走 auto-fit 自适应
  &__grid--3col {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 4px 12px;
  }
  &__item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
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
    font-size: 12.5px;
    font-weight: 500;
    color: #334155;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  &__item-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    background: #0f172a;
    color: #fff;
    border-radius: 50%;
    font-size: 10px;
    font-weight: 600;
    flex-shrink: 0;
  }
  &__item-desc {
    font-size: 11px;
    color: #64748b;
    line-height: 1.4;
    padding-left: 22px;
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

/* ============== W47: 用户菜单(整合"我的申请" + profile + 退出登录) ============== */
.user-menu {
  position: relative;
}
.user-menu__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 34px;
  height: 34px;
  padding: 0;
  background: transparent;
  border: 1px solid transparent;
  color: var(--ink-2, #334155);
  cursor: pointer;
  border-radius: 50%;
  transition: color .15s, background .15s, border-color .15s;
}
.user-menu__trigger:hover,
.user-menu.is-open .user-menu__trigger {
  color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .08);
  border-color: rgba(59, 110, 245, .2);
}
.user-menu__trigger:focus-visible {
  outline: 2px solid var(--el-color-primary, #3B6EF5);
  outline-offset: 2px;
}
.user-menu__chevron {
  display: none;  /* trigger 是圆形按钮,不带 chevron 视觉更干净 */
}
.user-menu__panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;     /* trigger 在右侧,panel 从右对齐 */
  min-width: 220px;
  padding: 6px;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, .14), 0 2px 6px rgba(15, 23, 42, .06);
  z-index: 1000;
  animation: userMenuIn .18s ease-out;
}
@keyframes userMenuIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.user-menu__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border: 0;
  background: transparent;
  border-radius: 8px;
  color: var(--ink-1, #0F172A);
  text-decoration: none;
  font-size: 14px;
  font-family: inherit;
  text-align: left;
  transition: background .15s, color .15s;
  cursor: pointer;
}
.user-menu__item:hover {
  background: rgba(59, 110, 245, .08);
  color: var(--el-color-primary, #3B6EF5);
}
.user-menu__item.router-link-active {
  background: rgba(59, 110, 245, .12);
  color: var(--el-color-primary, #3B6EF5);
  font-weight: 600;
}
.user-menu__item:focus-visible {
  outline: 2px solid var(--el-color-primary, #3B6EF5);
  outline-offset: -2px;
}
.user-menu__item--danger {
  color: #DC2626;
}
.user-menu__item--danger:hover {
  background: rgba(220, 38, 38, .08);
  color: #B91C1C;
}
.user-menu__item--danger .user-menu__icon {
  color: #DC2626;
}
.user-menu__icon {
  flex: 0 0 16px;
  color: var(--ink-3, #64748B);
  transition: color .15s;
}
.user-menu__item:hover .user-menu__icon,
.user-menu__item.router-link-active .user-menu__icon {
  color: var(--el-color-primary, #3B6EF5);
}
.user-menu__divider {
  height: 1px;
  margin: 6px 4px;
  background: var(--border, #E2E8F0);
}

/* W59: 顶部申请人列表已挪到 /profile 个人中心 — 弹窗里不再展示 */

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* W47: 删了 .app-header__profile-link 旧样式 — 人物头像已挪到 user-menu__trigger 内 */
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

/* W57: 信任徽章的样式已迁到 TrustBadgePopover.vue(组件 scoped) */
</style>
