<template>
  <div class="country-picker" role="group" :aria-label="ariaLabel || undefined">
    <template v-if="normalizedGroups.length">
      <div
        v-for="group in normalizedGroups"
        :key="group.key"
        class="country-picker__group"
        :data-testid="group.testId || undefined"
      >
        <h3 v-if="group.title" class="country-picker__group-title">
          {{ group.title }}
          <span v-if="group.showCount !== false" class="country-picker__count">{{ group.items.length }}</span>
        </h3>
        <div class="country-picker__grid">
          <button
            v-for="item in group.items"
            :key="item.code"
            type="button"
            class="country-picker__btn"
            :class="{ 'is-selected': modelValue === item.code }"
            :aria-pressed="modelValue === item.code"
            :data-testid="item.testId || undefined"
            @click="onSelect(item.code)"
          >
            <span class="country-picker__flag" aria-hidden="true">{{ item.flag }}</span>
            <span class="country-picker__name">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  /** Flat list: [{ code, flag, label, testId? }] */
  items: { type: Array, default: () => [] },
  /**
   * Grouped list: [{ key, title?, items, testId?, showCount? }]
   * When provided, takes precedence over `items`.
   */
  groups: { type: Array, default: null },
  ariaLabel: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'select'])

const normalizedGroups = computed(() => {
  if (Array.isArray(props.groups) && props.groups.length) {
    return props.groups.map((g, i) => ({
      key: g.key || `g-${i}`,
      title: g.title || '',
      items: g.items || [],
      testId: g.testId,
      showCount: g.showCount,
    }))
  }
  if (props.items?.length) {
    return [{ key: 'all', title: '', items: props.items, showCount: false }]
  }
  return []
})

function onSelect(code) {
  emit('update:modelValue', code)
  emit('select', code)
}
</script>
