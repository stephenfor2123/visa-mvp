<!--
  AuthExpiredBanner.vue — W56 全局「会话过期」非阻塞提示条
  ===================================================================
  触发:http.js 401 → auth.markAuthExpired() → 派发 htex:auth-expired 事件
        → App.vue 渲染这个组件。

  设计:顶部 sticky 横幅(不像 toast 3s 自动消失),一直挂到用户重新登录或主动关闭。
  避免在每个页面的 catch 里散落 toast("登录已过期") — 统一在这。

  4 国 i18n 在 common.session_expired / common.relogin / common.dismiss。
-->
<template>
  <div class="auth-expired" role="alert" data-testid="auth-expired-banner">
    <div class="auth-expired__inner">
      <span class="auth-expired__icon" aria-hidden="true">
        <el-icon><WarningFilled /></el-icon>
      </span>
      <span class="auth-expired__msg">{{ t('common.session_expired') }}</span>
      <div class="auth-expired__actions">
        <button
          type="button"
          class="auth-expired__btn auth-expired__btn--primary"
          data-testid="auth-expired-login"
          @click="$emit('login')"
        >
          {{ t('common.relogin') }}
        </button>
        <button
          type="button"
          class="auth-expired__btn auth-expired__btn--ghost"
          data-testid="auth-expired-dismiss"
          @click="$emit('dismiss')"
        >
          {{ t('common.dismiss') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { WarningFilled } from '@element-plus/icons-vue'

defineEmits(['login', 'dismiss'])

const { t } = useI18n()
</script>

<style scoped lang="scss">
.auth-expired {
  position: sticky;
  top: 0;
  z-index: 5500;
  background: linear-gradient(180deg, #FEF2F2 0%, #FEE2E2 100%);
  border-bottom: 1px solid #FCA5A5;
  box-shadow: 0 1px 3px rgba(220, 38, 38, .08);
  animation: auth-slide-in .25s ease-out;
}
.auth-expired__inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.auth-expired__icon {
  color: #B91C1C;
  font-size: 18px;
  display: inline-flex;
  flex: 0 0 auto;
}
.auth-expired__msg {
  flex: 1 1 auto;
  font-size: 14px;
  color: #7F1D1D;
  font-weight: 500;
  line-height: 1.4;
  min-width: 0;
}
.auth-expired__actions {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
}
.auth-expired__btn {
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .15s ease;
  font-family: inherit;
}
.auth-expired__btn--primary {
  background: #B91C1C;
  color: #fff;
}
.auth-expired__btn--primary:hover {
  background: #991B1B;
}
.auth-expired__btn--ghost {
  background: transparent;
  color: #7F1D1D;
  border: 1px solid #FCA5A5;
}
.auth-expired__btn--ghost:hover {
  background: rgba(255, 255, 255, .4);
}

@keyframes auth-slide-in {
  from { transform: translateY(-100%); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@media (max-width: 640px) {
  .auth-expired__inner {
    padding: 8px 16px;
    gap: 8px;
  }
  .auth-expired__msg {
    font-size: 13px;
  }
  .auth-expired__btn {
    padding: 5px 10px;
    font-size: 12px;
  }
}
</style>
