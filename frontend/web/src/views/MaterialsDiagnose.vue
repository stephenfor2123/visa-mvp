<template>
  <div class="diag-page">
    <AppHeader scope="materials-diagnose" />
    <main class="diag-shell">
      <h1 class="page-title">{{ t('diagnose.title', 'AI 拒签风险诊断') }}</h1>
      <p class="page-sub">{{ t('diagnose.subtitle', '系统根据你上传的材料 + 目标国签证政策,综合评估拒签风险并给出可操作的优化建议。') }}</p>

      <!-- Step 1: 选择国家 + 签证类型 -->
      <section class="diag-form-section" data-testid="diag-form-section">
        <div class="diag-form-row">
          <label class="diag-field">
            <span class="diag-field__label">{{ t('diagnose.country', '目标国家') }}</span>
            <select v-model="countryCode" class="diag-input" data-testid="diag-country-select">
              <option v-for="c in countries" :key="c.code" :value="c.code">{{ c.name }}</option>
            </select>
          </label>
          <label class="diag-field">
            <span class="diag-field__label">{{ t('diagnose.visa_type', '签证类型') }}</span>
            <select v-model="visaType" class="diag-input" data-testid="diag-visa-select">
              <option value="">{{ t('diagnose.visa_default', '默认 (推荐)') }}</option>
              <option value="tourist">{{ t('diagnose.visa_tourist', '旅游') }}</option>
              <option value="business">{{ t('diagnose.visa_business', '商务') }}</option>
            </select>
          </label>
        </div>
      </section>

      <!-- Step 2: 选择参与诊断的材料 -->
      <section class="diag-mat-section" data-testid="diag-mat-section">
        <h2>{{ t('diagnose.pick_materials', '选择要诊断的材料') }} <span class="diag-mat-count">{{ selectedIds.length }}/{{ materials.length }}</span></h2>
        <div v-if="loadingMats" class="state-loading">⏳ {{ t('common.loading') }}</div>
        <div v-else-if="materials.length === 0" class="diag-empty">
          <p>{{ t('diagnose.no_materials', '你还没有上传任何材料,先去材料收集向导上传吧。') }}</p>
          <router-link :to="{ name: 'MaterialWizard', query: { country: countryCode, visa_type: visaType || 'tourism' } }" class="diag-cta">{{ t('diagnose.go_upload', '去上传材料') }}</router-link>
        </div>
        <div v-else class="diag-mat-list">
          <label
            v-for="m in materials"
            :key="m.id || m.material_id"
            class="diag-mat-card"
            :class="{ selected: selectedIds.includes(m.id || m.material_id) }"
            :data-testid="`diag-mat-card-${m.id || m.material_id}`"
          >
            <input
              type="checkbox"
              :value="m.id || m.material_id"
              v-model="selectedIds"
              class="diag-mat-card__cb"
            />
            <div class="diag-mat-card__body">
              <div class="diag-mat-card__name">{{ m.file_name || m.original_filename }}</div>
              <div class="diag-mat-card__meta">
                <span class="badge badge-type">{{ m.material_type }}</span>
                <span v-if="m.ocr_status" :class="`badge badge-ocr badge-ocr--${m.ocr_status}`">{{ m.ocr_status }}</span>
              </div>
            </div>
          </label>
        </div>
      </section>

      <!-- CTA -->
      <div class="diag-actions">
        <AppButton
          ref="runBtnRef"
          variant="primary"
          size="lg"
          :disabled="selectedIds.length === 0 || running"
          :loading="running"
          @click="runDiagnose"
          data-testid="diag-run-btn"
        >
          {{ running ? t('diagnose.running', '诊断中…') : t('diagnose.run', '开始 AI 诊断') }}
        </AppButton>
      </div>

      <!-- 诊断结果 -->
      <section v-if="result" class="diag-result-section" data-testid="diag-result-section">
        <header class="diag-result-head">
          <div :class="`diag-risk-badge diag-risk-badge--${result.overall_risk}`" data-testid="diag-risk-badge">
            <span class="diag-risk-badge__icon">{{ riskIcon }}</span>
            <span class="diag-risk-badge__text">{{ riskLabel }}</span>
            <span class="diag-risk-badge__score">{{ Math.round(result.risk_score * 100) }}</span>
          </div>
          <div class="diag-result-summary" data-testid="diag-summary">{{ result.summary }}</div>
        </header>

        <!-- 优化建议 (issues) -->
        <div v-if="result.issues.length > 0" class="diag-issues" data-testid="diag-issues">
          <h3>⚠️ {{ t('diagnose.issues_title', '需要优化的问题') }} ({{ result.issues.length }})</h3>
          <div
            v-for="iss in result.issues"
            :key="iss.code"
            :class="`diag-issue diag-issue--${iss.severity}`"
            :data-testid="`diag-issue-${iss.code}`"
          >
            <div class="diag-issue__head">
              <span :class="`diag-issue__sev diag-issue__sev--${iss.severity}`">{{ severityLabel(iss.severity) }}</span>
              <span class="diag-issue__title">{{ translateIssue(iss).title }}</span>
            </div>
            <p class="diag-issue__detail">{{ translateIssue(iss).detail }}</p>
            <p v-if="translateIssue(iss).fix" class="diag-issue__fix">👉 {{ translateIssue(iss).fix }}</p>
          </div>
        </div>

        <!-- 已达标项 -->
        <div v-if="result.positives.length > 0" class="diag-positives" data-testid="diag-positives">
          <h3>✅ {{ t('diagnose.positives_title', '已达标项') }} ({{ result.positives.length }})</h3>
          <ul>
            <li v-for="(p, i) in result.positives" :key="i">{{ p }}</li>
          </ul>
        </div>

        <!-- 政策引用 -->
        <div v-if="result.policy_refs && result.policy_refs.length > 0" class="diag-policy">
          <h3>📚 {{ t('diagnose.policy_title', '参考政策') }}</h3>
          <ul>
            <li v-for="(url, i) in result.policy_refs" :key="i">
              <a :href="url" target="_blank" rel="noopener">{{ url }}</a>
            </li>
          </ul>
        </div>

        <p class="diag-meta">
          {{ t('diagnose.rule_count', '本次共检查 {n} 条规则').replace('{n}', result.rule_count) }}
        </p>
      </section>

      <section v-if="errorMsg" class="diag-error" data-testid="diag-error">
        ⚠️ {{ errorMsg }}
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { listMaterials, diagnoseMaterials } from '@/api/materials'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import AppHeader from '@/components/AppHeader.vue'

