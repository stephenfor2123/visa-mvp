<!--
  OrderPrecheck.vue — W50: AI 拒签风险预审 (美签订单专属)
  ==========================================================
  插在 MaterialWizard / OrderNew 提交订单成功 → 跳 RpaSubmit 之间。
  流程:用户提交订单 → US 国家 → 自动跳到这里 → 自动跑 /v2/materials/diagnose
        显示综合风险 + 可操作的优化建议 → 用户点"继续提交 RPA"才走原 RpaSubmit 流程。

  设计原则:
    - 不阻断:全展示,所有问题只是建议,critical/high/warning 都可以继续提交。
    - US-only:非 US 国家永远不会走到这页(由调用方判断 countryCode==='US' 决定是否
              跳过来,所以这页本身不再做国家判断,接受就是 US)。
    - 材料自动全选:跟 /materials/diagnose 不一样 — 这里用户已经在提交订单的语境,
                  不需要再勾选,直接把订单关联的 material_ids 传过去即可。

  关键字段:
    - url: /orders/:orderNo/precheck?countryCode=US&visaType=tourism&materialIds=1,2,3&fields={...}
      (fields 用 JSON 字符串塞进 query,因为表单字段较多)
-->
<template>
  <div class="precheck-page">
    <AppHeader scope="materials-diagnose" />
    <main class="diag-shell">
      <h1 class="page-title">{{ t('precheck.title', 'AI 拒签风险预审') }}</h1>
      <p class="page-sub">
        {{ t('precheck.subtitle',
          '根据你刚才提交的材料 + 美签申请表内容,综合评估一次签证风险。下面的提示仅供参考,你可以直接继续提交 RPA。'
        ) }}
      </p>

      <!-- 订单信息条 — 已删除,信息并入下方 4 张概览卡(Resources 风格) -->

      <!-- Loading / Empty / Result -->
      <div v-if="running" class="state-loading" data-testid="precheck-loading">
        <span class="spinner" aria-hidden="true"></span>
        {{ t('precheck.running', 'AI 正在分析材料,大约需要 10-20 秒…') }}
      </div>

      <section v-else-if="result" class="diag-result-section" data-testid="precheck-result-section">
        <!-- 4 张概览卡:订单号 / 风险分数 / 材料数 / 规则数 (Resources 风格:序号圆 + 标题 + 副标题) -->
        <div class="precheck-overview" data-testid="precheck-overview">
          <div class="precheck-overview__card">
            <span class="precheck-overview__num">1</span>
            <div class="precheck-overview__body">
              <div class="precheck-overview__ttl">{{ t('precheck.card_order', '订单号') }}</div>
              <div class="precheck-overview__sub" data-testid="precheck-order-no">{{ orderNo || '—' }}</div>
            </div>
          </div>
          <div class="precheck-overview__card">
            <span class="precheck-overview__num">2</span>
            <div class="precheck-overview__body">
              <div class="precheck-overview__ttl">{{ t('precheck.card_risk', '风险等级') }}</div>
              <div class="precheck-overview__sub" :class="`is-${result.overall_risk}`">
                <span class="precheck-overview__risk" :data-testid="precheck-risk-badge">
                  <span class="precheck-overview__risk-icon">{{ riskIcon }}</span>
                  <span class="precheck-overview__risk-text">{{ riskLabel }}</span>
                  <span class="precheck-overview__risk-score">{{ Math.round(result.risk_score * 100) }}</span>
                  <button
                    type="button"
                    class="precheck-overview__risk-info"
                    :aria-label="t('precheck.score_info_aria', '查看分数说明')"
                    data-testid="precheck-score-info"
                    @click="scoreInfoOpen = !scoreInfoOpen"
                  >ⓘ</button>
                </span>
              </div>
            </div>
          </div>
          <div class="precheck-overview__card">
            <span class="precheck-overview__num">3</span>
            <div class="precheck-overview__body">
              <div class="precheck-overview__ttl">{{ t('precheck.card_materials', '参与诊断的材料') }}</div>
              <div class="precheck-overview__sub" data-testid="precheck-material-count">
                {{ snapshotCount }} {{ t('precheck.material_count_unit', '份') }}
              </div>
            </div>
          </div>
          <div class="precheck-overview__card">
            <span class="precheck-overview__num">4</span>
            <div class="precheck-overview__body">
              <div class="precheck-overview__ttl">{{ t('precheck.card_rules', '本次检查规则') }}</div>
              <div class="precheck-overview__sub">{{ result.rule_count }} {{ t('precheck.card_rules_unit', '条') }}</div>
            </div>
          </div>
        </div>

        <!-- 总结句 — 单独成行,字号大,跟 Resources 副标题对齐 -->
        <p class="precheck-summary" data-testid="precheck-summary">{{ result.summary }}</p>

        <!-- 分数构成 popover:解释"45/100 是什么"以及每条 issue 贡献多少分 -->
        <div v-if="scoreInfoOpen" class="diag-score-info" data-testid="precheck-score-info-panel">
          <header class="diag-score-info__head">
            <strong>{{ t('precheck.score_info_title', '这个分数是怎么算的?') }}</strong>
            <button type="button" class="diag-score-info__close" @click="scoreInfoOpen = false">×</button>
          </header>
          <p class="diag-score-info__intro">
            {{ t('precheck.score_info_intro',
              '系统对每条问题按严重度扣分,把所有问题扣分累加得到总分(0~100,越低越好)。点击下方的阈值可看到完整的风险等级。') }}
          </p>
          <table class="diag-score-info__thresholds">
            <thead>
              <tr>
                <th>{{ t('precheck.threshold_label', '风险等级') }}</th>
                <th>{{ t('precheck.threshold_range', '分数范围') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr :class="{ 'is-current': result.overall_risk === 'low' }">
                <td>✅ {{ t('diagnose.risk_low', '低风险') }}</td>
                <td>0 — 9</td>
              </tr>
              <tr :class="{ 'is-current': result.overall_risk === 'medium' }">
                <td>⚠️ {{ t('diagnose.risk_medium', '中风险') }}</td>
                <td>10 — 29</td>
              </tr>
              <tr :class="{ 'is-current': result.overall_risk === 'high' }">
                <td>🚨 {{ t('diagnose.risk_high', '高风险') }}</td>
                <td>30 — 49</td>
              </tr>
              <tr :class="{ 'is-current': result.overall_risk === 'critical' }">
                <td>🛑 {{ t('diagnose.risk_critical', '严重风险') }}</td>
                <td>50 — 100</td>
              </tr>
            </tbody>
          </table>
          <div class="diag-score-info__current">
            <strong>{{ t('precheck.score_breakdown_title', '本次分数构成') }}: {{ Math.round(result.risk_score * 100) }} / 100</strong>
            <ul v-if="scoreBreakdown.length">
              <li v-for="(line, i) in scoreBreakdown" :key="`sb-${i}`" :class="`is-${line.severity}`">
                <span class="diag-score-info__contrib">+{{ line.contrib }}</span>
                <span class="diag-score-info__sev">{{ severityLabel(line.severity) }}</span>
                <span class="diag-score-info__ttl">{{ line.title }}</span>
              </li>
            </ul>
            <p v-else class="diag-score-info__clean">
              ✅ {{ t('precheck.score_breakdown_clean', '目前没有任何扣分项,继续保持。') }}
            </p>
          </div>
          <details class="diag-score-info__weights">
            <summary>{{ t('precheck.score_weights_title', '查看每种严重度扣多少分') }}</summary>
            <ul>
              <li><span class="sev-pill is-info">{{ t('diagnose.severity_info', '提示') }}</span> +0</li>
              <li><span class="sev-pill is-warning">{{ t('diagnose.severity_warning', '警告') }}</span> +15</li>
              <li><span class="sev-pill is-error">{{ t('diagnose.severity_error', '错误') }}</span> +35</li>
              <li><span class="sev-pill is-critical">{{ t('diagnose.severity_critical', '严重') }}</span> +60</li>
            </ul>
          </details>
        </div>

        <!-- 优化建议 — 跟 Resources "热门问题" 一样的 2 列卡片网格 -->
        <section v-if="result.issues.length > 0" class="precheck-issues" data-testid="precheck-issues">
          <h2 class="precheck-section__ttl">
            <span class="precheck-section__icon">⚠️</span>
            {{ t('diagnose.issues_title', '需要优化的问题') }}
            <span class="precheck-section__count">({{ result.issues.length }})</span>
          </h2>
          <div class="precheck-issues__grid">
            <div
              v-for="(iss, idx) in result.issues"
              :key="iss.code"
              :class="`precheck-issue precheck-issue--${iss.severity}`"
              :data-testid="`precheck-issue-${iss.code}`"
            >
              <div class="precheck-issue__head">
                <span class="precheck-issue__num">{{ idx + 1 }}</span>
                <span :class="`precheck-issue__sev precheck-issue__sev--${iss.severity}`">
                  {{ severityLabel(iss.severity) }}
                </span>
              </div>
              <h3 class="precheck-issue__title">{{ translateIssue(iss).title }}</h3>
              <p class="precheck-issue__detail">{{ translateIssue(iss).detail }}</p>
              <p v-if="translateIssue(iss).fix" class="precheck-issue__fix">
                👉 {{ translateIssue(iss).fix }}
              </p>
            </div>
          </div>
        </section>
        <section v-else class="precheck-issues precheck-issues--empty" data-testid="precheck-no-issues">
          <h2 class="precheck-section__ttl">
            <span class="precheck-section__icon">✅</span>
            {{ t('precheck.no_issues', '没有发现明显问题,可以放心继续提交。') }}
          </h2>
        </section>

        <!-- 已达标项 — 同样 2 列网格 -->
        <section v-if="result.positives && result.positives.length > 0" class="precheck-positives" data-testid="precheck-positives">
          <h2 class="precheck-section__ttl">
            <span class="precheck-section__icon">✅</span>
            {{ t('diagnose.positives_title', '已达标项') }}
            <span class="precheck-section__count">({{ result.positives.length }})</span>
          </h2>
          <div class="precheck-positives__grid">
            <div v-for="(p, i) in result.positives" :key="`pos-${i}`" class="precheck-positive">
              <span class="precheck-positive__check">✓</span>
              <span class="precheck-positive__text">{{ p }}</span>
            </div>
          </div>
        </section>

        <!-- 政策引用 -->
        <section v-if="result.policy_refs && result.policy_refs.length > 0" class="precheck-policy">
          <h2 class="precheck-section__ttl">
            <span class="precheck-section__icon">📚</span>
            {{ t('diagnose.policy_title', '参考政策') }}
          </h2>
          <ul class="precheck-policy__list">
            <li v-for="(url, i) in result.policy_refs" :key="`pol-${i}`">
              <a :href="url" target="_blank" rel="noopener">{{ url }}</a>
            </li>
          </ul>
        </section>
      </section>

      <section v-else-if="errorMsg" class="diag-error" data-testid="precheck-error">
        ⚠️ {{ errorMsg }}
      </section>

      <!-- W67: 删掉底部"以上只是参考建议..."+ 2 个按钮栏。
           用户反馈: 反复让人"决定先优化材料"很烦,既然不会阻止提交就别劝退。
           现在页面只剩诊断结果展示本身,看完就关/走系统流程。 -->
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { diagnoseMaterials } from '@/api/materials'
import { loadPrecheckSnapshot, buildDiagnosableSnapshotFromOcrCache } from '@/utils/localPrivacyStorage'
import AppButton from '@/components/AppButton.vue'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// url 参数 ---------------------------------------------------------- //
// - orderNo    : 订单号(必传)
// - countryCode : 国家码(默认 'US',OrderPrecheck 当前只服务 US)
// - visaType   : 签证类型,默认 'tourism'
// - materialIds : 逗号分隔的材料 id 列表(必传)
// - fields     : base64(JSON.stringify(formData)),表单字段(关键:让后端识别美签 DS-160
//                表的字段跟护照是否一致、出生地是否填好、婚姻状态等)
const orderNo = ref('')
const countryCode = ref('US')
const visaType = ref('tourism')
const materialsSnapshot = ref([])
const fieldsMap = ref({})

const snapshotCount = computed(() => materialsSnapshot.value.length)

function decodeFields(b64) {
  if (!b64) return {}
  try {
    const json = atob(decodeURIComponent(b64))
    return JSON.parse(json) || {}
  } catch {
    return {}
  }
}

const running = ref(true) // 默认是 running 状态,onMounted 一进来就自动跑
const result = ref(null)
const errorMsg = ref('')
const scoreInfoOpen = ref(false)

// 与后端 visa_diagnoser._SEVERITY_WEIGHT 保持一致 — 前端展示分数构成用
const SEVERITY_WEIGHT = { info: 0, warning: 15, error: 35, critical: 60 }

// 把所有 issue 按严重度扣分拆出来,给"分数构成"面板用
const scoreBreakdown = computed(() => {
  if (!result.value?.issues) return []
  return result.value.issues.map((iss) => ({
    severity: iss.severity || 'info',
    contrib: SEVERITY_WEIGHT[iss.severity] ?? 0,
    title: translateIssue(iss).title || iss.title || iss.code,
  }))
})

const riskIcon = computed(() => {
  if (!result.value) return ''
  return { low: '✅', medium: '⚠️', high: '🚨', critical: '🛑' }[result.value.overall_risk] || '❓'
})
const riskLabel = computed(() => {
  if (!result.value) return ''
  return {
    low: t('diagnose.risk_low'),
    medium: t('diagnose.risk_medium'),
    high: t('diagnose.risk_high'),
    critical: t('diagnose.risk_critical'),
  }[result.value.overall_risk] || t('diagnose.risk_unknown')
})

function severityLabel(sev) {
  return t(`diagnose.severity_${sev}`) || sev
}

// 与 MaterialsDiagnose.vue 同一套 i18n 翻译策略:title_key/detail_key/fix_key 优先,
// 否则回退用后端原文。这样将来后端新增 issue code 也不至于整页空白。
function translateIssue(issue) {
  const out = { title: issue.title, detail: issue.detail, fix: issue.fix_suggestion }
  const ccKey = `diagnose.country_${(countryCode.value || '').toLowerCase()}`
  const ccLocal = t(ccKey) !== ccKey ? t(ccKey) : countryCode.value
  const visaRaw = (issue.params && issue.params.visa) || ''
  const visaKey = `diagnose.visa_${visaRaw || 'default'}_lbl`
  const visaLocal = t(visaKey) !== visaKey ? t(visaKey) : visaRaw
  let typesLocal = (issue.params && issue.params.types) || ''
  if (issue.params && Array.isArray(issue.params.type_tokens)) {
    typesLocal = issue.params.type_tokens
      .map((tk) => {
        const k = `diagnose.type_${tk}`
        return t(k) !== k ? t(k) : tk
      })
      .join(', ')
  }
  if (issue.title_key) {
    const params = { cc: ccLocal, country: ccLocal, visa: visaLocal, types: typesLocal, ...(issue.params || {}) }
    const v = t(issue.title_key, params)
    if (v !== issue.title_key) out.title = v
  }
  if (issue.detail_key) {
    const params = { ...(issue.params || {}), cc: ccLocal, country: ccLocal, visa: visaLocal }
    const v = t(issue.detail_key, params)
    if (v !== issue.detail_key) out.detail = v
  }
  if (issue.fix_key) {
    const params = { types: typesLocal, ...(issue.params || {}) }
    const v = t(issue.fix_key, params)
    if (v !== issue.fix_key) out.fix = v
  }
  return out
}

onMounted(async () => {
  orderNo.value = String(route.params.orderNo || '')
  countryCode.value = String(route.query.countryCode || 'US').toUpperCase()
  visaType.value = String(route.query.visaType || 'tourism')

  fieldsMap.value = decodeFields(String(route.query.fields || ''))

  // 优先读提交订单时写入的本机 snapshot；回退到 OCR 缓存
  const fromSession = loadPrecheckSnapshot(orderNo.value)
  if (fromSession.length) {
    materialsSnapshot.value = fromSession
  } else {
    materialsSnapshot.value = buildDiagnosableSnapshotFromOcrCache()
  }

  if (!materialsSnapshot.value.length) {
    running.value = false
    errorMsg.value = t('precheck.err_no_materials', '没找到可诊断的本机材料，请先在向导中上传并识别。')
    return
  }

  try {
    const data = await diagnoseMaterials({
      materials_snapshot: materialsSnapshot.value,
      country_code: countryCode.value,
      visa_type: visaType.value,
      fields: fieldsMap.value,
    })
    result.value = data
  } catch (e) {
    errorMsg.value = `诊断失败: ${e?.message || e}`
  } finally {
    running.value = false
  }
})

function goDiagnose() {
  // 跳完整诊断页(/materials/diagnose 已经要求登录),让用户可以重跑 / 加材料
  router.push({
    name: 'MaterialsDiagnose',
    query: { country: countryCode.value, visa_type: visaType.value },
  })
}

function goNext() {
  // 还原 MaterialWizard/OrderNew 原本的 RpaSubmit 跳转逻辑。
  // sessionStorage 里的 passport data 是由调用方在跳过来前写入的
  // (rpa_passport_{orderNo}),RpaSubmit.vue 自己会读。
  router.push({
    name: 'RpaSubmit',
    query: {
      orderNo: orderNo.value,
      countryCode: countryCode.value,
      visaType: visaType.value,
    },
  }).catch(() => {
    router.push({ name: 'OrderDetail', params: { orderNo: orderNo.value } })
  })
}
</script>

<style scoped lang="scss">
// 复用 Resources 资源中心的视觉 — 居中标题、4 张概览卡、2 列问题网格。
.precheck-page { min-height: 100vh; background: #FFFFFF; }
.diag-shell {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 20px 80px;
}
.page-title {
  font-size: 30px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #0F172A;
  text-align: center;
  letter-spacing: -0.01em;
}
.page-sub {
  font-size: 14.5px;
  color: #64748B;
  text-align: center;
  margin: 0 auto 28px;
  line-height: 1.6;
  max-width: 640px;
}
.state-loading {
  text-align: center;
  padding: 56px 12px;
  color: #64748B;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  .spinner { display: inline-block; vertical-align: middle; margin-right: 8px; }
}
.diag-result-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

// 4 张概览卡:Resources 风格 — 序号圆 + 标题 + 副标题
.precheck-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  @media (max-width: 900px) { grid-template-columns: repeat(2, 1fr); }
  @media (max-width: 540px) { grid-template-columns: 1fr; }
}
.precheck-overview__card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  transition: border-color .15s;
  &:hover { border-color: #CBD5E1; }
}
.precheck-overview__num {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #0F172A;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.precheck-overview__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.precheck-overview__ttl {
  font-size: 13px;
  color: #64748B;
  font-weight: 500;
}
.precheck-overview__sub {
  font-size: 14px;
  color: #0F172A;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.precheck-overview__risk {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  width: fit-content;
}
.precheck-overview__sub.is-low      .precheck-overview__risk { background: #DCFCE7; color: #15803D; }
.precheck-overview__sub.is-medium   .precheck-overview__risk { background: #FEF3C7; color: #B45309; }
.precheck-overview__sub.is-high     .precheck-overview__risk { background: #FED7AA; color: #C2410C; }
.precheck-overview__sub.is-critical .precheck-overview__risk { background: #FEE2E2; color: #B91C1C; }
.precheck-overview__risk-icon { font-size: 14px; }
.precheck-overview__risk-score { font-size: 12px; opacity: .8; }
.precheck-overview__risk-info {
  background: transparent;
  border: 1px solid currentColor;
  color: inherit;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  opacity: .7;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: opacity .15s;
  &:hover { opacity: 1; }
  &:focus-visible { outline: 2px solid #3B6EF5; outline-offset: 1px; }
}

// 总结句 — 居中大字,Resources 副标题同款
.precheck-summary {
  text-align: center;
  font-size: 16px;
  color: #1E293B;
  line-height: 1.6;
  margin: 0;
  padding: 4px 12px;
}

// section 标题 — Resources "热门问题" 那种
.precheck-section__ttl {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
  color: #0F172A;
  margin: 8px 0 0;
}
.precheck-section__icon { font-size: 18px; }
.precheck-section__count {
  font-size: 13px;
  font-weight: 500;
  color: #94A3B8;
  margin-left: 4px;
}

// 问题卡:2 列网格,Resources 热门问题样式
.precheck-issues__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 12px;
  @media (max-width: 720px) { grid-template-columns: 1fr; }
}
.precheck-issue {
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  border-left: 4px solid #94A3B8;
  &--critical { border-left-color: #DC2626; background: linear-gradient(90deg, #FEF2F2 0%, #fff 60%); }
  &--error    { border-left-color: #EA580C; background: linear-gradient(90deg, #FFF7ED 0%, #fff 60%); }
  &--warning  { border-left-color: #CA8A04; background: linear-gradient(90deg, #FEFCE8 0%, #fff 60%); }
  &--info     { border-left-color: #2563EB; background: linear-gradient(90deg, #EFF6FF 0%, #fff 60%); }
}
.precheck-issue__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.precheck-issue__num {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #0F172A;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.precheck-issue__sev {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
  &--critical { background: #DC2626; color: #fff; }
  &--error    { background: #EA580C; color: #fff; }
  &--warning  { background: #CA8A04; color: #fff; }
  &--info     { background: #2563EB; color: #fff; }
}
.precheck-issue__title {
  font-size: 14.5px;
  font-weight: 600;
  color: #0F172A;
  margin: 0 0 6px;
  line-height: 1.4;
}
.precheck-issue__detail {
  font-size: 13px;
  color: #475569;
  margin: 0 0 6px;
  line-height: 1.6;
}
.precheck-issue__fix {
  font-size: 12.5px;
  color: #1E40AF;
  margin: 4px 0 0;
  line-height: 1.5;
  padding-top: 6px;
  border-top: 1px dashed #E2E8F0;
}
.precheck-issues--empty {
  background: #F0FDF4;
  border-radius: 12px;
  padding: 18px 22px;
  text-align: center;
  .precheck-section__ttl { justify-content: center; color: #15803D; }
}

// 已达标项 — 2 列网格
.precheck-positives__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 16px;
  margin-top: 12px;
  @media (max-width: 720px) { grid-template-columns: 1fr; }
}
.precheck-positive {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  font-size: 13.5px;
  color: #475569;
  line-height: 1.5;
}
.precheck-positive__check {
  flex-shrink: 0;
  color: #15803D;
  font-weight: 700;
  margin-top: 1px;
}
.precheck-positive__text { flex: 1; }

// 政策引用
.precheck-policy__list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  li { font-size: 13px; }
  a {
    color: #3B6EF5;
    text-decoration: none;
    word-break: break-all;
    &:hover { text-decoration: underline; }
  }
}

.diag-error {
  background: #FEE2E2;
  color: #B91C1C;
  padding: 12px 16px;
  border-radius: 8px;
  margin-top: 16px;
}

/* ---------- 分数构成 popover ---------- */
.diag-score-info {
  margin-top: 12px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, .06);
  font-size: 13px;
  color: #334155;
  max-width: 560px;
}
.diag-score-info__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  color: #0F172A;
  margin-bottom: 6px;
}
.diag-score-info__close {
  background: transparent;
  border: 0;
  font-size: 20px;
  line-height: 1;
  color: #94A3B8;
  cursor: pointer;
  padding: 0 4px;
  &:hover { color: #475569; }
}
.diag-score-info__intro {
  margin: 4px 0 12px;
  line-height: 1.5;
  color: #475569;
}
.diag-score-info__thresholds {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 12px;
  font-size: 12.5px;
  th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #F1F5F9; }
  th { color: #64748B; font-weight: 600; font-size: 12px; }
  tr.is-current { background: #FEF3C7; font-weight: 600; }
  tr.is-current td { color: #92400E; }
}
.diag-score-info__current {
  margin-bottom: 10px;
  padding-top: 4px;
  border-top: 1px dashed #E2E8F0;
  > strong { font-size: 13px; color: #0F172A; }
  ul { list-style: none; margin: 8px 0 0; padding: 0; }
  li {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 4px 0;
    font-size: 12.5px;
    color: #475569;
  }
  li.is-warning .diag-score-info__contrib { color: #B45309; font-weight: 700; }
  li.is-error .diag-score-info__contrib { color: #DC2626; font-weight: 700; }
  li.is-critical .diag-score-info__contrib { color: #B91C1C; font-weight: 700; }
}
.diag-score-info__contrib {
  font-variant-numeric: tabular-nums;
  min-width: 32px;
  display: inline-block;
}
.diag-score-info__sev {
  font-size: 11px;
  background: #F1F5F9;
  color: #475569;
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}
.diag-score-info__ttl { flex: 1; }
.diag-score-info__clean {
  margin: 8px 0 0;
  color: #15803D;
  font-size: 12.5px;
}
.diag-score-info__weights {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #E2E8F0;
  font-size: 12px;
  summary { cursor: pointer; color: #64748B; padding: 4px 0; }
  ul { list-style: none; margin: 6px 0 0; padding: 0; }
  li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
  }
}
.sev-pill {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
  min-width: 50px;
  text-align: center;
  &.is-info      { background: #DBEAFE; color: #1E40AF; }
  &.is-warning   { background: #FEF3C7; color: #92400E; }
  &.is-error     { background: #FEE2E2; color: #B91C1C; }
  &.is-critical  { background: #FECACA; color: #7F1D1D; }
}
</style>
