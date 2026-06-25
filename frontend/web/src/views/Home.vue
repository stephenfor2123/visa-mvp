<template>
  <div class="home-page">
    <header class="app-header app-container">
      <router-link to="/home" class="app-header__brand">
        <span class="app-header__brand-mark">V</span>
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
      <!-- Hero: 干净的 slogan + CTA -->
      <section class="hero">
        <div class="hero__copy">
          <h1 class="hero__title">{{ t('common.app_slogan') }}</h1>
          <p v-if="t('home.hero.sub')" class="hero__sub">{{ t('home.hero.sub') }}</p>
          <div class="hero__cta">
            <AppButton ref="heroLoginBtnRef" variant="primary" size="lg" data-testid="home-hero-login">
              {{ t('nav.login') }}
            </AppButton>
            <AppButton ref="heroExploreBtnRef" variant="outline" size="lg" data-testid="home-hero-explore">
              {{ t('home.hero.explore_cta') }}
            </AppButton>
          </div>
        </div>
        <div class="hero__visual">
          <div class="hero__orbit">
            <div class="hero__orbit-ring"></div>
            <span class="hero__orbit-flag hero__orbit-flag--us">🇺🇸</span>
            <span class="hero__orbit-flag hero__orbit-flag--au">🇦🇺</span>
            <span class="hero__orbit-flag hero__orbit-flag--eu">🇪🇺</span>
            <span class="hero__orbit-flag hero__orbit-flag--gb">🇬🇧</span>
            <div class="hero__orbit-center">🌏</div>
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
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppCard from '@/components/AppCard.vue'
import AppButton from '@/components/AppButton.vue'
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
const heroLoginBtnRef = ref(null)
const heroExploreBtnRef = ref(null)

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

function onExplore() {
  router.push('/destinations')
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

onMounted(() => {
  if (heroLoginBtnRef.value) heroLoginBtnRef.value.setOnTrigger(onLogin)
  if (heroExploreBtnRef.value) heroExploreBtnRef.value.setOnTrigger(onExplore)
})

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
/* ============== Hero: slogan + CTA + 装饰 orbit ============== */
.hero {
  position: relative;
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 40px;
  align-items: center;
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
  color: #fff;
  border-radius: 20px;
  padding: 64px 56px;
  margin-bottom: 56px;
  box-shadow: 0 16px 40px rgba(59,110,245,.25);
  overflow: hidden;
}
.hero__title { font-size: 40px; font-weight: 800; margin: 0 0 14px; line-height: 1.15; letter-spacing: -.5px; }
.hero__sub { font-size: 16px; opacity: .9; margin: 0 0 28px; max-width: 460px; }
.hero__cta { display: flex; gap: 12px; }
.hero__cta .app-btn--primary { background: #fff; color: var(--el-color-primary); }
.hero__cta .app-btn--primary:hover { background: #F1F5FE; }
.hero__cta .app-btn--outline { color: #fff; border-color: rgba(255,255,255,.6); background: transparent; }
.hero__cta .app-btn--outline:hover { background: rgba(255,255,255,.1); }

/* 装饰性 orbit:4 个国家旗围绕地球,纯 CSS 动画 */
.hero__visual {
  position: relative;
  height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hero__orbit {
  position: relative;
  width: 280px;
  height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hero__orbit-ring {
  position: absolute;
  inset: 0;
  border: 2px dashed rgba(255,255,255,.35);
  border-radius: 50%;
  animation: spin 24s linear infinite;
}
.hero__orbit-center {
  font-size: 100px;
  filter: drop-shadow(0 8px 20px rgba(0,0,0,.3));
  animation: spin 24s linear infinite reverse;
}
.hero__orbit-flag {
  position: absolute;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  box-shadow: 0 8px 20px rgba(0,0,0,.25);
  animation: spin 24s linear infinite reverse;
}
.hero__orbit-flag--us { top: 0;   left: 50%; transform: translate(-50%, 0); }
.hero__orbit-flag--au { top: 50%; right: 0;  transform: translate(0, -50%); }
.hero__orbit-flag--gb { bottom: 0; left: 50%; transform: translate(-50%, 0); }
.hero__orbit-flag--eu { top: 50%; left: 0;   transform: translate(0, -50%); }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.hero__orbit-flag--us, .hero__orbit-flag--au, .hero__orbit-flag--gb, .hero__orbit-flag--eu {
  /* 保持 flag 自身不翻转,父级旋转 */
}
.hero__orbit-flag--us, .hero__orbit-flag--au, .hero__orbit-flag--gb, .hero__orbit-flag--eu {
  animation: orbit-counter 24s linear infinite;
}
@keyframes orbit-counter {
  from { transform: rotate(0deg); }
  to { transform: rotate(-360deg); }
}
.hero__orbit-flag--us { transform-origin: 50% 140px; animation: orbit-counter 24s linear infinite; }
.hero__orbit-flag--au { transform-origin: -140px 50%; animation: orbit-counter 24s linear infinite; }
.hero__orbit-flag--gb { transform-origin: 50% -140px; animation: orbit-counter 24s linear infinite; }
.hero__orbit-flag--eu { transform-origin: 140px 50%; animation: orbit-counter 24s linear infinite; }

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
}
@media (max-width: 960px) {
  .hero { grid-template-columns: 1fr; padding: 36px 28px; text-align: center; }
  .hero__visual { height: 240px; }
  .hero__cta { justify-content: center; }
  .features__grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .hero__title { font-size: 30px; }
  .destinations__grid { grid-template-columns: 1fr; }
  .country-card { height: 280px; }
  .features__grid { grid-template-columns: 1fr; }
}
</style>
