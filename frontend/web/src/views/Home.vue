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
      <section class="hero">
        <div class="hero__copy">
          <h1 class="hero__title">{{ t('common.app_slogan') }}</h1>
          <p class="hero__sub">{{ t('home.hero.sub') }}</p>
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
          <div class="hero__chip" v-for="c in heroCountries" :key="c.code" @click="onCountry(c.code)" role="button" tabindex="0" @keydown.enter="onCountry(c.code)" style="cursor: pointer">
            <span class="flag">{{ c.flag }}</span>
            <span class="name">{{ c.name }}</span>
            <span class="meta">{{ t('home.hero.chip_meta') }}</span>
          </div>
        </div>
      </section>

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

// ============== W6-7 治本:ref + setOnTrigger 模式 ==============
// 4 处 AppButton 全部 ref 化,vue @click 冒泡不再依赖 AppButton 内部
// 登录/登出 v-if 互斥:watch auth.isLoggedIn 触发 + nextTick 注入
// Hero 2 个按钮 onMounted 即可
const loginBtnRef = ref(null)
const logoutBtnRef = ref(null)
const heroLoginBtnRef = ref(null)
const heroExploreBtnRef = ref(null)

// W10-2 L4 i18n: heroCountries 用 computed + t() 确保 i18n 加载后才渲染
// 国家名来自 i18n keys (country.xxx) 而非硬编码
const countryNameKeys = {
  TH: 'country.th', VN: 'country.vn', ID: 'country.id',
  PH: 'country.ph', MY: 'country.my', SG: 'country.sg'
}
const heroCountries = computed(() =>
  ['TH', 'VN', 'ID', 'PH', 'MY', 'SG'].map(code => ({
    code,
    flag: { TH: '🇹🇭', VN: '🇻🇳', ID: '🇮🇩', PH: '🇵🇭', MY: '🇲🇾', SG: '🇸🇬' }[code],
    name: t(countryNameKeys[code])
  }))
)

// W10-2 L4 i18n: features 必须用 computed,否则 t() 在 i18n 加载前被调用
// 导致 DOM 显示原始 key 字符串(如 "home.features.materials.title")
const features = computed(() => [
  { titleKey: 'home.features.materials.title', descKey: 'home.features.materials.desc' },
  { titleKey: 'home.features.insurance.title', descKey: 'home.features.insurance.desc' },
  { titleKey: 'home.features.templates.title', descKey: 'home.features.templates.desc' },
  { titleKey: 'home.features.affiliate.title', descKey: 'home.features.affiliate.desc' }
])

// W10-2: watch locale change → force re-compute heroCountries/features
// (computed auto-tracks t() reactive deps, but guard against SSR/hydration edge-cases)
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
  router.push({ path: '/destinations', query: { country: countryCode } })
}

// Login navigation
function onLogin() {
  router.push('/login')
}

// Inject 4 AppButton click callbacks
// Hero 2 persistent buttons: onMounted is enough to inject
onMounted(() => {
  if (heroLoginBtnRef.value) heroLoginBtnRef.value.setOnTrigger(onLogin)
  if (heroExploreBtnRef.value) heroExploreBtnRef.value.setOnTrigger(onExplore)
})

// Login/Logout button v-if mutex: watch trigger + nextTick inject (same as Materials template)
watch(
  () => auth.isLoggedIn,
  async (val) => {
    await nextTick()
    if (val) {
      // Logged in -> logoutBtnRef mounts
      if (logoutBtnRef.value) logoutBtnRef.value.setOnTrigger(onLogout)
    } else {
      // Not logged in -> loginBtnRef mounts
      if (loginBtnRef.value) loginBtnRef.value.setOnTrigger(onLogin)
    }
  },
  { immediate: true }
)
</script>

<style scoped lang="scss">
.hero {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 40px;
  align-items: center;
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%);
  color: #fff;
  border-radius: 20px;
  padding: 56px 48px;
  margin-bottom: 56px;
  box-shadow: 0 16px 40px rgba(59,110,245,.25);
}
.hero__title { font-size: 36px; font-weight: 700; margin: 0 0 12px; line-height: 1.2; }
.hero__sub { font-size: 16px; opacity: .9; margin: 0 0 24px; max-width: 420px; }
.hero__cta { display: flex; gap: 12px; }
.hero__cta .app-btn--primary { background: #fff; color: var(--el-color-primary); }
.hero__cta .app-btn--primary:hover { background: #F1F5FE; }
.hero__cta .app-btn--outline { color: #fff; border-color: rgba(255,255,255,.6); background: transparent; }
.hero__cta .app-btn--outline:hover { background: rgba(255,255,255,.1); }

.hero__visual {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.hero__chip {
  background: rgba(255,255,255,.15);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(255,255,255,.2);
  border-radius: 12px;
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}
.hero__chip .flag { font-size: 22px; }
.hero__chip .name { font-weight: 600; }
.hero__chip .meta { opacity: .8; font-size: 11px; }

.features__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.feature__title { margin: 0; font-size: 15px; font-weight: 600; color: var(--ink-1); }
.feature__desc { margin: 0; font-size: 13px; color: var(--ink-3); line-height: 1.6; }

@media (max-width: 960px) {
  .hero { grid-template-columns: 1fr; padding: 32px 24px; }
  .hero__visual { grid-template-columns: repeat(3, 1fr); }
  .features__grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .features__grid { grid-template-columns: 1fr; }
}
</style>