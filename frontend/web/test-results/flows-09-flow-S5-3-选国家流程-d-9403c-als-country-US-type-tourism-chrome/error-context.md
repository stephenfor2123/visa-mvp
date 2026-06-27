# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: flows/09-flow.spec.js >> S5.3 选国家流程 (/destinations → /materials) >> D15: 登录后 /destinations 渲染 → 点 US "立即申请" → 跳 /materials?country=US&type=tourism
- Location: tests/e2e/flows/09-flow.spec.js:237:3

# Error details

```
TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
=========================== logs ===========================
waiting for navigation until "load"
============================================================
```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e3]:
    - banner [ref=e4]:
      - link "Htex" [ref=e5] [cursor=pointer]:
        - /url: /home
        - generic "Htex" [ref=e6]:
          - img [ref=e7]:
            - generic [ref=e8]: Htex
      - navigation [ref=e9]:
        - button "我的申请" [ref=e11] [cursor=pointer]:
          - generic [ref=e12]: 我的申请
          - img [ref=e13]
      - generic [ref=e15]:
        - button "切换深色模式" [ref=e16] [cursor=pointer]:
          - img [ref=e17]
        - button "当前语言 简体中文,点击切换" [ref=e20] [cursor=pointer]:
          - generic [ref=e21]: 🇨🇳
          - generic [ref=e22]: 中文
          - img [ref=e23]
        - link "个人中心" [ref=e25] [cursor=pointer]:
          - /url: /profile
          - img [ref=e26]
        - button "退出登录" [ref=e29] [cursor=pointer]
    - main [ref=e30]:
      - heading "选择目的地" [level=1] [ref=e31]
      - paragraph [ref=e32]: V2 首批支持美国(US),其他 8 国 V3+ 开放
      - generic [ref=e33]:
        - article [ref=e34]:
          - generic [ref=e35]:
            - generic [ref=e37]: 🇬🇧
            - generic [ref=e38]: 🇬🇧
          - generic [ref=e39]:
            - generic [ref=e40]: 英国
            - generic [ref=e41]:
              - generic [ref=e42]: 旅游签
              - generic [ref=e43]: 学生签
              - generic [ref=e44]: 学生签
            - button "立即申请 →" [ref=e45] [cursor=pointer]
        - article [ref=e46]:
          - generic [ref=e47]:
            - img "法国" [ref=e48]
            - generic [ref=e49]: 🇫🇷
          - generic [ref=e50]:
            - generic [ref=e51]: 法国
            - generic [ref=e52]:
              - generic [ref=e53]: 旅游签
              - generic [ref=e54]: 学生签
              - generic [ref=e55]: 学生签
            - button "立即申请 →" [ref=e56] [cursor=pointer]
        - article [ref=e57]:
          - generic [ref=e58]:
            - generic [ref=e60]: 🇩🇪
            - generic [ref=e61]: 🇩🇪
          - generic [ref=e62]:
            - generic [ref=e63]: 德国
            - generic [ref=e64]:
              - generic [ref=e65]: 旅游签
              - generic [ref=e66]: 学生签
              - generic [ref=e67]: 学生签
            - button "立即申请 →" [ref=e68] [cursor=pointer]
        - article [ref=e69]:
          - generic [ref=e70]:
            - generic [ref=e72]: 🇮🇹
            - generic [ref=e73]: 🇮🇹
          - generic [ref=e74]:
            - generic [ref=e75]: 意大利
            - generic [ref=e76]:
              - generic [ref=e77]: 旅游签
              - generic [ref=e78]: 学生签
              - generic [ref=e79]: 学生签
            - button "立即申请 →" [ref=e80] [cursor=pointer]
        - article [ref=e81]:
          - generic [ref=e82]:
            - generic [ref=e84]: 🇪🇸
            - generic [ref=e85]: 🇪🇸
          - generic [ref=e86]:
            - generic [ref=e87]: 西班牙
            - generic [ref=e88]:
              - generic [ref=e89]: 旅游签
              - generic [ref=e90]: 学生签
              - generic [ref=e91]: 学生签
            - button "立即申请 →" [ref=e92] [cursor=pointer]
        - article [ref=e93]:
          - generic [ref=e94]:
            - generic [ref=e96]: 🇦🇺
            - generic [ref=e97]: 🇦🇺
          - generic [ref=e98]:
            - generic [ref=e99]: 澳大利亚
            - generic [ref=e100]:
              - generic [ref=e101]: 旅游签
              - generic [ref=e102]: 学生签
              - generic [ref=e103]: 学生签
            - button "立即申请 →" [ref=e104] [cursor=pointer]
        - article [ref=e105]:
          - generic [ref=e106]:
            - generic [ref=e108]: 🇺🇸
            - generic [ref=e109]: 🇺🇸
          - generic [ref=e110]:
            - generic [ref=e111]: US
            - generic [ref=e113]: 旅游签
            - button "立即申请 →" [active] [ref=e114] [cursor=pointer]
        - article [ref=e115]:
          - generic [ref=e116]:
            - generic [ref=e118]: 🇹🇭
            - generic [ref=e119]: 🇹🇭
          - generic [ref=e120]:
            - generic [ref=e121]: 泰国
            - generic [ref=e123]: 旅游签
            - generic [ref=e124]: 🔒 V3+ 即将开放
        - article [ref=e125]:
          - generic [ref=e126]:
            - generic [ref=e128]: 🇻🇳
            - generic [ref=e129]: 🇻🇳
          - generic [ref=e130]:
            - generic [ref=e131]: 越南
            - generic [ref=e133]: 旅游签
            - generic [ref=e134]: 🔒 V3+ 即将开放
        - article [ref=e135]:
          - generic [ref=e136]:
            - generic [ref=e138]: 🇸🇬
            - generic [ref=e139]: 🇸🇬
          - generic [ref=e140]:
            - generic [ref=e141]: 新加坡
            - generic [ref=e143]: 旅游签
            - generic [ref=e144]: 🔒 V3+ 即将开放
        - article [ref=e145]:
          - generic [ref=e146]:
            - generic [ref=e148]: 🇯🇵
            - generic [ref=e149]: 🇯🇵
          - generic [ref=e150]:
            - generic [ref=e151]: 日本
            - generic [ref=e152]:
              - generic [ref=e153]: 旅游签
              - generic [ref=e154]: 学生签
            - generic [ref=e155]: 🔒 V3+ 即将开放
        - article [ref=e156]:
          - generic [ref=e157]:
            - generic [ref=e159]: 🇰🇷
            - generic [ref=e160]: 🇰🇷
          - generic [ref=e161]:
            - generic [ref=e162]: 韩国
            - generic [ref=e163]:
              - generic [ref=e164]: 旅游签
              - generic [ref=e165]: 学生签
            - generic [ref=e166]: 🔒 V3+ 即将开放
        - article [ref=e167]:
          - generic [ref=e168]:
            - generic [ref=e170]: 🇲🇾
            - generic [ref=e171]: 🇲🇾
          - generic [ref=e172]:
            - generic [ref=e173]: 马来西亚
            - generic [ref=e175]: 旅游签
            - generic [ref=e176]: 🔒 V3+ 即将开放
  - generic [ref=e179]:
    - generic [ref=e180]: "[plugin:vite:vue] [vue/compiler-sfc] Unexpected keyword 'import'. (13:0) /Users/apple/Desktop/签证项目/frontend/web/src/views/Materials.vue 167| import { useToast } from '@/composables/useToast' 168| import { useAuthStore } from '@/stores/auth' 169| import { 170| import AppHeader from '@/components/AppHeader.vue' 171| uploadMaterial,"
    - generic [ref=e181]: /Users/apple/Desktop/签证项目/frontend/web/src/views/Materials.vue:13:0
    - generic [ref=e182]: "15 | :data-testid=\"`mat-tab-${tab.key}`\" 16 | role=\"tab\" 17 | :aria-selected=\"activeTab === tab.key\" | ^ 18 | @click=\"onTabClick(tab)\" 19 | >"
    - generic [ref=e183]: at constructor (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:365:19) at Parser.raise (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:6616:19) at Parser.checkReservedWord (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:12241:12) at Parser.parseImportSpecifier (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:14431:12) at Parser.parseNamedImportSpecifiers (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:14415:36) at Parser.parseImportSpecifiersAndAfter (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:14259:37) at Parser.parseImport (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:14252:17) at Parser.parseStatementContent (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:12893:27) at Parser.parseStatementLike (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:12784:17) at Parser.parseModuleItem (/Users/apple/Desktop/签证项目/frontend/web/node_modules/@babel/parser/lib/index.js:12761:17
    - generic [ref=e184]:
      - text: Click outside, press Esc key, or fix the code to dismiss.
      - text: You can also disable this overlay by setting
      - code [ref=e185]: server.hmr.overlay
      - text: to
      - code [ref=e186]: "false"
      - text: in
      - code [ref=e187]: vite.config.js
      - text: .
```

# Test source

```ts
  149 |     const submit = page.getByTestId('login-submit')
  150 |     await expect(submit).toBeEnabled()
  151 |   })
  152 | 
  153 |   test('D5: 登录带 ?redirect= 参数: 成功跳到 redirect 而非 /destinations', async ({ page, request }) => {
  154 |     const { phone } = await registerFreshUser(request)
  155 |     await page.goto('/login?redirect=/orders')
  156 |     await page.locator('[data-testid="login-country"]').selectOption(PHONE_COUNTRY)
  157 |     await page.locator('[data-testid="login-phone"] input').fill(phone)
  158 |     await page.locator('[data-testid="login-password"] input').fill(PASSWORD)
  159 |     await page.getByTestId('login-submit').click()
  160 |     // Login.vue:287 `const redirect = route.query.redirect || '/destinations'`
  161 |     await page.waitForURL(/\/orders$/, { timeout: 10_000 })
  162 |   })
  163 | 
  164 |   test('D6: 表单空时 submit click → 不跳走 (前端校验拦截)', async ({ page }) => {
  165 |     await page.goto('/login')
  166 |     await page.getByTestId('login-submit').click()
  167 |     await page.waitForTimeout(500)
  168 |     await expect(page).toHaveURL(/\/login$/)
  169 |   })
  170 | })
  171 | 
  172 | test.describe('S5.2 路由 guard 中间态 (Router beforeEach)', () => {
  173 |   test('D7: 未登录访 /orders → 跳 /login?redirect=/orders', async ({ page }) => {
  174 |     await page.goto('/orders')
  175 |     await page.waitForURL(/\/login/, { timeout: 5_000 })
  176 |     expect(page.url()).toMatch(/redirect=.+orders/)
  177 |   })
  178 | 
  179 |   test('D8: 未登录访 /orders/new → 跳 /login?redirect=/orders/new', async ({ page }) => {
  180 |     await page.goto('/orders/new')
  181 |     await page.waitForURL(/\/login/, { timeout: 5_000 })
  182 |     expect(page.url()).toMatch(/redirect=/)
  183 |   })
  184 | 
  185 |   test('D9: 未登录访 /materials → 跳 /login?redirect=/materials', async ({ page }) => {
  186 |     await page.goto('/materials')
  187 |     await page.waitForURL(/\/login/, { timeout: 5_000 })
  188 |     expect(page.url()).toMatch(/redirect=/)
  189 |   })
  190 | 
  191 |   test('D10: 未登录访 /profile → 跳 /login?redirect=/profile', async ({ page }) => {
  192 |     await page.goto('/profile')
  193 |     await page.waitForURL(/\/login/, { timeout: 5_000 })
  194 |     expect(page.url()).toMatch(/redirect=/)
  195 |   })
  196 | 
  197 |   test('D11: 未登录访 /destinations → 不跳 /login (页面公开)', async ({ page }) => {
  198 |     await page.goto('/destinations')
  199 |     await page.waitForTimeout(1000)
  200 |     // router/index.js:38 - Destinations 没有 requiresAuth meta
  201 |     await expect(page).toHaveURL(/\/destinations/)
  202 |   })
  203 | 
  204 |   test('D12: 未登录访 /home → 不跳 /login (页面公开)', async ({ page }) => {
  205 |     await page.goto('/home')
  206 |     await page.waitForTimeout(500)
  207 |     await expect(page).toHaveURL(/\/home/)
  208 |   })
  209 | 
  210 |   test('D13: 已登录访 /login → 跳 /home (guestOnly 守卫)', async ({ page }) => {
  211 |     // W19 fix: 不调真 API register (限流 + 慢), 直接 injectAuth 假 token 触发 isLoggedIn=true.
  212 |     // router guard 只检查 isLoggedIn = !!accessToken && !!user, 不验证 token 真假.
  213 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  214 |     await injectAuth(page, {
  215 |       accessToken: 'fake.token.d13',
  216 |       refreshToken: 'fake.r',
  217 |       user: { id: 't-d13', phone: '+8613800000013' }
  218 |     })
  219 |     await page.goto('/login')
  220 |     // router/index.js:152 guestOnly + isLoggedIn → /home
  221 |     await page.waitForURL(/\/home$/, { timeout: 5_000 })
  222 |   })
  223 | 
  224 |   test('D14: 已登录访 /register → 跳 /home (guestOnly 守卫)', async ({ page }) => {
  225 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  226 |     await injectAuth(page, {
  227 |       accessToken: 'fake.token.d14',
  228 |       refreshToken: 'fake.r',
  229 |       user: { id: 't-d14', phone: '+8613800000014' }
  230 |     })
  231 |     await page.goto('/register')
  232 |     await page.waitForURL(/\/home$/, { timeout: 5_000 })
  233 |   })
  234 | })
  235 | 
  236 | test.describe('S5.3 选国家流程 (/destinations → /materials)', () => {
  237 |   test('D15: 登录后 /destinations 渲染 → 点 US "立即申请" → 跳 /materials?country=US&type=tourism', async ({ page }) => {
  238 |     // fake auth 避免 registerFreshUser 限流
  239 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  240 |     await injectAuth(page, {
  241 |       accessToken: 'fake.token.d15',
  242 |       refreshToken: 'fake.r',
  243 |       user: { id: 't-d15', phone: '+8613800000015' }
  244 |     })
  245 |     await page.goto('/destinations', { waitUntil: 'networkidle' })
  246 |     const usApply = page.getByTestId('dest-apply-US')
  247 |     await usApply.waitFor({ state: 'visible', timeout: 15_000 })
  248 |     await usApply.click()
> 249 |     await page.waitForURL(/\/materials/, { timeout: 10_000 })
      |                ^ TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
  250 |     // Destinations.vue:88 router.push({ name: 'Materials', query: { country, type: 'tourism' } })
  251 |     expect(page.url()).toMatch(/country=US/)
  252 |     expect(page.url()).toMatch(/type=tourism/)
  253 |   })
  254 | 
  255 |   test('D16: /destinations 加载时 US 卡片显示 + JP 灰显', async ({ page }) => {
  256 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  257 |     await injectAuth(page, {
  258 |       accessToken: 'fake.token.d16',
  259 |       refreshToken: 'fake.r',
  260 |       user: { id: 't-d16', phone: '+8613800000016' }
  261 |     })
  262 |     await page.goto('/destinations', { waitUntil: 'networkidle' })
  263 |     await expect(page.getByTestId('dest-card-US')).toBeVisible({ timeout: 15_000 })
  264 |     await expect(page.getByTestId('dest-card-JP')).toBeVisible()
  265 |     // JP enabled=false → 没有 dest-apply-JP
  266 |     await expect(page.getByTestId('dest-apply-JP')).toHaveCount(0)
  267 |   })
  268 | 
  269 |   test('D17: 已登录访 /destinations 不要求 token (无需重新登录)', async ({ page }) => {
  270 |     // fake auth 避免 registerFreshUser 限流
  271 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  272 |     await injectAuth(page, {
  273 |       accessToken: 'fake.token.d17',
  274 |       refreshToken: 'fake.r',
  275 |       user: { id: 't-d17', phone: '+8613800000017' }
  276 |     })
  277 |     await page.goto('/destinations', { waitUntil: 'networkidle' })
  278 |     await expect(page).toHaveURL(/\/destinations/)
  279 |   })
  280 | })
  281 | 
  282 | test.describe('S5.4 /orders/new 流程 (3-tab 提交)', () => {
  283 |   test('D18: 登录后 /orders/new → 3 个 tab 按钮渲染', async ({ page, request }) => {
  284 |     // fake auth 避免 registerFreshUser 限流
  285 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  286 |     await injectAuth(page, {
  287 |       accessToken: 'fake.token.dX',
  288 |       refreshToken: 'fake.r',
  289 |       user: { id: 't-dX', phone: '+86138000000XX' }
  290 |     })
  291 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  292 |     await expect(page.getByTestId('ordernew-tab-basic')).toBeVisible()
  293 |     await expect(page.getByTestId('ordernew-tab-travel')).toBeVisible()
  294 |     await expect(page.getByTestId('ordernew-tab-emergency')).toBeVisible()
  295 |   })
  296 | 
  297 |   test('D19: /orders/new 默认在 basic tab,active 类正确', async ({ page, request }) => {
  298 |     // fake auth 避免 registerFreshUser 限流
  299 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  300 |     await injectAuth(page, {
  301 |       accessToken: 'fake.token.dX',
  302 |       refreshToken: 'fake.r',
  303 |       user: { id: 't-dX', phone: '+86138000000XX' }
  304 |     })
  305 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  306 |     const cls = await page.getByTestId('ordernew-tab-basic').getAttribute('class')
  307 |     expect(cls).toContain('on')
  308 |   })
  309 | 
  310 |   test('D20: 点 Basic tab → 验证 surname 字段 (surname/given_name/sex/dob/nationality/passport_no 必填)', async ({ page }) => {
  311 |     // fake auth + materials mock 避免 registerFreshUser 限流
  312 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  313 |       await route.fulfill({ status: 200, contentType: 'application/json',
  314 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  315 |     })
  316 |     await page.goto('/home', { waitUntil: 'load' })
  317 |     await injectAuth(page, {
  318 |       accessToken: 'fake.token.d20',
  319 |       refreshToken: 'fake.r',
  320 |       user: { id: 't-d20', phone: '+8613800000020' }
  321 |     })
  322 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  323 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  324 |     await expect(page.getByTestId('ordernew-surname')).toBeVisible()
  325 |     await expect(page.getByTestId('ordernew-given-name')).toBeVisible()
  326 |   })
  327 | 
  328 |   test('D21: 切到 Travel tab → arrival_date / departure_date 字段可见', async ({ page }) => {
  329 |     // fake auth + materials mock 避免 registerFreshUser 限流
  330 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  331 |       await route.fulfill({ status: 200, contentType: 'application/json',
  332 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  333 |     })
  334 |     await page.goto('/home', { waitUntil: 'load' })
  335 |     await injectAuth(page, {
  336 |       accessToken: 'fake.token.d21',
  337 |       refreshToken: 'fake.r',
  338 |       user: { id: 't-d21', phone: '+8613800000021' }
  339 |     })
  340 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  341 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  342 |     await page.getByTestId('ordernew-tab-travel').click()
  343 |     await page.waitForTimeout(300)
  344 |     await expect(page.getByTestId('ordernew-arrival')).toBeVisible()
  345 |     await expect(page.getByTestId('ordernew-departure')).toBeVisible()
  346 |   })
  347 | 
  348 |   test('D22: 切到 Travel → destination 字段 select 渲染 + 默认选 US (auto-fill)', async ({ page }) => {
  349 |     // fake auth + materials mock 避免 registerFreshUser 限流
```