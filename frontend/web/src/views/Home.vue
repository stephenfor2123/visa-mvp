<template>
  <div class="home-page">
    <AppHeader scope="home" />
    <main class="app-container app-page">
      <!-- Hero: 旅行图轮播背景 + slogan 永远在前景 -->
      <!-- W29: 用户不能手动切换,纯自动轮播 -->
      <section class="hero hero--slideshow">
        <!-- 10 张真实运动视频(轮船开/海浪动/云动/极光流动) — atlys 风格 -->
        <div class="hero__slides" aria-hidden="true">
          <div
            v-for="(s, i) in slides"
            :key="i"
            class="hero__slide"
            :class="{ 'is-active': i === activeIdx }"
          >
            <!-- video 优先,失败 fallback 到同名 jpg;再失败显示深色兜底 -->
            <video
              v-if="s.image && /\.(mp4|webm)$/i.test(s.image) && !failedHero.has(i)"
              :src="s.image"
              :alt="`${t(s.captionKey)} · ${t(s.cityKey)}`"
              class="hero__slide-video"
              autoplay
              loop
              muted
              playsinline
              preload="auto"
              @error="onHeroImgError(i)"
            />
            <img
              v-else-if="(failedHero.has(i) && s.fallback) || (s.image && !/\.(mp4|webm)$/i.test(s.image))"
              :src="failedHero.has(i) ? s.fallback : s.image"
              :alt="`${t(s.captionKey)} · ${t(s.cityKey)}`"
              class="hero__slide-video hero__slide-img"
              loading="eager"
              @error="onHeroImgError(i)"
            />
            <div v-else class="hero__slide-fallback" aria-hidden="true" />
            <div class="hero__slide-overlay" />
          </div>
        </div>

        <!-- 前景文案 -->
        <div class="hero__copy">
          <h1 class="hero__title">{{ t('common.app_slogan') }}</h1>
          <p v-if="t('home.hero.sub')" class="hero__sub">{{ t('home.hero.sub') }}</p>
          <p class="hero__caption" :key="`cap-${activeIdx}`">
            <span class="hero__caption-text">{{ t(slides[activeIdx].captionKey) }}</span>
            <span class="hero__caption-sep" aria-hidden="true">·</span>
            <span class="hero__caption-city">{{ t(slides[activeIdx].cityKey) }}</span>
          </p>
          <!-- B4: trust chip 数据带 -->
          <div class="hero__trust">
            <span class="hero__trust-item">
              <span class="hero__trust-num">12,847+</span>
              <span class="hero__trust-label">{{ t('home.trust_stats.users') }}</span>
            </span>
            <span class="hero__trust-divider" aria-hidden="true">·</span>
            <span class="hero__trust-item">
              <span class="hero__trust-num">99.2%</span>
              <span class="hero__trust-label">{{ t('home.trust_stats.on_time') }}</span>
            </span>
            <span class="hero__trust-divider" aria-hidden="true">·</span>
            <span class="hero__trust-item">
              <span class="hero__trust-num">4.9★</span>
              <span class="hero__trust-label">{{ t('home.trust_stats.rating') }}</span>
            </span>
          </div>
        </div>

      </section>

      <!-- 4 大签证目的地:大图卡片 -->
      <section class="destinations">
        <div class="destinations__head">
          <h2 class="section-title">{{ t('home.destinations.title') }}</h2>
          <p class="section-sub">{{ t('home.destinations.subtitle') }}</p>
        </div>

        <div class="destinations__grid">
          <article
            v-for="c in heroCountries"
            :key="c.code"
            class="country-card"
            :class="`country-card--${c.code.toLowerCase()}`"
            @click="onCountry(c.code)"
            role="button"
            tabindex="0"
            @keydown.enter="onCountry(c.code)"
            :data-testid="`home-country-${c.code.toLowerCase()}`"
          >
            <div class="country-card__media">
              <img
                v-if="c.image"
                :src="c.image"
                :alt="c.name"
                loading="lazy"
                class="country-card__img"
                @error="onImgError(c.code)"
              />
              <div class="country-card__media-fallback" v-else>{{ c.flag }}</div>
              <div class="country-card__media-overlay"></div>
            </div>

            <div class="country-card__top">
              <span class="country-card__flag">{{ c.flag }}</span>
              <span class="country-card__code">{{ c.code === 'SCHENGEN' ? 'EU' : c.code }}</span>
            </div>

            <div class="country-card__bottom">
              <h3 class="country-card__name">{{ c.name }}</h3>
              <p class="country-card__sub">{{ c.sub }}</p>
              <!-- W28 P1: SCHENGEN 卡显示 "Apply through this country" 提示 -->
              <p v-if="c.code === 'SCHENGEN'" class="country-card__hint" data-testid="home-card-hint-schengen">
                <span class="country-card__hint-icon" aria-hidden="true">🇪🇺</span>
                {{ t('home.card.apply_through') }}
              </p>
              <!-- W28 Atlys-style: 3 列属性 TYPE / VALID / FEES -->
              <div class="country-card__attrs" v-if="c.fee_usd != null">
                <div class="country-card__attr">
                  <span class="country-card__attr-label">{{ t('home.card.type') || 'TYPE' }}</span>
                  <span class="country-card__attr-val">{{ c.visa_type_label }}</span>
                </div>
                <div class="country-card__attr">
                  <span class="country-card__attr-label">{{ t('home.card.valid') || 'VALID' }}</span>
                  <span class="country-card__attr-val">{{ c.valid_label }}</span>
                </div>
                <!-- B3: 价格透明化 — "FROM $X 起" 风格, Atlys 范 -->
                <div class="country-card__attr country-card__attr--price">
                  <span class="country-card__attr-label">{{ t('home.card.fees') || 'FEES' }}</span>
                  <span class="country-card__attr-val">
                    <span class="country-card__price-from">FROM</span>
                    <span class="country-card__price-num">\${{ c.fee_usd }}</span>
                  </span>
                </div>
              </div>
              <!-- W28 Atlys-style: 精准交付时间 "Guaranteed Visa on DD MMM, HH:MM" -->
              <div class="country-card__eta" v-if="c.eta_label">
                <span class="country-card__eta-icon" aria-hidden="true">⏱</span>
                <span class="country-card__eta-text">{{ t('home.card.guaranteed_on') || 'Guaranteed Visa on' }} <b>{{ c.eta_label }}</b></span>
              </div>
              <div class="country-card__meta">
                <span class="country-card__arrow" aria-hidden="true">→</span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- W28 重构:Why choose us — 从"功能描述"改成"用户利益 + SVG icon" -->
      <section class="features">
        <div class="features__head">
          <h2 class="section-title features__title">{{ t('home.features.title') }}</h2>
          <p class="section-sub features__sub">{{ t('home.features.subtitle') }}</p>
        </div>
        <div class="features__grid">
          <article
            v-for="(f, i) in features"
            :key="f.id"
            class="feature"
            :class="`feature--${f.id}`"
            :data-testid="`home-feature-${f.id}`"
          >
            <div class="feature__head">
              <span class="feature__num" aria-hidden="true">{{ i + 1 }}</span>
              <h3 class="feature__title">{{ t(f.titleKey) }}</h3>
            </div>
            <p class="feature__desc">{{ t(f.descKey) }}</p>
          </article>
        </div>
      </section>

    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppButton from '@/components/AppButton.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { listDestinations } from '@/api/destinations'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

