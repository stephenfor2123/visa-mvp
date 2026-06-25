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

      <!-- 方形签证章(略 -4° 旋转,模拟盖章质感) -->
      <g transform="rotate(-4 16 17)">
        <rect
          x="6.5" y="8" width="19" height="19" rx="2"
          fill="none" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"
        />
      </g>

      <!-- H 字母(也跟随印章旋转) -->
      <g transform="rotate(-4 16 17)" fill="#fff">
        <rect x="11"   y="12"   width="2.4" height="11" rx="0.5" />
        <rect x="18.6" y="12"   width="2.4" height="11" rx="0.5" />
        <rect x="11"   y="16.5" width="10"  height="2.4" rx="0.5" />
      </g>

      <!-- 纸飞机(印章上方,小一角,营造"已盖章+启程") -->
      <path
        d="M 22 3 L 29 5 L 22.8 7.4 L 24.4 5 Z"
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
