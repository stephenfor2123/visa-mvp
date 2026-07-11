<template>
  <el-config-provider :locale="elLocale">
    <router-view />
    <!-- W56: 全局「会话过期」提示条,401 链路 → http.js markAuthExpired → 事件 → 这里显示。
         非阻塞,跟 Toast 区分(Toast 是临时浮动,这里是一旦过期就一直显示,直到重新登录)。 -->
    <AuthExpiredBanner v-if="showAuthExpired" @login="goLogin" @dismiss="dismiss" />
    <ToastContainer />
  </el-config-provider>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import en from 'element-plus/es/locale/lang/en'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import ToastContainer from '@/components/ToastContainer.vue'
import AuthExpiredBanner from '@/components/AuthExpiredBanner.vue'
// useGeoLocale is imported for its side effect: it queries the visitor's
// public IP via ipapi.co and auto-switches the UI locale (unless the user
// has previously picked one manually). The actual toast is shown by
// LangSwitch via the onLocaleChange event bus.
import { useGeoLocale } from '@/composables/useGeoLocale'

useGeoLocale()

const { locale } = useI18n()
const elLocale = computed(() => (locale.value === 'en' ? en : zhCn))

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// W56: 显示条件 — 已 expired 且不在登录/注册页(去了也会被路由守卫踢回来)。
// 用户主动 dismiss 后标记 dismissed = true,这次会话内不再显示(避免点重试后又弹)。
const dismissed = ref(false)
const showAuthExpired = computed(() => {
  if (!auth.isAuthExpired) return false
  if (dismissed.value) return false
  if (route.path === '/login' || route.path === '/register') return false
  return true
})

function onAuthExpired() {
  // 新的过期事件 → 重置 dismiss 状态(给用户机会重新看到这个提示)
  dismissed.value = false
}
function dismiss() {
  dismissed.value = true
}
function goLogin() {
  router.push({ name: 'Login', query: { redirect: route.fullPath } })
}

onMounted(() => {
  window.addEventListener('htex:auth-expired', onAuthExpired)
  // 页面刷新时 auth.hydrate() 后 isAuthExpired 已经是 true(从 store 拿到),
  // 这里不用手动触发,响应式会自动渲染。
})
onBeforeUnmount(() => {
  window.removeEventListener('htex:auth-expired', onAuthExpired)
})
</script>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: var(--font-family-base, -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif);
  background: #fff;
  color: var(--ink-1, #0F172A);
}
</style>