const { t } = useI18n()
const auth = useAuthStore()

const countries = [
  { code: 'US', name: '美国 🇺🇸' },
  { code: 'GB', name: '英国 🇬🇧' },
  { code: 'JP', name: '日本 🇯🇵' },
  { code: 'KR', name: '韩国 🇰🇷' },
  { code: 'SG', name: '新加坡 🇸🇬' },
  { code: 'TH', name: '泰国 🇹🇭' },
  { code: 'VN', name: '越南 🇻🇳' },
  { code: 'ID', name: '印尼 🇮🇩' },
  { code: 'AU', name: '澳大利亚 🇦🇺' },
  { code: 'DE', name: '德国 🇩🇪' },
  { code: 'FR', name: '法国 🇫🇷' },
]

const countryCode = ref('US')
const visaType = ref('')
const materials = ref([])
const selectedIds = ref([])
const loadingMats = ref(true)
const running = ref(false)
const result = ref(null)
const errorMsg = ref('')

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

// W46: render issue title/detail/fix via the i18n keys returned by the backend.
// Fallback chain: (1) use key + params interpolation, (2) use key without
// params, (3) use the pre-rendered zh-CN field the server sent. This way a
// brand-new issue code that has no frontend translation yet still shows
// something readable.
function translateIssue(issue) {
  const out = { title: issue.title, detail: issue.detail, fix: issue.fix_suggestion }

  // Resolve country name in the current locale for {cc}/{country} interpolation
  const ccKey = `diagnose.country_${(countryCode.value || '').toLowerCase()}`
  const ccLocal = t(ccKey) !== ccKey ? t(ccKey) : countryCode.value

  // Resolve visa-type label
  const visaRaw = (issue.params && issue.params.visa) || ''
  const visaKey = `diagnose.visa_${visaRaw || 'default'}_lbl`
  const visaLocal = t(visaKey) !== visaKey ? t(visaKey) : visaRaw

  // Resolve material-type labels (for the "please add" suggestion)
  let typesLocal = (issue.params && issue.params.types) || ''
  if (issue.params && Array.isArray(issue.params.type_tokens)) {
    typesLocal = issue.params.type_tokens.map((tk) => {
      const k = `diagnose.type_${tk}`
      return t(k) !== k ? t(k) : tk
    }).join(', ')
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
  try {
    materials.value = await listMaterials({})
    // 默认全选
    selectedIds.value = materials.value.map((m) => m.id || m.material_id)
  } catch (e) {
    errorMsg.value = `加载材料列表失败: ${e.message || e}`
  } finally {
    loadingMats.value = false
  }
})

