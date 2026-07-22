<!--
  CityInput.vue — 简化为纯文本输入框

  W48: 删掉 Combobox 建议下拉（用户反馈"什么形式的下拉都不要"）。
  - 之前 v-click-outside / keyboard nav / suggestions 列表全部移除
  - 行为：普通 input,用户想填啥填啥,没有任何自动补全/弹层
-->
<template>
  <input
    ref="inputEl"
    :value="modelValue"
    type="text"
    class="city-input__field"
    :class="[`city-input__field--${size}`]"
    :placeholder="placeholder"
    :data-testid="testId"
    autocomplete="off"
    spellcheck="false"
    @input="onInput"
  />
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入城市' },
  testId: { type: String, default: 'city-input' },
  countryCode: { type: String, default: '' },  // 保留以兼容调用方,不再使用
  size: { type: String, default: 'md' },
})
const emit = defineEmits(['update:modelValue'])

const inputEl = ref(null)

function onInput(e) {
  emit('update:modelValue', e.target.value)
}
</script>

<style scoped>
.city-input__field {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: var(--radius-control, 8px);
  background: #ffffff;
  color: #0f172a;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.city-input__field:focus {
  border-color: #3B6EF5;
  box-shadow: var(--focus-ring, 0 0 0 3px rgba(59, 110, 245, .18));
}
.city-input__field--sm {
  padding: 6px 10px;
  font-size: 13px;
}
</style>
