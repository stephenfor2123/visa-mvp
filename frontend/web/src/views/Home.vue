<template>
  <div class="home-page">
    <AppHeader scope="home" />
    <main class="app-container app-page">
      <!-- Hero: 旅行图轮播背景 + slogan 永远在前景 -->
      <section class="hero hero--slideshow" @mouseenter="pauseCarousel" @mouseleave="resumeCarousel">
        <!-- 5 张背景图 crossfade + 平移 + SVG 动效层(雪花/海鸟/极光/沙粒/流星) -->
        <div class="hero__slides" aria-hidden="true">
          <div
            v-for="(s, i) in slides"
            :key="i"
            class="hero__slide"
            :class="[`hero__slide--pan-${s.pan}`, { 'is-active': i === activeIdx }]"
          >
            <img
              v-if="s.image"
              :src="s.image"
              :alt="t(s.captionKey)"
              class="hero__slide-img"
              loading="lazy"
              @error="onHeroImgError(i)"
            />
            <!-- SVG 动效层(每张图配一个,内容在图上动) -->
            <div class="hero__fx" v-html="s.fx" />
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
import LangSwitch from '@/components/LangSwitch.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

// ============== Hero 旅行图轮播 ==============
// 5 张 Unsplash 旅行图,每 5s 自动切换,hover 暂停,左右箭头可手翻
// 每张图配 pan 方向 + SVG 动效层(雪花/海鸟/极光/沙粒/流星),图像本身"内容在动"
const SLIDE_DURATION = 5000
const FX_SNOWFALL = `
  <svg class="fx fx-snow" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice">
    <g class="fx-snow__layer">
      <circle cx="120" cy="80"  r="2" fill="rgba(255,255,255,.9)"/>
      <circle cx="280" cy="40"  r="1.5" fill="rgba(255,255,255,.75)"/>
      <circle cx="420" cy="120" r="2.5" fill="rgba(255,255,255,.95)"/>
      <circle cx="620" cy="60"  r="1.8" fill="rgba(255,255,255,.8)"/>
      <circle cx="780" cy="150" r="2.2" fill="rgba(255,255,255,.9)"/>
      <circle cx="950" cy="50"  r="1.6" fill="rgba(255,255,255,.7)"/>
      <circle cx="1100" cy="180" r="2" fill="rgba(255,255,255,.85)"/>
    </g>
    <g class="fx-snow__layer fx-snow__layer--2">
      <circle cx="80"  cy="180" r="1.5" fill="rgba(255,255,255,.7)"/>
      <circle cx="240" cy="220" r="2" fill="rgba(255,255,255,.85)"/>
      <circle cx="380" cy="280" r="1.2" fill="rgba(255,255,255,.6)"/>
      <circle cx="560" cy="240" r="1.8" fill="rgba(255,255,255,.75)"/>
      <circle cx="720" cy="320" r="2.2" fill="rgba(255,255,255,.9)"/>
      <circle cx="900" cy="260" r="1.5" fill="rgba(255,255,255,.7)"/>
      <circle cx="1060" cy="340" r="1.8" fill="rgba(255,255,255,.8)"/>
    </g>
  </svg>`
const FX_BIRDS = `
  <svg class="fx fx-birds" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice">
    <g class="fx-bird fx-bird--1">
      <path d="M0 0 q 6 -6 12 0 q 6 -6 12 0" fill="none" stroke="rgba(15,23,42,.7)" stroke-width="1.6" stroke-linecap="round"/>
    </g>
    <g class="fx-bird fx-bird--2">
      <path d="M0 0 q 4 -4 8 0 q 4 -4 8 0" fill="none" stroke="rgba(15,23,42,.5)" stroke-width="1.4" stroke-linecap="round"/>
    </g>
    <g class="fx-bird fx-bird--3">
      <path d="M0 0 q 5 -5 10 0 q 5 -5 10 0" fill="none" stroke="rgba(15,23,42,.6)" stroke-width="1.5" stroke-linecap="round"/>
    </g>
  </svg>`
const FX_AURORA = `
  <svg class="fx fx-aurora" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice">
    <defs>
      <linearGradient id="aurora-grad" x1="0" y1="0" x2="1" y2="0.4">
        <stop offset="0%"  stop-color="rgba(74,222,128,0)"/>
        <stop offset="30%" stop-color="rgba(74,222,128,.55)"/>
        <stop offset="55%" stop-color="rgba(167,243,208,.7)"/>
        <stop offset="80%" stop-color="rgba(110,231,183,.4)"/>
        <stop offset="100%" stop-color="rgba(74,222,128,0)"/>
      </linearGradient>
    </defs>
    <g class="fx-aurora__band">
      <path d="M -200 200 Q 200 100 600 220 T 1400 180 L 1400 380 Q 1000 320 600 380 T -200 380 Z" fill="url(#aurora-grad)"/>
    </g>
    <g class="fx-aurora__band fx-aurora__band--2">
      <path d="M -200 260 Q 300 200 700 300 T 1400 260 L 1400 420 Q 900 380 600 420 T -200 420 Z" fill="url(#aurora-grad)" opacity=".6"/>
    </g>
  </svg>`
