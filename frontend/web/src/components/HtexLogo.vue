<template>
  <span class="htex-logo" :style="wrapStyle" aria-label="Htex">
    <svg
      :width="width"
      :height="size"
      :viewBox="`0 0 ${vbW} ${vbH}`"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-hidden="true"
    >
      <text
        x="0"
        :y="vbH * 0.78"
        font-family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', 'PingFang SC', 'Inter', Arial, sans-serif"
        :font-size="vbH * 0.78"
        font-weight="900"
        fill="#000"
        :letter-spacing="vbH * -0.045"
      >Htex</text>
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 28 },
  // 宽高比 — 默认 3:1 适配 Htex 文字比例
  width: { type: [Number, String], default: null },
  // 颜色 — 默认纯黑(用户拍板:简单黑色)
  color: { type: String, default: '#000' },
})

// viewBox 比例:宽 = 高 × 3
const vbH = 32
const vbW = vbH * 3

// 文字尺寸 = 高的 78%(让 H t e x 视觉上居中)
const fontSize = vbH * 0.78

// 实际渲染宽度
const width = computed(() => {
  if (props.width !== null) return Number(props.width)
  return Number(props.size) * 3
})

const wrapStyle = computed(() => ({
  width: width.value + 'px',
  height: Number(props.size) + 'px',
  color: props.color,
}))
</script>

<style scoped>
.htex-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  vertical-align: middle;
  line-height: 0;
}
.htex-logo svg {
  display: block;
}
</style>
