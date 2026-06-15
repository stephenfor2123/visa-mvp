<!--
  AffiliateLink.vue — A-W9-2 推广链接生成器

  能力:
    1) partner_id 输入 → 实时生成完整推广 URL (含 aff_code, 可选 click_id)
    2) 一键复制 (Clipboard API + fallback)
    3) 二维码占位 (V2 mock 用 SVG hash 网格,V2.1 替换为 qrcode 库)
    4) 调 /api/v2/affiliate/track 后端记录点击 (fire-and-forget)

  父组件 (eg. admin) 传 partnerId 即可,组件内部:
    - 监听 partnerId 变化,实时更新生成的链接
    - 一键复制时,存 click_id 到 LS 供 OrderNew 读取

  V2 限制: 不接 partner 端 /stats (B-W8-4 第 5 端点),需要 partner-key auth
  → 留 TODO,partner dashboard 在 W10+ 接
-->
<template>
  <div class="affiliate-link">
    <h3 class="affiliate-link__title">{{ t('affiliate.generator_title') }}</h3>
    <p class="affiliate-link__desc">{{ t('affiliate.generator_desc') }}</p>

    <div class="affiliate-link__field">
      <label class="affiliate-link__label">
        {{ t('affiliate.partner_label') }}
      </label>
      <div class="affiliate-link__input-row">
        <input
          v-model="partnerId"
          class="affiliate-link__input"
          :placeholder="t('affiliate.partner_placeholder')"
          maxlength="32"
          data-testid="affiliate-partner-input"
        />
        <button
          type="button"
          class="affiliate-link__btn affiliate-link__btn--primary"
          :disabled="!isValidPartner"
          data-testid="affiliate-generate-btn"
          @click="onGenerate"
        >{{ t('affiliate.track_button') }}</button>
      </div>
      <span v-if="!isValidPartner && partnerId" class="affiliate-link__err">
        {{ t('affiliate.err_format') }}
      </span>
    </div>

    <!-- 生成的推广链接 + 复制 + 二维码 -->
    <div v-if="generatedUrl" class="affiliate-link__result" data-testid="affiliate-result">
      <div class="affiliate-link__url-row">
        <code class="affiliate-link__url" data-testid="affiliate-url">{{ generatedUrl }}</code>
        <button
          type="button"
          class="affiliate-link__btn affiliate-link__btn--outline"
          data-testid="affiliate-copy-btn"
          @click="onCopy"
        >
          {{ copied ? '✓ ' + t('affiliate.copied') : t('affiliate.copy_link') }}
        </button>
      </div>
      <div class="affiliate-link__qr-row">
        <div class="affiliate-link__qr" data-testid="affiliate-qr" v-html="qrSvg"></div>
        <div class="affiliate-link__meta">
          <p class="affiliate-link__meta-line">
            <span class="affiliate-link__meta-key">{{ t('affiliate.code_label') }}:</span>
            <span class="affiliate-link__meta-val">{{ partnerId }}</span>
          </p>
          <p class="affiliate-link__meta-line" v-if="lastClickId">
            <span class="affiliate-link__meta-key">{{ t('affiliate.click_id_label') }}:</span>
            <span class="affiliate-link__meta-val">{{ lastClickId }}</span>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { trackClick, savePendingClick } from '@/api/affiliate'

const { t } = useI18n()

const props = defineProps({
  // 可选: 父级直接传 partner_id (eg. 管理员后台)
  modelValue: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'generated'])

const partnerId = ref(props.modelValue || '')
watch(() => props.modelValue, (v) => { if (v) partnerId.value = v })
watch(partnerId, (v) => emit('update:modelValue', v))

// 4-32 [A-Za-z0-9_-]
const isValidPartner = computed(() => /^[A-Za-z0-9_-]{4,32}$/.test(partnerId.value))

const generatedUrl = ref('')
const lastClickId = ref('')
const copied = ref(false)

// 实时预览 URL (不写后端,只展示)
const previewUrl = computed(() => {
  if (!isValidPartner.value) return ''
  const base = window.location.origin || 'https://visa.example.com'
  return `${base}/?aff=${encodeURIComponent(partnerId.value)}`
})

