<template>
  <!--
    AppButton.vue — W3 P0 治本重构 (Option 1: emit + defineExpose trigger 模式)

    改动要点 (相对 W2 1.2.1b-fix 临时方案 D):
    1. spinner 改 CSS-only ::after 伪元素旋转,不再用 <span v-if> 触发 layout shift
       → Playwright actionability 不再因 v-if 重渲染失败
    2. 新增 onTrigger setter:父级 btnRef.value.onTrigger = handler 注入回调
       → 不依赖 @click 冒泡,Vue 不会因 v-on 在内部 wrapper 而漏触发
    3. 新增 trigger() 方法:父级 btnRef.value?.trigger() 手动触发,绕过 DOM click 链
    4. 保留 emit('click') 用于兼容老代码
  -->
  <button
    ref="rootEl"
    class="app-btn"
    :class="[
      `app-btn--${variant}`,
      `app-btn--${size}`,
      { 'is-loading': loading }
    ]"
    :disabled="disabled || loading"
    :type="nativeType"
    @click="handleClick"
  >
    <slot />
  </button>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'primary' }, // primary | outline | ghost | danger
  size: { type: String, default: 'md' },          // sm | md | lg
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  nativeType: { type: String, default: 'button' }
})
const emit = defineEmits(['click'])
const rootEl = ref(null)

// _onTrigger: 父级通过 setOnTrigger(fn) 注入的 callback
// 用 plain variable 而非 ref,避免 defineExpose 后父级
// btnRef.value.onTrigger = fn 通过代理赋值时不触发 ref.value 更新的坑
let _onTrigger = null

function _doClick(e) {
  if (props.disabled || props.loading) return
  emit('click', e)
  if (typeof _onTrigger === 'function') {
    try { _onTrigger(e) } catch (err) { console.error('[AppButton] onTrigger threw:', err) }
  }
}

function handleClick(e) {
  _doClick(e)
}

// trigger(): 父级可手动触发(绕过 DOM click 链,适合 W2 Playwright actionability 失败场景)
function trigger(e) {
  const evt = e || { type: 'manual', target: rootEl.value }
  _doClick(evt)
}

// setOnTrigger: 父级注入回调
function setOnTrigger(fn) {
  _onTrigger = fn
}
// getOnTrigger: 父级可读 (调试/双绑定场景)
function getOnTrigger() {
  return _onTrigger
}

defineExpose({
  trigger,
  el: rootEl,
  setOnTrigger,
  getOnTrigger
})
</script>

<style scoped lang="scss">
.app-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-weight: 500;
  border-radius: var(--radius-control, 8px);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background-color .15s ease, border-color .15s ease, color .15s ease, box-shadow .15s ease, transform .15s ease;
  white-space: nowrap;
  user-select: none;
  line-height: 1;
  // 防 loading 时宽度变化(原 v-if spinner 移除,加 min-width 兜底)
  min-width: 64px;
}
.app-btn:disabled { cursor: not-allowed; opacity: .6; }
.app-btn--sm { padding: 6px 12px; font-size: 13px; }
.app-btn--md { padding: 9px 16px; font-size: 14px; }
.app-btn--lg { padding: 12px 22px; font-size: 16px; }

.app-btn--primary {
  background: var(--el-color-primary, #3B6EF5);
  color: #fff;
  &:hover:not(:disabled) { background: var(--primary-hover, #2C5DE0); }
  &:active:not(:disabled) { background: var(--primary-active, #1F4DC2); }
  &:focus-visible { outline: none; box-shadow: var(--focus-ring, 0 0 0 3px rgba(59,110,245,.18)); }
}
.app-btn--outline {
  background: #fff;
  color: var(--el-color-primary, #3B6EF5);
  border-color: var(--el-color-primary, #3B6EF5);
  &:hover:not(:disabled) { background: var(--primary-bg, #EAF0FE); }
}
.app-btn--ghost {
  background: transparent;
  color: var(--ink-2, #334155);
  &:hover:not(:disabled) { background: rgba(15,23,42,.05); }
}
.app-btn--danger {
  background: var(--el-color-danger, #DC2626);
  color: #fff;
  &:hover:not(:disabled) { background: #B91C1C; }
}
.app-btn.is-loading { cursor: wait; }
// CSS-only loading 旋转器 (::after 伪元素,不触发 layout shift)
.app-btn.is-loading::after {
  content: '';
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid currentColor;
  border-top-color: transparent;
  animation: spin .7s linear infinite;
  margin-left: 4px;
  flex-shrink: 0;
}
// loading 时让 slot 文字轻微透明(视觉提示在跑)
.app-btn.is-loading > * { opacity: 0.7; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