// ============== Hero 真实动图轮播(atlys 风格) ==============
// 10 段真实视频(雪山/海岛/极光/沙漠/星空/云海),每 4.5s 自动切换
// 视频加载失败时 fallback 到同名 .jpg 静态图
// I6: mobile 端禁用视频自动轮播 (轮询 + 解码耗电 + 流量),
// 只显示 slide 0 静态首屏。检测 600px 以下 viewport。
const SLIDE_DURATION = 4500
function isMobileViewport() {
  if (typeof window === 'undefined') return false
  return window.matchMedia && window.matchMedia('(max-width: 600px)').matches
}

// 10 张幻灯片:每条先 mp4 视频,失败 fallback 到同名 .jpg
const slides = [
  // t1 — 雪山 / 山野主题
  { image: '/hero/videos/t1_snow.mp4',          fallback: '/hero/t1_snow.jpg',          captionKey: 'home.hero.cap1',  cityKey: 'home.hero.city1' },
  { image: '/hero/videos/t1_hiker.mp4',         fallback: '/hero/t1_hiker.jpg',         captionKey: 'home.hero.cap6',  cityKey: 'home.hero.city2' },
  // t2 — 海岛 / 城市主题
  { image: '/hero/videos/t2_island.mp4',        fallback: '/hero/t2_island.jpg',        captionKey: 'home.hero.cap2',  cityKey: 'home.hero.city3' },
  { image: '/hero/videos/t2_backpack_city.mp4', fallback: '/hero/t2_backpack_city.jpg', captionKey: 'home.hero.cap7',  cityKey: 'home.hero.city4' },
  // t3 — 极光 / 天空主题
  { image: '/hero/videos/t3_aurora.mp4',        fallback: '/hero/t3_aurora.jpg',        captionKey: 'home.hero.cap3',  cityKey: 'home.hero.city5' },
  { image: '/hero/videos/t3_plane_sunset.mp4',  fallback: '/hero/t3_plane_sunset.jpg',  captionKey: 'home.hero.cap8',  cityKey: 'home.hero.city6' },
  // t4 — 沙漠 / 山系主题
  { image: '/hero/videos/t4_desert.mp4',        fallback: '/hero/t4_desert.jpg',        captionKey: 'home.hero.cap4',  cityKey: 'home.hero.city7' },
  { image: '/hero/videos/t4_dolomites.mp4',     fallback: '/hero/t4_dolomites.jpg',     captionKey: 'home.hero.cap9',  cityKey: 'home.hero.city8' },
  // t5 — 星空 / 云海主题
  { image: '/hero/videos/t5_stars.mp4',         fallback: '/hero/t5_stars.jpg',         captionKey: 'home.hero.cap5',  cityKey: 'home.hero.city9' },
  { image: '/hero/videos/t5_window_clouds.mp4', fallback: '/hero/t5_window_clouds.jpg', captionKey: 'home.hero.cap10', cityKey: 'home.hero.city10' },
]
const activeIdx = ref(0)
let timer = null
const failedHero = ref(new Set())