async function runDiagnose() {
  if (selectedIds.value.length === 0) return
  running.value = true
  result.value = null
  errorMsg.value = ''
  try {
    const data = await diagnoseMaterials({
      material_ids: selectedIds.value,
      country_code: countryCode.value,
      visa_type: visaType.value || undefined,
    })
    result.value = data
  } catch (e) {
    errorMsg.value = `诊断失败: ${e.message || e}`
  } finally {
    running.value = false
  }
}
</script>

<style scoped lang="scss">
.diag-page { min-height: 100vh; background: #FFFFFF; }
.diag-shell {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px 80px;
}

.diag-form-section, .diag-mat-section {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.diag-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.diag-field { display: flex; flex-direction: column; gap: 6px; }
.diag-field__label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.diag-input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  font-size: 14px;
  background: #fff;
  color: #0F172A;
  outline: none;
  &:focus { border-color: #3B6EF5; box-shadow: 0 0 0 3px rgba(59, 110, 245, 0.15); }
}

.diag-mat-section h2 {
  font-size: 16px;
  margin: 0 0 12px;
  color: #0F172A;
}
.diag-mat-count {
  font-size: 13px;
  color: #94A3B8;
  font-weight: 400;
}

.diag-mat-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.diag-mat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  cursor: pointer;
  background: #fff;
  transition: border-color .15s, background .15s;
  &:hover { border-color: #94A3B8; }
  &.selected {
    border-color: #3B6EF5;
    background: #F0F4FF;
  }
}
.diag-mat-card__cb { flex-shrink: 0; }
.diag-mat-card__name {
  font-size: 13px;
  font-weight: 500;
  color: #0F172A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.diag-mat-card__meta {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 500;
}
.badge-type { background: #EEF2FF; color: #4338CA; }
.badge-ocr--done { background: #DCFCE7; color: #15803D; }
.badge-ocr--pending { background: #FEF3C7; color: #B45309; }
.badge-ocr--failed { background: #FEE2E2; color: #B91C1C; }

.diag-empty {
  text-align: center;
  padding: 24px 12px;
  color: #64748B;
}
.diag-cta {
  display: inline-block;
  margin-top: 8px;
  color: #3B6EF5;
  text-decoration: none;
  font-weight: 600;
}

.diag-actions {
  display: flex;
  justify-content: center;
  margin: 24px 0;
}

.diag-result-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.diag-result-head {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #E2E8F0;
}
.diag-risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
  &--low      { background: #DCFCE7; color: #15803D; }
  &--medium   { background: #FEF3C7; color: #B45309; }
  &--high     { background: #FED7AA; color: #C2410C; }
  &--critical { background: #FEE2E2; color: #B91C1C; }
}
.diag-risk-badge__icon { font-size: 18px; }
.diag-risk-badge__score {
  margin-left: 4px;
  font-size: 12px;
  opacity: .8;
}
.diag-result-summary {
  font-size: 15px;
  color: #1E293B;
  line-height: 1.5;
  flex: 1;
}

.diag-issues h3, .diag-positives h3, .diag-policy h3 {
  font-size: 14px;
  margin: 16px 0 8px;
  color: #475569;
}
.diag-issue {
  padding: 12px 16px;
  border-radius: 10px;
  margin-bottom: 10px;
  border-left: 4px solid #94A3B8;
  &--critical { border-left-color: #DC2626; background: #FEF2F2; }
  &--error    { border-left-color: #EA580C; background: #FFF7ED; }
  &--warning  { border-left-color: #CA8A04; background: #FEFCE8; }
  &--info     { border-left-color: #2563EB; background: #EFF6FF; }
}
.diag-issue__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.diag-issue__sev {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
  &--critical { background: #DC2626; color: #fff; }
  &--error    { background: #EA580C; color: #fff; }
  &--warning  { background: #CA8A04; color: #fff; }
  &--info     { background: #2563EB; color: #fff; }
}
.diag-issue__title {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
}
.diag-issue__detail {
  font-size: 13px;
  color: #475569;
  margin: 4px 0 0;
  line-height: 1.5;
}
.diag-issue__fix {
  font-size: 13px;
  color: #1E40AF;
  margin: 6px 0 0;
  line-height: 1.5;
}
.diag-positives ul, .diag-policy ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: #475569;
  li { margin-bottom: 4px; }
}
.diag-policy a {
  color: #3B6EF5;
  text-decoration: none;
  &:hover { text-decoration: underline; }
}
.diag-meta {
  margin-top: 16px;
  font-size: 12px;
  color: #94A3B8;
  text-align: right;
}

.diag-error {
  background: #FEE2E2;
  color: #B91C1C;
  padding: 12px 16px;
  border-radius: 8px;
  margin-top: 16px;
}

.state-loading {
  text-align: center;
  padding: 32px;
  color: #94A3B8;
}
</style>