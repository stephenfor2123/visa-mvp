<template>
  <header class="page-hero" :class="{ 'page-hero--on-dark': onDark, 'page-hero--flush': flush }">
    <component :is="heading" class="page-hero__title">
      <slot>{{ title }}</slot>
    </component>
    <p v-if="subtitle || $slots.subtitle" class="page-hero__sub">
      <slot name="subtitle">{{ subtitle }}</slot>
    </p>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  heading: { type: String, default: 'h1' },
  onDark: { type: Boolean, default: false },
  flush: { type: Boolean, default: false },
})
</script>
