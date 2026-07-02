<template>
  <div class="mw-page">
    <AppHeader scope="materials" />

    <main class="mw-main">
      <header class="mw-hero">
        <h1 class="mw-hero__title">{{ t('wizard.title') }}</h1>
        <p class="mw-hero__sub">{{ flagOf(countryCode) }} {{ destinationName || countryCode }} · {{ t('wizard.subtitle') }}</p>
      </header>

      <!-- 整体进度条 -->
      <div class="mw-progress">
        <div class="mw-progress__bar"><div class="mw-progress__fill" :style="{ width: wizard.overallPercent.value + '%' }" /></div>
        <div class="mw-progress__text">{{ wizard.overallPercent.value }}% {{ t('wizard.progress_done') }}</div>
      </div>

      <!-- 分类导航 -->
      <div class="mw-steps">
        <button
          v-for="(cat, i) in wizard.CATEGORIES"
          :key="cat.key"
          type="button"
          class="mw-step"
          :class="{
            'is-active': wizard.state.activeCategory === cat.key,
            'is-done': wizard.categoryDone(cat.key),
          }"
          :data-testid="`mw-step-${cat.key}`"
          @click="wizard.goToCategory(cat.key)"
        >
          <span class="mw-step__icon" :class="`is-${cat.icon}`">
            <CategoryIcon :name="cat.icon" />
          </span>
          <span class="mw-step__label">{{ t(cat.labelKey) }}</span>
          <span v-if="wizard.categoryDone(cat.key)" class="mw-step__check">✓</span>
        </button>
      </div>

      <!-- 当前分类内容 -->
      <section class="mw-panel" :data-testid="`mw-panel-${wizard.activeCategoryDef.value.key}`">
        <h2 class="mw-panel__title">{{ t(wizard.activeCategoryDef.value.labelKey) }}</h2>

        <!-- 表单大类：走完前面5类之后的收尾 -->
        <template v-if="wizard.activeCategoryDef.value.isFormStep">
          <div class="mw-finish">
            <p class="mw-finish__text">{{ t('wizard.finish_text', { n: wizard.allMaterialIds.value.length }) }}</p>
            <button class="mw-finish__cta" data-testid="mw-goto-form" @click="goToOrderForm">
              {{ t('wizard.finish_cta') }} →
            </button>
          </div>
        </template>

        <!-- 行程住宿 -->
        <template v-else-if="wizard.activeCategoryDef.value.isTravelPlanner">
          <TravelPlanner
            :plan="wizard.state.travelPlan"
            :destination-name="destinationName"
            :on-generate-itinerary="wizard.generateItinerary"
            :on-compile-itinerary-text="wizard.compileItineraryText"
            :on-rebuild-days="wizard.rebuildTravelDays"
            :on-validate-for-generate="wizard.validateForGenerate"
            :day-city-display-fn="wizard.dayCityDisplay"
            :on-mark-day-field-manual="wizard.markDayFieldManual"
            :on-sync-destination-to-days="wizard.syncDestinationToDays"
          />
        </template>

        <!-- 普通上传大类 -->
        <template v-else>
          <div class="mw-items">
            <UploadItemCard
              v-for="item in wizard.activeCategoryDef.value.items"
              :key="item.key"
              :item-key="item.key"
              :item="item"
              :record="wizard.state.categories[wizard.activeCategoryDef.value.key].items[item.key]"
              :upload-fn="(file, onProgress) => wizard.uploadItem(wizard.activeCategoryDef.value.key, item.key, file, onProgress)"
              :country-code="countryCode"
              @remove="wizard.removeItem(wizard.activeCategoryDef.value.key, item.key)"
            />
          </div>
        </template>

        <!-- 校验问题 -->
        <div v-if="currentIssues.length" class="mw-issues" data-testid="mw-issues">
          <div v-for="(iss, i) in currentIssues" :key="i" class="mw-issue" :class="`is-${iss.severity}`">
            <b>{{ iss.title }}</b>
            <span v-if="iss.detail">{{ iss.detail }}</span>
          </div>
        </div>

        <!-- 底部操作 -->
        <div v-if="!wizard.activeCategoryDef.value.isFormStep" class="mw-footer">
          <button
            v-if="wizard.activeCategoryDef.value.skippable && !wizard.categoryDone(wizard.activeCategoryDef.value.key)"
            class="mw-footer__skip"
            data-testid="mw-skip"
            @click="onSkip"
          >
            {{ t('wizard.skip') }}
          </button>
          <button
            class="mw-footer__next"
            :class="{ 'is-disabled': !canAdvance }"
            :disabled="!canAdvance || validating"
            data-testid="mw-next"
            @click="onNext"
          >
            {{ validating ? t('wizard.validating') : t('wizard.next') + ' →' }}
          </button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import UploadItemCard from '@/components/UploadItemCard.vue'