const FX_SAND = `
  <svg class="fx fx-sand" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice">
    <g class="fx-sand__layer">
      <circle cx="100"  cy="380" r="1.5" fill="rgba(253,224,71,.9)"/>
      <circle cx="260"  cy="320" r="1.2" fill="rgba(253,224,71,.7)"/>
      <circle cx="420"  cy="420" r="1.8" fill="rgba(253,224,71,.85)"/>
      <circle cx="580"  cy="360" r="1.3" fill="rgba(253,224,71,.75)"/>
      <circle cx="740"  cy="400" r="1.5" fill="rgba(253,224,71,.8)"/>
      <circle cx="900"  cy="340" r="1.2" fill="rgba(253,224,71,.7)"/>
      <circle cx="1060" cy="420" r="1.7" fill="rgba(253,224,71,.85)"/>
    </g>
    <g class="fx-sand__layer fx-sand__layer--2">
      <circle cx="160"  cy="460" r="1" fill="rgba(253,224,71,.55)"/>
      <circle cx="320"  cy="500" r="1.4" fill="rgba(253,224,71,.7)"/>
      <circle cx="500"  cy="480" r="1.1" fill="rgba(253,224,71,.6)"/>
      <circle cx="680"  cy="520" r="1.5" fill="rgba(253,224,71,.75)"/>
      <circle cx="860"  cy="490" r="1.2" fill="rgba(253,224,71,.65)"/>
      <circle cx="1020" cy="530" r="1.3" fill="rgba(253,224,71,.7)"/>
    </g>
  </svg>`
const FX_METEOR = `
  <svg class="fx fx-meteor" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice">
    <defs>
      <linearGradient id="meteor-grad" x1="1" y1="0" x2="0" y2="1">
        <stop offset="0%"  stop-color="rgba(255,255,255,0)"/>
        <stop offset="40%" stop-color="rgba(244,232,255,.4)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,1)"/>
      </linearGradient>
    </defs>
    <line class="fx-meteor__trail" x1="1000" y1="80" x2="1180" y2="20" stroke="url(#meteor-grad)" stroke-width="1.4" stroke-linecap="round"/>
    <circle class="fx-meteor__head" cx="1180" cy="20" r="2.2" fill="white"/>
    <line class="fx-meteor__trail fx-meteor__trail--2" x1="800" y1="180" x2="950" y2="125" stroke="url(#meteor-grad)" stroke-width="1" stroke-linecap="round" opacity=".5"/>
    <circle class="fx-meteor__head fx-meteor__head--2" cx="950" cy="125" r="1.5" fill="white" opacity=".7"/>
  </svg>`

