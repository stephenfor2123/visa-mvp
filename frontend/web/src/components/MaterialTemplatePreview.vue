<!--
  MaterialTemplatePreview.vue — 材料参考样本预览组件

  W55 v4 (2026-07): 财务证明 + 在职证明统一为「Word 风格文字模板」(上下两版)
  - 财务: 4 国银行版(本地语 + 英文) × 4 国 = 8 张
  - 在职证明: 1 套 × 2 版(中文本地 + 英文)
  - 共用同一渲染器: 蓝色标签 + 边框内容区 + 占位符下划线
  - 4 国 UI 语言翻译卡跟随全局 locale
  - 身份证明保持原有「左右双语」模式
-->
<template>
  <div class="mtp" :data-testid="`mtp-${categoryKey}`">
    <!-- 标题栏（可点击折叠） -->
    <div class="mtp-toolbar">
      <button
        type="button"
        class="mtp-header"
        :aria-expanded="expanded"
        :aria-controls="`mtp-body-${categoryKey}`"
        :data-testid="`mtp-toggle-${categoryKey}`"
        @click="toggle"
      >
        <span class="mtp-header__title">
          <span class="mtp-header__primary">{{ t('mtp.preview_title') }}</span>
          <span class="mtp-header__secondary">{{ categoryTitle }}</span>
        </span>
        <span class="mtp-header__chevron" :class="{ 'is-open': expanded }" aria-hidden="true">▾</span>
      </button>
      <button
        v-if="props.categoryKey === 'work'"
        type="button"
        class="mtp-export"
        :disabled="props.exporting"
        data-testid="mtp-export-employment-word"
        @click="$emit('export-word')"
      >
        {{ props.exporting ? t('mtp.exporting_word') : t('mtp.export_word') }}
      </button>
    </div>

    <!-- 折叠体 -->
    <div v-show="expanded" :id="`mtp-body-${categoryKey}`" class="mtp-body">
      <!-- 工作证明: Word 风格文字模板 (在职证明) -->
      <!-- 财务 tab 不再渲染 Word 风格的 Deposit Certificate 存款证明,
           改为在下方直接显示银行流水样本(参考第 2 张图的标准) -->
      <template v-if="props.categoryKey === 'work' && currentTpl?.primary">
        <div class="mtp-lang-col mtp-lang-col--single">
          <!-- 文字模板：跟随 UI 语言的本地语版 + 永远英文对照版 -->
          <div v-if="currentTpl?.primary?.templates" class="mtp-word-templates">
            <!-- 本地语模板 (跟随 UI 语言: zh / vi / id; en UI 时不显示) -->
            <section
              v-if="localTemplate && currentLang !== 'en'"
              class="mtp-word"
              :data-testid="`mtp-word-local-${categoryKey}`"
            >
              <div class="mtp-word__label">{{ localTemplate.label }}</div>
              <div class="mtp-word__doc">
                <p v-if="localTemplate.headerNote" class="mtp-word__header-note">
                  {{ localTemplate.headerNote }}
                </p>
                <h5 class="mtp-word__title">{{ localTemplate.title }}</h5>
                <div class="mtp-word__body">
                  <template v-for="(line, li) in localTemplate.body" :key="`local-${li}`">
                    <p v-if="line === ''" class="mtp-word__spacer">&nbsp;</p>
                    <p v-else v-html="renderPlaceholder(line)" />
                  </template>
                </div>
                <div v-if="localTemplate.signature?.length" class="mtp-word__signature">
                  <p v-for="(s, si) in localTemplate.signature" :key="`local-sig-${si}`">
                    {{ s }}
                  </p>
                </div>
              </div>
            </section>

            <!-- 英文对照版 (永远英文,不变) -->
            <section
              v-if="enTemplate"
              class="mtp-word"
              :data-testid="`mtp-word-en-${categoryKey}`"
            >
              <div class="mtp-word__label">{{ enTemplate.label }}</div>
              <div class="mtp-word__doc">
                <p v-if="enTemplate.headerNote" class="mtp-word__header-note">
                  {{ enTemplate.headerNote }}
                </p>
                <h5 class="mtp-word__title">{{ enTemplate.title }}</h5>
                <div class="mtp-word__body">
                  <template v-for="(line, li) in enTemplate.body" :key="`en-${li}`">
                    <p v-if="line === ''" class="mtp-word__spacer">&nbsp;</p>
                    <p v-else v-html="renderPlaceholder(line)" />
                  </template>
                </div>
                <div v-if="enTemplate.signature?.length" class="mtp-word__signature">
                  <p v-for="(s, si) in enTemplate.signature" :key="`en-sig-${si}`">
                    {{ s }}
                  </p>
                </div>
              </div>
             </section>
          </div>

           <!-- 📌 字段说明表 / 翻译卡 / caption 已移除 — 只保留 Word 风格模板本身 -->

        </div>
      </template>

      <!-- 银行流水样本 (财务 tab 专用) — 上下两版模式 -->
      <template v-if="props.categoryKey === 'financial' && (bankStatement || bankStatementEn)">
        <!-- 上方: zh/vi/id 走本地语版 + 英文对照 mirror; en UI 只显示一版英文样本 -->
        <section
          v-if="bankStatement"
          class="mtp-bank-statement"
          :data-testid="`mtp-bank-statement-local`"
        >
          <!-- W63-c / W63-e: 左上角水贴 label,跟随 UI 语言 (zh/en/vi/id) -->
          <div class="mtp-bank-statement__corner">{{ bankCornerLabel }}</div>
          <h6 class="mtp-bank-statement__title">
            {{ bankStatement.title }}
          </h6>
          <div class="mtp-bank-statement__meta">
            <div v-for="(val, key) in bankStatement.meta" :key="key" class="mtp-bank-statement__meta-row">
              <span class="mtp-bank-statement__meta-label">{{ key }}</span>
              <span class="mtp-bank-statement__meta-value">{{ val }}</span>
            </div>
          </div>
          <div class="mtp-bank-statement__table-wrap">
            <table class="mtp-bank-statement__table">
              <thead>
                <tr>
                  <th v-for="(col, ci) in bankStatement.columns" :key="ci">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="month in 6" :key="`m-${month}`">
                  <tr class="mtp-bank-statement__month-header">
                    <td :colspan="bankStatement.columns.length">
                      {{ t('mtp.month_label', { n: month }) }}
                    </td>
                  </tr>
                  <tr
                    v-for="tx in bankStatement.transactions.filter(t => t.month === month)"
                    :key="`tx-${tx.month}-${tx.date}-${tx.desc}`"
                    :class="['mtp-bank-statement__tx', { 'is-credit': tx.isCredit }]"
                  >
                    <td>{{ tx.date }}</td>
                    <td>{{ tx.desc }}</td>
                    <td>{{ tx.category }}</td>
                    <td class="num">{{ tx.credit }}</td>
                    <td class="num">{{ tx.debit }}</td>
                    <td class="num">{{ tx.balance }}</td>
                  </tr>
                </template>
              </tbody>
              <tfoot>
                <tr class="mtp-bank-statement__summary">
                  <td :colspan="3">{{ bankStatement.summary.label }}</td>
                  <td class="num">{{ bankStatement.summary.credit }}</td>
                  <td class="num">{{ bankStatement.summary.debit }}</td>
                  <td class="num">{{ bankStatement.summary.balance }}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p class="mtp-bank-statement__note">{{ bankStatement.note }}</p>
        </section>

        <!-- 下方: 永远英文对照版 -->
        <section
          v-if="bankStatementEn"
          class="mtp-bank-statement"
          :data-testid="`mtp-bank-statement-en`"
        >
          <!-- W63-c / W63-e + W67: 左上角水贴 label
                - 跟随 UI 语言 (zh/vi/id → 各自本地语 label,en UI → 英文)
                - 下方英文对照 mirror 是英文内容,label 走固定英文 (无视 UI 语言),
                  避免 zh 用户看到 "中文银行流水" 配全英文表头的视觉冲突。
           -->
          <div class="mtp-bank-statement__corner">{{ bankCornerLabelEn }}</div>
          <h6 class="mtp-bank-statement__title">
            {{ bankStatementEn.title }}
          </h6>
          <div class="mtp-bank-statement__meta">
            <div v-for="(val, key) in bankStatementEn.meta" :key="key" class="mtp-bank-statement__meta-row">
              <span class="mtp-bank-statement__meta-label">{{ key }}</span>
              <span class="mtp-bank-statement__meta-value">{{ val }}</span>
            </div>
          </div>
          <div class="mtp-bank-statement__table-wrap">
            <table class="mtp-bank-statement__table">
              <thead>
                <tr>
                  <th v-for="(col, ci) in bankStatementEn.columns" :key="ci">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="month in 6" :key="`m-en-${month}`">
                  <tr class="mtp-bank-statement__month-header">
                    <td :colspan="bankStatementEn.columns.length">Month {{ month }}</td>
                  </tr>
                  <tr
                    v-for="tx in bankStatementEn.transactions.filter(t => t.month === month)"
                    :key="`tx-en-${tx.month}-${tx.date}-${tx.desc}`"
                    :class="['mtp-bank-statement__tx', { 'is-credit': tx.isCredit }]"
                  >
                    <td>{{ tx.date }}</td>
                    <td>{{ tx.desc }}</td>
                    <td>{{ tx.category }}</td>
                    <td class="num">{{ tx.credit }}</td>
                    <td class="num">{{ tx.debit }}</td>
                    <td class="num">{{ tx.balance }}</td>
                  </tr>
                </template>
              </tbody>
              <tfoot>
                <tr class="mtp-bank-statement__summary">
                  <td :colspan="3">{{ bankStatementEn.summary.label }}</td>
                  <td class="num">{{ bankStatementEn.summary.credit }}</td>
                  <td class="num">{{ bankStatementEn.summary.debit }}</td>
                  <td class="num">{{ bankStatementEn.summary.balance }}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p class="mtp-bank-statement__note">{{ bankStatementEn.note }}</p>
        </section>
      </template>

      <!-- 身份证明: 中英双语对照 (左中文, 右英文)。
           W62 fix: 显式 v-if 限定 identity,避免 work/financial 模式下 currentTpl
           不带 zhCN/enUS 字段时,grid 仍渲染出两个空的 lang-col 占位框(旗子有但内容空)。 -->
      <template v-if="props.categoryKey === 'identity'">
        <div class="mtp-lang-grid">
          <div class="mtp-lang-col">
            <header class="mtp-lang-col__head">
              <span class="mtp-lang-col__flag">🇨🇳</span>
              <h4 class="mtp-lang-col__title">{{ currentTpl?.zhCN?.title }}</h4>
            </header>
            <p class="mtp-lang-col__sub">{{ currentTpl?.zhCN?.subtitle }}</p>

            <div
              v-for="(sample, idx) in currentTpl?.zhCN?.samples"
              :key="`zh-${idx}`"
              class="mtp-sample"
            >
              <h5 class="mtp-sample__name">{{ sample.name }}</h5>
              <div v-if="sample.header" class="mtp-sample__header">{{ sample.header }}</div>

              <table v-if="sample.fields" class="mtp-fields">
                <tbody>
                  <tr v-for="(f, fi) in sample.fields" :key="`zh-f-${fi}`">
                    <th>{{ f.key }}</th>
                    <td v-html="renderPlaceholder(f.value)" />
                  </tr>
                </tbody>
              </table>

              <pre v-if="sample.body" class="mtp-sample__body">{{ sample.body }}</pre>

              <div v-if="sample.footer" class="mtp-sample__footer">{{ sample.footer }}</div>
            </div>

            <ul v-if="currentTpl?.zhCN?.tips?.length" class="mtp-tips">
              <li v-for="(tip, i) in currentTpl?.zhCN?.tips" :key="`zh-tip-${i}`">{{ tip }}</li>
            </ul>
          </div>

          <div class="mtp-lang-col">
            <header class="mtp-lang-col__head">
              <span class="mtp-lang-col__flag">🇺🇸</span>
              <h4 class="mtp-lang-col__title">{{ currentTpl?.enUS?.title }}</h4>
            </header>
            <p class="mtp-lang-col__sub">{{ currentTpl?.enUS?.subtitle }}</p>

            <div
              v-for="(sample, idx) in currentTpl?.enUS?.samples"
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

            <ul v-if="currentTpl?.enUS?.tips?.length" class="mtp-tips">
              <li v-for="(tip, i) in currentTpl?.enUS?.tips" :key="`en-tip-${i}`">{{ tip }}</li>
            </ul>
          </div>
        </div>
       </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { TEMPLATE_BY_CATEGORY, getBankTemplate, getCountryNotes, EMPLOYMENT_WORD_TEMPLATE, BANK_STATEMENT_TEMPLATES } from '@/data/materialTemplates'

