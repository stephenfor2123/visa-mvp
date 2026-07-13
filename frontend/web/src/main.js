import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import i18n, { loadLocale, onLocaleChange } from './i18n'
import { reapplySeoForLastRoute } from '@/seo/applySeo'
import './styles/main.scss'

// W19 fix: 移除全量 ElementPlus 注册 — 项目不使用任何 <el-*> 组件
// (UI 全是自写 AppButton / AppInput / AppCard), 全量注册 + resolver
// 在 dist 里生成空 dynamic import 触发 Proxy.<anonymous> SyntaxError.

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

// W19 fix: await detected locale 后再 mount, 否则 t() 拿到 raw key
// "login.title" 而不是 "欢迎回来", 因为 lazy load 跟 mount 是 race.
// "login.title" 而不是 "欢迎回来", 因为 lazy load 跟 mount 是 race.
loadLocale(i18n.global.locale.value).finally(() => {
  app.mount('#app')
  // Locale switches refresh meta description / OG tags for the current route.
  onLocaleChange(() => {
    reapplySeoForLastRoute(i18n)
  })
})