import TravelPlanner from '@/components/TravelPlanner.vue'
import { useMaterialWizard } from '@/composables/useMaterialWizard'
import { listDestinations } from '@/api/destinations'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const countryCode = (route.query.country || '').toString().toUpperCase()
const visaType = (route.query.visa_type || 'tourism').toString()

const wizard = useMaterialWizard(countryCode, visaType)
// 组合式函数里的 computed 在 <script setup> 顶层会被自动解包，但这里我们把整个
// wizard 对象透传给 template，所以模板里读取时手动 .value（wizard.overallPercent.value 等）。

const destinationName = ref('')
listDestinations({ lang: locale.value }).then((list) => {
  const d = (list || []).find((x) => x.country_code === countryCode)
  if (d) destinationName.value = d.country_name
}).catch(() => {})

const FLAG_MAP = {
  US: '🇺🇸', GB: '🇬🇧', AU: '🇦🇺', FR: '🇫🇷', DE: '🇩🇪', IT: '🇮🇹', ES: '🇪🇸',
}
function flagOf(cc) { return FLAG_MAP[cc] || '🌐' }

const validating = ref(false)

const currentIssues = computed(() => {
  const cat = wizard.state.categories[wizard.activeCategoryDef.value.key]
  return cat?.issues || []
})

const canAdvance = computed(() => wizard.activeCategoryReady.value)

async function onNext() {
  if (!canAdvance.value) return
  validating.value = true
  try {
    const result = await wizard.validateCategory(wizard.activeCategoryDef.value.key)
    if (result.validated) {
      wizard.goToNextCategory()
    }
  } finally {
    validating.value = false
  }
}

function onSkip() {
  wizard.skipCategory(wizard.activeCategoryDef.value.key)
  wizard.goToNextCategory()
}

function goToOrderForm() {
  router.push({
    name: 'OrderNew',
    query: {
      country: countryCode,
      visa_type: visaType,
      material_ids: wizard.allMaterialIds.value.join(','),
    },
  })
}

