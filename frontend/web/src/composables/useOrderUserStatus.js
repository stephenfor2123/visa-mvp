// useOrderUserStatus.js — W1 P2
// Compute the user-facing status from backend order fields.
//
// Why this exists: the backend has 8 business states (created / submitted /
// reviewing / approved / rejected / closed / abnormal / failed) but most of
// them are internal details the user doesn't need to know. The user only
// cares about ~7 distinct moments: draft, awaiting payment, paid, embassy
// review, issued, refused, refunding / refunded, cancelled, error.
//
// This composable is the single source of truth for that translation. It
// also drives the timeline progress (which steps are done/current/pending).
//
// Backend dependency (W2 — not in flight yet): payment_status, refund_status.
// For W1 we approximate with order.status + (heuristic) order.total_amount.

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * User-facing status keys.
 * Each maps to: label key, tone (for badge color), progress stage (0-3).
 */
export const USER_STATUSES = {
  draft:            { tone: 'muted',      stage: 0, failed: false },
  pending_payment:  { tone: 'warning',    stage: 0, failed: false },
  // W67: ready_to_submit = 订单已支付,但还没用 RPA 插件提交到使馆。
  // 用户在 /orders/:id/precheck 页就能看到自己处于"待提交"阶段,
  // timeline 单独多一步,清楚告诉用户"差最后一步就能进使馆了"。
  ready_to_submit:  { tone: 'info',       stage: 1, failed: false },
  paid:             { tone: 'info',       stage: 1, failed: false },  // alias
  processing:       { tone: 'processing', stage: 2, failed: false },
  approved:         { tone: 'success',    stage: 3, failed: false },
  rejected:         { tone: 'danger',     stage: 3, failed: true  },
  refunding:        { tone: 'warning',    stage: 3, failed: false },
  refunded:         { tone: 'muted',      stage: 3, failed: false },
  cancelled:        { tone: 'muted',      stage: 0, failed: true  },
  error:            { tone: 'danger',     stage: 0, failed: true  },
}

/**
 * Map backend order → user-facing status key.
 *
 * @param {Object} order
 * @param {string} order.status         - backend status (8 values)
 * @param {string} [order.payment_status] - 'unpaid' | 'paid' | 'refunding' | 'refunded' | 'failed'
 * @param {string} [order.refund_status]  - 'none' | 'refunding' | 'refunded' | 'failed'
 * @param {string} [order.closed_reason]  - 'user_cancel' | 'system' | ...
 * @returns {{ key: string, tone: string, stage: number, failed: boolean }}
 */
export function computeUserStatus(order) {
  if (!order) return { key: 'error', tone: 'danger', stage: 0, failed: true }

  const status = (order.status || '').toLowerCase()
  const pay = (order.payment_status || '').toLowerCase()
  const refund = (order.refund_status || '').toLowerCase()

  // Refund sub-track takes precedence
  if (refund === 'pending') return { key: 'refunding', ...USER_STATUSES.refunding }
  if (refund === 'completed') return { key: 'refunded', ...USER_STATUSES.refunded }
  if (refund === 'failed') return { key: 'error', ...USER_STATUSES.error }
  if (refund === 'rejected') return { key: 'cancelled', ...USER_STATUSES.cancelled }

  switch (status) {
    case 'created':
      return { key: 'pending_payment', ...USER_STATUSES.pending_payment }
    case 'paid':
      return { key: 'paid', ...USER_STATUSES.paid }
    case 'completed':
      return { key: 'completed', ...USER_STATUSES.approved }
    case 'cancelled':
      return { key: 'cancelled', ...USER_STATUSES.cancelled }
    // Legacy rows
    case 'submitted':
    case 'reviewing':
      return { key: 'processing', ...USER_STATUSES.processing }
    case 'approved':
      return { key: 'approved', ...USER_STATUSES.approved }
    case 'rejected':
      return { key: 'rejected', ...USER_STATUSES.rejected }
    case 'closed':
      return { key: 'cancelled', ...USER_STATUSES.cancelled }
    case 'abnormal':
    case 'failed':
      return { key: 'error', ...USER_STATUSES.error }
    default:
      return { key: 'error', ...USER_STATUSES.error }
  }
}

/**
 * Composable: returns the i18n-aware status + helpers.
 */
export function useOrderUserStatus() {
  const { t } = useI18n()

  function statusOf(order) {
    const u = computeUserStatus(order)
    return {
      ...u,
      label: t(`order_list.user_status.${u.key}`),
    }
  }

  /**
   * Build the timeline step list for a given order.
   * Returns an array of { key, label, state } where state ∈
   *   'done' | 'current' | 'failed' | 'pending'
   *
   * Stage mapping (W67+: 5 步):
   *   0 草稿          → current if user status is in {draft, pending_payment, error}
   *   1 待提交        → current if user status is in {ready_to_submit, paid} (created + paid)
   *   2 已提交        → current if user status is in {processing} 的前一步 (RpaSubmit 调通后)
   *   3 使馆审核      → current if user status is in {processing, refunding}
   *   4 已出签        → current if user status is approved → done, rejected → failed
   *   cancelled/refunded → failed style
   */
  function timelineOf(order) {
    const u = computeUserStatus(order)
    const keys = ['draft', 'ready_to_submit', 'submitted', 'processing', u.key === 'rejected' ? 'rejected' : 'approved']
    const stageOfUser = {
      draft: 0,
      pending_payment: 0,
      error: 0,
      ready_to_submit: 1,  // W67: paid 后但还没 RPA 提交,卡在第 2 步
      paid: 1,             // alias
      processing: 3,       // W67: 直接跳到第 4 步(使馆审核)。中间"已提交"算瞬时态
      refunding: 3,
      approved: 4,
      rejected: 4,
      refunded: 4,
      cancelled: 1,        // cancelled right after ready_to_submit
    }
    const curIdx = stageOfUser[u.key] ?? 0
    return keys.map((k, i) => {
      let state = 'pending'
      if (i < curIdx) state = 'done'
      else if (i === curIdx) {
        if (u.key === 'rejected') state = 'failed'
        else if (u.key === 'approved') state = 'done'
        else if (u.key === 'cancelled' || u.key === 'refunded') state = 'failed'
        else state = 'current'
      }
      return { key: k, label: t(`order_list.timeline.${k}`), state }
    })
  }

  return {
    statusOf,
    timelineOf,
  }
}
