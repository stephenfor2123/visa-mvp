<template>
  <div class="ldi" :data-locale="localeTag">
    <!-- 真正的输入：用 type="date" 保证移动端/桌面都有原生日历 picker，
         值契约保持 ISO "YYYY-MM-DD"，跟父组件调用方零改动。

         empty 时把 native input 自身颜色置透明 → 浏览器默认占位文案
         ("yyyy/mm/dd"、"MM/DD/YYYY" 等，跟系统 locale 走) 完全看不见；
         但宽度 / 边框 / 右侧 picker 图标照常显示，点击仍能弹出日历。
         浮层 hint 接管 placeholder 文案。这样无论用户切到哪种语言，
         看到的是 vue-i18n 的提示文字，而不是浏览器的"年/月/日"。 -->
    <input
      ref="nativeInput"
      :value="modelValue"
      type="date"
      class="ldi__native"
      :class="{ 'is-empty': !modelValue }"
      :data-testid="testId"
      :min="min"
      :max="max"
      @input="onInput"
      @change="onInput"
    />

    <!-- 自定义浮层：i18n placeholder + 跟随当前 locale 切换显示文案。
         pointer-events: none 让点击穿透到 input。 -->
    <div v-if="!modelValue" class="ldi__hint" :aria-hidden="true">
      <span class="ldi__hint-text">{{ hintText }}</span>
      <span class="ldi__hint-icon" aria-hidden="true">📅</span>
    </div>

    <!-- 选完后显示本地化日期（跟表格里其它日期列一致）+ 清除按钮 -->
    <div v-else class="ldi__display" :aria-hidden="true">
      <span>{{ displayText }}</span>
      <button
        type="button"
        class="ldi__clear"
        :aria-label="clearLabel"
        @click.prevent.stop="clear"
      >×</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: { type: String, default: '' },   // ISO YYYY-MM-DD
  testId: { type: String, default: '' },
  min: { type: String, default: '' },
  max: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const { t, locale } = useI18n()

// placeholder 文案：depart / return 用各自 i18n key
const hintText = computed(() => {
  const k = props.min
    ? 'wizard.travel_depart_date_ph'
    : 'wizard.travel_return_date_ph'
  return t(k)
})

// 已选日期：当前 locale 下的本地化格式
const displayText = computed(() => {
  if (!props.modelValue) return ''
  // 加 T00:00:00 避免 new Date('YYYY-MM-DD') 被当成 UTC 导致跨日显示错位
  const d = new Date(props.modelValue + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return props.modelValue
  try {
    return new Intl.DateTimeFormat(locale.value || 'en', {
      year: 'numeric', month: 'short', day: 'numeric',
    }).format(d)
  } catch {
    return props.modelValue
  }
})

const clearLabel = computed(() => t('wizard.date_clear_aria') || 'Clear')
const localeTag = computed(() => (locale.value || 'en').split('-')[0])

function onInput(e) {
  const v = e.target.value || ''
  emit('update:modelValue', v)
}

function clear() {
  emit('update:modelValue', '')
}
</script>

<style scoped lang="scss">
.ldi {
  position: relative;
  width: 100%;
  font-family: inherit;
}

// 原生 date input：撑满父容器；边框/高度跟 .tp-input 完全一致。
// 关键：empty 状态把文本颜色置透明，把浏览器自己的"yyyy/mm/dd"占位文案
// 完全藏起来 —— 我们的浮层 hint 会接管 placeholder。
.ldi__native {
  width: 100%;
  box-sizing: border-box;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 13.5px;
  color: #0f172a;
  font-family: inherit;
  background: #fff;
  min-height: 38px;
  &:focus {
    outline: none;
    border-color: #3b6ef5;
  }
  &.is-empty {
    color: transparent;
    caret-color: transparent;
    // ::-webkit-datetime-edit 是 Webkit date input 内部的占位区域，
    // 把它的颜色也置透明才能彻底去掉 "yyyy/mm/dd" 这种浏览器自带文案。
    &::-webkit-datetime-edit { color: transparent; }
    &::-webkit-datetime-edit-fields-wrapper { color: transparent; }
    &::-webkit-datetime-edit-text { color: transparent; }
    &::-webkit-datetime-edit-month-field,
    &::-webkit-datetime-edit-day-field,
    &::-webkit-datetime-edit-year-field { color: transparent; }
  }
  // 有值时也把 native 文本藏掉，让浮层 display 接管（避免重影）
  &:not(.is-empty) {
    color: transparent;
    caret-color: transparent;
    &::-webkit-datetime-edit { color: transparent; }
    &::-webkit-datetime-edit-fields-wrapper { color: transparent; }
    &::-webkit-datetime-edit-text { color: transparent; }
    &::-webkit-datetime-edit-month-field,
    &::-webkit-datetime-edit-day-field,
    &::-webkit-datetime-edit-year-field { color: transparent; }
  }
}

// 浮层 hint：empty 时显示。pointer-events: none 让点击穿透到 input。
.ldi__hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 36px 0 12px; // 右侧留出 native picker 按钮的宽度
  pointer-events: none;
  color: #94a3b8;
  font-size: 13.5px;
  user-select: none;
}
.ldi__hint-icon {
  font-size: 14px;
  opacity: 0.6;
}

// 选完日期后的展示行：本地化日期 + 清除按钮
.ldi__display {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 36px 0 12px; // 右侧留出 native picker 按钮的宽度
  pointer-events: none;
  color: #0f172a;
  font-size: 13.5px;
  font-weight: 500;
}
.ldi__clear {
  pointer-events: auto;
  background: transparent;
  border: 0;
  color: #94a3b8;
  font-size: 18px;
  line-height: 1;
  padding: 0 4px;
  cursor: pointer;
  border-radius: 4px;
  &:hover { color: #ef4444; background: #fef2f2; }
  &:focus-visible { outline: 2px solid #3b6ef5; outline-offset: 1px; }
}
</style>