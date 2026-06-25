<template>
  <div class="lang-switch" ref="rootRef">
    <button
      type="button"
      class="lang-switch__trigger"
      :class="{ open }"
      :aria-expanded="open"
      :aria-label="$t('common.lang_switch_aria', { lang: currentLocale.name }) || currentLocale.name"
      :title="currentLocale.name"
      @click="toggle"
    >
      <span class="lang-switch__flag" aria-hidden="true">{{ currentLocale.flag }}</span>
      <span class="lang-switch__short">{{ currentLocale.short }}</span>
      <svg
        class="lang-switch__caret"
        :class="{ open }"
        width="10" height="10" viewBox="0 0 12 12" fill="none"
        aria-hidden="true"
      >
        <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>

    <Transition name="lang-fade">
      <ul v-if="open" class="lang-switch__menu" role="listbox" :aria-label="$t('common.lang_switch_aria_menu') || 'Language'">
        <li
          v-for="loc in localeList"
          :key="loc.code"
          role="option"
          :aria-selected="current === loc.code"
          class="lang-switch__item"
          :class="{ on: current === loc.code }"
          @click="onPick(loc.code)"
        >
          <span class="lang-switch__flag" aria-hidden="true">{{ loc.flag }}</span>
          <span class="lang-switch__name">{{ loc.name }}</span>
          <svg
            v-if="current === loc.code"
            class="lang-switch__check"
            width="14" height="14" viewBox="0 0 16 16" fill="none"
            aria-hidden="true"
          >
            <path d="M3 8.5L6.5 12L13 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </li>
      </ul>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale, SUPPORTED_LOCALES, LOCALES, markUserLocaleChoice, onLocaleChange } from '@/i18n'
import { useToast } from '@/composables/useToast'

const { locale, t } = useI18n()
const current = locale
const toast = useToast()

const localeList = computed(() =>
  SUPPORTED_LOCALES.map(code => LOCALES[code])
)
const currentLocale = computed(() => LOCALES[current.value] || LOCALES['zh-CN'])

const open = ref(false)
const rootRef = ref(null)

function toggle() { open.value = !open.value }
function close() { open.value = false }

function onPick(code) {
  if (!SUPPORTED_LOCALES.includes(code)) return
  // Mark as user-chosen so the IP detector won't override it on next page load.
  markUserLocaleChoice()
  setLocale(code)
  close()
}

function onDocClick(e) {
  if (!rootRef.value) return
  if (!rootRef.value.contains(e.target)) close()
}
function onKeydown(e) {
  if (e.key === 'Escape' && open.value) close()
}

let _unsubLocale = null
onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
  // When IP detector switches locale, show a one-time hint.
  _unsubLocale = onLocaleChange(({ source }) => {
    if (source === 'ip') {
      const name = LOCALES[current.value]?.name || current.value
      try { toast.info(t('common.lang_switched_by_ip', { locale: name })) } catch (_) {}
    }
  })
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
  if (_unsubLocale) _unsubLocale()
})
</script>

<style scoped lang="scss">
.lang-switch {
  position: relative;
  display: inline-flex;
}

.lang-switch__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px;
  background: #fff;
  color: var(--ink-2, #334155);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color .15s, background .15s, color .15s, box-shadow .15s;
  white-space: nowrap;
}
.lang-switch__trigger:hover {
  border-color: var(--el-color-primary, #3B6EF5);
  color: var(--el-color-primary, #3B6EF5);
}
.lang-switch__trigger.open {
  border-color: var(--el-color-primary, #3B6EF5);
  box-shadow: 0 0 0 3px rgba(59, 110, 245, .12);
}

.lang-switch__flag {
  font-size: 16px;
  line-height: 1;
  font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", "Twemoji", sans-serif;
}

.lang-switch__short {
  letter-spacing: .02em;
}

.lang-switch__caret {
  transition: transform .2s;
  color: var(--ink-3, #94A3B8);
  flex-shrink: 0;
}
.lang-switch__caret.open { transform: rotate(180deg); }

.lang-switch__menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 200px;
  margin: 0;
  padding: 4px;
  list-style: none;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px;
  box-shadow: 0 10px 30px -8px rgba(15, 23, 42, .18), 0 4px 10px -4px rgba(15, 23, 42, .08);
  z-index: 1000;
  overflow: hidden;
}

.lang-switch__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--ink-2, #334155);
  transition: background .12s, color .12s;
  user-select: none;
}
.lang-switch__item:hover {
  background: var(--bg-alt, #F1F5F9);
}
.lang-switch__item.on {
  background: rgba(59, 110, 245, .08);
  color: var(--el-color-primary, #3B6EF5);
  font-weight: 500;
}

.lang-switch__name {
  flex: 1;
  min-width: 0;
}

.lang-switch__check {
  color: var(--el-color-primary, #3B6EF5);
  flex-shrink: 0;
}

// Menu transition
.lang-fade-enter-active,
.lang-fade-leave-active {
  transition: opacity .14s, transform .14s;
  transform-origin: top right;
}
.lang-fade-enter-from,
.lang-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(.98);
}
</style>
