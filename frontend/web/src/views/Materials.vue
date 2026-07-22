<!-- Materials.vue — Atlys 风格的资料采集页(5 步导航 + 进度条 + 4 个 doc 槽) -->
<template>
  <div class="mat-page">
    <AppHeader scope="materials" />

    <div class="mat-layout">
      <!-- 左侧 5 步导航 -->
      <aside class="mat-side">
        <button class="mat-side__back" @click="$router.back()" data-testid="mat-back">
          ← {{ t('common.back') }}
        </button>

        <ul class="mat-steps">
          <li
            v-for="(s, i) in STEPS"
            :key="s.key"
            class="mat-step"
            :class="{
              'is-active': s.key === currentStep,
              'is-done': state.steps[s.key]?.completed,
            }"
            :data-testid="`mat-step-${s.key}`"
          >
            <span class="mat-step__icon">{{ s.icon }}</span>
            <span class="mat-step__label">{{ s.label }}</span>
            <span v-if="state.steps[s.key]?.completed" class="mat-step__check">✓</span>
          </li>
        </ul>
      </aside>

      <!-- 主区 -->
      <main class="mat-main">
        <!-- 顶部进度条 -->
        <div class="mat-progress" data-testid="mat-progress">
          <div class="mat-progress__bar">
            <div class="mat-progress__fill" :style="{ width: percent + '%' }" />
          </div>
          <div class="mat-progress__text">{{ percent }}% COMPLETED</div>
        </div>

        <PageHero :title="t('materials.docs_title', 'The Essential Documents') " :subtitle="t('materials.docs_sub', 'Official requirements for your visa. Upload each item to continue.') " />

        <!-- 当前旅客 -->
        <div class="mat-traveler">
          <div class="mat-traveler__avatar">T1</div>
          <div class="mat-traveler__name">{{ state.steps.traveler?.data?.name || 'Traveler 1' }}</div>
          <div class="mat-traveler__count">
            {{ collectedCount }} / {{ totalSlots }} {{ t('materials.slots_collected', 'docs uploaded') }}
          </div>
        </div>

        <!-- 4 个 doc slot -->
        <div class="mat-slots">
          <div
            v-for="slot in DOC_SLOTS"
            :key="slot.key"
            class="mat-slot"
            :class="{
              'is-done': state.slots[slot.key]?.collected,
              'is-error': state.slots[slot.key]?.error,
            }"
            :data-testid="`mat-slot-${slot.key}`"
            @click="openSlot(slot)"
          >
            <!-- 状态:未收集 -->
            <template v-if="!state.slots[slot.key]?.collected">
              <div class="mat-slot__icon">{{ slot.icon }}</div>
              <div class="mat-slot__label">{{ slot.label }}</div>
              <div class="mat-slot__desc">{{ slot.description }}</div>
              <div class="mat-slot__cta">{{ t('mat.cta_upload', 'Upload') }} →</div>
            </template>

            <!-- 状态:已收集 -->
            <template v-else>
              <div class="mat-slot__check">✓</div>
              <div class="mat-slot__label">{{ slot.label }}</div>
              <div class="mat-slot__summary">
                <template v-if="slot.key === 'passport' && state.slots.passport.ocrResult">
                  {{ state.slots.passport.ocrResult.first_name || '—' }}
                  {{ state.slots.passport.ocrResult.last_name || '' }}
                </template>
                <template v-else-if="slot.key === 'photo'">
                  {{ t('mat.photo_done', 'Selfie captured') }}
                </template>
                <template v-else>
                  {{ t('mat.uploaded', 'Uploaded') }}
                </template>
              </div>
              <button class="mat-slot__reupload" @click.stop="openSlot(slot)">
                {{ t('mat.reupload', 'Re-upload') }}
              </button>
            </template>
          </div>
        </div>

        <!-- 底部 Proceed -->
        <div class="mat-footer">
          <div class="mat-footer__lock">🔒 {{ t('mat.aes', 'AES-256 encryption, data stays secure') }}</div>
          <button
            class="mat-footer__proceed"
            :class="{ 'is-disabled': !docsComplete }"
            :disabled="!docsComplete"
            data-testid="mat-proceed"
            @click="onProceed"
          >
            {{ t('mat.proceed', 'Proceed to checkout') }} →
          </button>
        </div>
      </main>
    </div>

    <!-- Passport 上传 modal(3 种方式 + OCR) -->
    <PassportUploadModal
      v-if="activeSlot?.type === 'passport'"
      :open="!!activeSlot"
      :slot-key="activeSlot?.key"
      @close="activeSlot = null"
      @uploaded="onUploaded"
    />

    <!-- 通用上传 modal(其他 type 用 MaterialUploader) -->
    <MaterialUploader
      v-else-if="activeSlot && activeSlot.type !== 'selfie'"
      :slot-key="activeSlot.key"
      :slot-type="activeSlot.type"
      :slot-label="activeSlot.label"
      :existing="state.slots[activeSlot.key]"
      @close="activeSlot = null"
      @uploaded="onUploaded"
    />

    <!-- 自拍活体 modal(仅 photo slot 用) -->
    <SelfieCapture
      v-if="activeSlot?.type === 'selfie'"
      :open="showSelfie"
      @close="showSelfie = false"
      @captured="onSelfieCaptured"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import PageHero from '@/components/PageHero.vue'
