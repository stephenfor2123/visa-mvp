<template>
  <!--
    W56: 产品定价页 — 从首页抽出, 独立路由 /pricing
    复用 PricingSection (区块组件) 渲染主表格 + 退款规则双卡 + 3 条合规 bullet
    顶部为 page-hero 让导航返回 / 锚点都顺手
  -->
  <div class="pricing-page">
    <AppHeader />

    <main class="app-container app-page pricing-page__main">
      <!--
        独立页不重复 page hero 标题:
        PricingSection 内部已经有标题/副标题区块, 与页面标题内容重复 (W58 精简)
        standalone prop 关掉首页那种外层卡片框, 让定价区块直接铺到页面背景上
      -->
      <PricingSection standalone />

      <!-- W47d+ : 删底部"立即办签证"+"联系客服"双 CTA。
           - "立即办签证":首页 hero 已有,产品决策页面底部不再重复
           - "联系客服":全站 header/footer 已可触达,定价页不重复放
      -->
    </main>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import PricingSection from '@/components/PricingSection.vue'

const { t } = useI18n()
</script>

<style scoped lang="scss">
.pricing-page {
  min-height: 100vh;
  background: #fff;
  display: flex;
  flex-direction: column;

  &__main {
    flex: 1;
    width: 100%;
  }

  // __cta / __btn 已删 (W47d+)
}
</style>
