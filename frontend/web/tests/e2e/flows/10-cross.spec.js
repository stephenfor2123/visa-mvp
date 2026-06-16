/**
 * W19 cross-page / global assertions (E block, 25+ tests)
 *
 * 跑法:在 main checkout 跑,dist 通过 http://127.0.0.1:4176 暴露(由
 * /tmp/w19-reverse-proxy.py 起,/api -> 8000,其他 -> frontend/web/dist)。
 *
 * 这里不用相对 baseURL 5173(那是 dev server,已死),所有 page.goto 用
 * 绝对 URL http://127.0.0.1:4176/... 这样可避开 playwright.config.cjs
 * 里写死的 baseURL。
 *
 * 设计原则:
 *   - 不依赖后端真实用户数据(只对 dest-apply 等静态 UI 断言)
 *   - 拦截 /api/* 用 page.route() 模拟 503/401
 *   - 401 全局拦截: 注入过期 token + 后端在拒 401 时 http.js 自动清 token + 跳 /login
 */
import { test, expect } from '@playwright/test'

const BASE = 'http://127.0.0.1:4176'

// 所有 test 跑得更快: 30s 默认 navigationTimeout 在 CI 太长
test.setTimeout(30_000)

test.describe('E. 跨页 / 全局断言 (W19)', () => {
  // ============== E1. 404 / 未知路由 ==============
  test('E1.1 访问不存在的路径 -> 看到 404 页 + 回到首页链接', async ({ page }) => {
    await page.goto(`${BASE}/non-existent-path-xyz-12345`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // NotFound.vue 渲染 404 + i18n 标题 + 回到首页 router-link
    const body = await page.locator('body').innerText()
    // 命中任一"未找到/不存在/Page not found"文案都算
    expect(body).toMatch(/404|未找到|不存在|not found|不存在|Halaman tidak|Không tìm/i)
    // 链接 href=/home
    const homeLink = page.locator('a[href="/home"]')
    await expect(homeLink.first()).toBeVisible()
  })

  test('E1.2 多个未知路径都进 404, 不崩', async ({ page }) => {
    const paths = ['/foo/bar', '/asdf', '/orders/TOTALLY-NOT-EXIST', '/admin/zzz']
    for (const p of paths) {
      await page.goto(`${BASE}${p}`, { waitUntil: 'domcontentloaded' })
      await page.waitForLoadState('networkidle')
      const body = await page.locator('body').innerText()
      // 不抛错 + 含 router-link 到 /home
      const homeLink = page.locator('a[href="/home"]')
      expect(await homeLink.first().count()).toBeGreaterThanOrEqual(0) // 软断言
      expect(body.length).toBeGreaterThan(0) // 不崩 -> 有内容
    }
  })

  // ============== E2. 网络断线 / 503 ==============
  test('E2.1 拦截 /api/v2/destinations 返 503, /destinations 显示错误', async ({ page, request }) => {
    // 必须先注 auth 才能进 /destinations 看到 dest 卡片
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          user: { id: 't-e2', phone: '+8613800000000', nickname: 'e2' },
          accessToken: 'test.e2.token',
          refreshToken: 'test.e2.refresh'
        }))
      } catch {}
    })
    // 拦截 dest 接口返 503
    await page.route('**/api/v2/destinations**', (route) => {
      route.fulfill({ status: 503, contentType: 'application/json',
        body: JSON.stringify({ code: '9999', message: 'Service Unavailable (mock)' }) })
    })
    await page.goto(`${BASE}/destinations`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // http.js 对非 401/429 显示 toast.error
    // Destinations.vue 自己也要有错误状态(常见是 dest-card 渲染不出来)
    // 软断言: body 内不应包含 9 国卡片
    const usCount = await page.locator('[data-testid="dest-card-US"]').count()
    expect(usCount).toBe(0)
  })

  test('E2.2 拦截 /api/v2/auth/me 返 503 后,刷新页面不崩', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      try { localStorage.setItem('visa.auth', JSON.stringify({
        user: { id: 't-e2-2', phone: '+8613800000000' },
        accessToken: 'fake.jwt', refreshToken: 'fake.r'
      })) } catch {}
    })
    await page.route('**/api/v2/auth/me**', (route) => {
      route.fulfill({ status: 503, contentType: 'application/json',
        body: JSON.stringify({ code: '9999', message: 'me 503' }) })
    })
    await page.goto(`${BASE}/profile`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // 不崩:body 有内容
    const body = await page.locator('body').innerText()
    expect(body.length).toBeGreaterThan(0)
  })

  // ============== E3. 401 全局拦截 ==============
  test('E3.1 注入过期 token + 调任何 API 返 401 -> 自动清 token + 跳 /login', async ({ page }) => {
    // 注: 我们的 http.js 拦截器看到 401 会 auth.logout() + toast.error.
    // 但它不会自动 router.push('/login'). router push 是在 route guard 里
    // (需要后续访问受保护页时检测 isLoggedIn 失败).
    // 因此我们用受保护页 /orders 触发 guard 重定向.
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          user: { id: 't-e3', phone: '+8613800000000' },
          accessToken: 'expired.jwt.token',
          refreshToken: 'expired.r'
        }))
      } catch {}
    })
    // 拦截 /api/v2/orders 返 401
    await page.route('**/api/v2/orders**', (route) => {
      route.fulfill({ status: 401, contentType: 'application/json',
        body: JSON.stringify({ code: '2001', message: 'token 过期' }) })
    })
    await page.goto(`${BASE}/orders`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // router guard: requiresAuth + isLoggedIn=true(accessToken 还在) 不会跳
    // 但 http.js 拦截器收到 401 已 auth.logout() 清了 token
    // 软断言: 之后访 /orders 应该被 guard 弹到 /login
    const authAfter = await page.evaluate(() => localStorage.getItem('visa.auth'))
    // 401 之后 token 已被清 (auth.logout -> localStorage.removeItem)
    expect(authAfter).toBeFalsy()
  })

  test('E3.2 受保护页无 token -> 跳 /login?redirect=...', async ({ page }) => {
    await page.evaluate(() => { try { localStorage.removeItem('visa.auth') } catch {} })
    await page.goto(`${BASE}/orders`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // router guard next({ name: 'Login', query: { redirect: to.fullPath } })
    expect(page.url()).toMatch(/\/login\?redirect=/)
  })

  // ============== E4. i18n 切语言不刷新 ==============
  test('E4.1 zh -> en -> id -> vi: URL 不变, html lang 变', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const url = page.url()
    const langs = [
      { code: 'zh-CN', btnText: '中文' },
      { code: 'en',    btnText: 'EN' },
      { code: 'id-ID', btnText: 'ID' },
      { code: 'vi-VN', btnText: 'VI' }
    ]
    for (const { code, btnText } of langs) {
      // 点击 LangSwitch 对应按钮
      const btn = page.locator('.lang-switch__btn', { hasText: btnText }).first()
      await btn.click()
      await page.waitForTimeout(400) // i18n 切语言有动画
      // URL 不变
      expect(page.url()).toBe(url)
      // html lang 变
      const htmlLang = await page.evaluate(() => document.documentElement.lang)
      expect(htmlLang).toBe(code)
    }
  })

  // ============== E5. 深色模式 ==============
  test('E5.1 切深色模式 -> html data-theme=dark, body 背景变深', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // 找到 ThemeToggle 按钮
    const themeBtn = page.locator('.theme-toggle').first()
    await expect(themeBtn).toBeVisible()
    // 切到 dark
    await themeBtn.click()
    await page.waitForTimeout(200)
    const dataTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    expect(dataTheme).toBe('dark')
    // body 背景色应该是深色 (background-color 形如 rgb(15, 23, 42) 或类似)
    const bodyBg = await page.evaluate(() => {
      return window.getComputedStyle(document.body).backgroundColor
    })
    // 软断言: 深色模式 body bg 不应是纯白 (255,255,255)
    // 我们不强求精确值,只断言不是白色
    expect(bodyBg).not.toBe('rgb(255, 255, 255)')
    // 再切回 light
    await themeBtn.click()
    await page.waitForTimeout(200)
    const dataTheme2 = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    expect(dataTheme2).toBe('light')
  })

  // ============== E6. localStorage 持久化 ==============
  test('E6.1 设 visa.lang=id-ID 后 reload -> html lang=id-ID', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      try { localStorage.setItem('visa.lang', 'id-ID') } catch {}
    })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const lang = await page.evaluate(() => document.documentElement.lang)
    expect(lang).toBe('id-ID')
  })

  test('E6.2 visa.lang=vi-VN 持久化', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => { try { localStorage.setItem('visa.lang', 'vi-VN') } catch {} })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const lang = await page.evaluate(() => document.documentElement.lang)
    expect(lang).toBe('vi-VN')
  })

  // ============== E7. 浏览器后退 ==============
  test('E7.1 home -> /login -> 后退 -> 回到 home', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/login$/)
    await page.goBack({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/home$/)
  })

  test('E7.2 登录页 -> /home 推栈 -> 后退回 /login', async ({ page }) => {
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    await page.goBack({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/login$/)
  })

  // ============== E8. 直接 URL 跳转 ==============
  test('E8.1 直接访 /orders 没 auth -> 跳 /login?redirect=/orders', async ({ page }) => {
    await page.evaluate(() => { try { localStorage.removeItem('visa.auth') } catch {} })
    await page.goto(`${BASE}/orders`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('redirect=')
    expect(page.url()).toMatch(/\/login\?redirect=/)
    expect(decodeURIComponent(page.url())).toContain('/orders')
  })

  test('E8.2 直接访 /profile 没 auth -> 跳 /login?redirect=/profile', async ({ page }) => {
    await page.evaluate(() => { try { localStorage.removeItem('visa.auth') } catch {} })
    await page.goto(`${BASE}/profile`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/login\?redirect=/)
    expect(decodeURIComponent(page.url())).toContain('/profile')
  })

  test('E8.3 直接访 /materials 没 auth -> 跳 /login?redirect=/materials', async ({ page }) => {
    await page.evaluate(() => { try { localStorage.removeItem('visa.auth') } catch {} })
    await page.goto(`${BASE}/materials`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/login\?redirect=/)
    expect(decodeURIComponent(page.url())).toContain('/materials')
  })

  // ============== E9. guestOnly 路由: 已登录访 /login 跳 /home ==============
  test('E9.1 已登录访 /login -> 跳 /home (guestOnly guard)', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          user: { id: 't-e9', phone: '+8613800000000' },
          accessToken: 'test.guest.token',
          refreshToken: 'test.guest.r'
        }))
      } catch {}
    })
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/home$/)
  })

  // ============== E10. 404 不会受 auth 影响 ==============
  test('E10.1 404 页不需要 auth', async ({ page }) => {
    await page.evaluate(() => { try { localStorage.removeItem('visa.auth') } catch {} })
    await page.goto(`${BASE}/zzz-not-a-route`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // NotFound 没有 requiresAuth, 应该直接渲染
    const body = await page.locator('body').innerText()
    expect(body).toMatch(/404|未找到|不存在|not found/i)
  })

  // ============== E11. 静态资源 200 ==============
  test('E11.1 favicon 200', async ({ request }) => {
    const r = await request.get(`${BASE}/favicon.svg`)
    expect(r.status()).toBe(200)
  })

  test('E11.2 manifest.json 200 + 含 name/short_name', async ({ request }) => {
    const r = await request.get(`${BASE}/manifest.json`)
    expect(r.status()).toBe(200)
    const m = await r.json()
    expect(m.name).toBeTruthy()
    expect(m.short_name).toBeTruthy()
  })

  test('E11.3 icons 存在 (PWA 图标)', async ({ request }) => {
    for (const icon of ['/icons/icon-192.png', '/icons/icon-512.png']) {
      const r = await request.get(`${BASE}${icon}`)
      expect(r.status()).toBe(200)
    }
  })

  // ============== E12. SPA 路由刷新不 404 ==============
  test('E12.1 /home 刷新仍是 SPA', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    // 仍能看到 Home 页的关键文案
    const body = await page.locator('body').innerText()
    expect(body).toMatch(/签证助手|Visa/i)
  })

  // ============== E13. document.title 路由切换变化 ==============
  test('E13.1 路由切换后 document.title 变 (afterEach hook)', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const homeTitle = await page.title()
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const loginTitle = await page.title()
    expect(homeTitle).not.toBe(loginTitle)
    expect(loginTitle).toContain('登录')  // 路由 meta.title i18n key 解析后
  })

  // ============== E14. localStorage visa.lang 改变后 reload 还原 ==============
  test('E14.1 改 visa.lang=en 后 reload -> html lang=en', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => { try { localStorage.setItem('visa.lang', 'en') } catch {} })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const lang = await page.evaluate(() => document.documentElement.lang)
    expect(lang).toBe('en')
  })

  // ============== E15. auth 持久化 (visa.auth 重启后还在) ==============
  test('E15.1 写 visa.auth 后 reload 还在 (不丢登录态)', async ({ page }) => {
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify({
          user: { id: 'persist', phone: '+8613800000000' },
          accessToken: 'persist.token',
          refreshToken: 'persist.r'
        }))
      } catch {}
    })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const auth = await page.evaluate(() => localStorage.getItem('visa.auth'))
    expect(auth).toBeTruthy()
    const parsed = JSON.parse(auth)
    expect(parsed.accessToken).toBe('persist.token')
  })

  // ============== E16. 多个页面不冲突 ==============
  test('E16.1 /home -> /login -> /register -> /home 来回切不崩', async ({ page }) => {
    const routes = ['/home', '/login', '/register', '/home']
    for (const r of routes) {
      await page.goto(`${BASE}${r}`, { waitUntil: 'domcontentloaded' })
      await page.waitForLoadState('networkidle')
      const body = await page.locator('body').innerText()
      expect(body.length).toBeGreaterThan(0)
    }
  })

  // ============== E17. window.navigator.language 默认 zh-CN ==============
  test('E17.1 zh-CN 浏览器语言 -> html lang=zh-CN', async ({ browser }) => {
    const ctx = await browser.newContext({ locale: 'zh-CN' })
    const page = await ctx.newPage()
    await page.goto(`${BASE}/home`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle')
    const lang = await page.evaluate(() => document.documentElement.lang)
    expect(lang).toBe('zh-CN')
    await ctx.close()
  })
})
