<template>
  <div class="documents-page">
    <AppHeader scope="profile" />

    <main class="app-container app-page documents-page__main">
      <nav class="documents-page__crumb">
        <router-link to="/profile">{{ t('profile.page_title') }}</router-link>
        <span class="documents-page__crumb-sep">›</span>
        <span>{{ t('documents.page_title') }}</span>
      </nav>

      <h1 class="documents-page__title">{{ t('documents.page_title') }}</h1>
      <p class="documents-page__sub">{{ t('documents.page_subtitle') }}</p>
      <p class="documents-page__privacy">{{ t('documents.local_only_hint') }}</p>

      <!-- 上传动作区 -->
      <AppCard class="documents-page__action">
        <div class="documents-page__actions-grid">
          <button
            type="button"
            class="documents-page__action-btn documents-page__action-btn--primary"
            data-testid="documents-open-qr"
            @click="qrOpen = true"
          >
            <span class="documents-page__action-ico">📱</span>
            <div>
              <p class="documents-page__action-t">{{ t('documents.action_phone_t') }}</p>
              <p class="documents-page__action-d">{{ t('documents.action_phone_d') }}</p>
            </div>
          </button>
          <label class="documents-page__action-btn">
            <span class="documents-page__action-ico">⬆️</span>
            <div>
              <p class="documents-page__action-t">{{ t('documents.action_pc_t') }}</p>
              <p class="documents-page__action-d">{{ t('documents.action_pc_d') }}</p>
            </div>
            <input
              ref="pcInputEl"
              type="file"
              accept="image/jpeg,image/png,image/webp,application/pdf"
              multiple
              class="documents-page__hidden-input"
              data-testid="documents-pc-input"
              @change="onPcPick"
            />
          </label>
        </div>
      </AppCard>

      <!-- 列表 -->
      <AppCard v-if="materials.length">
        <template #header>
          <div class="documents-page__list-head">
            <h3 class="documents-page__list-title">
              {{ t('documents.list_title') }} · {{ materials.length }}
            </h3>
            <select
              v-model="filterType"
              class="documents-page__filter"
              :aria-label="t('documents.filter_label')"
            >
              <option value="">{{ t('documents.filter_all') }}</option>
              <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </template>
        <ul class="documents-page__grid">
          <li
            v-for="m in filteredMaterials"
            :key="m.localId || m.material_id || m.id"
            class="documents-page__item"
          >
            <a
              v-if="m.thumbnail_url || m.download_url"
              :href="m.download_url || m.thumbnail_url"
              target="_blank"
              rel="noopener"
              class="documents-page__thumb-link"
            >
              <img
                v-if="m.thumbnail_url && m.thumbnail_url.startsWith('data:')"
                :src="m.thumbnail_url"
                :alt="m.file_name"
                class="documents-page__thumb"
              />
              <div v-else-if="m.thumbnail_url" class="documents-page__thumb documents-page__thumb--meta">
                {{ typeLabel(m.material_type) }}
              </div>
              <div v-else class="documents-page__thumb documents-page__thumb--pdf">PDF</div>
            </a>
            <div class="documents-page__meta">
              <p class="documents-page__fname">{{ m.file_name }}</p>
              <p class="documents-page__meta-sub">
                {{ typeLabel(m.material_type) }} · {{ humanSize(m.file_size) }}
              </p>
            </div>
          </li>
        </ul>
      </AppCard>

      <AppCard v-else>
        <div class="documents-page__empty">
          <p class="documents-page__empty-t">{{ t('documents.empty_t') }}</p>
          <p class="documents-page__empty-d">{{ t('documents.empty_d') }}</p>
        </div>
      </AppCard>
    </main>

    <QrUploadModal v-model:open="qrOpen" @received="onQrReceived" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import AppCard from '@/components/AppCard.vue'
import QrUploadModal from '@/components/QrUploadModal.vue'
import {
  getMaterialTypeOptions,
  processMaterial,
} from '@/api/materials'
import {
  addLocalDocument,
  fileToDataUrl,
  listLocalDocuments,
} from '@/utils/localPrivacyStorage'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()

const qrOpen = ref(false)
const materials = ref([])
const filterType = ref('')
const pcInputEl = ref(null)
const uploading = ref(false)

