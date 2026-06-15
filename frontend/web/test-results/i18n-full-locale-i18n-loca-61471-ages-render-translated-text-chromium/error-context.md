# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: i18n-full-locale.spec.js >> i18n locale=zh-CN auth-pages render translated text
- Location: tests/e2e/i18n-full-locale.spec.js:125:3

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: locator('body')
Timeout: 10000ms
- Expected substring  - 1
+ Received string     + 5

- 基本信息
+
+     V签证助手中文ENIDVI👋 i18n🇺🇸— · 旅游签← 返回材料•基本•旅行•紧急 加载中...
+     
+   
+

Call log:
  - Expect "toContainText" with timeout 10000ms
  - waiting for locator('body')
    24 × locator resolved to <body>…</body>
       - unexpected value "
    V签证助手中文ENIDVI👋 i18n🇺🇸— · 旅游签← 返回材料•基本•旅行•紧急 加载中...
    
  
"

```

```yaml
- banner:
  - link "V 签证助手":
    - /url: /home
  - button "中文"
  - button "EN"
  - button "ID"
  - button "VI"
  - text: 👋 i18n
- main:
  - text: 🇺🇸
  - heading "— · 旅游签" [level=1]
  - button "← 返回材料"
  - tablist:
    - tab "• 基本" [selected]
    - tab "• 旅行"
    - tab "• 紧急"
  - text: 加载中...
```

# Test source

```ts
  56  |     'zh-CN': '签证助手',
  57  |     'en':    'Visa Helper',
  58  |     'id-ID': 'Asisten Visa',
  59  |     'vi-VN': 'Trợ lý Visa'
  60  |   }
  61  | }
  62  | 
  63  | const ROUTES_GUEST = {
  64  |   Home:     '/home',
  65  |   Login:    '/login',
  66  |   Register: '/register'
  67  | }
  68  | 
  69  | const ROUTES_AUTH = {
  70  |   OrderNew:    '/orders/new',
  71  |   OrderDetail: '/orders/TEST-LOCALE-CHECK'
  72  | }
  73  | 
  74  | for (const locale of SUPPORTED) {
  75  |   test(`i18n locale=${locale} home.* keys render (W10-2 13 keys)`, async ({ page }) => {
  76  |     // W10-2: 14 home.* keys must render in body, NOT raw 'home.hero.sub' etc.
  77  |     // Verifier feedback attempt 4/5: must cover 4 features × {title, desc} = 8 keys
  78  |     // not just 'home.features.materials' — that substring was found in body
  79  |     // when nested keys were missing.
  80  |     await page.addInitScript((lang) => {
  81  |       try { localStorage.setItem('visa.lang', lang) } catch {}
  82  |       try { localStorage.removeItem('visa.auth') } catch {}
  83  |     }, locale)
  84  |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  85  |     // Wait for Vue to render — domcontentloaded fires before Vue finishes mounting
  86  |     await page.waitForLoadState('networkidle')
  87  |     await page.waitForSelector('.hero', { timeout: 10000 })
  88  |     const body = await page.locator('body').innerText()
  89  |     // Must contain the locale-specific translated string AND must NOT contain raw key
  90  |     const expected = HOME_SPOT[locale]
  91  |     expect(body).toContain(expected)
  92  |     // Hero (3 keys)
  93  |     expect(body).not.toContain('home.hero.sub')
  94  |     expect(body).not.toContain('home.hero.explore_cta')
  95  |     expect(body).not.toContain('home.hero.chip_meta')
  96  |     // Features section (2 keys)
  97  |     expect(body).not.toContain('home.features.title')
  98  |     expect(body).not.toContain('home.features.subtitle')
  99  |     // 4 features × {title, desc} = 8 keys (path-aligned A: nested structure)
  100 |     expect(body).not.toContain('home.features.materials.title')
  101 |     expect(body).not.toContain('home.features.materials.desc')
  102 |     expect(body).not.toContain('home.features.insurance.title')
  103 |     expect(body).not.toContain('home.features.insurance.desc')
  104 |     expect(body).not.toContain('home.features.templates.title')
  105 |     expect(body).not.toContain('home.features.templates.desc')
  106 |     expect(body).not.toContain('home.features.affiliate.title')
  107 |     expect(body).not.toContain('home.features.affiliate.desc')
  108 |   })
  109 | 
  110 |   test(`i18n locale=${locale} guest-pages render translated text`, async ({ page }) => {
  111 |     // Seed only the language (no auth), so Home / Login / Register are reachable.
  112 |     await page.addInitScript((lang) => {
  113 |       try { localStorage.setItem('visa.lang', lang) } catch {}
  114 |       try { localStorage.removeItem('visa.auth') } catch {}
  115 |     }, locale)
  116 | 
  117 |     for (const [pageName, route] of Object.entries(ROUTES_GUEST)) {
  118 |       await page.goto(route, { waitUntil: 'domcontentloaded' })
  119 |       await page.waitForLoadState('networkidle')
  120 |       const expected = SPOT_CHECKS[pageName][locale]
  121 |       await expect(page.locator('body')).toContainText(expected, { timeout: 10000 })
  122 |     }
  123 |   })
  124 | 
  125 |   test(`i18n locale=${locale} auth-pages render translated text`, async ({ page }) => {
  126 |     // Seed language + a fake auth payload so OrderNew / OrderDetail pass the guard.
  127 |     // auth.js hydrate() reads this exact JSON shape.
  128 |     await page.addInitScript((lang) => {
  129 |       try { localStorage.setItem('visa.lang', lang) } catch {}
  130 |       try {
  131 |         localStorage.setItem('visa.auth', JSON.stringify({
  132 |           user: { id: 't-i18n', phone: '+8613800000000', nickname: 'i18n' },
  133 |           accessToken: 'test.i18n.token',
  134 |           refreshToken: 'test.i18n.refresh'
  135 |         }))
  136 |       } catch {}
  137 |     }, locale)
  138 | 
  139 |     // W10-2: Mock /api/v2/destinations so OrderNew can render without backend.
  140 |     // OrderNew needs destination data to render the form section title "基本信息".
  141 |     await page.route('**/api/v2/destinations*', (route) => {
  142 |       route.fulfill({
  143 |         status: 200,
  144 |         contentType: 'application/json',
  145 |         body: JSON.stringify([
  146 |           { id: 1, country_code: 'US', country_name: 'United States', visa_types: ['tourism', 'student'], enabled: true },
  147 |           { id: 2, country_code: 'JP', country_name: 'Japan', visa_types: ['tourism', 'student'], enabled: false }
  148 |         ])
  149 |       })
  150 |     })
  151 | 
  152 |     for (const [pageName, route] of Object.entries(ROUTES_AUTH)) {
  153 |       await page.goto(route, { waitUntil: 'domcontentloaded' })
  154 |       await page.waitForLoadState('networkidle')
  155 |       // W10-2: Wait for form to load (OrderNew loads destinations async)
> 156 |       await expect(page.locator('body')).toContainText(SPOT_CHECKS[pageName][locale], { timeout: 10000 })
      |                                          ^ Error: expect(locator).toContainText(expected) failed
  157 |     }
  158 |   })
  159 | }
  160 | 
```