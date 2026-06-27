// useMaterialsProgress — 管所有材料收集的进度和状态(persist 到 localStorage)
import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'visa.materials.progress'

// 默认 step 列表(Atlys 风格 5 步:Traveler / Sponsor / Docs / Essentials / Checkout)
export const STEPS = [
  { key: 'traveler',  label: 'Traveler',  icon: '👤' },
  { key: 'sponsor',   label: 'Sponsor',   icon: '⭐' },
  { key: 'docs',      label: 'Docs',      icon: '📄' },
  { key: 'essentials',label: 'Essentials',icon: '🛡️' },
  { key: 'checkout',  label: 'Checkout',  icon: '🛒' },
]

// 子 doc 列表 — 每个独立收集+OCR
export const DOC_SLOTS = [
  {
    key: 'photo',
    label: 'Photo',
    description: 'Take a selfie (live)',
    icon: '🤳',
    type: 'selfie',
  },
  {
    key: 'passport',
    label: 'Passport',
    description: 'Front page of your passport',
    icon: '📘',
    type: 'passport',
  },
  {
    key: 'photo2',
    label: 'Visa Photo',
    description: 'White background, 2x2 inch',
    icon: '🖼️',
    type: 'photo',
  },
  {
    key: 'itinerary',
    label: 'Itinerary',
    description: 'Flight reservation / hotel booking',
    icon: '✈️',
    type: 'pdf',
  },
]

const defaultState = () => ({
  steps: {
    traveler:   { completed: true,  data: { name: 'Traveler 1' } },
    sponsor:    { completed: false, data: null },
    docs:       { completed: false, data: null },
    essentials: { completed: false, data: null },
    checkout:   { completed: false, data: null },
  },
  slots: {
    photo:     { collected: false, fileUrl: null, ocrResult: null, error: null },
    passport:  { collected: false, fileUrl: null, ocrResult: null, error: null },
    photo2:    { collected: false, fileUrl: null, ocrResult: null, error: null },
    itinerary: { collected: false, fileUrl: null, ocrResult: null, error: null },
  },
  // 临时扫的 passport 字段,review 提交后写入 slots.passport.ocrResult
  pendingPassportReview: null,
})

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState()
    const parsed = JSON.parse(raw)
    // 合并默认结构(防止老 storage 缺字段)
    const def = defaultState()
    return {
      steps: { ...def.steps, ...(parsed.steps || {}) },
      slots: { ...def.slots, ...(parsed.slots || {}) },
      pendingPassportReview: parsed.pendingPassportReview || null,
    }
  } catch {
    return defaultState()
  }
}

const state = ref(load())
const currentStep = ref('docs')

watch(
  state,
  (v) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)) } catch {}
  },
  { deep: true }
)

// 进度计算
const totalSlots = computed(() => DOC_SLOTS.length)
const collectedCount = computed(
  () => Object.values(state.value.slots).filter((s) => s.collected).length
)
const percent = computed(() => {
  // docs step 完成度 = 收集 slot 数 / 总 slot 数
  // 整体完成度 = docs percent * 0.5 (docs 是主体,其他 step 占 50%)
  const docsPct = (collectedCount.value / totalSlots.value) * 100
  const stepsCount = STEPS.length
  const doneSteps = Object.values(state.value.steps).filter((s) => s.completed).length
  return Math.round(((doneSteps + docsPct / 100) / stepsCount) * 100)
})

// docs step 是否完成(所有 slot 都收集了)
const docsComplete = computed(() => collectedCount.value === totalSlots.value)

function setSlot(key, patch) {
  const cur = state.value.slots[key]
  if (!cur) return
  state.value.slots[key] = { ...cur, ...patch }
  // 自动检查 docs step 完成
  if (state.value.slots[key].collected) {
    const allDone = DOC_SLOTS.every((d) => state.value.slots[d.key].collected)
    state.value.steps.docs.completed = allDone
  }
}

function setStep(key, patch) {
  const cur = state.value.steps[key]
  if (!cur) return
  state.value.steps[key] = { ...cur, ...patch }
}

function setPendingPassportReview(fields, fileUrl) {
  state.value.pendingPassportReview = { fields, fileUrl, ts: Date.now() }
}

function reset() {
  state.value = defaultState()
}

export function useMaterialsProgress() {
  return {
    state,
    currentStep,
    percent,
    totalSlots,
    collectedCount,
    docsComplete,
    setSlot,
    setStep,
    setPendingPassportReview,
    reset,
  }
}
