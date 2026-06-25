<template>
  <div class="home-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <HtexLogo :size="28" />
        <span>{{ t('common.app_name') }}</span>
      </router-link>
      <nav class="app-header__nav">
        <router-link to="/home">{{ t('nav.home') }}</router-link>
        <router-link v-if="auth.isLoggedIn" to="/destinations">{{ t('nav.destinations') }}</router-link>
        <router-link v-if="auth.isLoggedIn" to="/orders">我的申请</router-link>
        <router-link to="/profile">{{ t('nav.profile') }}</router-link>
      </nav>
      <div class="app-header__right">
        <ThemeToggle />
        <LangSwitch />
        <AppButton v-if="!auth.isLoggedIn" ref="loginBtnRef" variant="primary" size="sm" data-testid="home-login">
          {{ t('nav.login') }}
        </AppButton>
        <AppButton v-else ref="logoutBtnRef" variant="outline" size="sm" data-testid="home-logout">
          {{ t('nav.logout') }}
        </AppButton>
      </div>
    </header>

    <main class="app-container app-page">
      <!-- Hero: 旅行图轮播背景 + slogan 永远在前景 -->
      <section class="hero hero--slideshow" @mouseenter="pauseCarousel" @mouseleave="resumeCarousel">
        <!-- 5 张背景图 crossfade -->
        <div class="hero__slides" aria-hidden="true">
          <div
            v-for="(s, i) in slides"
            :key="i"
            class="hero__slide"
            :class="{ 'is-active': i === activeIdx }"
          >
            <img
              v-if="s.image"
              :src="s.image"
              :alt="t(s.captionKey)"
              class="hero__slide-img"
              loading="lazy"
              @error="onHeroImgError(i)"
            />
            <div class="hero__slide-overlay" />
          </div>
        </div>

        <!-- 前景文案 -->
        <div class="hero__copy">
          <h1 class="hero__title">{{ t('common.app_slogan') }}</h1>
          <p v-if="t('home.hero.sub')" class="hero__sub">{{ t('home.hero.sub') }}</p>
          <p class="hero__caption" :key="`cap-${activeIdx}`">
            <span class="hero__caption-tag">{{ String(activeIdx + 1).padStart(2, '0') }} / 05</span>
            <span class="hero__caption-text">{{ t(slides[activeIdx].captionKey) }}</span>
          </p>
        </div>

        <!-- 左右翻页箭头 -->
        <button class="hero__nav hero__nav--prev" @click="prev" aria-label="Previous">‹</button>
        <button class="hero__nav hero__nav--next" @click="next" aria-label="Next">›</button>

        <!-- 底部进度条 + 点指示 -->
        <div class="hero__dots">
          <button
            v-for="(s, i) in slides"
            :key="i"
            class="hero__dot"
            :class="{ 'is-active': i === activeIdx }"
            @click="setActive(i)"
            :aria-label="`Slide ${i + 1}`"
          >
            <span class="hero__dot-bar" :style="i === activeIdx ? { animation: `heroProgress 5s linear` } : null" />
          </button>
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
              <div class="country-card__meta">
                <span class="country-card__chip">⏱ {{ t('home.hero.chip_meta') }}</span>
                <span class="country-card__arrow" aria-hidden="true">→</span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- 为什么选我们 -->
      <section class="features">
        <h2 class="section-title">{{ t('home.features.title') }}</h2>
        <p class="section-sub">{{ t('home.features.subtitle') }}</p>
        <div class="features__grid">
          <AppCard
            v-for="f in features"
            :key="f.title"
            hoverable
          >
            <template #header>
              <h3 class="feature__title">{{ t(f.titleKey) }}</h3>
            </template>
            <p class="feature__desc">{{ t(f.descKey) }}</p>
          </AppCard>
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
import HtexLogo from '@/components/HtexLogo.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

// ============== W6-7 ref + setOnTrigger 模式 ==============
const loginBtnRef = ref(null)
const logoutBtnRef = ref(null)

// ============== Hero 旅行图轮播 ==============
// 5 张 Unsplash 旅行图,每 5s 自动切换,hover 暂停,左右箭头可手翻
const SLIDE_DURATION = 5000
const slides = [
  { image: '/hero/t1_hiker.jpg',         captionKey: 'home.hero.cap1' },
  { image: '/hero/t2_backpack_city.jpg', captionKey: 'home.hero.cap2' },
  { image: '/hero/t3_plane_sunset.jpg',  captionKey: 'home.hero.cap3' },
  { image: '/hero/t4_dolomites.jpg',     captionKey: 'home.hero.cap4' },
  { image: '/hero/t5_window_clouds.jpg', captionKey: 'home.hero.cap5' },
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
  startTimer()
}
function next() { setActive((activeIdx.value + 1) % slides.length) }
function prev() { setActive((activeIdx.value - 1 + slides.length) % slides.length) }

function startTimer() {
  stopTimer()
  timer = setInterval(next, SLIDE_DURATION)
}
function stopTimer() {
  if (timer) { clearInterval(timer); timer = null }
}
function pauseCarousel() { stopTimer() }
function resumeCarousel() { startTimer() }

onMounted(startTimer)
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
  }))
)

const features = computed(() => [
  { titleKey: 'home.features.materials.title', descKey: 'home.features.materials.desc' },
  { titleKey: 'home.features.insurance.title', descKey: 'home.features.insurance.desc' },
  { titleKey: 'home.features.templates.title', descKey: 'home.features.templates.desc' },
  { titleKey: 'home.features.affiliate.title', descKey: 'home.features.affiliate.desc' }
])

