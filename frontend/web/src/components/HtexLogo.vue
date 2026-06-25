<template>
  <span class="htex-logo" :style="{ width: size + 'px', height: size + 'px' }" aria-label="Htex">
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 32 32"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-hidden="true"
    >
      <defs>
        <linearGradient :id="gradId" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#3B6EF5" />
          <stop offset="1" stop-color="#6E59F0" />
        </linearGradient>
      </defs>

      <!-- 渐变圆角方块底 -->
      <rect width="32" height="32" rx="8" :fill="`url(#${gradId})`" />

      <!-- 虚线航迹:H 出发到纸飞机 -->
      <path
        d="M 5 22 Q 12 19, 16 14 T 23 6"
        stroke="#fff"
        stroke-opacity="0.45"
        stroke-width="1"
        stroke-dasharray="1.4 1.6"
        stroke-linecap="round"
        fill="none"
      />

      <!-- H 字(粗,白)— 经典 H 形 -->
      <g fill="#fff">
        <!-- 左竖 -->
        <rect x="6" y="9" width="3.5" height="14" rx="1.2" />
        <!-- 右竖 -->
        <rect x="18.5" y="9" width="3.5" height="14" rx="1.2" />
        <!-- 横 -->
        <rect x="6" y="14.5" width="16" height="3" rx="1.2" />
      </g>

      <!-- 纸飞机(右上,白) -->
      <path
        d="M 22 3.5 L 30 6 L 22.5 8.8 L 24.5 6.2 Z"
        fill="#fff"
      />
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 28 },
})

// 每个实例独立 gradient id,避免 SVG defs 冲突
const gradId = computed(() => `htex-grad-${Math.random().toString(36).slice(2, 9)}`)
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
