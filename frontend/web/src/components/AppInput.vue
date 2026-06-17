<template>
  <!-- label wrapping input — for proper a11y association use `id` on input + `for` on label -->
  <label class="app-input" :class="{ 'is-error': error, 'is-disabled': disabled }" :data-testid="$attrs['data-testid']" :data-test="$attrs['data-test']">
    <span v-if="label" class="app-input__label">
      {{ label }}<span v-if="required" class="app-input__required" aria-hidden="true">*</span>
    </span>
    <span class="app-input__wrap">
      <span v-if="$slots.prefix" class="app-input__prefix" aria-hidden="true"><slot name="prefix" /></span>
      <input
        v-bind="omitAttrs"
        :id="inputId"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :maxlength="maxlength"
        :inputmode="inputmode"
        :aria-required="required"
        :aria-invalid="!!error"
        :aria-describedby="error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined"
        class="app-input__el"
        @input="onInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />
      <span v-if="$slots.suffix" class="app-input__suffix" aria-hidden="true"><slot name="suffix" /></span>
    </span>
    <span v-if="error" :id="`${inputId}-error`" class="app-input__error" role="alert">{{ error }}</span>
    <span v-else-if="hint" :id="`${inputId}-hint`" class="app-input__hint">{{ hint }}</span>
  </label>
</template>

<script setup>
import { useAttrs, computed } from 'vue'
defineOptions({ inheritAttrs: false })
defineProps({
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
  inputId: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'blur', 'focus'])
const attrs = useAttrs()
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
.app-input__prefix, .app-input__suffix {
  color: var(--ink-3, #64748B);
  display: inline-flex;
  align-items: center;
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