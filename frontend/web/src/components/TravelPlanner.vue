<template>
  <div class="tp">
    <!-- 去程 -->
    <section class="tp-block">
      <h3 class="tp-block__title">
        <span class="tp-block__icon">🛫</span> {{ t('wizard.travel_outbound_title') }}
      </h3>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_origin_label') }}</span>
          <input v-model="plan.origin" list="tp-origin-cities" :placeholder="t('wizard.travel_origin_ph')" class="tp-input" data-testid="tp-origin" />
          <datalist id="tp-origin-cities">
            <option v-for="c in ORIGIN_CITIES" :key="c" :value="c" />
          </datalist>
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_destination_label') }}</span>
          <input v-model="plan.destination" :placeholder="destinationName" class="tp-input" data-testid="tp-destination" />
        </label>
      </div>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_depart_label') }}</span>
          <input v-model="plan.departDate" type="date" class="tp-input" data-testid="tp-depart-date" />
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_flight_out_label') }}</span>
          <input v-model="plan.flightOutNo" :placeholder="t('wizard.travel_flight_out_ph')" class="tp-input" data-testid="tp-flight-out" />
        </label>
      </div>
    </section>

    <!-- 返程：出发/到达地独立可编辑（开口程——回程不一定飞回同一个城市） -->
    <section class="tp-block">
      <h3 class="tp-block__title">
        <span class="tp-block__icon">🛬</span> {{ t('wizard.travel_return_title') }}
      </h3>
      <p class="tp-block__hint">{{ t('wizard.travel_return_openjaw_hint') }}</p>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_return_origin_label') }}</span>
          <input v-model="plan.returnOrigin" :placeholder="plan.destination || destinationName" class="tp-input" data-testid="tp-return-origin" />
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_return_destination_label') }}</span>
          <input v-model="plan.returnDestination" :placeholder="plan.origin" class="tp-input" data-testid="tp-return-destination" />
        </label>
      </div>
      <div class="tp-row">
        <label class="tp-field">
          <span>{{ t('wizard.travel_return_label') }}</span>
          <input v-model="plan.returnDate" type="date" class="tp-input" data-testid="tp-return-date" />
        </label>
        <label class="tp-field">
          <span>{{ t('wizard.travel_flight_back_label') }}</span>
          <input v-model="plan.flightBackNo" :placeholder="t('wizard.travel_flight_out_ph')" class="tp-input" data-testid="tp-flight-back" />
        </label>
      </div>
    </section>

    <!-- 行程单：日期一定就直接显示，逐格可编辑；"一键生成" 只补空白格 -->
    <section class="tp-block" v-if="plan.days.length">
      <h3 class="tp-block__title"><span class="tp-block__icon">📅</span> {{ t('wizard.travel_days_title', { n: plan.days.length }) }}</h3>
      <p class="tp-block__hint">{{ t('wizard.travel_days_hint') }}</p>

      <div class="tp-preview" data-testid="tp-itinerary-preview">
        <table class="tp-table">
          <thead>
            <tr>
              <th>{{ t('wizard.itinerary_col_day') }}<template v-if="!isEnglishLocale"><br />Day</template></th>
              <th>{{ t('wizard.itinerary_col_date') }}<template v-if="!isEnglishLocale"><br />Date</template></th>
              <th>{{ t('wizard.itinerary_col_city') }}<template v-if="!isEnglishLocale"><br />City</template></th>
              <th>{{ t('wizard.itinerary_col_transport') }}<template v-if="!isEnglishLocale"><br />Transport</template></th>
              <th>{{ t('wizard.itinerary_col_attraction') }}<template v-if="!isEnglishLocale"><br />Itinerary</template></th>
              <th>{{ t('wizard.itinerary_col_hotel') }}<template v-if="!isEnglishLocale"><br />Hotel</template></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(d, i) in plan.days" :key="d.date" :data-testid="`tp-day-${i}`">
              <td class="tp-td-day">Day {{ d.day }}</td>
              <td class="tp-td-date">{{ formatDate(d.date) }}</td>
              <td>
                <span v-if="d.transport === 'flight'" class="tp-city-from">{{ dayCityDisplayFn(i).split('→')[0] }}→</span>
                <input v-model="d.city" :placeholder="t('wizard.travel_day_city_ph')" class="tp-input tp-cell-input" :data-testid="`tp-day-city-${i}`" />
              </td>
              <td>
                <select
                  v-model="d.transport"
                  class="tp-input tp-cell-input"
                  :class="{ 'is-ai-filled': d._auto?.transport }"
                  :data-testid="`tp-day-transport-${i}`"
                  @change="onManualEdit(d, 'transport')"
                >
                  <option value="">{{ t('wizard.travel_transport_ph') }}</option>
                  <option value="flight">{{ t('wizard.transport_flight') }}</option>
                  <option value="train">{{ t('wizard.transport_train') }}</option>
                  <option value="car">{{ t('wizard.transport_car') }}</option>
                  <option value="bus">{{ t('wizard.transport_bus') }}</option>
                  <option value="walk">{{ t('wizard.transport_walk') }}</option>
                  <option value="other">{{ t('wizard.transport_other') }}</option>
                </select>
              </td>
              <td>
                <input
                  v-model="d.attraction"
                  :placeholder="t('wizard.travel_day_attraction_ph')"
                  class="tp-input tp-cell-input tp-cell-input--wide"
                  :class="{ 'is-ai-filled': d._auto?.attraction }"
                  :data-testid="`tp-day-attraction-${i}`"
                  @input="onManualEdit(d, 'attraction')"
                />
              </td>
              <td>
                <input
                  v-model="d.hotel"
                  :placeholder="t('wizard.travel_day_hotel_ph')"
                  class="tp-input tp-cell-input"
                  :class="{ 'is-ai-filled': d._auto?.hotel }"
                  :data-testid="`tp-day-hotel-${i}`"
                  @input="onManualEdit(d, 'hotel')"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="genIssues.length" class="tp-gen-issues" data-testid="tp-gen-issues">
        <div v-for="(iss, i) in genIssues" :key="i" class="tp-gen-issue">{{ iss.title }}<template v-if="iss.detail"> — {{ iss.detail }}</template></div>
      </div>
      <div v-if="genError" class="tp-gen-error" data-testid="tp-gen-error">{{ genError }}</div>

      <div class="tp-generate">
        <div v-if="generating" class="tp-progress" data-testid="tp-progress">
          <div class="tp-progress__bar"><div class="tp-progress__fill" :style="{ width: progress + '%' }" /></div>
          <div class="tp-progress__text">{{ t('wizard.travel_generating') }} {{ progress }}%</div>
        </div>
        <button v-else type="button" class="tp-generate__btn" data-testid="tp-generate" @click="onGenerate">
          ✨ {{ t('wizard.travel_mode_auto') }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()

// W45 fix: when the active locale is English, the second header row
// ("Day"/"Date"/…) would render the English word twice. Detect the
// English locale (BCP-47 "en" or "en-US") and hide the duplicated line.
const isEnglishLocale = computed(() => /^en(-|$)/i.test(locale.value || 'en'))

const props = defineProps({
  plan: { type: Object, required: true },
  destinationName: { type: String, default: '' },
  onGenerateItinerary: { type: Function, required: true }, // async () => text
  onCompileItineraryText: { type: Function, required: true }, // () => void, 逐格编辑后重新编译
  onRebuildDays: { type: Function, required: true }, // () => void, 日期变化时重建 days
  onValidateForGenerate: { type: Function, required: true }, // () => issues[]
  dayCityDisplayFn: { type: Function, required: true }, // (index) => string
  onMarkDayFieldManual: { type: Function, required: true }, // (day, field) => void
  onSyncDestinationToDays: { type: Function, required: true }, // (oldDest, newDest) => void
})

const ORIGIN_CITIES = ['北京', '上海', '广州', '深圳', '成都', '杭州', '武汉', '西安']

const generating = ref(false)
const genError = ref('')
const genIssues = ref([])
const progress = ref(0)
let progressTimer = null

// 出发/返回日期一变就重建逐日行程（保留已有城市/交通/住宿/景点，按日期对齐）
watch(() => [props.plan.departDate, props.plan.returnDate], () => {
  props.onRebuildDays()
}, { immediate: true })

// W41：不再有单独的"逐日行程"输入区——表格本身就是可编辑区，任何一格改了都
// 直接重新编译 itineraryText（给 OrderNew.vue / 提交用的文本版）。
watch(() => props.plan.days, () => {
  props.onCompileItineraryText()
}, { deep: true })

watch(() => props.destinationName, (name) => {
  if (name && !props.plan.destination) props.plan.destination = name
}, { immediate: true })

// 顶部"目的地"文字改了 -> 跟旧目的地文字一样的"每天城市"格子跟着批量改
// （单城市行程的常见情况；多城市行程里跟旧目的地文字不一样的格子不受影响）
watch(() => props.plan.destination, (newVal, oldVal) => {
  props.onSyncDestinationToDays(oldVal, newVal)
})

// 用户在某个格子里手动改了内容 -> 标记成"手填"，以后"一键生成"不会再碰它
// （否则会一直卡在上一次 AI 生成的内容，改了目的地/航班信息后也刷新不了）
function onManualEdit(day, field) {
  props.onMarkDayFieldManual(day, field)
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return dateStr
  try {
    return new Intl.DateTimeFormat(locale.value, { year: 'numeric', month: 'short', day: 'numeric' }).format(d)
  } catch {
    return dateStr
  }
}

function startProgress() {
  progress.value = 0
  clearInterval(progressTimer)
  // 没有真实进度事件（单次 LLM 调用），用一个越来越慢的假进度条：
  // 快速冲到 70%，然后慢慢逼近 90%，剩下的留给请求真正完成时跳到 100%。
  progressTimer = setInterval(() => {
    if (progress.value < 70) progress.value += 6
    else if (progress.value < 90) progress.value += 1
  }, 300)
}
function stopProgress(success) {
  clearInterval(progressTimer)
  progressTimer = null
  if (success) progress.value = 100
}
onBeforeUnmount(() => clearInterval(progressTimer))

async function onGenerate() {
  genError.value = ''
  const issues = props.onValidateForGenerate()
  genIssues.value = issues
  if (issues.length) return
  generating.value = true
  startProgress()
  try {
    await props.onGenerateItinerary()
    stopProgress(true)
  } catch (e) {
    stopProgress(false)
    genError.value = e?.message || t('wizard.err_upload_failed')
  } finally {
    setTimeout(() => { generating.value = false }, 300)
  }
}
</script>

<style scoped lang="scss">
.tp { display: flex; flex-direction: column; gap: 24px; }
.tp-block {
  border: 1px solid #eef1f6; border-radius: 16px; padding: 18px 20px; background: #fff;
}
.tp-block__title {
  font-size: 15px; font-weight: 700; color: #0f172a; margin: 0 0 4px;
  display: flex; align-items: center; gap: 8px;
}
.tp-block__hint { font-size: 12.5px; color: #64748b; margin: 0 0 12px; }
.tp-block__icon { font-size: 16px; }

.tp-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.tp-field { display: flex; flex-direction: column; gap: 5px; font-size: 12.5px; color: #475569; font-weight: 600; }
.tp-input {
  border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 9px 12px; font-size: 13.5px;
  color: #0f172a; font-weight: 400; font-family: inherit;
  &:focus { outline: none; border-color: #3b6ef5; }
}

.tp-preview { overflow-x: auto; }
.tp-table {
  width: 100%; border-collapse: collapse; font-size: 12.5px; color: #0f172a; background: #fff;
  th, td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; vertical-align: middle; }
  th { font-weight: 700; background: #f1f5f9; line-height: 1.4; white-space: nowrap; }
}
.tp-td-day, .tp-td-date { white-space: nowrap; font-weight: 600; color: #475569; }
.tp-cell-input { padding: 6px 8px; font-size: 12.5px; min-width: 90px; border-color: #e9edf5; }
.tp-cell-input--wide { min-width: 180px; }
// AI 填的格子给个淡紫底色提示"这是生成的，可以再点一次一键生成刷新，或者直接手改"
.tp-cell-input.is-ai-filled { background: #f5f3ff; border-color: #ddd6fe; }
.tp-city-from { font-size: 11px; color: #94a3b8; font-weight: 600; margin-right: 3px; white-space: nowrap; }

.tp-gen-issues { margin-top: 12px; }
.tp-gen-issue {
  font-size: 12.5px; color: #b91c1c; background: #fef2f2; border-radius: 8px;
  padding: 8px 12px; margin-bottom: 6px;
}
.tp-gen-error {
  margin-top: 12px; font-size: 12.5px; color: #b91c1c; background: #fef2f2;
  border-radius: 8px; padding: 8px 12px;
}

.tp-generate { display: flex; flex-direction: column; align-items: center; margin-top: 14px; gap: 10px; }
.tp-generate__btn {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border: 0;
  padding: 12px 28px; border-radius: 999px; font-size: 14px; font-weight: 700; cursor: pointer;
  box-shadow: 0 8px 20px rgba(15,23,42,.18);
  &:hover:not(:disabled) { transform: translateY(-1px); }
}
.tp-progress { width: 100%; max-width: 360px; }
.tp-progress__bar { height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.tp-progress__fill {
  height: 100%; background: linear-gradient(90deg, #3B6EF5, #6E59F0);
  transition: width .3s ease;
}
.tp-progress__text { text-align: center; font-size: 12px; color: #64748b; margin-top: 6px; font-weight: 600; }
</style>