import MaterialUploader from '@/components/MaterialUploader.vue'
import PassportUploadModal from '@/components/PassportUploadModal.vue'
import SelfieCapture from '@/components/SelfieCapture.vue'
import { useMaterialsProgress, STEPS, DOC_SLOTS } from '@/composables/useMaterialsProgress'

const { t } = useI18n()
const router = useRouter()

const {
  state,
  currentStep,
  percent,
  totalSlots,
  collectedCount,
  docsComplete,
  setSlot,
} = useMaterialsProgress()

const activeSlot = ref(null)
const showSelfie = ref(false)

function openSlot(slot) {
  activeSlot.value = slot
  if (slot.type === 'selfie') {
    showSelfie.value = true
  }
}

function onUploaded({ slotKey, fileUrl, ocrResult, error }) {
  setSlot(slotKey, {
    collected: !error,
    fileUrl: fileUrl || null,
    ocrResult: ocrResult || null,
    error: error || null,
  })
  // 如果是 passport 且 OCR 拿到了字段,跳到 review 页
  if (slotKey === 'passport' && ocrResult && !error) {
    // 暂存 + 跳 review
    const fileUrlForReview = state.value.slots.passport.fileUrl
    setTimeout(() => {
      router.push({
        name: 'PassportReview',
        query: { from: '/materials' },
      })
    }, 600)
  }
  activeSlot.value = null
  showSelfie.value = false
}

function onSelfieCaptured(blob) {
  // 自拍不走 OCR,直接标完成
  const fileUrl = URL.createObjectURL(blob)
  setSlot('photo', { collected: true, fileUrl, ocrResult: null, error: null })
  showSelfie.value = false
  activeSlot.value = null
}

function onProceed() {
  if (!docsComplete.value) return
  // V2 demo: 跳回 destinations
  router.push({ name: 'Destinations' })
}

onMounted(() => {
  currentStep.value = 'docs'
})
</script>

<style scoped lang="scss">
/* ============================================================
   Materials — Atlys 风格(左侧步骤导航 + 顶部进度条 + 居中 doc 卡片)
   ============================================================ */
.mat-page { min-height: 100vh; background: #fff; }

.mat-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 24px 80px;
  gap: 32px;
  min-height: calc(100vh - 64px);
}