function onHeroImgError(i) {
  const next = new Set(failedHero.value)
  next.add(i)
  failedHero.value = next
}

function setActive(i) {
  activeIdx.value = i
}
function next() { setActive((activeIdx.value + 1) % slides.length) }

function startTimer() {
  stopTimer()
  // I6: mobile 上不轮播 (流量 + 渲染开销) — 只显示 slide 0
  if (isMobileViewport()) return
  timer = setInterval(next, SLIDE_DURATION)
}
function stopTimer() {
  if (timer) { clearInterval(timer); timer = null }
}

onMounted(() => {
  startTimer()
  applyDestinationsMeta()
})
onBeforeUnmount(stopTimer)

// 切语种时重置,避免 caption 切换不流畅
watch(locale, () => { /* 触发 caption 重新渲染,无需操作 */ }, { immediate: false })

// ============== W25 重新定位:4 大签证目的地 ==============
// 国家大图卡片(借鉴 atlys 设计):US / AU / Schengen / GB
// 每张卡:大图背景 + 角落国旗 + 底部国家名/visa类型/出签时长
const HERO_COUNTRY_IMAGES = {
  US: '/countries/us_liberty.jpg',
  AU: '/countries/au_sydney.jpg',
  SCHENGEN: '/countries/schengen_eiffel.jpg',
  GB: '/countries/gb_bigben.jpg',
}
const countryNameKeys = {
  US: 'country.us', AU: 'country.au',
  SCHENGEN: 'country.schengen', GB: 'country.gb',
}
const countrySubKeys = {
  US: 'country.us_sub', AU: 'country.au_sub',
  SCHENGEN: 'country.schengen_sub', GB: 'country.gb_sub',
}
const failedImages = ref(new Set())

function onImgError(code) {
  // 标记失败,vue 不再尝试加载
  const next = new Set(failedImages.value)
  next.add(code)
  failedImages.value = next
}

const heroCountries = computed(() =>
  ['US', 'AU', 'SCHENGEN', 'GB'].map(code => ({
    code,
    flag: { US: '🇺🇸', AU: '🇦🇺', SCHENGEN: '🇪🇺', GB: '🇬🇧' }[code],
    name: t(countryNameKeys[code]),
    sub: t(countrySubKeys[code]),
    image: failedImages.value.has(code) ? null : HERO_COUNTRY_IMAGES[code],
    // W28 Atlys-style meta (filled from destinations API via applyMeta later)
    fee_usd: null,
    valid_days: null,
    process_days: null,
    eta_iso: null,
    visa_type_label: t('home.card.type_evisa'),
    valid_label: '',
    eta_label: '',
  }))
)

