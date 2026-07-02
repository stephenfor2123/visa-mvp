<!--
  MaterialTemplatePreview.vue — 材料参考样本预览组件

  用法：在 MaterialWizard 的 3 个相关大类（identity / financial / work）展示。
  - 标题栏：分类名 + 折叠/展开按钮
  - 默认展开：让用户一进来就看到中英文对照样本
  - 中英双语并列：左右两栏，方便对照
  - 占位符 {{...}} 用 mono 字体高亮
  - 底部：各国差异说明（按目的国显示）
  - i18n：跟随全局 locale
-->
<template>
  <div class="mtp" :data-testid="`mtp-${categoryKey}`">
    <!-- 标题栏（可点击折叠） -->
    <button
      type="button"
      class="mtp-header"
      :aria-expanded="expanded"
      :aria-controls="`mtp-body-${categoryKey}`"
      :data-testid="`mtp-toggle-${categoryKey}`"
      @click="toggle"
    >
      <span class="mtp-header__icon" aria-hidden="true">📄</span>
      <span class="mtp-header__title">
        <span class="mtp-header__primary">{{ t('mtp.preview_title') }}</span>
        <span class="mtp-header__secondary">{{ categoryTitle }}</span>
      </span>
      <span class="mtp-header__chevron" :class="{ 'is-open': expanded }" aria-hidden="true">▾</span>
    </button>

    <!-- 折叠体 -->
    <div v-show="expanded" :id="`mtp-body-${categoryKey}`" class="mtp-body">
      <!-- 中英双语对照：左中文，右英文 -->
      <div class="mtp-lang-grid">
        <div class="mtp-lang-col">
          <header class="mtp-lang-col__head">
            <span class="mtp-lang-col__flag">🇨🇳</span>
            <h4 class="mtp-lang-col__title">{{ template.zhCN.title }}</h4>
          </header>
          <p class="mtp-lang-col__sub">{{ template.zhCN.subtitle }}</p>

          <div
            v-for="(sample, idx) in template.zhCN.samples"
            :key="`zh-${idx}`"
            class="mtp-sample"
          >
            <h5 class="mtp-sample__name">{{ sample.name }}</h5>
            <div v-if="sample.header" class="mtp-sample__header">{{ sample.header }}</div>

            <!-- fields list（适用于身份证明这种字段表形式） -->
            <table v-if="sample.fields" class="mtp-fields">
              <tbody>
                <tr v-for="(f, fi) in sample.fields" :key="`zh-f-${fi}`">
                  <th>{{ f.key }}</th>
                  <td v-html="renderPlaceholder(f.value)" />
                </tr>
              </tbody>
            </table>

            <!-- body text（适用于在职证明这种叙述形式） -->
            <pre v-if="sample.body" class="mtp-sample__body">{{ sample.body }}</pre>

            <div v-if="sample.footer" class="mtp-sample__footer">{{ sample.footer }}</div>
          </div>

          <!-- tips -->
          <ul v-if="template.zhCN.tips?.length" class="mtp-tips">
            <li v-for="(tip, i) in template.zhCN.tips" :key="`zh-tip-${i}`">{{ tip }}</li>
          </ul>
        </div>

        <div class="mtp-lang-col">
          <header class="mtp-lang-col__head">
            <span class="mtp-lang-col__flag">🇺🇸</span>
            <h4 class="mtp-lang-col__title">{{ template.enUS.title }}</h4>
          </header>
          <p class="mtp-lang-col__sub">{{ template.enUS.subtitle }}</p>

          <div
            v-for="(sample, idx) in template.enUS.samples"
            :key="`en-${idx}`"
            class="mtp-sample"
          >
            <h5 class="mtp-sample__name">{{ sample.name }}</h5>
            <div v-if="sample.header" class="mtp-sample__header">{{ sample.header }}</div>

            <table v-if="sample.fields" class="mtp-fields">
              <tbody>
                <tr v-for="(f, fi) in sample.fields" :key="`en-f-${fi}`">
                  <th>{{ f.key }}</th>
                  <td v-html="renderPlaceholder(f.value)" />
                </tr>
              </tbody>
            </table>

            <pre v-if="sample.body" class="mtp-sample__body">{{ sample.body }}</pre>

            <div v-if="sample.footer" class="mtp-sample__footer">{{ sample.footer }}</div>
          </div>

          <ul v-if="template.enUS.tips?.length" class="mtp-tips">
            <li v-for="(tip, i) in template.enUS.tips" :key="`en-tip-${i}`">{{ tip }}</li>
          </ul>
        </div>
      </div>

      <!-- 各国差异说明（按目的国显示） -->
      <div v-if="countryNote" class="mtp-country">
        <header class="mtp-country__head">
          <span class="mtp-country__flag">{{ countryNote.flag }}</span>
          <h4 class="mtp-country__title">{{ t('mtp.country_notes_title') }} · {{ countryNote.name }}</h4>
        </header>
        <ul class="mtp-country__list">
          <li v-for="(n, i) in countryNote.notes" :key="`cn-${i}`">{{ n }}</li>
        </ul>
      </div>

      <!-- 重要提示 -->
      <div class="mtp-warning">
        <span class="mtp-warning__icon" aria-hidden="true">⚠️</span>
        <span>{{ t('mtp.warning_disclaimer') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { TEMPLATE_BY_CATEGORY, COUNTRY_NOTES } from '@/data/materialTemplates'

const props = defineProps({
  categoryKey: {
    type: String,
    required: true, // 'identity' | 'financial' | 'work'
    validator: (v) => ['identity', 'financial', 'work'].includes(v),
  },
  countryCode: {
    type: String,
    default: '', // 目的国 code，例如 'US' / 'UK' / 'AU' / 'Schengen'
  },
  defaultExpanded: {
    type: Boolean,
    default: true,
  },
})

const { t } = useI18n()
const expanded = ref(props.defaultExpanded)

// 当前类目的多语言模板
const template = computed(() => TEMPLATE_BY_CATEGORY[props.categoryKey])
const categoryTitle = computed(() => t(`mtp.cat_${props.categoryKey}`))

// 当前目的国的差异说明（如果没有匹配就 null，不显示该模块）
const countryNote = computed(() => {
  const cc = props.countryCode
  if (!cc) return null
  // 申根国家映射
  const schengen = ['FR', 'DE', 'IT', 'ES', 'NL', 'AT', 'CH', 'BE', 'GR', 'PT', 'CZ', 'HU']
  if (schengen.includes(cc)) return COUNTRY_NOTES.Schengen
  return COUNTRY_NOTES[cc] || null
})

function toggle() {
  expanded.value = !expanded.value
}

// 高亮 {{placeholder}} 占位符为 mono 字体 + 蓝色背景
function renderPlaceholder(text) {
  if (!text) return ''
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/\{\{([a-z_]+)\}\}/g, '<code class="mtp-ph">$1</code>')
}
</script>

<style scoped>
.mtp {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  margin-top: 12px;
  overflow: hidden;
}

.mtp-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: none;
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
  cursor: pointer;
  text-align: left;
  transition: background 0.18s ease;
}
.mtp-header:hover { background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%); }
.mtp-header__icon { font-size: 18px; flex-shrink: 0; }
.mtp-header__title { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.mtp-header__primary {
  font-size: 13px; font-weight: 600; color: #4338ca; line-height: 1.2;
}
.mtp-header__secondary { font-size: 12px; color: #64748b; line-height: 1.2; }
.mtp-header__chevron {
  font-size: 16px; color: #4338ca; transition: transform 0.2s ease;
}
.mtp-header__chevron.is-open { transform: rotate(180deg); }

.mtp-body { padding: 16px; background: #fff; }

/* 双语对照：左中文，右英文 */
.mtp-lang-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 768px) {
  .mtp-lang-grid { grid-template-columns: 1fr; }
}

.mtp-lang-col {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}
.mtp-lang-col__head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.mtp-lang-col__flag { font-size: 20px; }
.mtp-lang-col__title {
  margin: 0; font-size: 14px; font-weight: 600; color: #1e293b;
}
.mtp-lang-col__sub { font-size: 12px; color: #64748b; margin: 0 0 10px; }

/* 样本块 */
.mtp-sample {
  margin-bottom: 14px;
  padding: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}
.mtp-sample:last-child { margin-bottom: 0; }
.mtp-sample__name {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.mtp-sample__header {
  font-size: 13px;
  font-weight: 700;
  text-align: center;
  color: #1e40af;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #cbd5e1;
}
.mtp-sample__body {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 11.5px;
  line-height: 1.6;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  background: transparent;
  border: none;
  padding: 0;
}
.mtp-sample__footer {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #cbd5e1;
  font-size: 11.5px;
  color: #64748b;
  text-align: right;
}

/* 字段表（身份证/户口本这种） */
.mtp-fields {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.mtp-fields th {
  text-align: left;
  padding: 4px 8px;
  width: 36%;
  color: #64748b;
  font-weight: 500;
  vertical-align: top;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}
.mtp-fields td {
  padding: 4px 8px;
  color: #1e293b;
  vertical-align: top;
  border-bottom: 1px solid #e2e8f0;
}

/* 占位符高亮 */
:deep(.mtp-ph) {
  display: inline-block;
  padding: 1px 5px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 10.5px;
  background: #dbeafe;
  color: #1e40af;
  border-radius: 3px;
  border: 1px dashed #93c5fd;
}

/* tips */
.mtp-tips {
  margin: 8px 0 0;
  padding: 8px 10px 8px 26px;
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  border-radius: 4px;
  font-size: 11.5px;
  color: #78350f;
  line-height: 1.6;
}
.mtp-tips li { margin-bottom: 4px; }
.mtp-tips li:last-child { margin-bottom: 0; }

/* 各国差异说明 */
.mtp-country {
  margin-top: 14px;
  padding: 12px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border: 1px solid #bae6fd;
  border-radius: 8px;
}
.mtp-country__head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.mtp-country__flag { font-size: 18px; }
.mtp-country__title {
  margin: 0; font-size: 13px; font-weight: 600; color: #0c4a6e;
}
.mtp-country__list {
  margin: 0; padding: 0 0 0 18px; font-size: 12px; color: #0c4a6e; line-height: 1.6;
}
.mtp-country__list li { margin-bottom: 4px; }

/* 免责声明 */
.mtp-warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 10px;
  background: #fef2f2;
  border-radius: 6px;
  font-size: 11px;
  color: #7f1d1d;
  line-height: 1.5;
}
.mtp-warning__icon { flex-shrink: 0; }
</style>