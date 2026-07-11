<template>
  <!-- label wrapping input — for proper a11y association use `id` on input + `for` on label -->
  <label class="app-input" :class="{ 'is-error': error, 'is-disabled': disabled, 'is-date-empty': isDateEmpty }" :data-testid="$attrs['data-testid']" :data-test="$attrs['data-test']">
    <span v-if="label" class="app-input__label">
      {{ label }}<span v-if="required" class="app-input__required" aria-hidden="true">*</span>
    </span>
    <span class="app-input__wrap" :class="{ 'is-date': props.type === 'date' }">
      <span v-if="$slots.prefix" class="app-input__prefix" aria-hidden="true"><slot name="prefix" /></span>
      <input
        v-bind="omitAttrs"
        :id="inputId"
        :type="resolvedType"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :maxlength="maxlength"
        :inputmode="inputmode"
        :autocomplete="autocomplete"
        :aria-required="required"
        :aria-invalid="!!error"
        :aria-describedby="error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined"
        class="app-input__el"
        @input="onInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />
      <!-- type=date 时 empty 状态叠加 i18n placeholder 浮层,
           有值时叠加本地化日期显示层(Intl.DateTimeFormat);
           避免浏览器系统 locale ("年/月/日") 露出。点击穿透到 input。
           disabled 时也显示浮层(灰底色),保证 dna 勾上后 native 文案也不露出。 -->
      <span
        v-if="props.type === 'date' && isDateEmpty"
        class="app-input__date-hint"
        :class="{ 'is-disabled': disabled }"
        aria-hidden="true"
      >{{ dateHintText }}</span>
      <span
        v-else-if="props.type === 'date' && !isDateEmpty"
        class="app-input__date-display"
        :class="{ 'is-disabled': disabled }"
        aria-hidden="true"
      >{{ dateDisplayText }}</span>
      <!-- W53: 密码可见性切换 — 仅 password-toggle=true 时显示,默认 false。
           内联 SVG,跟系统其他 input 图标风格统一(细线条 1.6px, viewBox 24x24)。
           默认显示「睁眼」(可点击显示密码),点击后切到「带斜线闭眼」(已显示,可点回隐藏)。 -->
      <button
        v-if="passwordToggle && props.type === 'password'"
        type="button"
        class="app-input__toggle"
        :aria-label="revealed ? t('app_input.hide_password', '隐藏密码') : t('app_input.show_password', '显示密码')"
        :aria-pressed="revealed"
        :data-testid="`${$attrs['data-testid'] || 'app-input'}-toggle`"
        @click="revealed = !revealed"
      >
        <svg
          v-if="revealed"
          aria-hidden="true"
          width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
        >
          <!-- 睁眼: 密码可见 -->
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
        <svg
          v-else
          aria-hidden="true"
          width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
        >
          <!-- 闭眼带斜线: 密码不可见 -->
          <path d="M3 3l18 18" />
          <path d="M10.5 6.2A10.4 10.4 0 0 1 12 6c6.5 0 10 6 10 6a13.2 13.2 0 0 1-3.1 3.8" />
          <path d="M6.6 6.6A13.2 13.2 0 0 0 2 12s3.5 6 10 6c1.7 0 3.3-.4 4.7-1" />
          <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
        </svg>
      </button>
      <span v-if="$slots.suffix" class="app-input__suffix" aria-hidden="true"><slot name="suffix" /></span>
    </span>
    <span v-if="error" :id="`${inputId}-error`" class="app-input__error" role="alert">{{ error }}</span>
    <span v-else-if="hint" :id="`${inputId}-hint`" class="app-input__hint">{{ hint }}</span>
  </label>
</template>