/* ── Sidebar ── */
.mat-side {
  position: sticky;
  top: 88px;
  align-self: start;
}
.mat-side__back {
  background: transparent; border: 0;
  color: var(--ink-3, #64748B); font-size: 13px;
  cursor: pointer; padding: 4px 0; margin-bottom: 24px;
}
.mat-side__back:hover { color: var(--el-color-primary, #3B6EF5); }

.mat-steps { list-style: none; padding: 0; margin: 0; }
.mat-step {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 12px;
  border-radius: 10px;
  font-size: 14px;
  color: var(--ink-3, #64748B);
  cursor: default;
  margin-bottom: 4px;
  transition: background .15s, color .15s;
}
.mat-step.is-active {
  background: rgba(59, 110, 245, .08);
  color: var(--ink-1, #0F172A);
  font-weight: 600;
}
.mat-step.is-done { color: var(--ink-1, #0F172A); }
.mat-step__icon { font-size: 18px; line-height: 1; width: 24px; text-align: center; }
.mat-step__label { flex: 1; }
.mat-step__check {
  font-size: 12px; font-weight: 700;
  width: 18px; height: 18px; border-radius: 50%;
  background: #10B981; color: #fff;
  display: flex; align-items: center; justify-content: center;
}

/* ── Main area ── */
.mat-main {
  display: flex; flex-direction: column;
  min-width: 0;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #0F172A;
  margin: 0 0 8px;
  letter-spacing: -.5px;
  line-height: 1.25;
}
.page-sub {
  font-size: 15px;
  color: #64748B;
  margin: 0 0 28px;
  line-height: 1.5;
}

/* ── Progress bar ── */
.mat-progress { margin-bottom: 24px; }
.mat-progress__bar {
  height: 6px; background: #E2E8F0; border-radius: 999px; overflow: hidden;
}
.mat-progress__fill {
  height: 100%; background: var(--el-color-primary, #3B6EF5);
  border-radius: 999px;
  transition: width .4s ease;
}
.mat-progress__text {
  font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
  color: var(--ink-3, #64748B);
  margin-top: 8px;
  text-align: center;
}

/* ── Traveler header ── */
.mat-traveler {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px;
  background: #F8FAFC;
  border-radius: var(--radius-card, 12px);
  margin-bottom: 24px;
}
.mat-traveler__avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--el-color-primary, #3B6EF5);
  color: #fff; font-size: 12px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  letter-spacing: 1px;
}
.mat-traveler__name { font-weight: 600; color: var(--ink-1, #0F172A); flex: 1; }
.mat-traveler__count { font-size: 13px; color: var(--ink-3, #64748B); }

/* ── Doc slots grid ── */
.mat-slots {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}
.mat-slot {
  position: relative;
  padding: 28px 20px 24px;
  background: #fff;
  border: 2px dashed #E2E8F0;
  border-radius: var(--radius-card, 12px);
  cursor: pointer;
  text-align: center;
  transition: all .2s ease;
  min-height: 160px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px;
}
.mat-slot:hover {
  border-color: var(--el-color-primary, #3B6EF5);
  background: rgba(59, 110, 245, .02);
  transform: translateY(-1px);
}
.mat-slot.is-done {
  border-style: solid;
  border-color: #10B981;
  background: #ECFDF5;
  cursor: default;
}
.mat-slot.is-done:hover { transform: none; background: #ECFDF5; }
.mat-slot.is-error { border-color: #DC2626; background: #FEF2F2; }

.mat-slot__icon { font-size: 36px; line-height: 1; margin-bottom: 4px; }
.mat-slot__label { font-size: 16px; font-weight: 700; color: var(--ink-1, #0F172A); }
.mat-slot__desc { font-size: 12px; color: var(--ink-3, #64748B); max-width: 220px; }
.mat-slot__cta {
  font-size: 12px; font-weight: 600;
  color: var(--el-color-primary, #3B6EF5);
  margin-top: 6px;
}
.mat-slot__check {
  position: absolute; top: 12px; right: 12px;
  width: 28px; height: 28px; border-radius: 50%;
  background: #10B981; color: #fff;
  font-size: 14px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.mat-slot__summary { font-size: 13px; color: var(--ink-1, #0F172A); }
.mat-slot__reupload {
  margin-top: 8px;
  background: transparent;
  border: 1px solid #10B981;
  color: #10B981;
  font-size: 11px; font-weight: 600;
  padding: 4px 12px; border-radius: 999px;
  cursor: pointer;
}
.mat-slot__reupload:hover { background: #10B981; color: #fff; }

/* ── Footer (encryption + Proceed) ── */
.mat-footer {
  position: sticky;
  bottom: 0;
  background: #fff;
  padding: 16px 0 0;
  border-top: 1px solid #E2E8F0;
  margin-top: auto;
}
.mat-footer__lock {
  text-align: center;
  font-size: 12px; color: var(--ink-3, #64748B);
  margin-bottom: 12px;
}
.mat-footer__proceed {
  width: 100%;
  background: var(--el-color-primary, #3B6EF5);
  color: #fff;
  border: 0; border-radius: var(--radius-control, 8px);
  padding: 14px 24px;
  font-size: 15px; font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.2px;
  transition: all .2s ease;
}
.mat-footer__proceed:hover:not(.is-disabled) {
  box-shadow: 0 6px 20px rgba(59, 110, 245, .35);
  transform: translateY(-1px);
}
.mat-footer__proceed.is-disabled {
  background: #E2E8F0; color: #94A3B8; cursor: not-allowed;
}

@media (max-width: 768px) {
  .mat-layout { grid-template-columns: 1fr; padding: 16px; }
  .mat-side { position: static; }
  .mat-steps { display: flex; gap: 8px; overflow-x: auto; margin-bottom: 16px; }
  .mat-step { flex-shrink: 0; padding: 8px 12px; }
  .mat-slots { grid-template-columns: 1fr; }
}
</style>