watch(locale, async () => {
  await nextTick()
}, { immediate: false })

function onLogout() {
  auth.logout()
  toast.success(t('toast.logout_success'))
  router.push('/home')
}

function onCountry(countryCode) {
  if (countryCode === 'SCHENGEN') {
    router.push({ path: '/destinations' })
  } else {
    router.push({ path: '/destinations', query: { country: countryCode } })
  }
}

function onLogin() {
  router.push('/login')
}

watch(
  () => auth.isLoggedIn,
  async (val) => {
    await nextTick()
    if (val) {
      if (logoutBtnRef.value) logoutBtnRef.value.setOnTrigger(onLogout)
    } else {
      if (loginBtnRef.value) loginBtnRef.value.setOnTrigger(onLogin)
    }
  },
  { immediate: true }
)
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
  box-shadow: 0 16px 40px rgba(15,23,42,.25);
  overflow: hidden;
  isolation: isolate;
  // 加载图前的渐变底色(防止白屏闪)
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
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
}
.hero__slide.is-active {
  opacity: 1;
}
.hero__slide.is-active .hero__slide-img {
  animation: kenburns 6s ease-in-out;
}
.hero__slide-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transform-origin: center;
}
.hero__slide-overlay {
  position: absolute;
  inset: 0;
  // 左侧只留极轻的"可读区"暗角,主体保持原图色彩
  background:
    linear-gradient(90deg, rgba(15,23,42,.42) 0%, rgba(15,23,42,.18) 35%, rgba(15,23,42,0) 60%),
    linear-gradient(180deg, rgba(0,0,0,0) 60%, rgba(15,23,42,.18) 100%);
}
@keyframes kenburns {
  from { transform: scale(1.0); }
  to   { transform: scale(1.12); }
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
  text-shadow: 0 2px 12px rgba(15,23,42,.55), 0 0 1px rgba(15,23,42,.4);
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
  gap: 12px;
  margin: 0;
  padding: 8px 14px;
  background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 999px;
  backdrop-filter: blur(8px);
  font-size: 13px;
  animation: captionIn .5s ease;
}
.hero__caption-tag {
  font-weight: 700;
  letter-spacing: 1.2px;
  opacity: .85;
  font-variant-numeric: tabular-nums;
}
.hero__caption-text {
  font-weight: 500;
}
@keyframes captionIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 左右翻页箭头 */
.hero__nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 3;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: rgba(255,255,255,.18);
  color: #fff;
  font-size: 28px;
  line-height: 1;
  font-weight: 300;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(8px);
  transition: background .2s ease, transform .2s ease;
  opacity: 0;
}
.hero--slideshow:hover .hero__nav { opacity: 1; }
.hero__nav:hover { background: rgba(255,255,255,.32); }
.hero__nav--prev { left: 20px; }
.hero__nav--next { right: 20px; }
.hero__nav:active { transform: translateY(-50%) scale(.92); }

/* 底部进度条 + 点指示 */
.hero__dots {
  position: absolute;
  bottom: 24px;
  left: 64px;
  right: 64px;
  display: flex;
  gap: 10px;
  z-index: 3;
}
.hero__dot {
  flex: 1;
  height: 3px;
  border: 0;
  border-radius: 2px;
  background: rgba(255,255,255,.28);
  cursor: pointer;
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
  height: 360px;
  border-radius: 18px;
  overflow: hidden;
  cursor: pointer;
  transition: transform .35s cubic-bezier(.2,.8,.2,1), box-shadow .35s ease;
  box-shadow: 0 6px 18px rgba(15,23,42,.08);
  background: #1f2937;
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
}
.country-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform .6s cubic-bezier(.2,.8,.2,1);
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
    rgba(0,0,0,.10) 0%,
    rgba(0,0,0,.05) 40%,
    rgba(0,0,0,.55) 100%);
  z-index: 1;
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
  padding: 20px 20px 22px;
  z-index: 2;
  color: #fff;
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
.country-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,.25);
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

/* ============== Features (Why us) ============== */
.features__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.feature__title { margin: 0; font-size: 15px; font-weight: 600; color: var(--ink-1); }
.feature__desc { margin: 0; font-size: 13px; color: var(--ink-3); line-height: 1.6; }

/* ============== 响应式 ============== */
@media (max-width: 1080px) {
  .destinations__grid { grid-template-columns: repeat(2, 1fr); }
  .country-card { height: 320px; }
  .hero__copy { padding: 56px 48px; }
  .hero__title { font-size: 38px; }
  .hero__dots { left: 48px; right: 48px; }
}
@media (max-width: 960px) {
  .hero--slideshow { min-height: 380px; }
  .hero__copy { padding: 48px 32px; }
  .hero__title { font-size: 32px; }
  .hero__nav { display: none; }
  .features__grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .hero--slideshow { min-height: 340px; border-radius: 14px; }
  .hero__copy { padding: 40px 24px; }
  .hero__title { font-size: 26px; }
  .hero__sub { font-size: 14px; }
  .hero__dots { left: 24px; right: 24px; bottom: 16px; }
  .destinations__grid { grid-template-columns: 1fr; }
  .country-card { height: 280px; }
  .features__grid { grid-template-columns: 1fr; }
}
</style>