<script setup>
import { useAttrs, computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
defineOptions({ inheritAttrs: false })
const { t, locale } = useI18n()
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: String,
  placeholder: String,
  type: { type: String, default: 'text' },
  error: String,
  hint: String,
  disabled: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
  maxlength: [String, Number],
  inputmode: String,
  // a11y: explicit input id (falls back to generated uid-based id)
  inputId: { type: String, default: '' },
  // W53: 密码可见性切换。父组件传 password-toggle 即可在 type=password 字段
  // 右侧加眼睛按钮;切到 type=text 时再点切回。默认关闭,跟旧用法兼容。
  passwordToggle: { type: Boolean, default: false },
  // 浏览器自动填充提示 — password 字段传 'new-password' / 'current-password'。
  autocomplete: { type: String, default: undefined },
})
const emit = defineEmits(['update:modelValue', 'blur', 'focus'])
const attrs = useAttrs()
const revealed = ref(false)
const resolvedType = computed(() => {
  if (props.type === 'password' && props.passwordToggle && revealed.value) {
    return 'text'
  }
  return props.type
})
// omit test-* attrs from input (they're on the label wrapper so spec
// queries like [data-testid="x"] .app-input__label resolve to 1 element).
const omitAttrs = computed(() => {
  const out = {}
  for (const k in attrs) {
    if (k.startsWith('data-test') || k.startsWith('aria-')) continue
    out[k] = attrs[k]
  }
  return out
})
function onInput(e) {
  emit('update:modelValue', e.target.value)
}
// type=date 占位浮层文案 — 用 orders.placeholder_date('YYYY-MM-DD' 4 国一致)。
// 浏览器原生 date picker 在 zh-CN 系统下默认显示 '年/月/日',英文界面下需要屏蔽掉
// native 文案,改用 vue-i18n 的统一占位文案,跟其他语种视觉一致。
const dateHintText = computed(() => {
  return t('orders.placeholder_date') || 'YYYY-MM-DD'
})
const isDateEmpty = computed(() => props.type === 'date' && !props.modelValue)
// 已选日期本地化显示 — 用 Intl.DateTimeFormat 把 ISO "YYYY-MM-DD"
// 转成当前 locale 的本地格式(Jul 7, 2026 / 2026年7月7日 等)
// 加 T00:00:00 避免 ISO 字符串被当 UTC 解析导致跨日错位
const dateDisplayText = computed(() => {
  if (props.type !== 'date' || !props.modelValue) return ''
  const d = new Date(String(props.modelValue) + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return String(props.modelValue)
  try {
    return new Intl.DateTimeFormat(locale.value || 'en', {
      year: 'numeric', month: 'short', day: 'numeric',
    }).format(d)
  } catch {
    return String(props.modelValue)
  }
})
</script>

<style scoped lang="scss">
.app-input { display: block; }
.app-input__label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2, #334155);
  margin-bottom: 6px;
}
.app-input__required { color: var(--el-color-danger, #DC2626); margin-left: 2px; }
.app-input__wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px;
  padding: 0 12px;
  transition: border-color .15s, box-shadow .15s;
}
.app-input__wrap:focus-within {
  border-color: var(--el-color-primary, #3B6EF5);
  box-shadow: 0 0 0 3px rgba(59,110,245,.15);
}
.is-error .app-input__wrap {
  border-color: var(--el-color-danger, #DC2626);
}
.is-disabled .app-input__wrap { background: var(--bg-disabled, #F1F5F9); }
.app-input__el {
  flex: 1;
  height: 40px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--ink-1, #0F172A);
  width: 100%;
  min-width: 0;
}
.app-input__el::placeholder { color: var(--muted, #94A3B8); }
// type=date: empty / disabled 时把浏览器自己的"年/月/日" / "MM/DD/YYYY" 透明化,
// 用 .app-input__date-hint 接管占位文案;有值时也透明,用 .app-input__date-display
// 显示本地化格式。两态都透明 → 一致地接管 native 的"显示层"
// Webkit / Blink: 用 ::-webkit-datetime-edit-* 系列
// Firefox: type=date 不渲染内部 text,直接显示 "mm/dd/yyyy",没有 placeholder 概念;
//          但 color: transparent 也会让 Firefox 的 text 透明 (实测有效)。
.app-input.is-date-empty .app-input__el,
.app-input__wrap.is-date .app-input__el,
.app-input.is-disabled .app-input__wrap.is-date .app-input__el {
  color: transparent;
  caret-color: transparent;
  &::-webkit-datetime-edit { color: transparent; }
  &::-webkit-datetime-edit-fields-wrapper { color: transparent; }
  &::-webkit-datetime-edit-text { color: transparent; }
  &::-webkit-datetime-edit-month-field,
  &::-webkit-datetime-edit-day-field,
  &::-webkit-datetime-edit-year-field { color: transparent; }
}
.app-input__date-hint {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--muted, #94A3B8);
  font-size: 14px;
  user-select: none;
  &.is-disabled { color: var(--ink-3, #94A3B8); }
}
.app-input__date-display {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--ink-1, #0F172A);
  font-size: 14px;
  font-weight: 500;
  user-select: none;
  &.is-disabled { color: var(--ink-3, #94A3B8); font-weight: 400; }
}
.app-input__wrap.is-date { position: relative; }
.app-input__prefix, .app-input__suffix {
  color: var(--ink-3, #64748B);
  display: inline-flex;
  align-items: center;
}
// W53: 密码可见性按钮 — 用 button 而不是 span 让键盘可达 + 屏幕阅读器读得到。
.app-input__toggle {
  background: transparent;
  border: 0;
  padding: 4px;
  margin-right: -4px; // 让按钮视觉上贴齐 input 右内边距
  cursor: pointer;
  color: var(--ink-3, #64748B);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: color .12s, background .12s;
}
.app-input__toggle:hover { color: var(--ink-1, #0F172A); background: var(--bg-hover, #F1F5F9); }
.app-input__toggle:focus-visible {
  outline: 2px solid var(--el-color-primary, #3B6EF5);
  outline-offset: 1px;
}
.app-input__error {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-color-danger, #DC2626);
}
.app-input__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-3, #64748B);
}
</style>