<template>
  <!-- W57: 点击"加密隐私保护"徽章弹出的 popover。
       强调 Htex 不像别的签证中介把敏感材料裸传到云上 —
       三条核心保证(不存云 / 端到端加密 / 不存敏感原图) + 技术锚点(AES-256)。

       用 Teleport 到 body + JS 同步 trigger 位置,沿用 AppHeader mega menu 模式(W47c)。
       350ms hover 桥接:鼠标跨 trigger ↔ panel 之间不会被误关。 -->
  <div class="trust-popover">
    <button
      type="button"
      class="trust-badge"
      :class="{ 'is-open': open }"
      :aria-expanded="open"
      :aria-haspopup="'dialog'"
      :aria-label="t('trust.popover_aria', 'View privacy & encryption details')"
      :title="t('trust.popover_aria', 'View privacy & encryption details')"
      :data-testid="`${scope}-trust-badge`"
      @click="toggle"
      @keydown.esc="close"
    >
      <svg class="trust-badge__shield" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <defs>
          <linearGradient :id="`trust-lock-grad-${uid}`" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#3B6EF5" />
            <stop offset="100%" stop-color="#2553D6" />
          </linearGradient>
        </defs>
        <rect x="5" y="11" width="14" height="10" rx="2"
              :fill="`url(#trust-lock-grad-${uid})`" stroke="#1E40AF" stroke-width=".6" />
        <path d="M8 11 V7.5 C8 5 9.8 3 12 3 C14.2 3 16 5 16 7.5 V11"
              fill="none" stroke="#1E40AF" stroke-width="2" stroke-linecap="round" />
        <circle cx="12" cy="15.5" r="1.4" fill="#fff" />
        <rect x="11.4" y="16" width="1.2" height="3" fill="#fff" />
      </svg>
      <span class="trust-badge__text">{{ t('trust.on_time') }}</span>
      <!-- 展开指示小箭头 -->
      <svg class="trust-badge__chevron" :class="{ 'is-open': open }"
           width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
        <path d="M3 4.5 L6 7.5 L9 4.5" stroke="currentColor" stroke-width="1.6"
              stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        ref="panelRef"
        class="trust-popover__panel"
        role="dialog"
        :aria-label="t('trust.popover_title')"
        :data-testid="`${scope}-trust-popover`"
        :style="panelStyle"
        @mouseenter="onPanelEnter"
        @mouseleave="onPanelLeave"
      >
        <!-- 顶部:大锁 + 标题 + 副标题 (W57b 简化:去掉 3 条列表,只保留核心承诺) -->
        <div class="trust-popover__header">
          <div class="trust-popover__shield" aria-hidden="true">
            <svg viewBox="0 0 48 48" width="40" height="40" fill="none">
              <defs>
                <linearGradient :id="`trust-pop-shield-${uid}`" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#3B6EF5" />
                  <stop offset="100%" stop-color="#2553D6" />
                </linearGradient>
              </defs>
              <path d="M24 4 L40 10 V24 C40 34 33 42 24 45 C15 42 8 34 8 24 V10 Z"
                    :fill="`url(#trust-pop-shield-${uid})`" />
              <rect x="17" y="22" width="14" height="11" rx="2" fill="#fff" />
              <path d="M19.5 22 V19 a4.5 4.5 0 0 1 9 0 V22"
                    fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" />
              <circle cx="24" cy="27" r="1.4" fill="#3B6EF5" />
              <path d="M24 27 V29.5" stroke="#3B6EF5" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </div>
          <h3 class="trust-popover__title">{{ t('trust.popover_title', '敏感证件内容优先在本地处理') }}</h3>
          <p class="trust-popover__sub">{{ t('trust.popover_sub', '传输全程加密，仅处理完成服务所必需的数据') }}</p>
        </div>

        <!-- 底部 CTA:了解更多 (W57b 简化后,CTA 升级为唯一行动入口) -->
        <a
          v-if="learnMoreTo"
          :href="learnMoreTo"
          class="trust-popover__cta"
          :data-testid="`${scope}-trust-learn-more`"
          @click="close"
        >
          {{ t('trust.learn_more', '了解我们的安全实践') }}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M3 6 L9 6 M6 3 L9 6 L6 9" stroke="currentColor"
                  stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </a>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  scope: { type: String, default: 'home' },
  learnMoreTo: { type: String, default: '' },
})

const { t } = useI18n()

// 唯一 id:gradient id 在一个页面可能有多个徽章(header + footer)避免冲突
const uid = Math.random().toString(36).slice(2, 8)

const open = ref(false)
const triggerRef = ref(null)   // 徽章 button
const panelRef = ref(null)     // teleported panel
const panelStyle = ref({})
let closeTimer = null