const slides = [
  { image: '/hero/t1_snow.jpg',   captionKey: 'home.hero.cap1', pan: 'tl', fx: FX_SNOWFALL },
  { image: '/hero/t2_island.jpg', captionKey: 'home.hero.cap2', pan: 'br', fx: FX_BIRDS },
  { image: '/hero/t3_aurora.jpg', captionKey: 'home.hero.cap3', pan: 'r',  fx: FX_AURORA },
  { image: '/hero/t4_desert.jpg', captionKey: 'home.hero.cap4', pan: 'l',  fx: FX_SAND },
  { image: '/hero/t5_stars.jpg',  captionKey: 'home.hero.cap5', pan: 't',  fx: FX_METEOR },
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

function onCountry(countryCode) {
  if (countryCode === 'SCHENGEN') {
    router.push({ path: '/destinations' })
  } else {
    router.push({ path: '/destinations', query: { country: countryCode } })
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
  overflow: hidden;
}
.hero__slide.is-active {
  opacity: 1;
}
// 用平移(pan)代替 Ken Burns 放大,每张图不同方向 — 图像在动,不是放大
.hero__slide.is-active .hero__slide-img {
  animation-duration: 8s;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
  animation-direction: alternate;
  will-change: transform;
}
.hero__slide--pan-tl .hero__slide-img { animation-name: panTL; }
.hero__slide--pan-br .hero__slide-img { animation-name: panBR; }
.hero__slide--pan-r  .hero__slide-img { animation-name: panR;  }
.hero__slide--pan-l  .hero__slide-img { animation-name: panL;  }
.hero__slide--pan-t  .hero__slide-img { animation-name: panT;  }
@keyframes panTL {
  from { transform: translate3d(2%, 1.5%, 0) scale(1.04); }
  to   { transform: translate3d(-3%, -2%, 0) scale(1.04); }
}
@keyframes panBR {
  from { transform: translate3d(-2.5%, -1.5%, 0) scale(1.04); }
  to   { transform: translate3d(2.5%, 2%, 0) scale(1.04); }
}
@keyframes panR {
  from { transform: translate3d(-3%, 0, 0) scale(1.04); }
  to   { transform: translate3d(3%, 1%, 0) scale(1.04); }
}
@keyframes panL {
  from { transform: translate3d(3%, 0, 0) scale(1.04); }
  to   { transform: translate3d(-3%, -1%, 0) scale(1.04); }
}
@keyframes panT {
  from { transform: translate3d(0, 2.5%, 0) scale(1.05); }
  to   { transform: translate3d(0, -2.5%, 0) scale(1.05); }
}
.hero__slide-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transform-origin: center;
}

// SVG 动效层 — 图像本身"有内容在动"
.hero__fx {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
  opacity: 0;
  transition: opacity 1.2s ease-in-out;
}
.hero__slide.is-active .hero__fx {
  opacity: 1;
}
.fx {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

// 雪山:雪花飘落
.hero__fx :deep(.fx-snow__layer) { animation: snowFall 6s linear infinite; }
.hero__fx :deep(.fx-snow__layer--2) { animation: snowFall 9s linear infinite; animation-delay: -3s; opacity: .7; }
@keyframes snowFall {
  0%   { transform: translate3d(0, -10%, 0); }
  100% { transform: translate3d(20px, 110%, 0); }
}

// 海岛:海鸟飞过(三条不同路径)
.hero__fx :deep(.fx-bird) { transform: translate3d(-200px, 0, 0); }
.hero__fx :deep(.fx-bird--1) { animation: birdFly 7s linear infinite; --s: 1; }
.hero__fx :deep(.fx-bird--2) { animation: birdFly 9s linear infinite; animation-delay: -3s; --s: .7; }
.hero__fx :deep(.fx-bird--3) { animation: birdFly 11s linear infinite; animation-delay: -6s; --s: 1.2; }
@keyframes birdFly {
  0%   { transform: translate3d(-100px, 0, 0) scale(var(--s, 1)); }
  50%  { transform: translate3d(50vw, 30px, 0) scale(var(--s, 1)); }
  100% { transform: translate3d(calc(100vw + 100px), -20px, 0) scale(var(--s, 1)); }
}

// 极光:渐变光带缓慢飘动
.hero__fx :deep(.fx-aurora__band) { animation: auroraDrift 7s ease-in-out infinite alternate; transform-origin: center; }
.hero__fx :deep(.fx-aurora__band--2) { animation: auroraDrift 11s ease-in-out infinite alternate; animation-delay: -2s; opacity: .55; }
@keyframes auroraDrift {
  0%   { transform: translate3d(-3%, -2%, 0) skewX(-3deg); }
  100% { transform: translate3d(3%, 2%, 0) skewX(3deg); }
}

// 沙漠:沙粒横向飘移
.hero__fx :deep(.fx-sand__layer) { animation: sandDrift 8s linear infinite; }
.hero__fx :deep(.fx-sand__layer--2) { animation: sandDrift 12s linear infinite; animation-delay: -4s; opacity: .65; }
@keyframes sandDrift {
  0%   { transform: translate3d(-5%, 0, 0); }
  100% { transform: translate3d(8%, -10px, 0); }
}

// 星空:流星划过
.hero__fx :deep(.fx-meteor__trail), .hero__fx :deep(.fx-meteor__head) { animation: meteor 4s linear infinite; }
.hero__fx :deep(.fx-meteor__trail--2), .hero__fx :deep(.fx-meteor__head--2) { animation: meteor 6s linear infinite; animation-delay: -2.5s; }
@keyframes meteor {
  0%   { transform: translate3d(0, 0, 0); opacity: 0; }
  10%  { opacity: 1; }
  40%  { opacity: 1; }
  100% { transform: translate3d(-260px, 110px, 0); opacity: 0; }
}

.hero__slide-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  // 左侧只留极轻的"可读区"暗角,主体保持原图色彩
  background:
    linear-gradient(90deg, rgba(15,23,42,.42) 0%, rgba(15,23,42,.18) 35%, rgba(15,23,42,0) 60%),
    linear-gradient(180deg, rgba(0,0,0,0) 60%, rgba(15,23,42,.18) 100%);
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