// 二维码: V2 mock 用 SVG hash 网格 (5x5 + 3 角定位框)
// V2.1 替换为 qrcode 库
const qrSvg = computed(() => {
  if (!generatedUrl.value) return ''
  const seed = generatedUrl.value
  const size = 11  // 11x11 网格
  const cells = []
  // 角定位框 (3 个): 左上、右上、左下 (7x7 子区域)
  const corners = [
    [0, 0], [size - 7, 0], [0, size - 7]
  ]
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let on = false
      // 3 个角定位框
      for (const [cx, cy] of corners) {
        const ox = x - cx
        const oy = y - cy
        if (ox >= 0 && ox < 7 && oy >= 0 && oy < 7) {
          // 7x7: 外框 + 中心 3x3
          const isOuter = ox === 0 || ox === 6 || oy === 0 || oy === 6
          const isInner = ox >= 2 && ox <= 4 && oy >= 2 && oy <= 4
          if (isOuter || isInner) on = true
        }
      }
      // 中间数据区: 用 seed 字符串 hash 决定
      if (!on) {
        // 简单 hash: (x * 31 + y * 17 + seed char codes) % 2
        let h = 0
        for (let i = 0; i < seed.length; i++) {
          h = (h * 31 + seed.charCodeAt(i)) >>> 0
        }
        h = (h + x * 31 + y * 17) >>> 0
        on = (h % 3) === 0
      }
      if (on) {
        cells.push(`<rect x="${x}" y="${y}" width="1" height="1" fill="#0F172A"/>`)
      }
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="120" height="120" shape-rendering="crispEdges"><rect width="${size}" height="${size}" fill="#fff"/>${cells.join('')}</svg>`
})

// 点击"生成 + 追踪"按钮: 调 trackClick 后端, 拿 click_id, 写 LS
async function onGenerate() {
  if (!isValidPartner.value) return
  try {
    const r = await trackClick({ aff_code: partnerId.value, landing_path: '/' })
    lastClickId.value = r?.click_id || ''
    if (r?.click_id) {
      savePendingClick({ click_id: r.click_id, aff_code: partnerId.value, landing_path: '/' })
    }
    generatedUrl.value = previewUrl.value
    emit('generated', { partner_id: partnerId.value, click_id: lastClickId.value, url: generatedUrl.value })
  } catch (e) {
    // track 失败仍展示 URL(本地用)
    lastClickId.value = ''
    generatedUrl.value = previewUrl.value
    emit('generated', { partner_id: partnerId.value, click_id: '', url: generatedUrl.value, error: e?.message })
  }
}

async function onCopy() {
  if (!generatedUrl.value) return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(generatedUrl.value)
    } else {
      // fallback: textarea
      const ta = document.createElement('textarea')
      ta.value = generatedUrl.value
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copied.value = true
    setTimeout(() => { copied.value = false }, 1600)
  } catch (_) {
    // 复制失败不阻塞,UI 也不弹 toast(静默)
  }
}
</script>

<style scoped lang="scss">
.affiliate-link {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px; padding: 20px 22px;
}
.affiliate-link__title {
  margin: 0 0 6px; font-size: 15px; font-weight: 600; color: #0F172A;
  display: flex; align-items: center; gap: 6px;
  &::before {
    content: '🔗'; font-size: 16px;
  }
}
.affiliate-link__desc {
  margin: 0 0 14px; font-size: 12px; color: #64748B;
}
.affiliate-link__field { margin-bottom: 14px; }
.affiliate-link__label {
  display: block; font-size: 12px; font-weight: 500;
  color: #334155; margin-bottom: 6px;
}
.affiliate-link__input-row {
  display: flex; gap: 8px; align-items: stretch;
}
.affiliate-link__input {
  flex: 1; height: 38px; padding: 0 12px;
  border: 1px solid var(--border, #E2E8F0); border-radius: 8px;
  font-size: 13px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #0F172A; background: #fff;
  outline: none; transition: border-color .15s, box-shadow .15s;
  &:focus { border-color: #3B6EF5; box-shadow: 0 0 0 3px rgba(59,110,245,.15); }
}
.affiliate-link__btn {
  display: inline-flex; align-items: center; justify-content: center;
  height: 38px; padding: 0 14px; border-radius: 8px;
  font-size: 13px; font-weight: 500; cursor: pointer;
  border: 1px solid transparent; transition: all .15s;
  &:disabled { opacity: .5; cursor: not-allowed; }
  &--primary { background: #3B6EF5; color: #fff; }
  &--primary:hover:not(:disabled) { background: #2C5DE0; }
  &--outline { background: #fff; color: #3B6EF5; border-color: #3B6EF5; }
  &--outline:hover { background: #EAF0FE; }
}
.affiliate-link__err {
  display: block; margin-top: 4px; font-size: 11px; color: #DC2626;
}

.affiliate-link__result {
  margin-top: 14px; padding: 14px;
  background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 10px;
}
.affiliate-link__url-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
}
.affiliate-link__url {
  flex: 1; padding: 8px 10px;
  background: #fff; border: 1px solid var(--border, #E2E8F0); border-radius: 6px;
  font-family: ui-monospace, monospace; font-size: 11px;
  color: #1E293B; word-break: break-all;
}
.affiliate-link__qr-row {
  display: flex; align-items: center; gap: 14px;
}
.affiliate-link__qr {
  flex-shrink: 0; width: 120px; height: 120px;
  border: 1px solid var(--border, #E2E8F0); border-radius: 6px;
  background: #fff; padding: 4px;
  :deep(svg) { display: block; width: 100%; height: 100%; }
}
.affiliate-link__meta { flex: 1; min-width: 0; }
.affiliate-link__meta-line {
  margin: 0 0 4px; font-size: 12px; color: #64748B;
}
.affiliate-link__meta-key { color: #94A3B8; margin-right: 4px; }
.affiliate-link__meta-val {
  font-family: ui-monospace, monospace; font-weight: 600; color: #0F172A;
  word-break: break-all;
}
</style>