// 把 destinations API 返回的价格/有效期/ETA 注入 heroCountries
// 注意: heroCountries 是静态 4 国(US/AU/SCHENGEN/GB),SCHENGEN 在 API 里没有 row,
// 用 AT/FR/DE 等价 fallback.
async function applyDestinationsMeta() {
  try {
    const rows = await listDestinations()
    const byCode = Object.fromEntries(rows.map(r => [r.country_code, r]))
    // SCHENGEN 用 FR 的 ETA (代表整个申根的处理时间)
    const schengenProxy = byCode['FR'] || byCode['DE'] || byCode['IT']
    const metaByCode = {
      US:       byCode['US'],
      AU:       byCode['AU'],
      GB:       byCode['GB'],
      SCHENGEN: schengenProxy,
    }
    for (let i = 0; i < heroCountries.value.length; i++) {
      const c = heroCountries.value[i]
      const m = metaByCode[c.code]
      if (!m) continue
      c.fee_usd     = m.visa_fee_usd != null ? Math.round(m.visa_fee_usd / 100) : null
      c.valid_days  = m.valid_days
      c.process_days = m.process_days
      c.eta_iso     = m.eta_iso
      // visa type label: 按 country_code 硬编码实际签发方式
      // (不能用 tourism/work/student 关键词判断 —— 那只是签证用途,不是签发方式)
      // 2026-02-25 起英国访问类签证已全面电子化,GB 也算 E-VISA
      const STICKER_VISA_COUNTRIES = new Set(['US', 'SCHENGEN', 'FR', 'DE', 'IT', 'ES', 'NL', 'AT', 'BE', 'GR', 'PT', 'CZ', 'DK', 'FI', 'HU', 'IS', 'LU', 'NO', 'PL', 'SE', 'CH'])
      if (STICKER_VISA_COUNTRIES.has(c.code)) {
        c.visa_type_label = t('home.card.type_sticker')
      } else {
        c.visa_type_label = t('home.card.type_evisa')
      }
      // valid label
      if (m.valid_days) {
        if (m.valid_days % 365 === 0) {
          const y = m.valid_days / 365
          c.valid_label = y === 1 ? '1 YEAR' : `${y} YEARS`
        } else if (m.valid_days % 30 === 0) {
          const mo = m.valid_days / 30
          c.valid_label = mo === 1 ? '1 MONTH' : `${mo} MONTHS`
        } else {
          c.valid_label = `${m.valid_days} DAYS`
        }
      }
      // ETA label - "DD MMM, HH:MM"
      if (m.eta_iso) {
        try {
          const d = new Date(m.eta_iso)
          const dd = String(d.getUTCDate()).padStart(2, '0')
          const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
          const mm = months[d.getUTCMonth()]
          const hh = String(d.getUTCHours()).padStart(2, '0')
          const mi = String(d.getUTCMinutes()).padStart(2, '0')
          c.eta_label = `${dd} ${mm} ${d.getUTCFullYear()}, ${hh}:${mi}`
        } catch (_) { c.eta_label = '' }
      }
    }
  } catch (e) {
    // 静默失败,卡仍可点;只是没有价格/ETA
    console.warn('[home] destinations meta load failed:', e?.message)
  }
}
onMounted(() => {
  startTimer()
  applyDestinationsMeta()
})

// W28 重构:Why choose us — 4 个用户利益点(从功能描述→用户价值)
// 顺序:数据安全 / 智能模版 / 智能核对 / 过签收费
// 每个 feature 带专属 SVG icon,不用 emoji
// 1. 数据安全 — 盾牌+锁 双重保护,蓝绿渐变
const ICON_DATA_SAFETY = `
  <svg viewBox="0 0 48 48" fill="none">
    <defs>
      <linearGradient id="ft-data-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stop-color="#10B981"/>
        <stop offset="100%" stop-color="#0891B2"/>
      </linearGradient>
    </defs>
    <!-- 外层盾牌 -->
    <path d="M24 3 L40 9 V22 C40 32 33 41 24 45 C15 41 8 32 8 22 V9 Z"
          fill="url(#ft-data-grad)"/>
    <!-- 内层高光 -->
    <path d="M24 7 L36 11.5 V22 C36 29.5 31 36.5 24 40"
          fill="none" stroke="rgba(255,255,255,.35)" stroke-width="1.6" stroke-linecap="round"/>
    <!-- 中心锁体 -->
    <rect x="17" y="22" width="14" height="11" rx="2" fill="#fff"/>
    <path d="M19.5 22 V19 a4.5 4.5 0 0 1 9 0 V22"
          fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>
    <circle cx="24" cy="27" r="1.4" fill="#10B981"/>
    <path d="M24 27 V29.5" stroke="#10B981" stroke-width="1.6" stroke-linecap="round"/>
  </svg>`

