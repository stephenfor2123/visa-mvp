<template>
  <div class="not-found app-container app-page">
    <h1 class="section-title">404</h1>
    <p class="section-sub">{{ t('notfound.title') }},<router-link to="/home">{{ t('notfound.back_home') }}</router-link></p>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<style scoped lang="scss">
.not-found {
  text-align: center;
  padding-top: 96px;
}
</style>