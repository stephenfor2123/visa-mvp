/** Shared audit_log action → 中文 label (admin logs + order detail). */
export const AUDIT_ACTION_LABELS = {
  'order.create': '订单创建',
  'order.submit': '订单提交',
  'order.cancel': '订单取消',
  'order.approve': '审核通过',
  'order.reject': '审核拒绝',
  'order.close': '订单关闭',
  'order.abnormal': '订单异常',
  'order.update_status': '状态变更',
  'order.diagnosis.complete': 'AI 诊断完成',
  'order.portal.submitted': '官网提交（用户/插件）',
  'order.refund.request': '用户申请退款',
  'payment.create': '发起支付',
  'payment.notify': '支付回调',
  'payment.close': '支付关闭',
  'payment.refund': '支付退款',
  'rpa.start': 'RPA 启动',
  'rpa.submit': 'RPA 提交',
  'rpa.done': 'RPA 完成',
  'rpa.failed': 'RPA 失败',
  'admin.login': '管理员登录',
  'admin.order.update_status': '管理员变更状态',
  'admin.order.refund.approve': '管理员同意退款',
  'admin.order.refund.reject': '管理员驳回退款',
  'admin.order.refund.complete': '管理员完成退款打款',
  'admin.order.refund.fail': '管理员标记退款失败',
  'admin.order.portal.submitted': '管理员确认官网提交',
  'admin.pricing.update': '更新平台定价',
  'ds160.portal.submitted': 'DS-160 官网提交（插件）',
}

function parsePayload(payload) {
  if (!payload) return null
  if (typeof payload === 'object') return payload
  try { return JSON.parse(payload) } catch { return null }
}

export function formatAuditAction(log) {
  const action = log?.action || ''
  const label = AUDIT_ACTION_LABELS[action] || action
  const payload = parsePayload(log?.payload)
  if (payload && typeof payload === 'object') {
    const from = payload.from_status
    const to = payload.to_status
    if (from && to) return `${label}：${from} → ${to}`
    if (payload.refund_status) return `${label}（${payload.refund_status}）`
  }
  return label
}
