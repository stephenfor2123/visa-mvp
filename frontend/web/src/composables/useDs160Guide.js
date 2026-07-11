// useDs160Guide.js — 从「用户档案 + 字段映射」生成 DS-160 引导式填写单
// =============================================================================
// 输出一份"照着抄"的结构化指引:按官网字段标签(不按页码)组织，
// 值直接从用户档案取好并转成官网要的格式，缺的标"待补"，可选空栏提示
// "勾 Does Not Apply"，条件不符的整段跳过。
//
// 关键:引导单是**生成的**，不是手写的 —— 官网改版只需改 ds160FieldMap.js。
// 与未来插件共用同一份映射，一分力两处用。
// =============================================================================
import {
  DS160_FIELD_MAP,
  DS160_MANUAL_STEPS,
  DS160_VERSION,
  DS160_VERIFIED_DATE,
} from '@/data/ds160FieldMap'

const _MONTHS_EN = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

// 按点路径取值:get(profile, 'passport.number')
function get(obj, path) {
  return path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj)
}

function isEmpty(v) {
  return v === undefined || v === null || String(v).trim() === ''
}

// DS-160 日期栏是 日 / 月缩写 / 年 三个下拉，官网展示成 DD-MMM-YYYY。
// 把 ISO 'YYYY-MM-DD'(或 'YYYY/M/D')转成 '14-MAY-1992'；解析不了就原样返回。
function toDs160Date(raw) {
  const m = String(raw).trim().match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/)
  if (!m) return String(raw)
  const [, y, mo, d] = m
  const mon = _MONTHS_EN[+mo - 1]
  if (!mon) return String(raw)
  return `${String(+d).padStart(2, '0')}-${mon}-${y}`
}

// 把档案原始值翻成官网要录入的最终值 + 动作文案
function resolveField(field, profile) {
  const raw = get(profile, field.profile)

  if (isEmpty(raw)) {
    // 可选栏为空 → 提示勾 Does Not Apply，不算缺失
    if (field.optional) {
      return {
        label: field.label,
        action: '勾选',
        value: field.whenEmpty || 'Does Not Apply（此项你没有）',
        missing: false,
        optional: true,
        note: field.note,
      }
    }
    // 必填栏为空 → 待补，绝不瞎填(防误导的关键)
    return { label: field.label, action: '待补', value: null, missing: true, note: field.note }
  }

  let value = raw
  if (field.valueMap && field.valueMap[raw] !== undefined) value = field.valueMap[raw]
  else if (field.valueMap && field.valueMap[String(raw)] !== undefined) value = field.valueMap[String(raw)]
  if (field.transform === 'upper') value = String(value).toUpperCase()
  else if (field.transform === 'date') value = toDs160Date(value)

  const action = field.input === 'select' || field.input === 'radio' ? '选择' : '输入'
  return { label: field.label, action, value, missing: false, note: field.note }
}

/**
 * 生成引导单。
 * @param {object} profile - ApplicantProfile(从 visa.wizard.* 收敛而来)
 * @returns {{
 *   meta: {version, verifiedDate},
 *   sections: Array<{section, officialTitle, steps: Array<{label, action, value, missing, optional, note}>}>,
 *   manualSteps: string[],
 *   missingCount: number
 * }}
 */
export function buildDs160Guide(profile = {}) {
  let missingCount = 0
  const sections = DS160_FIELD_MAP
    // 条件页:when 不满足整段跳过(单身不出现配偶页)
    .filter((sec) => (typeof sec.when === 'function' ? sec.when(profile) : true))
    .map((sec) => {
      const steps = sec.fields
        .filter((f) => (typeof f.when === 'function' ? f.when(profile) : true))
        .map((f) => {
          const step = resolveField(f, profile)
          if (step.missing) missingCount += 1
          return step
        })
      return { section: sec.section, officialTitle: sec.officialTitle, steps }
    })

  return {
    meta: { version: DS160_VERSION, verifiedDate: DS160_VERIFIED_DATE },
    sections,
    manualSteps: DS160_MANUAL_STEPS,
    missingCount,
  }
}

// 渲染成纯文本"照抄单"(用于导出 PDF / 复制，也方便调试)
export function renderGuideText(guide) {
  const lines = []
  lines.push('DS-160 填写单(照此录入官网)')
  const verified = guide.meta.verifiedDate || '未核对(初稿)'
  lines.push(`对应版本 DS-160 ${guide.meta.version}｜最后核对 ${verified}｜如与官网不符，以官网为准`)
  if (guide.missingCount > 0) lines.push(`⚠️ 有 ${guide.missingCount} 项待补，建议回 App 补全后再导出`)
  lines.push('')
  for (const sec of guide.sections) {
    lines.push(`【${sec.officialTitle}】`)
    for (const s of sec.steps) {
      const val = s.missing ? '⚠️ 待补(请回 App 补全)' : s.value
      lines.push(`  找到标着 "${s.label}" 的框 → ${s.action}:${val}${s.note ? `　(${s.note})` : ''}`)
    }
    lines.push('')
  }
  lines.push('👉 以下请你本人完成，工具不代做:')
  for (const m of guide.manualSteps) lines.push(`  · ${m}`)
  return lines.join('\n')
}
