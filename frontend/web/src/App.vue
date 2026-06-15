<template>
  <el-config-provider :locale="elLocale">
    <router-view />
    <ToastContainer />
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import en from 'element-plus/es/locale/lang/en'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import ToastContainer from '@/components/ToastContainer.vue'
// useTheme is imported for its side effect: it reads localStorage and
// applies data-theme="light|dark" to <html> before the app mounts, which
// avoids a flash of light theme for users with dark saved.
import { useTheme } from '@/composables/useTheme'

useTheme()

const { locale } = useI18n()
const elLocale = computed(() => (locale.value === 'en' ? en : zhCn))
</script>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: var(--font-family-base, -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif);
  background: var(--bg-alt, #F8FAFC);
  color: var(--ink-1, #0F172A);
  transition: background .2s, color .2s;
}
</style>