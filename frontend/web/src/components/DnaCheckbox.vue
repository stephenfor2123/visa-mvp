<template>
  <label class="dna-check" :class="{ 'is-on': modelValue }">
    <input
      type="checkbox"
      class="dna-check__cb"
      :checked="modelValue"
      :data-testid="dataTestid"
      @change="$emit('update:modelValue', $event.target.checked)"
    />
    <span class="dna-check__text">
      <span class="dna-check__label">{{ t('orders.dna_label', 'Does Not Apply') }}</span>
      <span class="dna-check__hint">{{ t('orders.dna_hint', '此字段不适用') }}</span>
    </span>
  </label>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
defineProps({
  modelValue: { type: Boolean, default: false },
  dataTestid: { type: String, default: '' },
})
defineEmits(['update:modelValue'])
const { t } = useI18n()
</script>

<style scoped lang="scss">
.dna-check {
  display: inline-flex;
  align-items: flex-start;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  padding: 2px 0;
  font-size: 12px;
  color: var(--ink-3, #64748B);
  line-height: 1.4;

  &__cb {
    margin: 2px 0 0;
    width: 13px;
    height: 13px;
    accent-color: var(--el-color-primary, #3B6EF5);
    cursor: pointer;
    flex-shrink: 0;
  }
  &__text { display: inline-flex; flex-direction: column; gap: 1px; }
  &__label {
    font-weight: 500;
    color: var(--ink-2, #475569);
  }
  &__hint {
    font-size: 11px;
    color: var(--ink-3, #94A3B8);
  }
  &.is-on &__label { color: var(--el-color-primary, #3B6EF5); }
}
</style>