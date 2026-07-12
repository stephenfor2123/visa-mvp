<template>
  <section v-if="guide" class="visa-guide card" data-testid="visa-guide-panel">
    <div class="visa-guide__head">
      <h2 class="card__title">{{ t('orderdetail.visa_guide_title') }}</h2>
      <span v-if="guide.missingCount > 0" class="visa-guide__badge visa-guide__badge--warn" data-testid="visa-guide-missing-badge">
        {{ t('orderdetail.visa_guide_missing', { n: guide.missingCount }) }}
      </span>
      <span v-else class="visa-guide__badge visa-guide__badge--ok" data-testid="visa-guide-complete-badge">
        {{ t('orderdetail.visa_guide_complete') }}
      </span>
    </div>
    <p class="visa-guide__hint">{{ t('orderdetail.visa_guide_hint') }}</p>
    <p class="visa-guide__portal-lang">{{ t('orderdetail.visa_guide_portal_lang') }}</p>

    <ol v-if="guide.manualSteps?.length" class="visa-guide__manual">
      <li v-for="(step, i) in guide.manualSteps" :key="'m-' + i">{{ step }}</li>
    </ol>

    <div v-for="sec in guide.sections" :key="sec.section" class="visa-guide__section" :data-testid="`visa-guide-sec-${sec.section}`">
      <h3 class="visa-guide__section-title">{{ sec.officialTitle }}</h3>
      <dl class="visa-guide__fields">
        <div
          v-for="(step, i) in sec.steps"
          :key="sec.section + '-' + i"
          class="visa-guide__row"
          :class="{ 'is-missing': step.missing, 'is-na': step.action === 'na' }"
        >
          <dt>{{ step.label }}</dt>
          <dd>
            <span v-if="step.missing" class="visa-guide__todo">{{ t('orderdetail.visa_guide_todo') }}</span>
            <span v-else>{{ step.value }}</span>
            <span v-if="step.note" class="visa-guide__note">{{ step.note }}</span>
          </dd>
        </div>
      </dl>
    </div>

    <div class="visa-guide__actions">
      <button type="button" class="visa-guide__copy" data-testid="visa-guide-copy-btn" @click="copyGuide">
        📋 {{ t('orderdetail.visa_guide_copy_btn') }}
      </button>
      <a
        v-if="officialUrl"
        :href="officialUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="visa-guide__official"
        data-testid="visa-guide-official-link"
      >
        🚀 {{ t('orderdetail.visa_guide_official_btn') }}
      </a>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { renderVisaGuideText } from '@/data/visaFieldMapUtils.js'

const props = defineProps({
  guide: { type: Object, default: null },
  countryCode: { type: String, default: '' },
})

const { t } = useI18n()
const toast = useToast()

const officialUrl = computed(() => {
  const c = (props.countryCode || props.guide?.meta?.country || '').toUpperCase()
  if (c === 'GB') return 'https://www.gov.uk/standard-visitor-visa/apply-standard-visitor-visa'
  if (c === 'AU') return 'https://online.immi.gov.au/lusc/login'
  if (c === 'US') return 'https://ceac.state.gov/genniv/'
  return ''
})

async function copyGuide() {
  if (!props.guide) return
  const text = renderVisaGuideText(props.guide, { title: t('orderdetail.visa_guide_copy_title') })
  try {
    await navigator.clipboard.writeText(text)
    toast.success(t('orderdetail.visa_guide_copy_ok'))
  } catch {
    toast.error(t('orderdetail.visa_guide_copy_fail'))
  }
}
</script>

<style scoped>
.visa-guide__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 8px;
}
.visa-guide__head .card__title {
  margin: 0;
  flex: 1 1 auto;
}
.visa-guide__badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
}
.visa-guide__badge--warn {
  background: #fef3c7;
  color: #92400e;
}
.visa-guide__badge--ok {
  background: #dcfce7;
  color: #166534;
}
.visa-guide__hint {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 12px;
}
.visa-guide__portal-lang {
  font-size: 12px;
  color: #0369a1;
  margin: -8px 0 12px;
}
.visa-guide__manual {
  margin: 0 0 16px;
  padding-left: 20px;
  font-size: 13px;
  color: #334155;
}
.visa-guide__manual li + li {
  margin-top: 4px;
}
.visa-guide__section {
  margin-bottom: 16px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.visa-guide__section-title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}
.visa-guide__fields {
  margin: 0;
}
.visa-guide__row {
  display: grid;
  grid-template-columns: minmax(120px, 38%) 1fr;
  gap: 4px 12px;
  padding: 6px 0;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
}
.visa-guide__row:last-child {
  border-bottom: 0;
}
.visa-guide__row dt {
  margin: 0;
  color: #64748b;
  font-weight: 500;
}
.visa-guide__row dd {
  margin: 0;
  color: #0f172a;
  word-break: break-word;
}
.visa-guide__row.is-missing dd {
  color: #b45309;
}
.visa-guide__todo {
  font-weight: 600;
}
.visa-guide__note {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}
.visa-guide__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.visa-guide__copy,
.visa-guide__official {
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  text-decoration: none;
}
.visa-guide__copy {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #0f172a;
}
.visa-guide__official {
  border: 0;
  background: #0ea5e9;
  color: #fff;
}
</style>