// 2. 智能模版 — 行程单(地图+航班路线),蓝紫渐变
const ICON_TEMPLATE = `
  <svg viewBox="0 0 48 48" fill="none">
    <defs>
      <linearGradient id="ft-tpl-grad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%"  stop-color="#3B6EF5"/>
        <stop offset="100%" stop-color="#8B5CF6"/>
      </linearGradient>
    </defs>
    <!-- 行程单底 -->
    <rect x="7" y="6" width="28" height="36" rx="3" fill="url(#ft-tpl-grad)"/>
    <path d="M20 6 V14 H35" fill="rgba(0,0,0,.18)"/>
    <!-- 行程节点线 -->
    <path d="M13 22 H29" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-dasharray="2 2" opacity=".7"/>
    <circle cx="13" cy="22" r="2" fill="#fff"/>
    <circle cx="29" cy="22" r="2" fill="#fff"/>
    <!-- 文字行 -->
    <rect x="13" y="28" width="16" height="2" rx="1" fill="#fff" opacity=".85"/>
    <rect x="13" y="32" width="12" height="2" rx="1" fill="#fff" opacity=".6"/>
    <rect x="13" y="36" width="14" height="2" rx="1" fill="#fff" opacity=".6"/>
    <!-- 飞机图标 -->
    <g transform="translate(30 30)">
      <circle cx="6" cy="6" r="9" fill="#fff"/>
      <path d="M2 6 L10 6 M6 2 L10 6 L6 10 L2 6 M6 2 L6 -1"
            stroke="#3B6EF5" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </g>
  </svg>`

// 3. 智能核对 — 文档 + 放大镜 + ✓,蓝橙渐变
const ICON_SMART_CHECK = `
  <svg viewBox="0 0 48 48" fill="none">
    <defs>
      <linearGradient id="ft-check-grad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%"  stop-color="#3B6EF5"/>
        <stop offset="100%" stop-color="#06B6D4"/>
      </linearGradient>
      <linearGradient id="ft-check-glass" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%"  stop-color="#F59E0B"/>
        <stop offset="100%" stop-color="#EF4444"/>
      </linearGradient>
    </defs>
    <!-- 文档底 -->
    <path d="M8 8 H26 L34 16 V40 H8 Z" fill="url(#ft-check-grad)"/>
    <path d="M26 8 V16 H34" fill="rgba(0,0,0,.18)"/>
    <!-- 文字行 -->
    <rect x="13" y="20" width="14" height="2" rx="1" fill="#fff" opacity=".85"/>
    <rect x="13" y="25" width="11" height="2" rx="1" fill="#fff" opacity=".65"/>
    <rect x="13" y="30" width="13" height="2" rx="1" fill="#fff" opacity=".65"/>
    <!-- 放大镜 -->
    <circle cx="30" cy="30" r="8" fill="#fff" stroke="url(#ft-check-glass)" stroke-width="2.5"/>
    <path d="M36 36 L41 41" stroke="url(#ft-check-glass)" stroke-width="3" stroke-linecap="round"/>
    <!-- ✓ -->
    <path d="M26 30 L29 33 L34 27" stroke="#F59E0B" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </svg>`

// 4. 过签收费 — 收据 + ✓ + $ 符号,紫粉渐变
const ICON_PAY_AFTER = `
  <svg viewBox="0 0 48 48" fill="none">
    <defs>
      <linearGradient id="ft-pay-grad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%"  stop-color="#8B5CF6"/>
        <stop offset="100%" stop-color="#EC4899"/>
      </linearGradient>
    </defs>
    <!-- 收据底 -->
    <path d="M10 6 H38 V40 L34 36 L30 40 L26 36 L22 40 L18 36 L14 40 L10 36 Z"
          fill="url(#ft-pay-grad)"/>
    <!-- $ 符号 -->
    <text x="24" y="24" font-size="14" font-weight="800" fill="#fff"
          text-anchor="middle" font-family="ui-sans-serif, sans-serif">$</text>
    <!-- 文字行 -->
    <rect x="15" y="27" width="18" height="1.6" rx=".8" fill="#fff" opacity=".85"/>
    <rect x="17" y="31" width="14" height="1.6" rx=".8" fill="#fff" opacity=".6"/>
    <!-- ✓ 圆章 -->
    <circle cx="36" cy="12" r="7" fill="#fff"/>
    <path d="M32.5 12 L35 14.5 L39.5 9.5" stroke="#8B5CF6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </svg>`

const features = computed(() => [
  {
    id: 'data-safety',
    titleKey: 'home.features.data_safety.title',
    descKey:  'home.features.data_safety.desc',
    icon: ICON_DATA_SAFETY,
  },
  {
    id: 'templates',
    titleKey: 'home.features.templates.title',
    descKey:  'home.features.templates.desc',
    icon: ICON_TEMPLATE,
  },
  {
    id: 'smart-check',
    titleKey: 'home.features.smart_check.title',
    descKey:  'home.features.smart_check.desc',
    icon: ICON_SMART_CHECK,
  },
  {
    id: 'pay-after',
    titleKey: 'home.features.pay_after.title',
    descKey:  'home.features.pay_after.desc',
    icon: ICON_PAY_AFTER,
  },
])

