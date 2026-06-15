<template>
  <button
    class="theme-toggle"
    :title="isDark ? t('theme.light_mode') : t('theme.dark_mode')"
    :aria-label="isDark ? t('theme.light_mode') : t('theme.dark_mode')"
    @click="toggleTheme"
  >
    <!-- Sun icon — shown in dark mode to switch to light -->
    <svg v-if="isDark" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="5"/>
      <line x1="12" y1="1" x2="12" y2="3"/>
      <line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/>
      <line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
    <!-- Moon icon — shown in light mode to switch to dark -->
    <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTheme } from '@/composables/useTheme'

const { t } = useI18n()
const { theme, toggleTheme } = useTheme()
const isDark = computed(() => theme.value === 'dark')
</script>

<style scoped lang="scss">
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 50%;
  background: transparent;
  color: var(--ink-2, #334155);
  cursor: pointer;
  transition: all .2s;
  padding: 0;

  &:hover {
    background: var(--bg-alt, #F8FAFC);
    color: var(--ink-1, #0F172A);
  }

  [data-theme="dark"] & {
    color: var(--ink-2, #CBD5E1);
    &:hover { background: var(--bg-alt, #0F172A); }
  }
}
</style>