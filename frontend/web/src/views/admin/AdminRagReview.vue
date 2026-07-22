<!--
  AdminRagReview.vue — W62: RAG 内容审核

  设计:3 tab 整合在 1 个页面上
  - Tab A 待审核 (默认):只看 pending_review,有 inline diff 摘要
  - Tab B 全部:历史 + 状态 + 多维过滤
  - 详情 (右侧 / 或下钻 view):完整 diff + 翻译状态 + 决策区

  用 inline 状态切换 + 右侧 sticky 详情面板的方式,避免来回跳路由。
-->
<template>
  <div class="admin-rag-review" data-testid="admin-rag-review-root">
    <main class="admin-main">
      <header class="admin-main__head">
        <div>
          <h1>签证政策内容</h1>
          <p class="admin-main__sub">{{ t('admin.rag_review.page_subtitle') }}</p>
        </div>
        <div class="admin-rag-review__head-actions">
          <button
            class="btn-secondary"
            :disabled="refreshing"
            data-testid="rag-refresh-btn"
            @click="onRefresh"
          >
            <span v-if="refreshing" class="spinner-inline"></span>
            {{ refreshing ? t('admin.rag_review.refreshing') : t('admin.rag_review.btn_refresh') }}
          </button>
        </div>
      </header>

      <!-- 顶部 KPI 条 -->
      <section class="rag-kpi-row">
        <div class="rag-kpi">
          <div class="rag-kpi__label">{{ t('admin.rag_review.kpi_pending') }}</div>
          <div class="rag-kpi__value" :class="pendingCount > 0 ? 'is-warn' : ''">
            {{ pendingCount }}
          </div>
        </div>
        <div class="rag-kpi">
          <div class="rag-kpi__label">{{ t('admin.rag_review.kpi_synced') }}</div>
          <div class="rag-kpi__value">{{ syncedCount }}</div>
        </div>
        <div class="rag-kpi">
          <div class="rag-kpi__label">{{ t('admin.rag_review.kpi_rejected') }}</div>
          <div class="rag-kpi__value">{{ rejectedCount }}</div>
        </div>
        <div class="rag-kpi">
          <div class="rag-kpi__label">{{ t('admin.rag_review.kpi_translation') }}</div>
          <div class="rag-kpi__value">{{ translationPct }}%</div>
          <div class="rag-kpi__hint">{{ t('admin.rag_review.kpi_translation_hint') }}</div>
        </div>
      </section>

      <!-- Tab 切换 -->
      <nav class="rag-tabs" role="tablist">
        <button
          v-for="tab in TABS"
          :key="tab.value"
          class="rag-tabs__item"
          :class="{ 'is-active': activeTab === tab.value }"
          role="tab"
          :data-testid="`rag-tab-${tab.value}`"
          @click="activeTab = tab.value"
        >
          {{ t(tab.label) }}
          <span v-if="tab.badge != null" class="rag-tabs__count">{{ tab.badge }}</span>
        </button>
      </nav>

      <!-- 状态过滤 chips (Tab B 用) -->
      <section v-if="activeTab === 'all'" class="rag-filter" role="tablist">
        <button
          v-for="f in STATUS_FILTERS"
          :key="f.value || 'all'"
          class="rag-filter__chip"
          :class="{ 'is-active': statusFilter === f.value }"
          :data-testid="`rag-filter-${f.value || 'all'}`"
          @click="statusFilter = f.value"
        >
          {{ t(f.labelKey) }}
          <span v-if="f.count != null" class="rag-filter__count">{{ f.count }}</span>
        </button>
      </section>

      <!-- 加载/错误/空态 -->
      <div v-if="loading" class="admin-panel__placeholder">{{ t('admin.loading') }}</div>
      <div v-else-if="loadError" class="admin-panel__placeholder admin-panel__placeholder--err">
        {{ loadError }}
      </div>
      <div v-else-if="!filteredSources.length" class="admin-panel__placeholder">
        <p>{{ t('admin.rag_review.empty_' + activeTab) }}</p>
      </div>

      <!-- Tab A: 待审核 (inline diff 摘要 + 快捷操作) -->
      <section v-else-if="activeTab === 'pending'" class="rag-list">
        <article
          v-for="src in filteredSources"
          :key="src.id"
          class="rag-card rag-card--pending"
          :data-testid="`rag-source-card-${src.id}`"
        >
          <header class="rag-card__head">
            <div class="rag-card__head-left">
              <span class="rag-card__flag">{{ flagEmoji(src.country_code) }}</span>
              <div>
                <h3 class="rag-card__name">{{ src.name }}</h3>
                <p class="rag-card__meta">
                  <span>{{ t('admin.rag_review.col_country') }}: <b>{{ src.country_code }}</b></span>
                  <span>·</span>
                  <span>{{ t('admin.rag_review.col_type') }}: <code>{{ src.content_type }}</code></span>
                  <span v-if="src.url">·</span>
                  <a v-if="src.url" :href="src.url" target="_blank" rel="noopener" class="rag-card__link">
                    {{ t('admin.rag_review.view_source') }} ↗
                  </a>
                </p>
              </div>
            </div>
            <div class="rag-card__head-right">
              <span class="rag-pill rag-pill--pending">⏳ {{ t('admin.rag_review.status_pending_review') }}</span>
              <p class="rag-card__time">
                {{ t('admin.rag_review.fetched_at') }}: {{ formatTime(src.last_refresh_at) }}
              </p>
            </div>
          </header>

          <!-- inline diff 摘要 -->
          <div v-if="src.pending_snapshots > 0" class="rag-card__diff">
            <div class="rag-card__diff-summary">
              <span class="rag-diff-badge rag-diff-badge--added">
                +{{ src.diff_summary?.added?.length || 0 }} {{ t('admin.rag_review.diff_added') }}
              </span>
              <span class="rag-diff-badge rag-diff-badge--removed">
                -{{ src.diff_summary?.removed?.length || 0 }} {{ t('admin.rag_review.diff_removed') }}
              </span>
              <span class="rag-diff-badge rag-diff-badge--changed">
                ~{{ src.diff_summary?.changed?.length || 0 }} {{ t('admin.rag_review.diff_changed') }}
              </span>
            </div>
            <!-- 翻译覆盖状态 -->
            <div class="rag-card__trans">
              <span
                v-for="(covered, lang) in src.translation_coverage"
                :key="lang"
                class="rag-trans-badge"
                :class="covered ? 'is-ok' : 'is-pending'"
                :title="covered ? t('admin.rag_review.translated') : t('admin.rag_review.untranslated')"
              >
                {{ lang }} {{ covered ? '✅' : '⏳' }}
              </span>
            </div>
          </div>

          <footer class="rag-card__actions">
            <button
              class="btn-primary"
              :data-testid="`rag-review-btn-${src.id}`"
              @click="openDetail(src)"
            >
              {{ t('admin.rag_review.btn_review') }} →
            </button>
            <button
              class="btn-text"
              :data-testid="`rag-quick-approve-${src.id}`"
              @click="quickDecide(src, 'approve')"
            >
              🟢 {{ t('admin.rag_review.btn_quick_approve') }}
            </button>
            <button
              class="btn-text"
              :data-testid="`rag-quick-reject-${src.id}`"
              @click="quickDecide(src, 'reject')"
            >
              🔴 {{ t('admin.rag_review.btn_quick_reject') }}
            </button>
          </footer>
        </article>
      </section>

      <!-- Tab B: 全部 (table view) -->
      <section v-else-if="activeTab === 'all'" class="admin-panel rag-table-panel">
        <table class="admin-table">
          <thead>
            <tr>
              <th>{{ t('admin.rag_review.col_source') }}</th>
              <th>{{ t('admin.rag_review.col_country') }}</th>
              <th>{{ t('admin.rag_review.col_status') }}</th>
              <th>{{ t('admin.rag_review.col_last_refresh') }}</th>
              <th>{{ t('admin.rag_review.col_hash') }}</th>
              <th>{{ t('admin.rag_review.col_translation') }}</th>
              <th>{{ t('admin.rag_review.col_action') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="src in filteredSources"
              :key="src.id"
              :data-testid="`rag-row-${src.id}`"
            >
              <td>
                <div class="rag-table__name">
                  <span class="rag-card__flag rag-card__flag--sm">{{ flagEmoji(src.country_code) }}</span>
                  <span>{{ src.name }}</span>
                </div>
              </td>
              <td><code>{{ src.country_code }}</code></td>
              <td>
                <span class="rag-pill" :class="`rag-pill--${src.review_status}`">
                  {{ t(`admin.rag_review.status_${src.review_status}`) }}
                </span>
              </td>
              <td class="admin-table__muted">{{ formatTime(src.last_refresh_at) }}</td>
              <td class="admin-table__mono">
                <span v-if="src.last_content_hash">{{ src.last_content_hash.slice(0, 8) }}…</span>
                <span v-else>—</span>
              </td>
              <td>
                <span
                  v-for="(covered, lang) in src.translation_coverage"
                  :key="lang"
                  class="rag-trans-badge rag-trans-badge--sm"
                  :class="covered ? 'is-ok' : 'is-pending'"
                >{{ lang }}{{ covered ? '✅' : '⏳' }}</span>
              </td>
              <td>
                <button class="admin-link" :data-testid="`rag-detail-link-${src.id}`" @click="openDetail(src)">
                  {{ t('admin.rag_review.btn_view_detail') }} →
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>

    <!-- 详情面板 (modal 形式) -->
    <Teleport to="body">
      <div v-if="detailSource" class="modal-overlay" @click.self="closeDetail">
        <div class="modal modal--lg" data-testid="rag-detail-modal">
          <div class="modal__head">
            <div>
              <h2 class="modal__title">
                <span class="rag-card__flag">{{ flagEmoji(detailSource.country_code) }}</span>
                {{ detailSource.name }}
              </h2>
              <p class="modal__sub">
                <span class="rag-pill" :class="`rag-pill--${detailSource.review_status}`">
                  {{ t(`admin.rag_review.status_${detailSource.review_status}`) }}
                </span>
                <span class="modal__sub-meta">· {{ detailSource.country_code }} · <code>{{ detailSource.content_type }}</code></span>
                <a v-if="detailSource.url" :href="detailSource.url" target="_blank" rel="noopener" class="admin-link">
                  {{ t('admin.rag_review.view_source') }} ↗
                </a>
              </p>
            </div>
            <button class="modal__close" @click="closeDetail" aria-label="Close">×</button>
          </div>

          <div class="modal__body rag-detail-body" v-if="detailData">
            <!-- 左侧 diff 区 (2/3) -->
            <div class="rag-detail-main">
              <!-- 内容 hash 对比 -->
              <div class="rag-detail__hash">
                <div>
                  <div class="rag-detail__hash-label">{{ t('admin.rag_review.detail_current_hash') }}</div>
                  <code class="rag-detail__hash-value">{{ detailSource.last_content_hash || '—' }}</code>
                </div>
                <div v-if="detailData.pending_snapshot">
                  <div class="rag-detail__hash-label">{{ t('admin.rag_review.detail_pending_hash') }}</div>
                  <code class="rag-detail__hash-value rag-detail__hash-value--new">
                    {{ detailData.pending_snapshot.content_hash }}
                  </code>
                </div>
              </div>

              <!-- diff 块 -->
              <div v-if="detailData.pending_snapshot" class="rag-detail__diff">
                <h3 class="rag-detail__section-title">
                  {{ t('admin.rag_review.detail_section_diff') }}
                </h3>
                <div class="rag-diff-summary">
                  <span class="rag-diff-badge rag-diff-badge--added">
                    +{{ detailData.pending_snapshot.diff?.added?.length || 0 }} {{ t('admin.rag_review.diff_added') }}
                  </span>
                  <span class="rag-diff-badge rag-diff-badge--removed">
                    -{{ detailData.pending_snapshot.diff?.removed?.length || 0 }} {{ t('admin.rag_review.diff_removed') }}
                  </span>
                  <span class="rag-diff-badge rag-diff-badge--changed">
                    ~{{ detailData.pending_snapshot.diff?.changed?.length || 0 }} {{ t('admin.rag_review.diff_changed') }}
                  </span>
                </div>

                <!-- 新增 chunks -->
                <details
                  v-if="detailData.pending_snapshot.diff?.added?.length"
                  class="rag-diff-section"
                  open
                >
                  <summary>
                    🟢 {{ t('admin.rag_review.diff_added') }}
                    ({{ detailData.pending_snapshot.diff.added.length }})
                  </summary>
                  <div
                    v-for="c in detailData.pending_snapshot.diff.added"
                    :key="`a-${c.chunk_index}`"
                    class="rag-diff-row rag-diff-row--added"
                  >
                    <div class="rag-diff-row__label">#{{ c.chunk_index }}</div>
                    <pre class="rag-diff-row__content">{{ c.content }}</pre>
                  </div>
                </details>

                <!-- 删除 chunks -->
                <details
                  v-if="detailData.pending_snapshot.diff?.removed?.length"
                  class="rag-diff-section"
                >
                  <summary>
                    🔴 {{ t('admin.rag_review.diff_removed') }}
                    ({{ detailData.pending_snapshot.diff.removed.length }})
                  </summary>
                  <div
                    v-for="c in detailData.pending_snapshot.diff.removed"
                    :key="`r-${c.chunk_index}`"
                    class="rag-diff-row rag-diff-row--removed"
                  >
                    <div class="rag-diff-row__label">#{{ c.chunk_index }}</div>
                    <pre class="rag-diff-row__content">{{ c.content }}</pre>
                  </div>
                </details>

                <!-- 变更 chunks (左右对比) -->
                <details
                  v-if="detailData.pending_snapshot.diff?.changed?.length"
                  class="rag-diff-section"
                  open
                >
                  <summary>
                    🟠 {{ t('admin.rag_review.diff_changed') }}
                    ({{ detailData.pending_snapshot.diff.changed.length }})
                  </summary>
                  <div
                    v-for="c in detailData.pending_snapshot.diff.changed"
                    :key="`c-${c.chunk_index}`"
                    class="rag-diff-changed"
                  >
                    <div class="rag-diff-changed__head">#{{ c.chunk_index }}</div>
                    <div class="rag-diff-changed__cols">
                      <div class="rag-diff-changed__col rag-diff-changed__col--old">
                        <div class="rag-diff-changed__col-label">{{ t('admin.rag_review.detail_old') }}</div>
                        <pre>{{ c.old }}</pre>
                      </div>
                      <div class="rag-diff-changed__col rag-diff-changed__col--new">
                        <div class="rag-diff-changed__col-label">{{ t('admin.rag_review.detail_new') }}</div>
                        <pre>{{ c.new }}</pre>
                      </div>
                    </div>
                  </div>
                </details>
              </div>

              <!-- 没有 pending snapshot 时,显示当前 chunks -->
              <div v-else class="rag-detail__current">
                <h3 class="rag-detail__section-title">
                  {{ t('admin.rag_review.detail_section_current') }}
                </h3>
                <div
                  v-for="chunk in detailData.chunks"
                  :key="chunk.chunk_id"
                  class="rag-chunk-row"
                >
                  <div class="rag-chunk-row__head">
                    <span class="rag-chunk-row__index">#{{ chunk.chunk_index }}</span>
                    <span class="rag-chunk-row__topic">{{ chunk.topic }}</span>
                    <code class="rag-chunk-row__hash">{{ chunk.content_hash.slice(0, 10) }}…</code>
                  </div>
                  <pre class="rag-chunk-row__content">{{ chunk.content }}</pre>
                </div>
              </div>

              <!-- 翻译状态 -->
              <div class="rag-detail__trans">
                <h3 class="rag-detail__section-title">
                  {{ t('admin.rag_review.detail_section_translation') }}
                </h3>
                <div class="rag-detail__trans-list">
                  <div
                    v-for="s in detailData.translation_stats"
                    :key="s.target_lang"
                    class="rag-detail__trans-row"
                  >
                    <span class="rag-detail__trans-lang">
                      {{ s.target_lang }}
                      <span v-if="s.translated_chunks === s.total_chunks && s.total_chunks > 0" class="rag-detail__trans-icon is-ok">✅</span>
                      <span v-else-if="s.translated_chunks === 0" class="rag-detail__trans-icon is-pending">⏳</span>
                      <span v-else class="rag-detail__trans-icon is-partial">⚠️</span>
                    </span>
                    <span class="rag-detail__trans-count">
                      {{ s.translated_chunks }} / {{ s.total_chunks }} ({{ s.coverage_pct }}%)
                    </span>
                    <span class="rag-detail__trans-time">
                      {{ s.last_translated_at ? formatTime(s.last_translated_at) : '—' }}
                    </span>
                    <button
                      class="btn-text"
                      :data-testid="`rag-retrans-${s.target_lang}`"
                      @click="onRetrans(detailSource.id, s.target_lang)"
                    >
                      {{ t('admin.rag_review.btn_retrans_lang') }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- 测试检索 -->
              <div class="rag-detail__test">
                <h3 class="rag-detail__section-title">
                  {{ t('admin.rag_review.test_query_title') }}
                </h3>
                <div class="rag-detail__test-row">
                  <input
                    v-model="testQuery"
                    class="form-input rag-detail__test-input"
                    :placeholder="t('admin.rag_review.test_query_input_placeholder')"
                    :data-testid="`rag-test-query-input-${detailSource.id}`"
                  />
                  <button
                    class="btn-secondary"
                    :disabled="!testQuery.trim()"
                    :data-testid="`rag-test-query-run-${detailSource.id}`"
                    @click="runTestQuery"
                  >
                    {{ t('admin.rag_review.test_query_run') }}
                  </button>
                </div>
                <div v-if="testResult" class="rag-detail__test-result" data-testid="rag-test-result">
                  <pre>{{ testResult }}</pre>
                </div>
              </div>
            </div>

            <!-- 右侧决策栏 (1/3 sticky) -->
            <aside class="rag-detail-side">
              <div class="rag-detail-side__card">
                <div class="rag-detail-side__title">
                  {{ t('admin.rag_review.detail_section_decision') }}
                </div>
                <p v-if="!detailData.pending_snapshot" class="rag-detail-side__msg">
                  {{ t('admin.rag_review.no_pending') }}
                </p>
                <template v-else>
                  <label class="form-field">
                    <span class="form-label">{{ t('admin.rag_review.note_placeholder') }}</span>
                    <textarea
                      v-model="decisionNote"
                      class="form-input rag-detail-side__note"
                      rows="3"
                      :placeholder="t('admin.rag_review.note_placeholder')"
                      :data-testid="`rag-decision-note-${detailSource.id}`"
                    />
                  </label>
                  <div class="rag-detail-side__actions">
                    <button
                      class="btn-primary rag-detail-side__btn--approve"
                      :disabled="deciding"
                      :data-testid="`rag-detail-approve-${detailSource.id}`"
                      @click="onApprove"
                    >
                      <span v-if="deciding === 'approve'" class="spinner-inline"></span>
                      🟢 {{ t('admin.rag_review.btn_approve') }}
                    </button>
                    <button
                      class="btn-secondary rag-detail-side__btn--reject"
                      :disabled="deciding"
                      :data-testid="`rag-detail-reject-${detailSource.id}`"
                      @click="onReject"
                    >
                      <span v-if="deciding === 'reject'" class="spinner-inline"></span>
                      🔴 {{ t('admin.rag_review.btn_reject') }}
                    </button>
                    <button
                      class="btn-text rag-detail-side__btn--force"
                      :data-testid="`rag-detail-force-${detailSource.id}`"
                      @click="onForce"
                    >
                      ⚪ {{ t('admin.rag_review.btn_force') }}
                    </button>
                  </div>
                </template>
                <p v-if="actionMessage" class="rag-detail-side__msg" :class="actionOk ? 'is-ok' : 'is-err'">
                  {{ actionMessage }}
                </p>
              </div>

              <!-- 历史决策 -->
              <div v-if="detailData.recent_decisions?.length" class="rag-detail-side__card">
                <div class="rag-detail-side__title">
                  {{ t('admin.rag_review.recent_decisions') }}
                </div>
                <ol class="rag-history">
                  <li
                    v-for="d in detailData.recent_decisions"
                    :key="d.snapshot_id"
                    class="rag-history__row"
                  >
                    <span class="rag-pill" :class="`rag-pill--${d.decision}`">
                      {{ t(`admin.rag_review.decision_${d.decision}`) }}
                    </span>
                    <span class="rag-history__note">{{ d.note || '—' }}</span>
                    <span class="rag-history__time">{{ formatTime(d.decided_at) }}</span>
                  </li>
                </ol>
              </div>
            </aside>
          </div>
          <div v-else-if="detailLoading" class="admin-panel__placeholder">
            {{ t('admin.loading') }}
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 强制覆盖二次确认 -->
    <Teleport to="body">
      <div v-if="confirmingForce" class="modal-overlay" @click.self="confirmingForce = null">
        <div class="modal modal--sm">
          <div class="modal__head">
            <h2>{{ t('admin.rag_review.confirm_force_title') }}</h2>
          </div>
          <div class="modal__body">
            <p>{{ t('admin.rag_review.confirm_force_desc') }}</p>
          </div>
          <div class="modal__foot">
            <button class="btn-secondary" @click="confirmingForce = null">
              {{ t('admin.rag_review.confirm_force_cancel') }}
            </button>
            <button
              class="btn-primary"
              :data-testid="`rag-force-confirm`"
              @click="onForceConfirm"
            >
              {{ t('admin.rag_review.confirm_force_btn') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  approveAdminRagSnapshot,
  getAdminRagSource,
  getAdminRagTranslationStats,
  listAdminRagSources,
  rejectAdminRagSnapshot,
  retransAdminRagSource,
  triggerAdminRagRefresh,
  triggerAdminRagRefreshForce,
} from '@/api/admin'

const { t, locale } = useI18n()

const TABS = [
  { value: 'pending', label: 'admin.rag_review.tab_pending' },
  { value: 'all',     label: 'admin.rag_review.tab_all' },
]

const STATUS_FILTERS = [
  { value: '',           labelKey: 'admin.rag_review.filter_all' },
  { value: 'synced',           labelKey: 'admin.rag_review.filter_synced' },
  { value: 'pending_review',   labelKey: 'admin.rag_review.filter_pending' },
  { value: 'approved',         labelKey: 'admin.rag_review.filter_approved' },
  { value: 'rejected',         labelKey: 'admin.rag_review.filter_rejected' },
  { value: 'force_applied',    labelKey: 'admin.rag_review.filter_force' },
]

const sources = ref([])
const loading = ref(false)
const loadError = ref('')
const refreshing = ref(false)
const activeTab = ref('pending')
const statusFilter = ref('')

// detail modal
const detailSource = ref(null)
const detailData = ref(null)
const detailLoading = ref(false)
const decisionNote = ref('')
const deciding = ref('')  // '' | 'approve' | 'reject'
const actionMessage = ref('')
const actionOk = ref(true)

// force confirm
const confirmingForce = ref(null)  // source obj or null

// test query
const testQuery = ref('')
const testResult = ref('')

// translation stats
const translationStats = ref(null)

// ----- derived -----
const pendingCount = computed(() => sources.value.filter((s) => s.review_status === 'pending_review').length)
const syncedCount = computed(() => sources.value.filter((s) => s.review_status === 'synced').length)
const rejectedCount = computed(() => sources.value.filter((s) => s.review_status === 'rejected').length)
const translationPct = computed(() => {
  const v = translationStats.value
  if (!v) return '—'
  return v.overall_coverage_pct
})

// 计数
const STATUS_FILTERS_WITH_COUNT = computed(() => STATUS_FILTERS.map((f) => ({
  ...f,
  count: f.value
    ? sources.value.filter((s) => s.review_status === f.value).length
    : sources.value.length,
})))

// Tabs with badge — pending 数量要 refresh 后实时更新
const TABS_WITH_BADGE = computed(() => TABS.map((tab) => ({
  ...tab,
  badge: tab.value === 'pending' ? pendingCount.value : null,
})))

const filteredSources = computed(() => {
  let list = sources.value
  if (activeTab.value === 'pending') {
    list = list.filter((s) => s.review_status === 'pending_review')
  }
  if (statusFilter.value) {
    list = list.filter((s) => s.review_status === statusFilter.value)
  }
  return list
})

// ----- loaders -----
async function loadSources() {
  loading.value = true
  loadError.value = ''
  try {
    sources.value = await listAdminRagSources()
  } catch (err) {
    loadError.value = err?.message || String(err)
    sources.value = []
  } finally {
    loading.value = false
  }
}

async function loadTranslationStats() {
  try {
    translationStats.value = await getAdminRagTranslationStats()
  } catch {
    /* dashboard 上 KPI 不影响主流程 */
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await triggerAdminRagRefresh()
    await Promise.all([loadSources(), loadTranslationStats()])
  } catch (err) {
    loadError.value = err?.message || String(err)
  } finally {
    refreshing.value = false
  }
}

// ----- detail modal -----
async function openDetail(src) {
  detailSource.value = src
  detailData.value = null
  decisionNote.value = ''
  actionMessage.value = ''
  testQuery.value = ''
  testResult.value = ''
  detailLoading.value = true
  try {
    detailData.value = await getAdminRagSource(src.id)
  } catch (err) {
    actionMessage.value = err?.message || String(err)
    actionOk.value = false
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailSource.value = null
  detailData.value = null
}

async function onApprove() {
  if (!detailData.value?.pending_snapshot) return
  deciding.value = 'approve'
  actionMessage.value = ''
  try {
    await approveAdminRagSnapshot(detailData.value.pending_snapshot.id, {
      note: decisionNote.value || undefined,
    })
    actionOk.value = true
    actionMessage.value = t('admin.rag_review.approve_success')
    await loadSources()
    closeDetail()
  } catch (err) {
    actionOk.value = false
    actionMessage.value = err?.message || String(err)
  } finally {
    deciding.value = ''
  }
}

async function onReject() {
  if (!detailData.value?.pending_snapshot) return
  deciding.value = 'reject'
  actionMessage.value = ''
  try {
    await rejectAdminRagSnapshot(detailData.value.pending_snapshot.id, {
      note: decisionNote.value || undefined,
    })
    actionOk.value = true
    actionMessage.value = t('admin.rag_review.reject_success')
    await loadSources()
    closeDetail()
  } catch (err) {
    actionOk.value = false
    actionMessage.value = err?.message || String(err)
  } finally {
    deciding.value = ''
  }
}

async function quickDecide(src, decision) {
  // 列表页上的"快速通过/拒绝" — 没有 diff 详情也能点(用 src 上 inline 的 diff)
  // mock 模式下 src 没有 pending_snapshot 字段,需要 fetch detail 拿 snapshot_id
  // 这里通过 list 接口直接走 approve — 后端会找 source 最新 pending snapshot
  const note = prompt(t('admin.rag_review.note_placeholder'), '') || undefined
  try {
    if (decision === 'approve') {
      // 没有 snapshot_id,需要先 fetch detail
      const det = await getAdminRagSource(src.id)
      if (det?.pending_snapshot) {
        await approveAdminRagSnapshot(det.pending_snapshot.id, { note })
      } else {
        actionMessage.value = t('admin.rag_review.no_pending')
        return
      }
    } else {
      const det = await getAdminRagSource(src.id)
      if (det?.pending_snapshot) {
        await rejectAdminRagSnapshot(det.pending_snapshot.id, { note })
      }
    }
    await loadSources()
  } catch (err) {
    actionMessage.value = err?.message || String(err)
  }
}

function onForce(src) {
  confirmingForce.value = src || detailSource.value
}

async function onForceConfirm() {
  const src = confirmingForce.value
  if (!src) return
  try {
    await triggerAdminRagRefreshForce({ country_code: src.country_code })
    await loadSources()
    if (detailSource.value?.id === src.id) closeDetail()
  } catch (err) {
    actionMessage.value = err?.message || String(err)
  } finally {
    confirmingForce.value = null
  }
}

async function onRetrans(sourceId, lang) {
  if (!confirm(t('admin.rag_review.confirm_retrans', { lang }))) return
  try {
    await retransAdminRagSource(sourceId)
    if (detailSource.value?.id === sourceId) {
      const det = await getAdminRagSource(sourceId)
      detailData.value = det
    }
  } catch (err) {
    actionMessage.value = err?.message || String(err)
  }
}

function runTestQuery() {
  // 简化为"按 query 走 fetchUrl 后 mock 一下":实际后端是 /v2/rag/query
  // 这里只 mock 一个 answer 字符串 (不调真实 LLM)
  testResult.value = `[mock] ${t('admin.rag_review.test_query_run')}: "${testQuery}" → 已找到 3 个相关 chunks, 顶层 chunk 来源: ${detailSource.value?.name}`
}

// ----- helpers -----
function flagEmoji(code) {
  if (!code) return '🌐'
  return code
    .toUpperCase()
    .split('')
    .map((c) => String.fromCodePoint(127397 + c.charCodeAt(0)))
    .join('')
}

function formatTime(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

// watch locale — 切换语言时, 重新拉翻译覆盖数据 (跟 C 端 Apply.vue 同模式)
watch(locale, () => {
  loadSources()
  loadTranslationStats()
})

onMounted(async () => {
  await Promise.all([loadSources(), loadTranslationStats()])
})
</script>

<style scoped lang="scss">
.admin-rag-review { min-width: 0; }

.admin-main__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.admin-main__head h1 {
  font-size: 22px;
  font-weight: 700;
  color: #0F172A;
  margin: 0 0 4px;
}
.admin-main__sub { font-size: 13px; color: #64748B; margin: 0; }
.admin-rag-review__head-actions { display: flex; gap: 8px; }

/* ----- KPI ----- */
.rag-kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.rag-kpi {
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 12px 16px;
}
.rag-kpi__label {
  font-size: 11px;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: .04em;
  font-weight: 600;
}
.rag-kpi__value {
  font-size: 24px;
  font-weight: 700;
  color: #0F172A;
  margin-top: 4px;
  line-height: 1.1;
}
.rag-kpi__value.is-warn { color: #B45309; }
.rag-kpi__hint { font-size: 11px; color: #94A3B8; margin-top: 2px; }

/* ----- Tabs ----- */
.rag-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #E2E8F0;
  margin-bottom: 16px;
}
.rag-tabs__item {
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.rag-tabs__item:hover { color: #0F172A; }
.rag-tabs__item.is-active {
  color: #3B6EF5;
  border-bottom-color: #3B6EF5;
}
.rag-tabs__count {
  background: #FEE2E2;
  color: #B91C1C;
  font-size: 11px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 10px;
}
.rag-tabs__item:not(.is-active) .rag-tabs__count { background: #F1F5F9; color: #475569; }

/* ----- filter chips ----- */
.rag-filter { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.rag-filter__chip {
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.rag-filter__chip:hover { border-color: #94A3B8; color: #0F172A; }
.rag-filter__chip.is-active { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }
.rag-filter__count {
  font-size: 10px;
  font-weight: 700;
  background: rgba(255,255,255,.25);
  padding: 1px 5px;
  border-radius: 8px;
}
.rag-filter__chip:not(.is-active) .rag-filter__count { background: #F1F5F9; color: #64748B; }

/* ----- list cards ----- */
.rag-list { display: flex; flex-direction: column; gap: 14px; }
.rag-card {
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 16px 18px;
  transition: border-color .15s, box-shadow .15s;
}
.rag-card:hover {
  border-color: #CBD5E1;
  box-shadow: 0 2px 8px rgba(15, 23, 42, .04);
}
.rag-card--pending { border-left: 3px solid #F59E0B; }
.rag-card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.rag-card__head-left { display: flex; gap: 10px; min-width: 0; }
.rag-card__head-right { text-align: right; flex-shrink: 0; }
.rag-card__flag { font-size: 20px; line-height: 1; }
.rag-card__flag--sm { font-size: 14px; }
.rag-card__name { margin: 0; font-size: 14px; font-weight: 700; color: #0F172A; }
.rag-card__meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748B;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.rag-card__link { color: #3B6EF5; text-decoration: none; font-weight: 600; }
.rag-card__link:hover { text-decoration: underline; }
.rag-card__time { margin: 4px 0 0; font-size: 11px; color: #94A3B8; }

/* diff summary badges */
.rag-card__diff {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 12px;
  background: #F8FAFC;
  border-radius: 8px;
  margin-bottom: 10px;
}
.rag-card__diff-summary { display: flex; gap: 6px; flex-wrap: wrap; }
.rag-card__trans { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }

.rag-diff-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.rag-diff-badge--added   { background: #D1FAE5; color: #047857; }
.rag-diff-badge--removed { background: #FEE2E2; color: #B91C1C; }
.rag-diff-badge--changed { background: #FEF3C7; color: #B45309; }

.rag-trans-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: #F1F5F9;
  color: #64748B;
}
.rag-trans-badge.is-ok { background: #D1FAE5; color: #047857; }
.rag-trans-badge.is-pending { background: #FEF3C7; color: #B45309; }
.rag-trans-badge--sm { font-size: 10px; padding: 1px 6px; }

.rag-card__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

/* ----- table view ----- */
.rag-table-panel { padding: 0; }
.rag-table__name {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* ----- shared status pills ----- */
.rag-pill {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .03em;
  background: #F1F5F9;
  color: #475569;
}
.rag-pill--synced          { background: #E0E7FF; color: #4338CA; }
.rag-pill--pending         { background: #FEF3C7; color: #B45309; }
.rag-pill--pending_review  { background: #FEF3C7; color: #B45309; }
.rag-pill--approved        { background: #D1FAE5; color: #047857; }
.rag-pill--rejected        { background: #FEE2E2; color: #B91C1C; }
.rag-pill--force_applied   { background: #FCE7F3; color: #9D174D; }

/* ----- detail modal ----- */
.modal--lg { max-width: 1100px; width: 100%; }
.rag-detail-body {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 18px;
  min-height: 480px;
}
.rag-detail-main { min-width: 0; }
.rag-detail-side { display: flex; flex-direction: column; gap: 14px; }
.rag-detail__hash {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
}
.rag-detail__hash-label {
  font-size: 10px;
  color: #64748B;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
  margin-bottom: 4px;
}
.rag-detail__hash-value {
  font-size: 11px;
  font-family: 'SF Mono', Menlo, monospace;
  color: #475569;
  word-break: break-all;
}
.rag-detail__hash-value--new { color: #047857; font-weight: 600; }

.rag-detail__section-title {
  font-size: 13px;
  font-weight: 700;
  color: #0F172A;
  margin: 18px 0 8px;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.rag-detail__section-title:first-child { margin-top: 0; }

.rag-detail__diff .rag-diff-summary { margin-bottom: 10px; }

.rag-diff-section {
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  margin-bottom: 8px;
  background: #fff;
}
.rag-diff-section > summary {
  cursor: pointer;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #0F172A;
  list-style: none;
  user-select: none;
}
.rag-diff-section > summary::-webkit-details-marker { display: none; }
.rag-diff-section > summary::before {
  content: '▸';
  display: inline-block;
  margin-right: 6px;
  transition: transform .15s;
  color: #94A3B8;
}
.rag-diff-section[open] > summary::before { transform: rotate(90deg); }
.rag-diff-section > *:not(summary) { padding: 0 12px 10px; }

.rag-diff-row {
  padding: 8px 0;
  border-top: 1px solid #F1F5F9;
}
.rag-diff-row:first-child { border-top: 0; }
.rag-diff-row__label {
  font-size: 11px;
  color: #94A3B8;
  font-weight: 700;
  margin-bottom: 4px;
}
.rag-diff-row__content {
  font-size: 12px;
  line-height: 1.6;
  color: #0F172A;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: inherit;
}
.rag-diff-row--added .rag-diff-row__label { color: #047857; }
.rag-diff-row--removed { opacity: .75; }
.rag-diff-row--removed .rag-diff-row__label { color: #B91C1C; }
.rag-diff-row--removed .rag-diff-row__content {
  text-decoration: line-through;
  color: #94A3B8;
}

.rag-diff-changed {
  padding: 10px 0;
  border-top: 1px solid #F1F5F9;
}
.rag-diff-changed:first-child { border-top: 0; }
.rag-diff-changed__head {
  font-size: 11px;
  color: #B45309;
  font-weight: 700;
  margin-bottom: 6px;
}
.rag-diff-changed__cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.rag-diff-changed__col {
  border-radius: 6px;
  padding: 8px 10px;
  border: 1px solid;
}
.rag-diff-changed__col--old {
  background: #FEF2F2;
  border-color: #FECACA;
}
.rag-diff-changed__col--new {
  background: #ECFDF5;
  border-color: #A7F3D0;
}
.rag-diff-changed__col-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
  margin-bottom: 4px;
}
.rag-diff-changed__col--old .rag-diff-changed__col-label { color: #B91C1C; }
.rag-diff-changed__col--new .rag-diff-changed__col-label { color: #047857; }
.rag-diff-changed__col pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #0F172A;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.rag-chunk-row {
  padding: 8px 0;
  border-top: 1px solid #F1F5F9;
}
.rag-chunk-row:first-child { border-top: 0; }
.rag-chunk-row__head {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 11px;
  color: #94A3B8;
  margin-bottom: 4px;
}
.rag-chunk-row__index { font-weight: 700; color: #475569; }
.rag-chunk-row__topic {
  background: #EEF2FF;
  color: #4338CA;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.rag-chunk-row__hash { font-family: 'SF Mono', Menlo, monospace; }
.rag-chunk-row__content {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #0F172A;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

/* translation list */
.rag-detail__trans-list {
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  background: #fff;
  padding: 4px 0;
}
.rag-detail__trans-row {
  display: grid;
  grid-template-columns: 100px 1fr 140px 100px;
  gap: 12px;
  padding: 8px 14px;
  align-items: center;
  border-top: 1px solid #F1F5F9;
  font-size: 12px;
}
.rag-detail__trans-row:first-child { border-top: 0; }
.rag-detail__trans-lang { font-weight: 600; color: #0F172A; display: flex; align-items: center; gap: 4px; }
.rag-detail__trans-icon.is-ok { color: #047857; }
.rag-detail__trans-icon.is-pending { color: #B45309; }
.rag-detail__trans-icon.is-partial { color: #B45309; }
.rag-detail__trans-count { color: #475569; font-variant-numeric: tabular-nums; }
.rag-detail__trans-time { color: #94A3B8; font-size: 11px; }

/* test query */
.rag-detail__test-row { display: flex; gap: 8px; }
.rag-detail__test-input { flex: 1; }
.rag-detail__test-result {
  margin-top: 8px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ----- side decision card ----- */
.rag-detail-side__card {
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 14px;
}
.rag-detail-side__title {
  font-size: 12px;
  font-weight: 700;
  color: #0F172A;
  text-transform: uppercase;
  letter-spacing: .04em;
  margin-bottom: 10px;
}
.rag-detail-side__note { resize: vertical; min-height: 64px; }
.rag-detail-side__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.rag-detail-side__btn--approve { background: #047857; border-color: #047857; }
.rag-detail-side__btn--approve:hover { background: #065F46; border-color: #065F46; }
.rag-detail-side__btn--reject { background: #B91C1C; border-color: #B91C1C; color: #fff; }
.rag-detail-side__btn--reject:hover { background: #991B1B; border-color: #991B1B; }
.rag-detail-side__btn--force { color: #9D174D; }
.rag-detail-side__msg {
  font-size: 12px;
  margin: 8px 0 0;
  color: #475569;
}
.rag-detail-side__msg.is-ok { color: #047857; }
.rag-detail-side__msg.is-err { color: #B91C1C; }

.rag-history {
  list-style: none;
  margin: 0;
  padding: 0;
}
.rag-history__row {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  border-top: 1px solid #F1F5F9;
  font-size: 11px;
  align-items: center;
  flex-wrap: wrap;
}
.rag-history__row:first-child { border-top: 0; }
.rag-history__note { color: #475569; flex: 1; min-width: 0; }
.rag-history__time { color: #94A3B8; white-space: nowrap; }

/* ----- shared ----- */
.btn-primary, .btn-secondary, .btn-text {
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s;
}
.btn-primary {
  background: #3B6EF5;
  color: #fff;
  border: 1px solid #3B6EF5;
  padding: 8px 16px;
}
.btn-primary:hover { background: #2E5BD8; border-color: #2E5BD8; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-secondary {
  background: #fff;
  color: #0F172A;
  border: 1px solid #E2E8F0;
  padding: 8px 16px;
}
.btn-secondary:hover { border-color: #3B6EF5; color: #3B6EF5; }
.btn-secondary:disabled { opacity: .6; cursor: not-allowed; }
.btn-text {
  background: transparent;
  border: 0;
  color: #3B6EF5;
  padding: 6px 10px;
}
.btn-text:hover { text-decoration: underline; }

.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.admin-table th {
  text-align: left;
  font-weight: 600;
  color: #475569;
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
  padding: 10px 12px;
  border-bottom: 1px solid #E2E8F0;
  background: #F8FAFC;
}
.admin-table td {
  padding: 12px;
  border-bottom: 1px solid #F1F5F9;
  color: #0F172A;
  vertical-align: middle;
}
.admin-table tr:hover td { background: #F8FAFC; }
.admin-table__mono { font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: #475569; }
.admin-table__muted { color: #94A3B8; font-size: 12px; }
.admin-link { color: #3B6EF5; text-decoration: none; font-weight: 600; }
.admin-link:hover { text-decoration: underline; }

.admin-panel__placeholder {
  padding: 32px 0;
  text-align: center;
  color: #94A3B8;
  font-size: 13px;
}
.admin-panel__placeholder--err { color: #DC2626; }

.form-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  font-family: inherit;
  background: #fff;
}
.form-input:focus {
  outline: none;
  border-color: #3B6EF5;
  box-shadow: 0 0 0 3px rgba(59,110,245,.12);
}
.form-label { display: block; font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 4px; }
.form-field { display: block; margin-bottom: 10px; }

.spinner-inline {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  vertical-align: middle;
  margin-right: 4px;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 960px) {
  .rag-detail-body { grid-template-columns: 1fr; }
  .rag-detail-side { order: -1; }
}
</style>
