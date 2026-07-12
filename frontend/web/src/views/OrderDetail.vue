<!--
  OrderDetail.vue — A Story 1.2.2a
  =================================
  N4 Order status detail page (V2 §3.6.2)

  Key capabilities:
    1) 5-state timeline: created -> submitted -> reviewing -> approved (rejected branch)
    2) WebSocket primary (ws://.../ws/orders/{orderNo}) + 30s polling fallback
    3) ETag If-None-Match (304 not updating UI)
    4) Current state highlight (blue/green/red/grey)
    5) RPA screenshot replay (rpa_screenshot_url + rpa_screenshots array)
    6) Cancel order (created state only, 4010 toast)
    7) Logout (clear localStorage.visa.auth -> jump /login)

  Mock mode: VITE_MOCK=true (default) uses localStorage fallback, WS via window.__visaMockPush()
  Real backend mode: VITE_MOCK=false direct to B /api/v2/orders/{no}, WS direct to backend ws endpoint
-->
<template>
  <div class="orderdetail-page">
    <AppHeader scope="order-detail" />
    <main class="app-container app-page orderdetail-shell">
      <!-- Loading/Error -->
      <div v-if="loading && !order" class="state-block" data-testid="orderdetail-loading">
        <span class="spinner" aria-hidden="true"></span> {{ t('common.loading') }}
      </div>
      <div v-else-if="loadError" class="state-block state-block--err" data-testid="orderdetail-error">
        <p v-if="isAuthExpiredState">🔒 {{ t('orderdetail.session_expired_msg') }}</p>
        <p v-else>❌ {{ loadError }}</p>
        <div class="state-block__actions" v-if="isAuthExpiredState">
          <AppButton ref="reloginBtnRef" variant="primary" size="md">{{ t('common.relogin') }}</AppButton>
        </div>
        <AppButton v-else ref="retryBtnRef" variant="outline" size="md">{{ t('orderdetail.retry_btn') }}</AppButton>
      </div>

      <template v-else-if="order">
        <!-- Top: order number + current status badge -->
        <section class="hero" data-testid="orderdetail-hero">
          <div class="hero__left">
            <p class="hero__label">{{ t('orderdetail.order_no_label') }}</p>
            <h1 class="hero__no" data-testid="orderdetail-order-no">{{ order.order_no }}</h1>
            <p class="hero__sub">{{ t('orderdetail.page_subtitle') }}</p>
          </div>
          <div class="hero__right">
            <span
              class="status-badge"
              :class="`status-badge--${userStatus.tone}`"
              data-testid="orderdetail-status-badge"
            >
              <span class="status-badge__icon">{{ userStatusIcon(userStatus.key) }}</span>
              <span>{{ userStatus.label }}</span>
            </span>
            <p class="hero__updated" data-testid="orderdetail-updated">
              {{ t('orderdetail.updated_at_label') }}: {{ formatDateTime(order.updated_at) }}
            </p>
          </div>
        </section>

        <!-- 申请进度 milestones（主轨 completed 后，官网提交为可选里程碑） -->
        <section
          v-if="orderMilestones.length"
          class="card"
          data-testid="orderdetail-milestones"
        >
          <h2 class="card__title">{{ t('orderdetail.section_milestones') }}</h2>
          <p class="milestones__hint">{{ t('orderdetail.milestones_hint') }}</p>
          <div class="milestones">
            <div
              v-for="(m, idx) in orderMilestones"
              :key="m.key"
              class="ms-step"
              :class="{
                'ms-step--done': m.state === 'done',
                'ms-step--current': m.state === 'current',
                'ms-step--pending': m.state === 'pending',
              }"
              :data-testid="`orderdetail-ms-${m.key}`"
            >
              <div class="ms-step__node">
                <span v-if="m.state === 'done'">✓</span>
                <span v-else>{{ m.icon }}</span>
              </div>
              <div class="ms-step__body">
                <p class="ms-step__label">{{ t(`orderdetail.milestone_${m.key}`) }}</p>
                <p class="ms-step__desc">{{ t(`orderdetail.milestone_${m.key}_desc`) }}</p>
                <p v-if="m.at" class="ms-step__at">{{ formatDateTime(m.at) }}</p>
              </div>
              <div v-if="idx < orderMilestones.length - 1" class="ms-step__line"></div>
            </div>
          </div>
          <div
            v-if="showPortalConfirmBtn"
            class="portal-confirm"
            data-testid="orderdetail-portal-confirm"
          >
            <p>{{ t('orderdetail.portal_confirm_hint') }}</p>
            <AppButton
              variant="primary"
              size="md"
              :loading="portalConfirming"
              data-testid="orderdetail-portal-confirm-btn"
              @click="onPortalConfirm"
            >{{ t('orderdetail.portal_confirm_btn') }}</AppButton>
          </div>
        </section>

        <!-- GB/AU: Web 填表引导单（无浏览器插件） -->
        <VisaGuidePanel
          v-if="visaGuide"
          :guide="visaGuide"
          :country-code="orderCountryCode"
        />

        <!-- 5-state timeline -->
        <section class="card" data-testid="orderdetail-timeline">
          <h2 class="card__title">{{ t('orderdetail.section_timeline') }}</h2>
          <div class="timeline">
            <div
              v-for="(step, idx) in TIMELINE_STEPS"
              :key="step.key"
              class="tl-step"
              :class="{
                'tl-step--done': isStepDone(step.key, order.status),
                'tl-step--current': order.status === step.key,
                'tl-step--pending': !isStepDone(step.key, order.status) && order.status !== step.key
              }"
              :data-testid="`orderdetail-tl-${step.key}`"
            >
              <div class="tl-step__node">
                <span v-if="isStepDone(step.key, order.status) && order.status !== step.key" class="tl-step__check">✓</span>
                <span v-else>{{ statusIcon(step.key) }}</span>
              </div>
              <div class="tl-step__body">
                <p class="tl-step__label">{{ t(step.label) }}</p>
                <p class="tl-step__desc">{{ t(`orderdetail.desc_${step.key}`) }}</p>
                <p
                  v-if="order.status === step.key"
                  class="tl-step__now"
                  data-testid="orderdetail-tl-current"
                >● {{ statusLabel(order.status) }}</p>
              </div>
              <div v-if="idx < TIMELINE_STEPS.length - 1" class="tl-step__line"></div>
            </div>

            <!-- Branch state: rejected / cancelled shown separately (W3 cancel flow strengthened add cancelled terminal) -->
            <template v-for="branch in TIMELINE_BRANCHES" :key="branch.key">
              <div
                v-if="isBranchReached(branch.key, order.status)"
                class="tl-step tl-step--branch"
                :class="{
                  'tl-step--current': order.status === branch.key,
                  [`tl-step--branch-${branch.key}`]: true
                }"
                :data-testid="`orderdetail-tl-${branch.key}`"
              >
              <div class="tl-step__node">
                <span>{{ statusIcon(branch.key) }}</span>
              </div>
              <div class="tl-step__body">
                <p class="tl-step__label">{{ t(branch.label) }}</p>
                <p class="tl-step__desc">{{ t(`orderdetail.desc_${branch.key}`) }}</p>
                <p
                  v-if="order.status === branch.key"
                  class="tl-step__now"
                  :data-testid="`orderdetail-tl-${branch.key}-current`"
                >● {{ statusLabel(order.status) }}</p>
              </div>
              </div>
            </template>
          </div>
        </section>

        <!-- Order basic info -->
        <section class="card" data-testid="orderdetail-info">
          <h2 class="card__title">{{ t('orderdetail.section_basic') }}</h2>
          <dl class="info-list">
            <div class="info-list__row">
              <dt>{{ t('orderdetail.destination_label') }}</dt>
              <dd>{{ destinationName }} <span v-if="order.destination_id" class="info-list__chip">#{{ order.destination_id }}</span></dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.visa_type_label') }}</dt>
              <dd>{{ visaTypeName }}</dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.amount_label') }}</dt>
              <dd>{{ formatAmount(order.total_amount, order.currency) }}</dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.created_at_label') }}</dt>
              <dd>{{ formatDateTime(order.created_at) }}</dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.status_label') }}</dt>
              <dd>
                <span class="status-chip" :class="`status-chip--${order.status}`">
                  {{ statusIcon(order.status) }} {{ statusLabel(order.status) }}
                </span>
              </dd>
            </div>
            <div class="info-list__row">
              <dt>{{ t('orderdetail.materials_count', { n: (order.material_ids || []).length }) }}</dt>
              <dd>
                <span v-if="(order.material_ids || []).length === 0">—</span>
                <span v-else class="info-list__ids">
                  <span
                    v-for="mid in order.material_ids"
                    :key="mid"
                    class="info-list__chip"
                  >#{{ mid }}</span>
                </span>
              </dd>
            </div>
            <!-- A-W9-2: affiliate source (only shown when commission loaded) -->
            <div
              v-if="commission"
              class="info-list__row"
              data-testid="orderdetail-affiliate-row"
            >
              <dt>{{ t('affiliate.commission_label') }}</dt>
              <dd>
                <span class="affiliate-pill" data-testid="orderdetail-affiliate-pill">
                  <span class="affiliate-pill__icon">🤝</span>
                  <span class="affiliate-pill__partner">{{ commission.partner_id }}</span>
                  <span class="affiliate-pill__rate">{{ formatRate(commission.commission_rate) }}</span>
                  <span class="affiliate-pill__amount" v-if="commission.commission_amount_cents">
                    · {{ formatCommission(commission.commission_amount_cents, commission.currency) }}
                  </span>
                </span>
              </dd>
            </div>
          </dl>

          <!-- Rejection reason -->
          <div
            v-if="order.status === 'rejected' && order.rejection_reason"
            class="rejection-box"
            data-testid="orderdetail-rejection"
          >
            <h3 class="rejection-box__title">❌ {{ t('orderdetail.rejection_reason_title') }}</h3>
            <p class="rejection-box__text">
              {{ order.rejection_reason[locale] || order.rejection_reason.zh || order.rejection_reason.en }}
            </p>
          </div>
        </section>

        <!-- RPA screenshots -->
        <section class="card" data-testid="orderdetail-rpa">
          <h2 class="card__title">{{ t('orderdetail.section_rpa') }}</h2>
          <div v-if="rpaImages.length === 0" class="rpa-empty" data-testid="orderdetail-rpa-empty">
            <span class="rpa-empty__icon">📷</span>
            <p>{{ t('orderdetail.rpa_empty') }}</p>
          </div>
          <div v-else class="rpa-grid" data-testid="orderdetail-rpa-grid">
            <a
              v-for="(url, i) in rpaImages"
              :key="i"
              :href="url"
              target="_blank"
              rel="noopener noreferrer"
              class="rpa-card"
            >
              <img
                :src="url"
                :alt="`RPA Step ${i + 1}`"
                loading="lazy"
                @error="onImgError($event, i)"
              />
              <span class="rpa-card__step">Step {{ i + 1 }}</span>
            </a>
          </div>
        </section>

        <!-- Action area -->
        <section class="card" data-testid="orderdetail-actions">
          <h2 class="card__title">{{ t('orderdetail.section_actions') }}</h2>
          <div class="actions-row">
            <!-- Cancel order: only clickable in created state -->
            <AppButton
              v-if="order.status === 'created'"
              ref="cancelBtnRef"
              variant="outline"
              size="md"
              :loading="cancelling"
              data-testid="orderdetail-cancel-btn"
            >{{ t('orderdetail.cancel_btn') }}</AppButton>
            <span
              v-else
              class="actions-hint"
              data-testid="orderdetail-cancel-hint"
            >{{ t('orderdetail.cancel_blocked') }}</span>

            <!-- W67: Delete draft — only available when status='created'.
                 Distinct from cancel: this is a hard-delete (order row gone,
                 materials soft-deleted); cancel preserves the row. -->
            <AppButton
              v-if="order.status === 'created'"
              ref="deleteBtnRef"
              variant="danger"
              size="md"
              :loading="deleting"
              data-testid="orderdetail-delete-btn"
            >🗑 {{ t('orderdetail.delete_btn') }}</AppButton>

            <!-- Visa issued PDF download -->
            <AppButton
              v-if="order.status === 'approved' && order.visa_pdf_url"
              ref="pdfBtnRef"
              variant="primary"
              size="md"
              data-testid="orderdetail-pdf-btn"
            >⬇ {{ t('orderdetail.visa_pdf_btn') }}</AppButton>

            <!-- W48 v0.2: DS-160 辅助填充 — 改成"生成 12 位 code" + 复制粘贴到插件
                 流程。点击后 App 调 POST /api/v2/ds160/code 拿 code + fingerprint,
                 展示给用户复制 → 用户打开 Chrome 插件粘贴 → 插件 redeem 拿档案 →
                 在 ceac.state.gov 看填充面板。 -->
            <AppButton
              v-if="orderCountryCode === 'US' && ['created', 'submitted', 'reviewing', 'approved'].includes(order.status)"
              ref="exportDs160BtnRef"
              variant="outline"
              size="md"
              :loading="exportingDs160"
              data-testid="orderdetail-ds160-get-code-btn"
              @click="onGetDs160Code"
            >🧩 {{ ds160Code ? t('orderdetail.ds160_refresh_code_btn') : t('orderdetail.ds160_get_code_btn') }}</AppButton>
            <AppButton
              v-if="order.status === 'approved'"
              ref="downloadExtBtnRef"
              variant="ghost"
              size="md"
              data-testid="orderdetail-ext-download-btn"
              @click="onDownloadExtension"
            >📦 {{ t('orderdetail.ext_download_btn') }}</AppButton>

            <!-- Re-apply after rejection -->
            <AppButton
              v-if="order.status === 'rejected'"
              ref="reapplyBtnRef"
              variant="outline"
              size="md"
              data-testid="orderdetail-reapply-btn"
            >↻ {{ t('orderdetail.reapply_btn') }}</AppButton>

            <!-- W48 v0.2: DS-160 code 展示面板 — 拿到 code 后展开,
                 展示 code + 复制按钮 + 重置按钮 + 档案指纹 -->
            <div
              v-if="ds160PanelOpen && ds160Code"
              class="ds160-code-panel"
              data-testid="orderdetail-ds160-code-panel"
              style="
                grid-column: 1 / -1;
                margin-top: 12px;
                padding: 14px 16px;
                background: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 12px;
                font-size: 13px;
              "
            >
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                <div style="font-weight:600;color:#0c4a6e;">
                  🔑 {{ t('orderdetail.ds160_code_panel_title') }}
                </div>
                <span
                  v-if="ds160LastUnchanged"
                  style="font-size:11px;color:#0369a1;background:#e0f2fe;padding:2px 8px;border-radius:10px;"
                  data-testid="orderdetail-ds160-unchanged-badge"
                >{{ t('orderdetail.ds160_unchanged_badge') }}</span>
              </div>
              <div
                style="
                  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                  font-size: 22px;
                  font-weight: 600;
                  letter-spacing: 3px;
                  color: #0c4a6e;
                  background: #fff;
                  border: 1px dashed #7dd3fc;
                  border-radius: 8px;
                  padding: 10px 14px;
                  text-align: center;
                  user-select: all;
                  cursor: text;
                "
                data-testid="orderdetail-ds160-code-value"
              >{{ formatDs160Code(ds160Code) }}</div>
              <div style="display:flex;gap:8px;margin-top:10px;">
                <button
                  type="button"
                  class="ds160-copy-btn"
                  data-testid="orderdetail-ds160-copy-btn"
                  style="
                    flex: 1; padding: 8px 12px;
                    border: 0; border-radius: 8px; cursor: pointer;
                    background: #0ea5e9; color: #fff;
                    font-size: 13px; font-weight: 500;
                  "
                  @click="onCopyDs160Code"
                >📋 {{ t('orderdetail.ds160_copy_btn') }}</button>
                <button
                  type="button"
                  class="ds160-open-btn"
                  data-testid="orderdetail-ds160-open-btn"
                  style="
                    flex: 1; padding: 8px 12px;
                    border: 0; border-radius: 8px; cursor: pointer;
                    background: #111; color: #fff;
                    font-size: 13px; font-weight: 500;
                  "
                  @click="onOpenDs160Website"
                >🚀 {{ t('orderdetail.ds160_open_website_btn') }}</button>
                <button
                  type="button"
                  class="ds160-rotate-btn"
                  data-testid="orderdetail-ds160-rotate-btn"
                  style="
                    padding: 8px 12px;
                    border: 1px solid #fca5a5; border-radius: 8px; cursor: pointer;
                    background: #fff; color: #b91c1c;
                    font-size: 12px;
                  "
                  @click="onRotateDs160Code"
                >↻ {{ t('orderdetail.ds160_rotate_btn') }}</button>
              </div>
              <div style="font-size:11px;color:#475569;margin-top:10px;line-height:1.5;">
                <div>{{ t('orderdetail.ds160_panel_hint_1') }}</div>
                <div style="margin-top:4px;">
                  {{ t('orderdetail.ds160_panel_hint_2') }}
                  <code style="background:#e0f2fe;padding:1px 6px;border-radius:4px;font-family:ui-monospace,monospace;">
                    {{ ds160Fingerprint }}{{ t('orderdetail.ds160_fingerprint_more') }}
                  </code>
                </div>
                <div v-if="ds160IssuedAt" style="margin-top:4px;color:#64748b;">
                  {{ t('orderdetail.ds160_issued_at') }}: {{ formatLocalTime(ds160IssuedAt) }}
                </div>
              </div>
            </div>

            <!-- Back -->
            <AppButton
              ref="backBtnRef"
              variant="ghost"
              size="md"
              data-testid="orderdetail-back-btn"
            >← {{ t('orderdetail.back_btn') }}</AppButton>
          </div>
        </section>
      </template>
    </main>

    <!-- Cancel order confirmation modal -->
    <div v-if="cancelModal" class="modal-mask" @click.self="cancelModal = false" data-testid="orderdetail-cancel-modal">
      <div class="modal-box">
        <h3 class="modal-box__title">{{ t('orderdetail.cancel_confirm_title') }}</h3>
        <p class="modal-box__body">{{ t('orderdetail.cancel_confirm_body') }}</p>
        <div class="modal-box__actions">
          <AppButton ref="cancelNoRef" variant="ghost" size="md" data-testid="orderdetail-cancel-no">
            {{ t('orderdetail.cancel_confirm_no') }}
          </AppButton>
          <AppButton ref="cancelYesRef" variant="danger" size="md" :loading="cancelling" data-testid="orderdetail-cancel-yes">
            {{ t('orderdetail.cancel_confirm_ok') }}
          </AppButton>
        </div>
      </div>
    </div>

    <!-- W67: Delete-draft confirmation modal.
         Distinct from cancel modal — title is more explicit about the
         cascade, body lists what gets cleared, OK button uses danger
         variant + trash icon to make the action obviously destructive. -->
    <div v-if="deleteModal" class="modal-mask" @click.self="deleteModal = false" data-testid="orderdetail-delete-modal">
      <div class="modal-box modal-box--danger">
        <h3 class="modal-box__title">{{ t('orderdetail.delete_confirm_title') }}</h3>
        <p class="modal-box__body">{{ t('orderdetail.delete_confirm_body', { n: (order.material_ids || []).length }) }}</p>
        <div class="modal-box__actions">
          <AppButton ref="deleteNoRef" variant="ghost" size="md" data-testid="orderdetail-delete-no">
            {{ t('orderdetail.delete_confirm_no') }}
          </AppButton>
          <AppButton ref="deleteYesRef" variant="danger" size="md" :loading="deleting" data-testid="orderdetail-delete-yes">
            🗑 {{ t('orderdetail.delete_confirm_ok') }}
          </AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
  getOrder,
  cancelOrder,
  deleteOrder,
  pollOrderStatus,
  markPortalSubmitted,
  TIMELINE_STEPS,
  BRANCH_STEPS
} from '@/api/orders'
import { useOrderUserStatus } from '@/composables/useOrderUserStatus'
// A-W9-2: query order commission, detail page shows "Affiliate source: PARTNER001 (5% commission)"
import { getCommission } from '@/api/affiliate'
// W48 v0.2: DS-160 辅助填充 — 改成后端 12 位 code 兑换流程
import { issueDs160Code, formatDs160Code, describeDs160Error } from '@/api/ds160'
import AppHeader from '@/components/AppHeader.vue'
import VisaGuidePanel from '@/components/VisaGuidePanel.vue'
import { buildApplicantProfile } from '@/composables/useApplicantProfile'
import { buildVisaGuide } from '@/data/visaFieldMaps.js'