watch(locale, async () => {
  await nextTick()
}, { immediate: false })

function onCountry(countryCode) {
  // W26 产品逻辑:首页 4 大卡点进去直接进材料收集向导,不再"再选一次国家"。
  // - 单一国家(US/AU/GB)→ 直接进 MaterialWizard,带 country + 默认 visa_type
  // - 申根(26 国)→ 跳专门"申根 26 国"页选具体哪个,因为一个卡不能代表 26 国
  // W47: /orders/new 已合并到 MaterialWizard 第 6 大类"签证表格",无跳页体验
  if (countryCode === 'SCHENGEN') {
    router.push({ name: 'SchengenCountries' })
  } else {
    router.push({ name: 'MaterialWizard', query: { country: countryCode, visa_type: 'tourism' } })
  }
}
</script>

<style scoped lang="scss">
/* ============== Hero: 旅行图轮播 + slogan 前景 ============== */
.hero--slideshow {
  position: relative;
  display: block;
  min-height: 420px;
  color: #fff;
  border-radius: 20px;
  margin-bottom: 56px;
  // 中性暖灰阴影(避免在浅背景下渲染出"蓝边"错觉)
  box-shadow: 0 12px 32px rgba(50, 50, 70, .18);
  overflow: hidden;
  isolation: isolate;
  // 加载图前的深色底色(防止白屏闪 & 避免跟 box-shadow 形成蓝边)
  background: #0f172a;
}
.hero__slides {
  position: absolute;
  inset: 0;
  z-index: 0;
}
.hero__slide {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 1.2s ease-in-out;
  overflow: hidden;
}
.hero__slide.is-active {
  opacity: 1;
}
// 真实动图:视频本身在动(轮船/海浪/云/极光),不需要 pan/zoom
.hero__slide-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  // 温和提一档清晰度,不再用高 contrast/saturate 把视频细节切掉
  // (海浪/雪山这种高亮素材再压容易把纹理吃掉变糊)
  filter: contrast(1.08) saturate(1.18);
}

.hero__slide-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  // 只保留左侧 0-68% 暗角给文字撑底, 不再额外加全屏压暗 (避免整图清晰度掉一档)
  // 海浪这种视频 0-50% 通常是水面/浪花, 比雪山稍暗, 暗角系数稍微回收避免太死
  background:
    linear-gradient(90deg, rgba(15,23,42,.72) 0%, rgba(15,23,42,.48) 25%, rgba(15,23,42,.20) 50%, rgba(15,23,42,0) 68%),
    linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(15,23,42,.22) 100%);
}

// 视频+jpg 都失败时的兜底底色,避免留白
.hero__slide-fallback {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(135deg, #1e3a8a 0%, #312e81 100%);
}

.hero__copy {
  position: relative;
  z-index: 2;
  padding: 72px 64px;
  max-width: 720px;
}
.hero__title {
  font-size: 44px;
  font-weight: 800;
  margin: 0 0 14px;
  line-height: 1.15;
  letter-spacing: -.5px;
  // 文字阴影保持稳定, 0-50% 暗角已经稳, 不再叠超深阴影让字周围"糊"
  text-shadow:
    0 4px 18px rgba(15,23,42,.7),
    0 1px 3px rgba(15,23,42,.55);
}
.hero__sub {
  font-size: 16px;
  opacity: .92;
  margin: 0 0 24px;
  max-width: 480px;
  text-shadow: 0 2px 8px rgba(0,0,0,.2);
}
.hero__caption {
  display: inline-flex;
  align-items: center;
  gap: 8px; // caption 主段 + 城市名之间留一点呼吸
  margin: 0;
  padding: 8px 18px;
  // chip 背景稍微回收 (.54 → .46), 配合暗角提供足够可读性, 不再死黑
  background: rgba(15,23,42,.46);
  border: 1px solid rgba(255,255,255,.32);
  border-radius: 999px;
  backdrop-filter: blur(10px);
  font-size: 13px;
  text-shadow: 0 1px 3px rgba(0,0,0,.45);
  animation: captionIn .5s ease;
}
.hero__caption-text {
  font-weight: 500;
}
.hero__caption-sep {
  opacity: .55;
  font-weight: 400;
}
.hero__caption-city {
  font-weight: 400;
  opacity: .85;
  font-size: 12px;
  letter-spacing: .2px;
}

/* B4: trust chip — 数据带,放在 hero 标题下方 */
.hero__trust {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
  color: #fff;
  font-size: 14px;
  text-shadow: 0 1px 2px rgba(0,0,0,.35);
}
.hero__trust-item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}
.hero__trust-num {
  font-weight: 700;
  font-size: 16px;
  color: #FFD66B;
  letter-spacing: .3px;
}
.hero__trust-label {
  opacity: .92;
}
.hero__trust-divider {
  opacity: .55;
}

