# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: flows/09-flow.spec.js >> S5.4 /orders/new 流程 (3-tab 提交) >> D19: /orders/new 默认在 basic tab,active 类正确
- Location: tests/e2e/flows/09-flow.spec.js:297:3

# Error details

```
TimeoutError: locator.getAttribute: Timeout 10000ms exceeded.
Call log:
  - waiting for getByTestId('ordernew-tab-basic')

```

# Test source

```ts
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
  249 |     await page.waitForURL(/\/materials/, { timeout: 10_000 })
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
> 306 |     const cls = await page.getByTestId('ordernew-tab-basic').getAttribute('class')
      |                                                              ^ TimeoutError: locator.getAttribute: Timeout 10000ms exceeded.
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
  350 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  351 |       await route.fulfill({ status: 200, contentType: 'application/json',
  352 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  353 |     })
  354 |     await page.goto('/home', { waitUntil: 'load' })
  355 |     await injectAuth(page, {
  356 |       accessToken: 'fake.token.d22',
  357 |       refreshToken: 'fake.r',
  358 |       user: { id: 't-d22', phone: '+8613800000022' }
  359 |     })
  360 |     await page.goto('/orders/new?country=US&visa_type=tourism', { waitUntil: 'networkidle' })
  361 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  362 |     await page.getByTestId('ordernew-tab-travel').click()
  363 |     await page.waitForTimeout(300)
  364 |     const dest = page.getByTestId('ordernew-destination')
  365 |     await expect(dest).toBeVisible()
  366 |     const val = await dest.inputValue()
  367 |     expect(val).toBeTruthy() // 选 US 自动填了
  368 |   })
  369 | 
  370 |   test('D23: 切到 Emergency tab → emergency_name/phone/relation 字段可见', async ({ page }) => {
  371 |     // fake auth + materials mock 避免 registerFreshUser 限流
  372 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  373 |       await route.fulfill({ status: 200, contentType: 'application/json',
  374 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  375 |     })
  376 |     await page.goto('/home', { waitUntil: 'load' })
  377 |     await injectAuth(page, {
  378 |       accessToken: 'fake.token.d23',
  379 |       refreshToken: 'fake.r',
  380 |       user: { id: 't-d23', phone: '+8613800000023' }
  381 |     })
  382 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  383 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  384 |     await page.getByTestId('ordernew-tab-emergency').click()
  385 |     await page.waitForTimeout(300)
  386 |     await expect(page.getByTestId('ordernew-emergency-name')).toBeVisible()
  387 |     await expect(page.getByTestId('ordernew-emergency-phone')).toBeVisible()
  388 |     await expect(page.getByTestId('ordernew-emergency-relation')).toBeVisible()
  389 |   })
  390 | 
  391 |   test('D24: 切到 Emergency 后 "上一步" 按钮 enabled', async ({ page }) => {
  392 |     // fake auth + materials mock 避免 registerFreshUser 限流
  393 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  394 |       await route.fulfill({ status: 200, contentType: 'application/json',
  395 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  396 |     })
  397 |     await page.goto('/home', { waitUntil: 'load' })
  398 |     await injectAuth(page, {
  399 |       accessToken: 'fake.token.d24',
  400 |       refreshToken: 'fake.r',
  401 |       user: { id: 't-d24', phone: '+8613800000024' }
  402 |     })
  403 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  404 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  405 |     await page.getByTestId('ordernew-tab-emergency').click()
  406 |     await page.waitForTimeout(200)
```