const DESTINATION_COUNTRY_MAP = {
  1: 'US', 2: 'JP', 3: 'GB', 4: 'AU', 5: 'CA',
  6: 'DE', 7: 'FR', 8: 'SG', 9: 'NZ',
}

function parseApplicantData(order) {
  const raw = order?.applicant_data
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  try { return JSON.parse(raw) } catch { return {} }
}

const { t, te, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()
const { statusOf: userStatusOf } = useOrderUserStatus()

// W2: user-facing status (single source of truth via composable)
const userStatus = computed(() => userStatusOf(order.value || {}))

// ============== State ==============
const order = ref(null)
const loading = ref(false)
const loadError = ref('')
// W56: 401 → 页面内「会话过期」错误态,隐藏 retry 按钮,换成「重新登录」跳 /login
const isAuthExpiredState = ref(false)
const cancelling = ref(false)
const cancelModal = ref(false)
// W67: delete-draft modal state — distinct from cancelModal because the
// confirm action and the success side-effect (router push to /orders) are
// different. Keeping them separate avoids accidental re-use and makes the
// test IDs / handlers cleanly partitioned.
const deleting = ref(false)
const deleteModal = ref(false)
const wsState = ref('connecting')  // connecting | connected | fallback
const countdownSec = ref(30)
const imgErrors = reactive(new Set())
// A-W9-2: commission data { partner_id, commission_rate, commission_amount_cents, currency }
// null means no affiliate source (404 silent) or Loading
const commission = ref(null)

// W48 v0.2: DS-160 辅助填充 — 12 位 code 兑换流程
const exportingDs160 = ref(false)   // 拉 code 时按钮的 loading
const ds160Code = ref('')           // 当前 code (raw 12 chars)
const ds160Fingerprint = ref('')    // 档案指纹前缀 (前 8 位 + ...)
const ds160IssuedAt = ref('')       // code 签发时间 (ISO)
const ds160PanelOpen = ref(false)   // 是否展开 code 展示面板
const ds160LastUnchanged = ref(false) // 上次是否幂等 (true=复用旧 code)
const portalConfirming = ref(false)

let cancelPoll = null
let countdownTimer = null

const orderNo = computed(() => (route.params.orderNo || '').toString())

// W3 Story 3.2.2 cancel flow strengthened: extend branch, add cancelled terminal (W2 1.2.2a only had rejected)
const TIMELINE_BRANCHES = [
  ...BRANCH_STEPS,
  { key: 'cancelled', label: 'orderdetail.status_cancelled' }
]

// ============== Status mapping ==============
function statusLabel(s) {
  const k = `orderdetail.status_${s}`
  return te(k) ? t(k) : s
}
// W2: user-facing status icon (5 keys)
const USER_STATUS_ICONS = {
  draft: '✎',
  pending_payment: '⏱',
  paid: '✓',
  processing: '⏳',
  approved: '🎉',
  rejected: '✗',
  refunding: '↻',
  refunded: '↩',
  cancelled: '—',
  error: '!',
}
function userStatusIcon(key) {
  return USER_STATUS_ICONS[key] || '•'
}
function statusIcon(s) {
  const k = `orderdetail.icon_${s}`
  if (te(k)) return t(k)
  // fallback unicode
  const map = {
    created: '📝', paid: '💳', completed: '✅',
    submitted: '📤', reviewing: '🔍',
    approved: '✅', rejected: '❌', cancelled: '🚫',
    closed: '🔒', failed: '⚠️', abnormal: '🆘'
  }
  return map[s] || '•'
}

function isStepDone(stepKey, currentStatus) {
  const order3 = ['created', 'paid', 'completed']
  const si = order3.indexOf(stepKey)
  if (si < 0) return false
  if (currentStatus === 'cancelled') {
    return si <= order3.indexOf('created')
  }
  // Legacy mapping
  const legacyIdx = {
    submitted: 1, reviewing: 2, approved: 2, rejected: 2,
    closed: 2, created: 0, paid: 1, completed: 2,
  }
  const ci = legacyIdx[currentStatus]
  if (ci === undefined) return false
  return si <= ci
}
function isBranchReached(branchKey, status) {
  // W3 cycle 5 double check: must reach branch (status in rejected/cancelled) + this branchKey equals status
  // Otherwise cancelled will also render rejected branch (cycle 1-4 bug)
  const terminalReached = status === 'rejected' || status === 'cancelled'
  return terminalReached && branchKey === status
}

const destinationName = computed(() => {
  if (!order.value) return '—'
  // mock mode: from destinations cache or hardcode guess (L4 i18n: use t() with i18n key)
  if (order.value.destination_id === 1) return t('country.us')
  if (order.value.destination_id === 2) return t('country.jp')
  if (order.value.destination_id === 3) return t('country.uk')
  if (order.value.destination_id === 4) return t('country.au')
  if (order.value.destination_id === 5) return t('country.ca')
  if (order.value.destination_id === 6) return t('country.de_schengen')
  if (order.value.destination_id === 7) return t('country.fr_schengen')
  if (order.value.destination_id === 8) return t('country.sg')
  if (order.value.destination_id === 9) return t('country.nz')
  return `#${order.value.destination_id}`
})

const orderCountryCode = computed(() => {
  if (!order.value) return ''
  return DESTINATION_COUNTRY_MAP[order.value.destination_id] || ''
})

const visaGuide = computed(() => {
  const cc = orderCountryCode.value
  if (cc !== 'GB' && cc !== 'AU') return null
  const form = parseApplicantData(order.value)
  const profile = buildApplicantProfile({ form })
  return buildVisaGuide(cc, profile)
})

const MILESTONE_DEFS = [
  { key: 'payment', icon: '💳' },
  { key: 'diagnosis', icon: '🤖' },
  { key: 'portal', icon: '🌐' },
]

const orderMilestones = computed(() => {
  if (!order.value) return []
  const o = order.value
  const status = (o.status || '').toLowerCase()
  const flags = [
    {
      key: 'payment',
      done: ['paid', 'completed'].includes(status) || !!o.paid_at,
      at: o.paid_at,
    },
    {
      key: 'diagnosis',
      done: status === 'completed' || !!o.diagnosis_completed_at,
      at: o.diagnosis_completed_at || o.completed_at,
    },
    {
      key: 'portal',
      done: !!(o.portal_submitted_at || o.ds160_portal_submitted_at),
      at: o.portal_submitted_at || o.ds160_portal_submitted_at,
    },
  ]
  let seenCurrent = false
  return MILESTONE_DEFS.map((def, i) => {
    const f = flags[i]
    let state = 'pending'
    if (f.done) state = 'done'
    else if (!seenCurrent) {
      state = 'current'
      seenCurrent = true
    }
    return { ...def, state, at: f.at }
  })
})

const showPortalConfirmBtn = computed(() => {
  if (!order.value) return false
  const s = order.value.status
  const done = order.value.portal_submitted_at || order.value.ds160_portal_submitted_at
  return (s === 'completed' || s === 'paid') && !done
})

async function onPortalConfirm() {
  if (!order.value) return
  portalConfirming.value = true
  try {
    await markPortalSubmitted(order.value.order_no)
    toast.success(t('orderdetail.portal_confirm_ok'))
    await loadInitial()
  } catch (e) {
    toast.error(e?.message || t('orderdetail.portal_confirm_fail'))
  } finally {
    portalConfirming.value = false
  }
}

const visaTypeName = computed(() => {
  if (!order.value) return '—'
  return order.value.visa_type === 'tourism' ? t('orders.visa_tourism')
       : order.value.visa_type === 'student' ? t('orders.visa_student')
       : order.value.visa_type
})

const rpaImages = computed(() => {
  if (!order.value) return []
  const arr = order.value.rpa_screenshots || []
  const single = order.value.rpa_screenshot_url
  if (single && !arr.includes(single)) arr.unshift(single)
  return arr.filter((u) => u && !imgErrors.has(u))
})

// ============== Formatters ==============
function formatDateTime(s) {
  if (!s) return '—'
  try {
    const d = new Date(s)
    if (isNaN(d.getTime())) return s
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${day} ${hh}:${mm}`
  } catch {
    return s
  }
}
function formatAmount(n, currency) {
  if (n == null || n === 0) return '—'
  return `${currency || 'USD'} ${Number(n).toFixed(2)}`
}
function onImgError(e, idx) {
  const src = e?.target?.src
  if (src) imgErrors.add(src)
}

// ============== Data Loading + Realtime subscription ==============
async function loadInitial() {
  if (!orderNo.value) {
    loadError.value = t('orderdetail.not_found')
    return
  }
  loading.value = true
  loadError.value = ''
  isAuthExpiredState.value = false
  try {
    const r = await getOrder(orderNo.value, { etag: null })
    if (r.data) {
      order.value = r.data
    } else if (r.notModified) {
      // Rare: first is 304, keep current
    }
  } catch (e) {
    // W56: 401 / 1005 → "会话过期"分支,不弹顶部 toast(顶部统一由 App.vue 提示条显示),
    // 在页面内显示「重新登录」按钮引导用户回到 /login
    if (e?.isAuthExpired || e?.code === '1005') {
      isAuthExpiredState.value = true
      loadError.value = ''  // 用 isAuthExpiredState 区分,不让 message 干扰模板
    } else if (e?.code === '4004' || e?.status === 404) {
      loadError.value = t('orderdetail.not_found')
    } else {
      loadError.value = e?.message || t('orderdetail.load_failed')
    }
    order.value = null
  } finally {
    loading.value = false
  }
  // A-W9-2: load commission (silent, failure as no source)
  // W56: 已 expired 时不再启动 realtime(避免无谓 WS / polling + 噪声日志)
  if (!isAuthExpiredState.value) {
    loadCommission()
    startRealtime()
  }
}

// A-W9-2: load commission - call /api/v2/affiliate/commission/{order_id}
// Return null means no source (404 silent), UI hides source row
async function loadCommission() {
  if (!order.value?.order_no) return
  try {
    const data = await getCommission(order.value.order_no)
    commission.value = data
  } catch (_) {
    commission.value = null
  }
}

// Commission display helper: convert cents to "$1.25" format
function formatCommission(cents, currency) {
  if (cents == null) return ''
  const cur = currency || 'USD'
  const val = (Number(cents) / 100).toFixed(2)
  return `${cur} ${val}`
}
// Commission rate "0.05" -> "5%"
function formatRate(rate) {
  if (!rate) return ''
  const n = Number(rate)
  if (isNaN(n)) return String(rate)
  return `${(n * 100).toFixed(0)}%`
}

function startRealtime() {
  stopRealtime()
  wsState.value = 'connecting'
  countdownSec.value = 30
  // Countdown (display)
  countdownTimer = setInterval(() => {
    countdownSec.value = Math.max(0, countdownSec.value - 1)
    if (countdownSec.value === 0) countdownSec.value = 30
  }, 1000)
  // Realtime subscription
  cancelPoll = pollOrderStatus(orderNo.value, (data, source) => {
    if (!data) return
    if (data.__ws === 'connected') {
      wsState.value = 'connected'
      return
    }
    if (data.__ws === 'error' || data.__ws === 'closed') {
      wsState.value = 'fallback'
      return
    }
    // Normal data update
    if (source === 'ws-mock' || source === 'ws' || source === 'polling' || source === 'polling-same') {
      order.value = { ...(order.value || {}), ...data }
      countdownSec.value = 30
      if (source === 'polling' || source === 'ws-mock') {
        // eslint-disable-next-line no-console
        if (typeof console !== 'undefined' && console.log) {
          console.log(`[orderdetail] status update via ${source}:`, data.status)
        }
      }
    }
  }, { intervalMs: 30000, wsTimeoutMs: 3000 })
}

function stopRealtime() {
  if (cancelPoll) {
    try { cancelPoll() } catch (_) {}
    cancelPoll = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// ============== Actions ==============
function onCancel() {
  cancelModal.value = true
}
async function doCancel() {
  if (!order.value) return
  cancelling.value = true
  try {
    await cancelOrder(order.value.order_no)
    order.value = { ...order.value, status: 'cancelled', updated_at: new Date().toISOString() }
    cancelModal.value = false
    toast.success(t('orderdetail.cancel_success'))
  } catch (e) {
    if (e?.code === '4010') {
      toast.error(t('orderdetail.cancel_blocked'))
    } else {
      toast.error(e?.message || t('orderdetail.cancel_failed'))
    }
  } finally {
    cancelling.value = false
  }
}

// ============== W67: Delete-draft handlers ==============
function onDelete() {
  deleteModal.value = true
}
async function doDelete() {
  if (!order.value) return
  deleting.value = true
  try {
    const r = await deleteOrder(order.value.order_no)
    deleteModal.value = false
    // Toast: if backend reported soft-deleted material count > 0, surface it
    // so the user knows exactly what got cleared (matters for the "I want to
    // see what was lost" recovery path).
    const count = r?.soft_deleted_materials ?? 0
    if (count > 0) {
      toast.success(t('orderdetail.delete_success_with_materials', { n: count }))
    } else {
      toast.success(t('orderdetail.delete_success'))
    }
    // After delete, the order row is gone server-side; bounce to /orders
    // list so the user sees the updated state. Use replace() so back-button
    // doesn't take them into a 404.
    router.replace('/orders')
  } catch (e) {
    if (e?.code === '4010') {
      toast.error(t('orderdetail.delete_blocked'))
    } else {
      toast.error(e?.message || t('orderdetail.delete_failed'))
    }
  } finally {
    deleting.value = false
  }
}

function onDownloadPdf() {
  if (order.value?.visa_pdf_url) {
    window.open(order.value.visa_pdf_url, '_blank', 'noopener,noreferrer')
  }
}
function onReapply() {
  // Jump back to /destinations to re-select
  router.push('/destinations')
}

// W48 v0.2: DS-160 辅助填充 — 后端发 12 位 code + 复制粘贴到插件的流程。
// 拿到 code → 弹窗展示 → 用户复制 → 打开插件 → 粘贴 → 插件 redeem。
async function onGetDs160Code() {
  if (!order.value || !order.value.id) return
  exportingDs160.value = true
  try {
    const data = await issueDs160Code(order.value.id, { forceRotate: false })
    ds160Code.value = data.code || ''
    ds160Fingerprint.value = (data.fingerprint || '').slice(0, 8) || ''
    ds160IssuedAt.value = data.issued_at || ''
    ds160LastUnchanged.value = !!data.unchanged
    ds160PanelOpen.value = true
    if (!data.unchanged) {
      toast.success(t('orderdetail.ds160_get_code_ok'))
    } else {
      // 幂等:档案没变 → 复用旧 code
      toast.info(t('orderdetail.ds160_unchanged_hint'))
    }
  } catch (err) {
    const code = err && err.code
    toast.error(describeDs160Error(code) + (err && err.message ? ` · ${err.message}` : ''))
    console.error('[ds160-get-code]', err)
  } finally {
    exportingDs160.value = false
  }
}

// 复制 code 到剪贴板 (优先用 Clipboard API,降级用 execCommand)
async function onCopyDs160Code() {
  if (!ds160Code.value) return
  const text = formatDs160Code(ds160Code.value)  // 带中划线的可读形式
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // 老浏览器兜底
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    toast.success(t('orderdetail.ds160_copy_ok'))
  } catch (err) {
    toast.error(t('orderdetail.ds160_copy_fail') + ': ' + (err && err.message || ''))
  }
}

// 重置 code (force_rotate) — 旧 code 进黑名单,新 code 重新生成
async function onRotateDs160Code() {
  if (!order.value || !order.value.id) return
  if (!confirm(t('orderdetail.ds160_rotate_confirm'))) return
  exportingDs160.value = true
  try {
    const data = await issueDs160Code(order.value.id, { forceRotate: true })
    ds160Code.value = data.code || ''
    ds160Fingerprint.value = (data.fingerprint || '').slice(0, 8) || ''
    ds160IssuedAt.value = data.issued_at || ''
    ds160LastUnchanged.value = false
    toast.success(t('orderdetail.ds160_rotate_ok'))
  } catch (err) {
    const code = err && err.code
    toast.error(describeDs160Error(code) + (err && err.message ? ` · ${err.message}` : ''))
  } finally {
    exportingDs160.value = false
  }
}

// W48 v0.2 UX1: 一键打开 ceac.state.gov (新标签页)
function onOpenDs160Website() {
  window.open('https://ceac.state.gov/genniv/', '_blank', 'noopener,noreferrer')
  toast.info(t('orderdetail.ds160_open_website_hint'))
}

// 简单的时间格式化 (本地化)
function formatLocalTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString(locale.value || 'zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch (e) {
    return iso
  }
}

// W47: 下载浏览器插件 zip —— 直接给个下载链接(后端静态资源),用户解压加载
function onDownloadExtension() {
  const url = '/downloads/htex-browser-extension.zip'
  window.open(url, '_blank', 'noopener,noreferrer')
  toast.info(t('orderdetail.ext_download_started'))
}
// W56: 401 → 跳登录页,带 redirect 回当前订单详情
function onRelogin() {
  router.push({ name: 'Login', query: { redirect: route.fullPath } })
}
function goBack() {
  // Back via history stack, else go /home
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/home')
  }
}

// Route change (orderNo change) reload
watch(orderNo, (v, prev) => {
  if (v && v !== prev) {
    order.value = null
    loadInitial()
  }
})

// ============== W4 P0 root-fix: ref + onTrigger pattern (reuse W3 A-3.1.1a) ==============
// 8 AppButtons use ref to expose onTrigger, Vue @click bubbling no longer depends on AppButton internals
// 6 persistent: logout / retry / cancel / pdf / reapply / back
// 2 modal: cancelNo / cancelYes (v-if controlled, nextTick inject on open)
const retryBtnRef = ref(null)
const reloginBtnRef = ref(null)
const cancelBtnRef = ref(null)
const deleteBtnRef = ref(null)
const pdfBtnRef = ref(null)
const reapplyBtnRef = ref(null)
const backBtnRef = ref(null)
const cancelNoRef = ref(null)
const cancelYesRef = ref(null)
const deleteNoRef = ref(null)
const deleteYesRef = ref(null)

// Inject 2 button triggers on modal open (v-if mount after ref has value)
watch(cancelModal, async (val) => {
  if (val) {
    await nextTick()
    if (cancelNoRef.value) cancelNoRef.value.setOnTrigger(() => { cancelModal.value = false })
    if (cancelYesRef.value) cancelYesRef.value.setOnTrigger(doCancel)
  }
})

// W67: same pattern for delete-draft modal
watch(deleteModal, async (val) => {
  if (val) {
    await nextTick()
    if (deleteNoRef.value) deleteNoRef.value.setOnTrigger(() => { deleteModal.value = false })
    if (deleteYesRef.value) deleteYesRef.value.setOnTrigger(doDelete)
  }
})

onMounted(async () => {
  auth.hydrate()
  await loadInitial()
  // Inject 5 persistent AppButton click callbacks (W3 root-fix AppButton + setOnTrigger pattern)
  if (retryBtnRef.value) retryBtnRef.value.setOnTrigger(loadInitial)
  if (reloginBtnRef.value) reloginBtnRef.value.setOnTrigger(onRelogin)
  if (cancelBtnRef.value) cancelBtnRef.value.setOnTrigger(onCancel)
  if (deleteBtnRef.value) deleteBtnRef.value.setOnTrigger(onDelete)
  if (pdfBtnRef.value) pdfBtnRef.value.setOnTrigger(onDownloadPdf)
  if (reapplyBtnRef.value) reapplyBtnRef.value.setOnTrigger(onReapply)
  if (backBtnRef.value) backBtnRef.value.setOnTrigger(goBack)
})

onBeforeUnmount(() => {
  stopRealtime()
})
</script>

<style scoped lang="scss">
.orderdetail-page { min-height: 100vh; background: #FFFFFF; }

// ============== Header ==============
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; background: #fff; border-bottom: 1px solid var(--border, #E2E8F0);
}
.ws-pill {
  display: inline-flex; align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.ws-pill--ok { background: #DCFCE7; color: #166534; border: 1px solid #86EFAC; }
.ws-pill--pending { background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; }
.ws-pill--fallback { background: #EAF0FE; color: #2D5BFF; border: 1px solid #93C5FD; }

.orderdetail-shell { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }

// ============== Hero ==============
.hero {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-bottom: 18px;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 14px; padding: 22px 26px;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
}
.hero__label { margin: 0 0 4px; font-size: 12px; color: var(--ink-3, #64748B); letter-spacing: 0.04em; text-transform: uppercase; }
.hero__no { margin: 0; font-size: 24px; font-weight: 700; color: var(--ink-1, #0F172A); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.hero__sub { margin: 6px 0 0; font-size: 13px; color: var(--ink-3, #64748B); }
.hero__right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.hero__updated { margin: 0; font-size: 12px; color: var(--ink-3, #64748B); }

.status-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 999px;
  font-size: 14px; font-weight: 600;
}
.status-badge__icon { font-size: 16px; }
.status-badge--created   { background: #F1F5F9; color: #475569; }
.status-badge--submitted { background: #DBEAFE; color: #1E40AF; }
.status-badge--reviewing { background: #FEF3C7; color: #92400E; }
.status-badge--approved  { background: #DCFCE7; color: #166534; }
.status-badge--rejected  { background: #FEE2E2; color: #991B1B; }
.status-badge--cancelled { background: #F1F5F9; color: #64748B; }
.status-badge--closed    { background: #E2E8F0; color: #475569; }
.status-badge--failed    { background: #FEF2F2; color: #B91C1C; }
.status-badge--abnormal  { background: #FFF7ED; color: #C2410C; }

// ============== Card ==============
.card {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 14px; padding: 22px 26px;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
  margin-bottom: 18px;
}
.card__title {
  margin: 0 0 16px; font-size: 17px; font-weight: 600;
  color: var(--ink-1, #0F172A);
  display: flex; align-items: center; gap: 8px;
  &::before {
    content: ''; width: 3px; height: 16px; background: #3B6EF5; border-radius: 2px;
  }
}

// ============== Timeline ==============
.timeline {
  position: relative;
  display: flex; flex-direction: column; gap: 4px;
}
.tl-step {
  position: relative;
  display: flex; align-items: flex-start; gap: 14px;
  padding: 12px 0;
  &__node {
    flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%;
    background: #F1F5F9; color: #94A3B8;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 16px;
    border: 2px solid #E2E8F0;
    transition: all .2s;
  }
  &__check { color: #16A34A; font-weight: 700; }
  &__body { flex: 1; min-width: 0; }
  &__label { margin: 0 0 2px; font-size: 14px; font-weight: 600; color: var(--ink-1, #0F172A); }
  &__desc  { margin: 0; font-size: 12px; color: var(--ink-3, #64748B); }
  &__now {
    margin: 6px 0 0; font-size: 12px; color: var(--el-color-primary, #3B6EF5);
    font-weight: 600; display: inline-flex; align-items: center; gap: 4px;
    animation: pulse 1.6s ease-in-out infinite;
  }
  &__line {
    position: absolute; left: 17px; top: 48px; bottom: -16px; width: 2px;
    background: #E2E8F0;
  }
  &--done &__node { background: #DCFCE7; border-color: #86EFAC; color: #166534; }
  &--done &__label { color: var(--ink-2, #334155); }
  &--current &__node { background: #3B6EF5; border-color: #3B6EF5; color: #fff; box-shadow: 0 0 0 4px rgba(59,110,245,.15); }
  &--current &__label { color: #2D5BFF; }
  &--pending &__node { background: #F8FAFC; border-color: #E2E8F0; color: #94A3B8; }
  &--branch { padding-left: 0; }
  &--branch &__node { background: #FEE2E2; border-color: #FCA5A5; color: #991B1B; }
  &--branch.tl-step--current &__node { background: #DC2626; border-color: #DC2626; color: #fff; box-shadow: 0 0 0 4px rgba(220,38,38,.15); }
  // W3 cancelled terminal branch style (grey, not glaring)
  &--branch-cancelled &__node { background: #F1F5F9; border-color: #CBD5E1; color: #64748B; }
  &--branch-cancelled.tl-step--current &__node { background: #64748B; border-color: #64748B; color: #fff; box-shadow: 0 0 0 4px rgba(100,116,139,.15); }
}
.tl-step:last-child .tl-step__line { display: none; }

.milestones__hint {
  margin: -4px 0 16px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.milestones {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.ms-step {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 0 12px;
  position: relative;
  padding-bottom: 20px;
  &__node {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; background: #f1f5f9; border: 2px solid #e2e8f0; color: #64748b;
  }
  &__body { padding-top: 4px; }
  &__label { font-weight: 600; font-size: 14px; margin: 0 0 2px; color: #0f172a; }
  &__desc { font-size: 13px; margin: 0; color: #64748b; line-height: 1.45; }
  &__at { font-size: 12px; margin: 4px 0 0; color: #059669; }
  &__line {
    position: absolute; left: 17px; top: 38px; bottom: 0; width: 2px; background: #e2e8f0;
  }
  &--done &__node { background: #ecfdf5; border-color: #10b981; color: #059669; }
  &--done &__line { background: #a7f3d0; }
  &--current &__node {
    background: #eff6ff; border-color: #3b82f6; color: #2563eb;
    box-shadow: 0 0 0 4px rgba(59,130,246,.12);
  }
  &--pending &__label { color: #94a3b8; }
}
.ms-step:last-child { padding-bottom: 0; }
.ms-step:last-child .ms-step__line { display: none; }
.portal-confirm {
  margin-top: 16px;
  padding: 14px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  p { margin: 0 0 10px; font-size: 13px; color: #475569; }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .55; }
}

// ============== Info list ==============
.info-list { margin: 0; padding: 0; }
.info-list__row {
  display: grid; grid-template-columns: 130px 1fr;
  gap: 12px; padding: 9px 0;
  border-bottom: 1px dashed var(--border, #E2E8F0);
  font-size: 14px;
}
.info-list__row:last-child { border-bottom: none; }
.info-list__row dt { color: var(--ink-3, #64748B); margin: 0; }
.info-list__row dd { color: var(--ink-1, #0F172A); margin: 0; font-weight: 500; }
.info-list__ids { display: inline-flex; flex-wrap: wrap; gap: 4px; }
.info-list__chip {
  display: inline-block; padding: 1px 8px; background: #EAF0FE; color: #2D5BFF;
  border-radius: 999px; font-size: 11px; font-weight: 500; font-family: ui-monospace, monospace;
}

.status-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 500;
}
.status-chip--created   { background: #F1F5F9; color: #475569; }
.status-chip--submitted { background: #DBEAFE; color: #1E40AF; }
.status-chip--reviewing { background: #FEF3C7; color: #92400E; }
.status-chip--approved  { background: #DCFCE7; color: #166534; }
.status-chip--rejected  { background: #FEE2E2; color: #991B1B; }
.status-chip--cancelled { background: #F1F5F9; color: #64748B; }

// A-W9-2: affiliate source pill (order detail commission display)
.affiliate-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; background: #FEF3C7; color: #92400E;
  border: 1px solid #FCD34D; border-radius: 999px;
  font-size: 12px; font-weight: 500;
  &__icon { font-size: 14px; }
  &__partner { font-family: ui-monospace, monospace; font-weight: 600; }
  &__rate { color: #B45309; font-weight: 600; }
  &__amount { color: var(--ink-3, #64748B); font-size: 11px; }
}

.rejection-box {
  margin-top: 18px;
  background: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 10px;
  padding: 14px 16px;
}
.rejection-box__title { margin: 0 0 6px; font-size: 14px; color: #991B1B; font-weight: 600; }
.rejection-box__text  { margin: 0; font-size: 13px; color: #7F1D1D; line-height: 1.55; }

// ============== RPA ==============
.rpa-empty {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 30px; color: var(--ink-3, #64748B);
  background: var(--bg-alt, #F8FAFC); border: 1px dashed var(--border, #E2E8F0);
  border-radius: 10px;
}
.rpa-empty__icon { font-size: 32px; }
.rpa-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.rpa-card {
  position: relative; display: block;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 10px; overflow: hidden;
  text-decoration: none;
  transition: transform .15s, box-shadow .15s;
}
.rpa-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(15,23,42,.08); }
.rpa-card img { display: block; width: 100%; height: 140px; object-fit: cover; background: #F1F5F9; }
.rpa-card__step {
  position: absolute; top: 8px; left: 8px;
  background: rgba(15,23,42,.7); color: #fff;
  font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 999px;
}

// ============== Actions ==============
.actions-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
}
.actions-hint { font-size: 12px; color: var(--ink-3, #64748B); }

// ============== State ==============
.state-block {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px; padding: 40px; text-align: center;
  color: var(--ink-3, #64748B); font-size: 14px;
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.state-block--err { color: #DC2626; flex-direction: column; }
.state-block--err p { margin: 0; }
.spinner {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid #3B6EF5; border-top-color: transparent;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

// ============== Modal ==============
.modal-mask {
  position: fixed; inset: 0;
  background: rgba(15,23,42,.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}
.modal-box {
  background: #fff; border-radius: 14px;
  padding: 24px 26px;
  max-width: 420px; width: calc(100% - 40px);
  box-shadow: 0 20px 60px rgba(15,23,42,.2);
  &__title { margin: 0 0 8px; font-size: 17px; font-weight: 700; color: #0F172A; }
  &__body  { margin: 0 0 18px; font-size: 14px; color: #475569; line-height: 1.55; }
  &__actions { display: flex; justify-content: flex-end; gap: 8px; }
  // W67: delete-draft modal uses a thin red top border to subtly emphasise
  // the destructive nature without screaming at the user. Action button is
  // already variant="danger"; this is purely a visual hint that this is
  // not the same modal as cancel.
  &--danger {
    border-top: 3px solid #DC2626;
  }
  &--danger .modal-box__title {
    color: #991B1B;
  }
}
</style>
