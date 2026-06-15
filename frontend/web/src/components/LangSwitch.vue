<template>
  <div class="lang-switch">
    <button
      v-for="loc in localeList"
      :key="loc.code"
      class="lang-switch__btn"
      :class="{ on: current === loc.code }"
      :title="loc.name"
      @click="onPick(loc.code)"
    >{{ loc.short }}</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale, SUPPORTED_LOCALES, LOCALES } from '@/i18n'

const { locale } = useI18n()
const current = locale
// Render order follows SUPPORTED_LOCALES so the button order is stable
// regardless of how LOCALES is iterated. Each entry exposes the BCP-47
// `code`, the localised `name` (for tooltips), and the UI `short` label.
const localeList = computed(() =>
  SUPPORTED_LOCALES.map(code => LOCALES[code])
)
function onPick(code) {
  if (!SUPPORTED_LOCALES.includes(code)) return
  setLocale(code)
}
</script>

<style scoped lang="scss">
.lang-switch {
  display: inline-flex;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px;
  padding: 2px;
  background: #fff;
}
.lang-switch__btn {
  border: none;
  background: transparent;
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 999px;
  color: var(--ink-3, #64748B);
  cursor: pointer;
  transition: all .15s;
}
.lang-switch__btn.on {
  background: var(--el-color-primary, #3B6EF5);
  color: #fff;
}
</style>