// ------------------------------------------------------------------ //
// 分类图标 — 与 Apply.vue 材料预览用的同一套线条图标，保持视觉一致           //
// ------------------------------------------------------------------ //
const CategoryIcon = {
  props: { name: String },
  render() {
    const common = { viewBox: '0 0 24 24', width: 16, height: 16, fill: 'none', 'aria-hidden': 'true' }
    const stroke = { stroke: 'currentColor' }
    switch (this.name) {
      case 'identity':
        return h('svg', common, [
          h('rect', { x: 3, y: 5, width: 18, height: 14, rx: 2.5, ...stroke, 'stroke-width': 1.7 }),
          h('circle', { cx: 8.5, cy: 11, r: 1.8, ...stroke, 'stroke-width': 1.5 }),
          h('path', { d: 'M5.5 16c.6-1.7 1.9-2.5 3-2.5s2.4.8 3 2.5', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
          h('path', { d: 'M14.5 10h4M14.5 13h4', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
      case 'financial':
        return h('svg', common, [
          h('circle', { cx: 12, cy: 12, r: 8.5, ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M9.3 9.3c0-1.1 1.1-2 2.7-2s2.7.9 2.7 2c0 2.8-5.4 1.4-5.4 4.2 0 1.1 1.2 2 2.7 2s2.7-.9 2.7-2', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
          h('path', { d: 'M12 6v1.3M12 16.7V18', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
      case 'work':
        return h('svg', common, [
          h('rect', { x: 3, y: 8, width: 18, height: 11, rx: 2, ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M8.5 8V6.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V8', ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M3 13h18', ...stroke, 'stroke-width': 1.5 }),
        ])
      case 'travel':
        return h('svg', common, [
          h('path', { d: 'M13 3.5l-2.4 2.4L4 7.3l-.9 1.6 6.6 1.6-.4 4.3-1.9 1.4.2 1.6 2.9-1 1.6 2.6 1.5-.6-.5-3 4-3 1.6-4.3-1.6-1.6-3.3.9-1-2.9z', ...stroke, 'stroke-width': 1.4, 'stroke-linejoin': 'round' }),
        ])
      case 'insurance':
        return h('svg', common, [
          h('path', { d: 'M12 3.5l7 3v5.2c0 4.6-3 7.9-7 8.8-4-.9-7-4.2-7-8.8V6.5l7-3z', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M9 12l2 2 4-4.2', ...stroke, 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }),
        ])
      case 'form':
      default:
        return h('svg', common, [
          h('path', { d: 'M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5z', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M14 3.5V8h4', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M9 12.5h6M9 15.5h6', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
    }
  },
}
</script>

<style scoped lang="scss">
.mw-page { min-height: 100vh; background: linear-gradient(180deg, #f8faff 0%, #fff 260px); }
.mw-main { max-width: 900px; margin: 0 auto; padding: 32px 24px 80px; }

.mw-hero { text-align: center; margin-bottom: 24px; }
.mw-hero__title {
  font-size: 30px; font-weight: 800; margin: 0 0 6px; letter-spacing: -.5px;
  background: linear-gradient(135deg, #0f172a 0%, #3B6EF5 120%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.mw-hero__sub { font-size: 14px; color: #64748b; margin: 0; }

.mw-progress { margin-bottom: 24px; }
.mw-progress__bar { height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.mw-progress__fill { height: 100%; background: linear-gradient(90deg, #3B6EF5, #6E59F0); border-radius: 999px; transition: width .4s ease; }
.mw-progress__text { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: #94a3b8; text-align: center; margin-top: 8px; }

.mw-steps { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 24px; }
.mw-step {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 12px 6px; border-radius: 12px; border: 1.5px solid transparent; background: transparent;
  cursor: pointer; transition: all .15s ease; position: relative;
  &.is-active { background: #eff6ff; border-color: #3b6ef5; }
  &.is-done .mw-step__icon { background: #ecfdf3; color: #16a34a; }
}
.mw-step__icon {
  width: 30px; height: 30px; border-radius: 9px; background: #f1f5f9; color: #64748b;
  display: flex; align-items: center; justify-content: center;
}
.mw-step__label { font-size: 11px; font-weight: 600; color: #475569; text-align: center; }
.mw-step__check {
  position: absolute; top: 4px; right: 4px; width: 14px; height: 14px; border-radius: 50%;
  background: #16a34a; color: #fff; font-size: 9px; display: flex; align-items: center; justify-content: center;
}

.mw-panel {
  background: #fff; border: 1px solid #e9edf5; border-radius: 20px;
  padding: 28px 30px; box-shadow: 0 8px 28px rgba(15,23,42,.06);
}
.mw-panel__title { font-size: 19px; font-weight: 700; color: #0f172a; margin: 0 0 18px; }

.mw-items { display: flex; flex-direction: column; gap: 14px; }

.mw-finish { text-align: center; padding: 20px 0; }
.mw-finish__text { color: #475569; font-size: 14px; margin: 0 0 20px; line-height: 1.6; }
.mw-finish__cta {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border: 0;
  padding: 14px 28px; border-radius: 14px; font-size: 15px; font-weight: 700; cursor: pointer;
  box-shadow: 0 10px 24px rgba(15,23,42,.18);
}

.mw-issues { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
.mw-issue {
  font-size: 12.5px; padding: 10px 14px; border-radius: 10px; display: flex; flex-direction: column; gap: 2px;
  &.is-error, &.is-critical { background: #fef2f2; color: #b91c1c; }
  &.is-warning { background: #fffbeb; color: #b45309; }
  &.is-info { background: #eff6ff; color: #1e40af; }
}

.mw-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.mw-footer__skip {
  background: transparent; border: 1px solid #cbd5e1; color: #64748b;
  padding: 12px 20px; border-radius: 12px; font-size: 13.5px; font-weight: 600; cursor: pointer;
}
.mw-footer__next {
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%); color: #fff; border: 0;
  padding: 12px 26px; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer;
  box-shadow: 0 8px 20px rgba(59,110,245,.25);
  &.is-disabled { background: #e2e8f0; color: #94a3b8; box-shadow: none; cursor: not-allowed; }
}

@media (max-width: 640px) {
  .mw-steps { grid-template-columns: repeat(3, 1fr); }
}
</style>