// --- 桥接 hover (W47c 经验:跨节点 hover 350ms 延迟 + cancel timer) ---
function onPanelEnter() {
  if (closeTimer) { clearTimeout(closeTimer); closeTimer = null }
}
function onPanelLeave() {
  // 350ms 延迟,允许鼠标从 trigger 移到 panel 跨 gap
  closeTimer = setTimeout(() => { open.value = false }, 350)
}

function toggle() {
  if (open.value) {
    close()
  } else {
    open.value = true
    nextTick(syncPosition)
  }
}
function close() {
  open.value = false
  if (closeTimer) { clearTimeout(closeTimer); closeTimer = null }
}

function syncPosition() {
  // panel 在 Teleport 里,要同步到 trigger 下方右侧
  const btn = document.querySelector(`[data-testid="${props.scope}-trust-badge"]`)
  if (!btn) return
  const rect = btn.getBoundingClientRect()
  panelStyle.value = {
    position: 'fixed',
    top: `${rect.bottom + 8}px`,
    right: `${Math.max(8, window.innerWidth - rect.right)}px`,
  }
}

// 外部点击 / ESC / resize / scroll 关闭
function onDocClick(e) {
  if (!open.value) return
  const inTrigger = e.target.closest(`[data-testid="${props.scope}-trust-badge"]`)
  const inPanel = e.target.closest(`[data-testid="${props.scope}-trust-popover"]`)
  if (!inTrigger && !inPanel) close()
}
function onKey(e) {
  if (e.key === 'Escape' && open.value) close()
}
function onResize() {
  if (open.value) syncPosition()
}
function onScroll() {
  if (open.value) syncPosition()
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
  window.addEventListener('resize', onResize)
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('scroll', onScroll)
  if (closeTimer) clearTimeout(closeTimer)
})

defineExpose({ open, close, toggle })
</script>

<style scoped>
/* ============ Trigger:徽章(沿用 W28 风格,改成 button) ============ */
.trust-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(59, 110, 245, 0.08);
  border: 1px solid rgba(59, 110, 245, 0.22);
  border-radius: 999px;
  color: #1E40AF;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  font-family: inherit;
}
.trust-badge:hover {
  background: rgba(59, 110, 245, 0.14);
  border-color: rgba(59, 110, 245, 0.4);
}
.trust-badge.is-open {
  background: rgba(59, 110, 245, 0.16);
  border-color: #3B6EF5;
}
.trust-badge__shield {
  flex-shrink: 0;
  display: block;
}
.trust-badge__text {
  line-height: 1;
}
.trust-badge__chevron {
  margin-left: 2px;
  transition: transform 0.18s ease;
  color: currentColor;
}
.trust-badge__chevron.is-open {
  transform: rotate(180deg);
}

/* ============ Panel:Teleport 到 body ============ */
.trust-popover__panel {
  width: 380px;
  max-width: calc(100vw - 16px);
  background: #fff;
  border-radius: 16px;
  box-shadow:
    0 12px 40px rgba(15, 23, 42, 0.16),
    0 4px 12px rgba(15, 23, 42, 0.08);
  padding: 20px 20px 16px;
  z-index: 9999;
  animation: trustPopIn 180ms cubic-bezier(.2, .8, .3, 1.2);
  font-family: inherit;
  color: #0f172a;
  border: 1px solid rgba(15, 23, 42, 0.06);
}
@keyframes trustPopIn {
  from { opacity: 0; transform: translateY(-6px) scale(0.96); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* 头部 — W57b 简化:盾牌大图 + 标题 + 副标题,视觉中心更突出 */
.trust-popover__header {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding-bottom: 14px;
  border-bottom: 1px solid #F1F5F9;
  gap: 8px;
}
.trust-popover__shield {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(59, 110, 245, 0.10) 0%, rgba(37, 83, 214, 0.10) 100%);
  margin-bottom: 2px;
}
.trust-popover__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.4;
}
.trust-popover__sub {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  max-width: 320px;
}

/* 底部 CTA — W57b 简化后变成全宽主按钮,视觉权重提升 */
.trust-popover__cta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 14px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(59, 110, 245, 0.08);
  border: 1px solid rgba(59, 110, 245, 0.18);
  font-size: 13px;
  font-weight: 600;
  color: #1E40AF;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.trust-popover__cta:hover {
  background: rgba(59, 110, 245, 0.14);
  border-color: rgba(59, 110, 245, 0.36);
  color: #1E40AF;
  text-decoration: none;
}

/* 移动端 fallback:徽章在小屏保持紧凑;panel 全宽靠右 */
@media (max-width: 640px) {
  .trust-badge {
    padding: 5px 9px;
    font-size: 12px;
  }
  .trust-badge__text {
    display: none; /* 小屏只显示锁图标 */
  }
  .trust-popover__panel {
    width: calc(100vw - 16px);
    right: 8px !important;
  }
}
</style>