const typeOptions = computed(() =>
  getMaterialTypeOptions().map((o) => ({
    value: o.value,
    label: o.label.startsWith('materials.') ? o.value : o.label,
  }))
)

function typeLabel(slug) {
  if (!slug) return ''
  const o = typeOptions.value.find((x) => x.value === slug)
  return o ? o.label : slug
}

function humanSize(n) {
  if (!n) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

const filteredMaterials = computed(() => {
  if (!filterType.value) return materials.value
  return materials.value.filter((m) => m.material_type === filterType.value)
})

function loadMaterials() {
  materials.value = listLocalDocuments()
}

async function onPcPick(ev) {
  const files = ev.target.files
  if (!files || !files.length) return
  uploading.value = true
  let ok = 0
  let fail = 0
  for (const file of Array.from(files)) {
    try {
      await processMaterial(file, 'other', {
        onProgress: () => {},
      })
      const thumbUrl = file.type.startsWith('image/') ? await fileToDataUrl(file) : ''
      addLocalDocument({
        localId: `doc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        file_name: file.name,
        file_size: file.size,
        material_type: 'other',
        thumbUrl,
        fileUrl: thumbUrl,
      })
      ok++
    } catch (e) {
      fail++
    }
  }
  uploading.value = false
  ev.target.value = ''
  if (ok > 0) {
    toast.success(t('toast.upload_success', { n: ok }))
    loadMaterials()
  }
  if (fail > 0) toast.error(t('toast.upload_failed', { n: fail }))
}

function onQrReceived(item) {
  const entry = addLocalDocument({
    localId: item.material_id || `transfer_${Date.now()}`,
    file_name: item.file_name || 'file',
    material_type: item.material_type || 'other',
    ocr_result: item.ocr_result || {},
    ephemeral: true,
  })
  materials.value = [entry, ...materials.value]
}

onMounted(loadMaterials)
</script>

<style scoped lang="scss">
.documents-page__main {
  padding-top: 32px;
  padding-bottom: 64px;
  max-width: 880px;
}
.documents-page__crumb {
  font-size: 13px;
  color: #64748B;
  margin-bottom: 12px;
}
.documents-page__crumb a {
  color: #2563EB;
  text-decoration: none;
}
.documents-page__crumb-sep {
  margin: 0 6px;
  color: #CBD5E1;
}
.documents-page__title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0F172A;
}
.documents-page__sub {
  margin: 6px 0 8px;
  color: #64748B;
  font-size: 14px;
}
.documents-page__privacy {
  margin: 0 0 20px;
  padding: 10px 12px;
  background: #F0F9FF;
  border: 1px solid #BAE6FD;
  border-radius: 8px;
  font-size: 13px;
  color: #0369A1;
  line-height: 1.5;
}
.documents-page__action {
  margin-bottom: 16px;
}
.documents-page__actions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.documents-page__action-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #E2E8F0;
  background: #fff;
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
}
.documents-page__action-btn--primary {
  border-color: #BFDBFE;
  background: #EFF6FF;
}
.documents-page__action-ico { font-size: 22px; }
.documents-page__action-t {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
}
.documents-page__action-d {
  margin: 4px 0 0;
  font-size: 12px;
  color: #475569;
}
.documents-page__hidden-input { display: none; }
@media (max-width: 600px) {
  .documents-page__actions-grid { grid-template-columns: 1fr; }
}
.documents-page__list-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.documents-page__list-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.documents-page__filter {
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid #E2E8F0;
  font-size: 13px;
}
.documents-page__grid {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.documents-page__item {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.documents-page__thumb-link {
  display: block;
  aspect-ratio: 1 / 1;
  background: #F1F5F9;
}
.documents-page__thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.documents-page__thumb--pdf,
.documents-page__thumb--meta {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748B;
  font-weight: 700;
  font-size: 14px;
  text-align: center;
  padding: 8px;
}
.documents-page__meta {
  padding: 8px 10px;
}
.documents-page__fname {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: #0F172A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.documents-page__meta-sub {
  margin: 2px 0 0;
  font-size: 11px;
  color: #94A3B8;
}
.documents-page__empty-t {
  margin: 0;
  font-size: 14px;
  color: #1F2937;
  font-weight: 500;
}
.documents-page__empty-d {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748B;
}
</style>
