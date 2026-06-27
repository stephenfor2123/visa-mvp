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
// useGeoLocale is imported for its side effect: it queries the visitor's
// public IP via ipapi.co and auto-switches the UI locale (unless the user
// has previously picked one manually). The actual toast is shown by
// LangSwitch via the onLocaleChange event bus.
import { useGeoLocale } from '@/composables/useGeoLocale'

useGeoLocale()

const { locale } = useI18n()
const elLocale = computed(() => (locale.value === 'en' ? en : zhCn))
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