/* I1: 首页 CTA — 4 个热门国家快捷入口 */
.hero__cta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}
.hero__cta .app-btn {
  /* override AppButton default: 让 ghost 在 dark hero 上清晰可见 */
  --btn-bg: rgba(255,255,255,.12);
  --btn-bg-hover: rgba(255,255,255,.22);
  --btn-color: #fff;
  --btn-border: rgba(255,255,255,.35);
  backdrop-filter: blur(6px);
}

/* B3: 价格透明化 — FROM $X 风格 */
.country-card__attr--price .country-card__attr-val {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
}
.country-card__price-from {
  font-size: 10px;
  letter-spacing: .8px;
  opacity: .75;
  font-weight: 600;
}
.country-card__price-num {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

@keyframes captionIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 左右翻页箭头 */
/* W29: 左右翻页按钮已删除,纯自动轮播 */

/* 底部进度条 + 点指示 — W29 纯视觉,不可点击 */
.hero__dots {
  position: absolute;
  bottom: 24px;
  left: 64px;
  right: 64px;
  display: flex;
  gap: 8px;
  z-index: 3;
  pointer-events: none; // 兜底:整条不可点
}
.hero__dot {
  flex: 1;
  height: 3px;
  border: 0;
  border-radius: 2px;
  background: rgba(255,255,255,.28);
  cursor: default; // 显式无指针
  padding: 0;
  position: relative;
  overflow: hidden;
  transition: background .25s ease;
}
.hero__dot.is-active {
  background: rgba(255,255,255,.5);
}
.hero__dot-bar {
  position: absolute;
  inset: 0;
  background: #fff;
  transform: scaleX(0);
  transform-origin: left;
  border-radius: 2px;
}
.hero__dot.is-active .hero__dot-bar {
  transform: scaleX(1);
}
@keyframes heroProgress {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}

/* ============== 4 大目的地:大图卡片网格 ============== */
.destinations {
  margin-bottom: 64px;
}
.destinations__head {
  text-align: center;
  margin-bottom: 32px;
}
.destinations__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.country-card {
  position: relative;
  height: 400px;
  border-radius: 18px;
  overflow: hidden;
  cursor: pointer;
  transition: transform .35s cubic-bezier(.2,.8,.2,1), box-shadow .35s ease;
  box-shadow: 0 6px 18px rgba(15,23,42,.08);
  background: #f8fafc;
  isolation: isolate;
}
.country-card:hover {
  transform: translateY(-6px) scale(1.015);
  box-shadow: 0 22px 48px rgba(15,23,42,.22);
}
.country-card:focus-visible {
  outline: 3px solid var(--el-color-primary);
  outline-offset: 3px;
}

.country-card__media {
  position: absolute;
  inset: 0;
  z-index: 0;
  isolation: isolate;  /* W27: confine mix-blend-mode to this stacking context */
}
.country-card__media::after {
  /* W27: 统一 4 张国家图色调 — 用品牌蓝色叠加 + mix-blend-mode: color
     color 模式只影响色相,保留原图亮度/对比度,让 4 张不同原图都染上同一种"冷蓝"调 */
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #1e3a8a 0%, #3B6EF5 100%);
  mix-blend-mode: color;
  opacity: 0;  /* W29: 0 = 不染冷蓝 (AI 生成的 jpg 本身已经是统一冷蓝调, 再叠会过重) */
  pointer-events: none;
  z-index: 1;
}
.country-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform .6s cubic-bezier(.2,.8,.2,1);
  filter: saturate(1.5) contrast(1.1);  /* W29: 从 1.3 → 1.5, 1.08 → 1.1, 提鲜艳度 */
}
.country-card:hover .country-card__img {
  transform: scale(1.08);
}
.country-card__media-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 100px;
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
}
.country-card__media-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg,
    rgba(0,0,0,.05) 0%,
    rgba(0,0,0,0) 35%,
    rgba(0,0,0,.30) 100%);
  z-index: 2;  /* W27: 在色调叠加层上面,保持底部文字阴影可读 */
  pointer-events: none;
}

.country-card__top {
  position: absolute;
  top: 16px;
  left: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 2;
}
.country-card__flag {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  box-shadow: 0 4px 14px rgba(0,0,0,.25);
  border: 2px solid rgba(255,255,255,.8);
}
.country-card__code {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,.92);
  color: #1f2937;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 8px rgba(0,0,0,.15);
}