const props = defineProps({
  categoryKey: {
    type: String,
    required: true, // 'identity' | 'financial' | 'work'
    validator: (v) => ['identity', 'financial', 'work'].includes(v),
  },
  countryCode: {
    type: String,
    default: '', // 目的国 code
  },
  defaultExpanded: {
    type: Boolean,
    default: true,
  },
  exporting: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['export-word'])

const { t, locale } = useI18n()
const expanded = ref(props.defaultExpanded)

// 财务 tab 不再用 Word 风格存款证明(改用下方银行流水样本);在职证明仍用 Word 风格

const currentTpl = computed(() => {
  if (props.categoryKey === 'work') {
    return { primary: EMPLOYMENT_WORD_TEMPLATE }
  }
  // 财务 tab 不再用 Word 风格存款证明(改用下方银行流水样本)
  if (props.categoryKey === 'financial') {
    return null
  }
  return TEMPLATE_BY_CATEGORY[props.categoryKey]
})
const categoryTitle = computed(() => t(`mtp.cat_${props.categoryKey}`))

const countryNote = computed(() => {
  const raw = (t('app.locale') || '').toLowerCase()
  const langKey =
    raw.startsWith('zh') ? 'zh' :
    raw.startsWith('vi') ? 'vi' :
    raw.startsWith('ja') ? 'ja' :
    raw.startsWith('ko') ? 'ko' :
    raw.startsWith('id') ? 'id' :
    'en'
  return getCountryNotes(props.countryCode, langKey)
})

const countryFlag = computed(() => {
  const cc = props.countryCode
  if (!cc) return '🏳️'
  const schengen = ['FR', 'DE', 'IT', 'ES', 'NL', 'AT', 'CH', 'BE', 'GR', 'PT', 'CZ', 'HU', 'PL', 'SE', 'FI', 'DK', 'NO', 'IS']
  if (schengen.includes(cc)) return '🇪🇺'
  const flag = cc.toUpperCase().replace(/./g, (c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65))
  return flag
})

// 工作证明 banner: 用 ✍️ emoji,不要国家旗帜(因为 1 套模板通用所有目的地)
const primaryFlag = computed(() => (props.categoryKey === 'work' ? '✍️' : countryFlag.value))

const primarySub = computed(() => {
  const p = currentTpl.value?.primary
  if (!p) return ''
  if (props.categoryKey === 'work') return p.bankName || ''
  const parts = [p.bankName, p.currency].filter(Boolean)
  return parts.join(' · ')
})

// 当前 UI 语言短码
const currentLang = computed(() => {
  const raw = (locale.value || '').toLowerCase()
  if (raw.startsWith('zh')) return 'zh'
  if (raw.startsWith('vi')) return 'vi'
  if (raw.startsWith('id')) return 'id'
  if (raw.startsWith('en')) return 'en'
  return 'zh'
})

// W63-e / W67: 流水方框左上角水贴 label — 跟随该模板自己的 locale,
// 不跟随 UI 语言。语义:label 应该描述这个表格的内容语言,不是用户的浏览器语言。
// zh 用户看到的本地语模板左上角写"中文银行流水",不是"Personal Bank Statement"。
// 下方英文对照 mirror (zh/vi/id UI 时存在) 单独走一份英文 label,
// 因为这个表格本身就是英文内容,不能跟 UI 语言走。
const BANK_CORNER_LABEL = {
  zh: '中文银行流水(标准版,可适用各国申请人)',
  en: 'Personal Bank Statement (Standard, all nationalities)',
  vi: 'Sao kê ngân hàng (Bản tiếng Việt, áp dụng mọi quốc tịch)',
  id: 'Mutasi Rekening Bank (Versi Bahasa Indonesia, untuk semua kewarganegaraan)',
}
const bankCornerLabel = computed(() => BANK_CORNER_LABEL[currentLang.value] || BANK_CORNER_LABEL.zh)
// W67: 下方英文对照 mirror 的 label — 写死英文(模板本身语言就是 en,不是 UI 语言)。
const bankCornerLabelEn = 'Personal Bank Statement (English reference, original CNY values retained)'

// 上方一版:跟随 UI 语言的「本地语模板」
//   严格按当前语言取,找不到就 null(不强制兜底,避免 en UI 时被喂中文)
const localTemplate = computed(() => {
  const t = currentTpl.value?.primary?.templates
  if (!t) return null
  return t[currentLang.value] || null
})

// 下方一版:永远英文 (en) 对照版
const enTemplate = computed(() => {
  return currentTpl.value?.primary?.templates?.en || null
})

// 银行流水样本 (财务 tab 额外展示)
// 4 国 × 4 语言,每语言一份样本(币种/金额/标签都按当前 locale 算)
// US/UK/AU 走 SG 银行(现实),schengen 也走 SG
// 双版渲染规则(W49 修订):
//   - en UI: 仅显示一版英文样本(USD)
//   - zh / vi / id UI: 上方本地语版 + 下方"英文对照 mirror"
//     mirror 不是独立数据,而是把上方模板的 desc / category / 字段名
//     翻译成英文,但**币种代码 + 数字保持一致**(跟上方完全相同)。
//     这样用户看到 zh 「人民币 45,000 / 月」时,英文对照版也是
//     「CNY 45,000 / month」,避免混淆。
function _getBankStatementBlock() {
  if (props.categoryKey !== 'financial') return null
  const cc = (props.countryCode || '').toUpperCase()
  if (!cc) return null
  const schengen = ['FR', 'DE', 'IT', 'ES', 'NL', 'AT', 'CH', 'BE', 'GR', 'PT', 'CZ', 'HU', 'PL', 'SE', 'FI', 'DK', 'NO', 'IS']
  let bankKey = cc
  if (schengen.includes(cc) || ['US', 'UK', 'AU'].includes(cc)) bankKey = 'SG'
  return BANK_STATEMENT_TEMPLATES[bankKey]?.bankStatement || null
}

// 上方一版: 跟随 UI 语言 (zh/vi/id); en UI 时也走 en 模板
const bankStatement = computed(() => {
  const block = _getBankStatementBlock()
  if (!block) return null
  return block[currentLang.value] || block.en || null
})

// 下方一版 (W49 改为 mirror): 当且仅当 currentLang 不是 'en' 时,
// 把上方 bankStatement 的字段名/desc/category 翻译成英文,但**数字和
// 币种代码完全保留上方模板的值**。这样双语对照表上的货币单位是同一套。
const bankStatementEn = computed(() => {
  const block = _getBankStatementBlock()
  if (!block) return null
  if (currentLang.value === 'en') return null  // en UI 不显示镜像
  const src = block[currentLang.value]
  const enBlock = block.en
  if (!src || !enBlock) return null

  // W48 fix: 数字保留 src 的(按上方 locale 算),只翻译 desc/category/title/meta
  // 通过 month+date 配对匹配 src.transactions[i] ↔ enBlock.transactions[i]
  // (同一 bankKey 下 4 套模板的 TXN_SCHEDULE 完全一致,所以顺序一致,可直接按索引匹配)
  const enTx = enBlock.transactions || []
  const mirroredTx = src.transactions.map((tx, i) => {
    const match = enTx[i] || {}
    return {
      ...tx,  // 保留 month / date / isCredit / credit / debit / balance
      desc: match.desc || tx.desc,
      category: match.category || tx.category,
    }
  })

  // meta: 用 en 的 key (Name / Account No. / Currency / Period / Print Date / Page),
  // value 从 src.meta 按位置镜像(同名不同语言对应的字段)。
  // 由于 4 套模板 meta 都是 7 个 key 一一对应(姓名/账号/身份证/币种/期间/打印日期/页码),
  // 我们按 src.meta 的 value 顺序取出来,塞进 enBlock.meta 的 key 顺序里。
  // 例外: Page 字段(src 是 "1 / 2" / "1 dari 2")保留 enBlock 的本地格式("1 of 2"),
  //       这样英文对照版的 Page 显示还是英文样式。
  const srcValues = Object.values(src.meta)  // ['XXX', 'XXX', 'XXX', '人民币 (CNY)', '...', '...', '1 / 2']
  const enEntries = Object.entries(enBlock.meta)
  const mirroredMeta = {}
  enEntries.forEach(([k, defaultVal], i) => {
    // "Page" 字段保留 enBlock 的本地格式
    if (k === 'Page') {
      mirroredMeta[k] = defaultVal
    } else {
      mirroredMeta[k] = srcValues[i] !== undefined ? srcValues[i] : defaultVal
    }
  })

  return {
    title: enBlock.title,
    subtitle: enBlock.subtitle,
    meta: mirroredMeta,
    columns: enBlock.columns,
    transactions: mirroredTx,
    summary: {
      ...enBlock.summary,
      credit: src.summary.credit,
      debit: src.summary.debit,
      balance: src.summary.balance,
    },
    note: enBlock.note,
  }
})

// 按 destination country 算币种展示名 (US → USD, Schengen → EUR, GB → GBP, AU → AUD, …)
// UI 模式(中/英/越/印)都覆盖,这样 en UI 看 US 银行流水不会显示 CNY,
// 中文 UI 看 US 银行流水也不会显示"人民币 (CNY)"。i18n key 模板里写死的币种字串全部失效。
const currencyLabelForCountry = computed(() => {
  const cc = (props.countryCode || '').toUpperCase()
  if (!cc) return 'CNY'
  const map = {
    US: 'USD',
    GB: 'GBP',
    AU: 'AUD',
    CA: 'CAD',
    JP: 'JPY',
    KR: 'KRW',
    SG: 'SGD',
    // Schengen 共用 EUR
    FR: 'EUR', DE: 'EUR', IT: 'EUR', ES: 'EUR', NL: 'EUR', AT: 'EUR',
    BE: 'EUR', GR: 'EUR', PT: 'EUR', CH: 'EUR', LU: 'EUR', FI: 'EUR',
    // 申根 4 国 26 国兜底:
    CZ: 'EUR', HU: 'EUR', PL: 'EUR', SE: 'EUR', DK: 'EUR', NO: 'EUR',
    IS: 'EUR',
    // 东南亚
    VN: 'VND', ID: 'IDR', TH: 'THB', MY: 'MYR', PH: 'PHP',
    CN: 'CNY', TW: 'TWD', HK: 'HKD',
  }
  return map[cc] || 'CNY'
})
// 4 国语言下,银行流水币种字段的 label (例: zh → "美元 (USD)", en → "USD")
function _i18nCurrencyLabel(code) {
  const map = {
    'zh-CN': { USD: '美元 (USD)', EUR: '欧元 (EUR)', GBP: '英镑 (GBP)', AUD: '澳元 (AUD)', CNY: '人民币 (CNY)' },
    'en':    { USD: 'USD', EUR: 'EUR', GBP: 'GBP', AUD: 'AUD', CNY: 'CNY' },
    'vi':    { USD: 'Đô la Mỹ (USD)', EUR: 'Euro (EUR)', GBP: 'Bảng Anh (GBP)', AUD: 'Đô la Úc (AUD)', CNY: 'Nhân dân tệ (CNY)' },
    'id':    { USD: 'Dolar AS (USD)', EUR: 'Euro (EUR)', GBP: 'Poundsterling (GBP)', AUD: 'Dolar Australia (AUD)', CNY: 'Yuan (CNY)' },
  }
  return (map[currentLang.value] || map['en'])[code] || code
}

// 银行流水的 meta 字段(姓名/账号/身份证等)按当前语言取值
// Currency 字段单独按 destination country 覆盖,避免 4 套模板里硬写死的 CNY/USD 干扰。
const bankStatementMeta = computed(() => {
  const meta = bankStatement.value?.meta || bankStatementEn.value?.meta || {}
  // 找币种字段(4 国 meta key 不同,统一覆盖)
  const currencyKey = ['Currency', '币种', 'Loại tiền', 'Mata Uang'].find((k) => k in meta)
  if (!currencyKey) return meta
  const cur = currencyLabelForCountry.value
  return { ...meta, [currencyKey]: _i18nCurrencyLabel(cur) }
})

const countryDisplayName = computed(() => {
  const cc = (props.countryCode || '').toUpperCase()
  if (!cc) return ''
  const schengen = ['FR', 'DE', 'IT', 'ES', 'NL', 'AT', 'CH', 'BE', 'GR', 'PT', 'CZ', 'HU', 'PL', 'SE', 'FI', 'DK', 'NO', 'IS']
  if (schengen.includes(cc)) return t('country.schengen', '申根')
  const key = `country.${cc.toLowerCase()}`
  const translated = t(key)
  if (translated && translated !== key) return translated
  return cc
})

function toggle() {
  expanded.value = !expanded.value
}

// 高亮 {{placeholder}} 占位符: 下划线 + 蓝色 mono
function renderPlaceholder(text) {
  if (!text) return ''
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(/\{\{([a-z_]+)\}\}/g, '<u class="mtp-ph">$1</u>')
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

/* 银行流水样本 (财务 tab 额外展示) — W63 重做:
   居中标题 / 保留 1 个外层方框(白底+细灰边,参考在职证明样式) / 内部干净 */
.mtp-bank-statement {
  position: relative;        /* W63-c: 给左上角水贴 label 提供定位上下文 */
  margin-top: 18px;
  padding: 28px 22px 22px;   /* 顶部 padding 留出水贴空间 */
  background: #fff;
  /* W63-b: 参考在职证明 (参考图) 给流水保留 1 个干净的外层方框,
     用户反馈"流水加一个方框就行,不能完全去掉" */
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
}
/* W63-c: 水贴 label(参考在职证明 .mtp-word__label 同款 — 深蓝左上角,圆角右下) */
.mtp-bank-statement__corner {
  position: absolute;
  top: 0;
  left: 0;
  background: #1e40af;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 12px;
  border-bottom-right-radius: 12px;
  letter-spacing: 0.3px;
  z-index: 1;
  line-height: 1.4;
}
/* 标题居中: 改成纵向 flex,主标题 + 英文副标题上下两行 */
.mtp-bank-statement__title {
  display: flex; align-items: center; justify-content: center;
  margin: 0 0 18px;
  font-size: 16px; font-weight: 600; color: #0f172a;
  text-align: center;
  letter-spacing: 0.01em;
}
.mtp-bank-statement__icon { font-size: 18px; }
.mtp-bank-statement__sub {
  font-size: 11px; color: #94a3b8; font-style: italic; font-weight: 400;
}
/* meta 区域: 去掉方框,改成纯白底 + 浅分割线 */
.mtp-bank-statement__meta {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px;
  margin: 0 0 16px;
  font-size: 11.5px;
  padding: 0 0 14px;
  background: transparent;
  border: none;
  border-bottom: 1px solid #f1f5f9;   /* 只保留一条最轻的分割线,把 meta 跟表格分开 */
  border-radius: 0;
}
.mtp-bank-statement__meta-row { display: flex; gap: 6px; }
.mtp-bank-statement__meta-label { color: #64748b; min-width: 70px; }
.mtp-bank-statement__meta-value { color: #0f172a; font-weight: 500; }
.mtp-bank-statement__table-wrap { overflow-x: auto; }
.mtp-bank-statement__table {
  width: 100%; border-collapse: collapse; font-size: 11.5px;
  background: #fff;
}
/* 表头: 浅蓝底,无下边框线(用 padding 撑开) */
.mtp-bank-statement__table th {
  background: #f8fafc;                /* 接近白,跟白底区分但不抢 */
  color: #334155; font-weight: 600;
  padding: 10px 10px;
  border: none;
  border-bottom: 1px solid #e2e8f0;
  text-align: left; white-space: nowrap;
  font-size: 11px;
}
/* 单元格: 无内边框,只用 padding + 底部分割线做行分隔 */
.mtp-bank-statement__table td {
  padding: 8px 10px;
  border: none;
  border-bottom: 1px solid #f1f5f9;  /* 极轻行线,几乎看不到 */
  color: #0f172a;
  vertical-align: middle;
  background: #fff;
}
.mtp-bank-statement__table td.num {
  text-align: right; font-family: "SF Mono", Menlo, monospace; font-size: 10.5px; white-space: nowrap;
}
/* 月份分隔行:无背景,字小,灰字 */
.mtp-bank-statement__month-header td {
  background: #fff;
  font-weight: 600; color: #475569;
  font-size: 11px; padding: 12px 10px 6px;
  border-bottom: none;
  letter-spacing: 0.04em;
}
/* 收入项:统一白底,整行加粗强调 */
.mtp-bank-statement__tx.is-credit td {
  background: #fff;
  color: #0F172A;
  font-weight: 700;
}
.mtp-bank-statement__tx.is-credit td.num { font-weight: 700; }
/* 占位符下划线(模板示例,xxx 那种占位) */
.mtp-bank-statement__meta-value {
  text-decoration: underline dotted; text-underline-offset: 2px;
}
/* 月度汇总行:统一白底,数字加粗强调 */
.mtp-bank-statement__summary td {
  background: #fff;
  font-weight: 700;
  border-top: 1px solid #E2E8F0;
  color: #0F172A;
}
.mtp-bank-statement__summary td.num { font-weight: 700; }
.mtp-bank-statement__note {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px solid #f1f5f9;
  font-size: 10px; color: #94a3b8; line-height: 1.6; white-space: pre-line;
}

.mtp-toolbar {
  display: flex;
  align-items: stretch;
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
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
.mtp-header:hover { background: rgba(255, 255, 255, .22); }
.mtp-export {
  flex: 0 0 auto;
  align-self: center;
  margin: 8px 12px 8px 0;
  padding: 8px 14px;
  border: 1px solid #2563eb;
  border-radius: 8px;
  color: #1d4ed8;
  background: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.mtp-export:hover { color: #fff; background: #2563eb; }
.mtp-export:disabled { opacity: .6; cursor: wait; }
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

.mtp-lang-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 768px) {
  .mtp-lang-grid { grid-template-columns: 1fr; }
  .mtp-toolbar { align-items: stretch; flex-direction: column; }
  .mtp-export { align-self: flex-end; margin: 0 12px 10px; }
}

.mtp-lang-col {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}
.mtp-lang-col--single {
  width: 100%;
  border: 0;
  border-radius: 0;
  padding: 0;
  background: transparent;
}
.mtp-lang-col__head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.mtp-lang-col__flag { font-size: 20px; }
.mtp-lang-col__title {
  margin: 0; font-size: 14px; font-weight: 600; color: #1e293b;
}
.mtp-lang-col__sub { font-size: 12px; color: #64748b; margin: 0 0 10px; }

/* W55 v3: Word 风格文字模板 (类似在职证明样式) */
.mtp-word-templates {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 14px;
}

.mtp-word {
  position: relative;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  background: #fff;
  overflow: hidden;
}

.mtp-word__label {
  position: absolute;
  top: 0;
  left: 0;
  background: #1e40af;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 12px;
  border-bottom-right-radius: 12px;
  letter-spacing: 0.3px;
  z-index: 1;
}

.mtp-word__doc {
  padding: 32px 28px 20px;
  background: #fff;
  min-height: 240px;
}

.mtp-word__header-note {
  text-align: center;
  font-size: 12px;
  color: #64748b;
  margin: 0 0 12px;
}

.mtp-word__title {
  text-align: center;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 18px;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.mtp-word__body p {
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
  margin: 0 0 6px;
  text-indent: 2em;
}

.mtp-word__spacer {
  height: 4px;
}

.mtp-word__signature {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.mtp-word__signature p {
  font-size: 13px;
  color: #334155;
  margin: 0;
  text-indent: 0;
}

.mtp-word__caption {
  font-size: 11px;
  color: #64748b;
  margin: 4px 0 0;
  font-style: italic;
}

/* 占位符下划线 */
:deep(.mtp-ph) {
  color: #1e40af;
  text-decoration: underline;
  text-decoration-style: solid;
  text-underline-offset: 3px;
  text-decoration-thickness: 1.5px;
  font-style: normal;
  padding: 0 2px;
}

/* 样本块 (身份证明/在职证明用) */
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

/* 字段表（身份证明样本块内用，financial/work 已不再展示） */
.mtp-fields {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin-bottom: 12px;
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

/* tips（身份证明样本块内可能用到） */
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
