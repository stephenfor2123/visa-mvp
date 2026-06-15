<template>
  <div class="toast-stack" aria-live="polite">
    <transition-group name="toast-fade">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast"
        :class="`toast--${t.type}`"
        @click="remove(t.id)"
      >
        <span class="toast__icon" aria-hidden="true">
          <el-icon><component :is="iconFor(t.type)" /></el-icon>
        </span>
        <span class="toast__msg">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useToast } from '@/composables/useToast'
import { Check, Close, WarningFilled, InfoFilled } from '@element-plus/icons-vue'

const { toasts, remove } = useToast()

function iconFor(type) {
  switch (type) {
    case 'success': return Check
    case 'error': return Close
    case 'warning': return WarningFilled
    default: return InfoFilled
  }
}
</script>

<style scoped lang="scss">
.toast-stack {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 6000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 240px;
  max-width: 380px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  font-size: 14px;
  cursor: pointer;
  border-left: 4px solid var(--el-color-primary);
}
.toast--success { border-left-color: var(--el-color-success); }
.toast--success .toast__icon { color: var(--el-color-success); }
.toast--error   { border-left-color: var(--el-color-danger); }
.toast--error .toast__icon   { color: var(--el-color-danger); }
.toast--warning { border-left-color: var(--el-color-warning); }
.toast--warning .toast__icon { color: var(--el-color-warning); }
.toast--info    { border-left-color: var(--el-color-info); }
.toast--info .toast__icon    { color: var(--el-color-info); }
.toast__msg { color: var(--ink-1, #0F172A); line-height: 1.5; }

.toast-fade-enter-active, .toast-fade-leave-active { transition: all .25s ease; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateY(-6px); }
</style>