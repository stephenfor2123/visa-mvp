<template>
  <div class="app-card" :class="{ 'app-card--hoverable': hoverable, 'app-card--padded': padded }">
    <header v-if="$slots.header || title" class="app-card__header">
      <slot name="header">
        <h3 class="app-card__title">{{ title }}</h3>
        <p v-if="subtitle" class="app-card__subtitle">{{ subtitle }}</p>
      </slot>
    </header>
    <div class="app-card__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="app-card__footer">
      <slot name="footer" />
    </footer>
  </div>
</template>

<script setup>
defineProps({
  title: String,
  subtitle: String,
  hoverable: { type: Boolean, default: false },
  padded: { type: Boolean, default: true }
})
</script>

<style scoped lang="scss">
.app-card {
  background: #fff;
  border: 0;
  border-radius: 12px;
  box-shadow: none;
  overflow: hidden;
  transition: box-shadow .2s, transform .2s;
}
.app-card--hoverable:hover {
  box-shadow: 0 8px 20px rgba(15, 23, 42, .08);
  transform: translateY(-1px);
}
.app-card--padded .app-card__body { padding: 18px 20px; }
.app-card__header {
  padding: 14px 20px;
  border-bottom: 0;
}
.app-card__title { margin: 0; font-size: 16px; font-weight: 600; color: var(--ink-1, #0F172A); }
.app-card__subtitle { margin: 4px 0 0; font-size: 13px; color: var(--ink-3, #64748B); }
.app-card__footer {
  padding: 12px 20px;
  border-top: 0;
  background: var(--bg-alt, #F8FAFC);
}
</style>