.country-card__bottom {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  padding: 18px 20px 20px;
  z-index: 2;
  color: #fff;
  background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.35) 50%, rgba(0,0,0,.7) 100%);
}
.country-card__name {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 800;
  line-height: 1.15;
  text-shadow: 0 2px 8px rgba(0,0,0,.4);
}
.country-card__sub {
  margin: 0 0 14px;
  font-size: 13px;
  opacity: .95;
  line-height: 1.4;
  text-shadow: 0 1px 4px rgba(0,0,0,.4);
}
/* W28 P1: SCHENGEN "Apply through this country" 提示 */
.country-card__hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(59, 110, 245, .85);
  color: #fff;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: .2px;
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 6px rgba(15, 23, 42, .25);
}
.country-card__hint-icon {
  font-size: 12px;
  line-height: 1;
}
/* W28 Atlys-style: 3 列属性 TYPE / VALID / FEES */
.country-card__attrs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 0 0 10px;
  padding: 10px 0;
  border-top: 1px solid rgba(255,255,255,.22);
  border-bottom: 1px solid rgba(255,255,255,.22);
}
.country-card__attr {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.country-card__attr-label {
  font-size: 10px;
  letter-spacing: 1.1px;
  font-weight: 700;
  color: rgba(255,255,255,.75);
  text-transform: uppercase;
}
.country-card__attr-val {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 4px rgba(0,0,0,.4);
}
/* W28 Atlys-style: 精准交付时间 */
.country-card__eta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 10px;
  font-size: 11.5px;
  color: rgba(255,255,255,.95);
  line-height: 1.4;
  text-shadow: 0 1px 4px rgba(0,0,0,.4);
}
.country-card__eta-icon {
  font-size: 13px;
}
.country-card__eta-text b {
  font-weight: 700;
  color: #fff;
}
.country-card__meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-top: 4px;
}
.country-card__chip {
  font-size: 12px;
  font-weight: 600;
  background: rgba(255,255,255,.18);
  padding: 5px 10px;
  border-radius: 999px;
  backdrop-filter: blur(6px);
}
.country-card__arrow {
  font-size: 18px;
  font-weight: 600;
  transition: transform .25s ease;
}
.country-card:hover .country-card__arrow {
  transform: translateX(4px);
}

/* ============== Features (Why us) — W48 重设计 ============== */
.features { margin-top: 8px; }
.features__head {
  max-width: 640px;
  margin: 0 auto 34px;
  text-align: center;
}
.features__eyebrow {
  display: inline-block;
  margin-bottom: 14px;
  padding: 5px 13px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--el-color-primary);
  background: var(--primary-bg);
  border-radius: 999px;
}
.features__title {
  font-size: 30px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -.01em;
  margin: 0 0 10px;
}
.features__sub {
  font-size: 15px;
  line-height: 1.6;
  margin: 0;
}
/* W60: 参照 mega menu 风格 — 深色圆形数字 + 加粗标题 + 灰色说明,去掉
   渐变图标块和水印大数字,跟 Apply 页数字徽标保持全站一致。 */
.features__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 28px 32px;
}
.feature {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.feature__head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.feature__num {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #0f172a;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-variant-numeric: tabular-nums;
}
.feature__title { margin: 0; font-size: 16px; font-weight: 700; color: var(--ink-1); line-height: 1.3; }
.feature__desc  { margin: 0; padding-left: 40px; font-size: 13px; color: var(--ink-3); line-height: 1.65; }

/* ============== 响应式 ============== */
@media (max-width: 1080px) {
  .destinations__grid { grid-template-columns: repeat(2, 1fr); }
  .country-card { height: 380px; }
  .hero__copy { padding: 56px 48px; }
  .hero__title { font-size: 38px; }
  .hero__dots { left: 48px; right: 48px; }
}
@media (max-width: 960px) {
  .hero--slideshow { min-height: 380px; }
  .hero__copy { padding: 48px 32px; }
  .hero__title { font-size: 32px; }
  .features__grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .hero--slideshow { min-height: 340px; border-radius: 14px; }
  .hero__copy { padding: 40px 24px; }
  .hero__title { font-size: 26px; }
  .hero__sub { font-size: 14px; }
  .hero__dots { left: 24px; right: 24px; bottom: 16px; }
  .destinations__grid { grid-template-columns: 1fr; }
  .country-card { height: 360px; }
  .features__grid { grid-template-columns: 1fr; }
  .features__title { font-size: 24px; }
}
</style>
