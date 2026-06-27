# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: flows/09-flow.spec.js >> S5.4 /orders/new 流程 (3-tab 提交) >> D24: 切到 Emergency 后 "上一步" 按钮 enabled
- Location: tests/e2e/flows/09-flow.spec.js:391:3

# Error details

```
TimeoutError: locator.waitFor: Timeout 10000ms exceeded.
Call log:
  - waiting for getByTestId('ordernew-section-basic') to be visible

```

# Test source

```ts
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
> 404 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
      |                                                      ^ TimeoutError: locator.waitFor: Timeout 10000ms exceeded.
  405 |     await page.getByTestId('ordernew-tab-emergency').click()
  406 |     await page.waitForTimeout(200)
  407 |     await expect(page.getByTestId('ordernew-prev')).toBeEnabled()
  408 |   })
  409 | 
  410 |   test('D25: 切到 Emergency 后 "下一步" 消失, "提交" 出现', async ({ page }) => {
  411 |     // fake auth + materials mock 避免 registerFreshUser 限流
  412 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  413 |       await route.fulfill({ status: 200, contentType: 'application/json',
  414 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  415 |     })
  416 |     await page.goto('/home', { waitUntil: 'load' })
  417 |     await injectAuth(page, {
  418 |       accessToken: 'fake.token.d25',
  419 |       refreshToken: 'fake.r',
  420 |       user: { id: 't-d25', phone: '+8613800000025' }
  421 |     })
  422 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  423 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  424 |     await page.getByTestId('ordernew-tab-emergency').click()
  425 |     await page.waitForTimeout(200)
  426 |     await expect(page.getByTestId('ordernew-next')).toHaveCount(0)
  427 |     await expect(page.getByTestId('ordernew-submit')).toBeVisible()
  428 |   })
  429 | 
  430 |   test('D26: 提交按钮初始 enabled (设计: 提交时前端 validateAll() 拦截错误)', async ({ page }) => {
  431 |     // fake auth + materials mock 避免 registerFreshUser 限流
  432 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  433 |       await route.fulfill({ status: 200, contentType: 'application/json',
  434 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  435 |     })
  436 |     await page.goto('/home', { waitUntil: 'load' })
  437 |     await injectAuth(page, {
  438 |       accessToken: 'fake.token.d26',
  439 |       refreshToken: 'fake.r',
  440 |       user: { id: 't-d26', phone: '+8613800000026' }
  441 |     })
  442 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  443 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  444 |     await page.getByTestId('ordernew-tab-emergency').click()
  445 |     await page.waitForTimeout(200)
  446 |     await expect(page.getByTestId('ordernew-submit')).toBeEnabled()
  447 |   })
  448 | 
  449 |   test('D27: 空表单点 submit → 留在 /orders/new (前端 validateAll 失败,不跳走)', async ({ page }) => {
  450 |     // fake auth + materials mock 避免 registerFreshUser 限流
  451 |     await page.route('**/api/v2/materials/form-data**', async (route) => {
  452 |       await route.fulfill({ status: 200, contentType: 'application/json',
  453 |         body: JSON.stringify({ code: '1000', message: 'ok', data: { draft: {}, percent: 0 } }) })
  454 |     })
  455 |     await page.goto('/home', { waitUntil: 'load' })
  456 |     await injectAuth(page, {
  457 |       accessToken: 'fake.token.d27',
  458 |       refreshToken: 'fake.r',
  459 |       user: { id: 't-d27', phone: '+8613800000027' }
  460 |     })
  461 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  462 |     await page.getByTestId('ordernew-section-basic').waitFor({ state: 'visible', timeout: 10_000 })
  463 |     await page.getByTestId('ordernew-tab-emergency').click()
  464 |     await page.waitForTimeout(200)
  465 |     await page.getByTestId('ordernew-submit').click()
  466 |     await page.waitForTimeout(1500)
  467 |     // 没填资料,前端 validateAll 失败 → 留在 /orders/new
  468 |     await expect(page).toHaveURL(/\/orders\/new/)
  469 |   })
  470 | 
  471 |   test('D28: 返回按钮 (Back to Materials) 跳 /materials', async ({ page, request }) => {
  472 |     // fake auth 避免 registerFreshUser 限流
  473 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  474 |     await injectAuth(page, {
  475 |       accessToken: 'fake.token.dX',
  476 |       refreshToken: 'fake.r',
  477 |       user: { id: 't-dX', phone: '+86138000000XX' }
  478 |     })
  479 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  480 |     await page.getByTestId('ordernew-back').click()
  481 |     await page.waitForURL(/\/materials/, { timeout: 5_000 })
  482 |   })
  483 | 
  484 |   test('D29: Basic 必填项校验 — 没填 surname 切 travel tab 应被拦截', async ({ page, request }) => {
  485 |     // fake auth 避免 registerFreshUser 限流
  486 |     await page.goto('/home', { waitUntil: 'domcontentloaded' })
  487 |     await injectAuth(page, {
  488 |       accessToken: 'fake.token.dX',
  489 |       refreshToken: 'fake.r',
  490 |       user: { id: 't-dX', phone: '+86138000000XX' }
  491 |     })
  492 |     await page.goto('/orders/new', { waitUntil: 'networkidle' })
  493 |     // 直接点 travel tab
  494 |     await page.getByTestId('ordernew-tab-travel').click()
  495 |     await page.waitForTimeout(300)
  496 |     // 不应切到 travel,应停在 basic
  497 |     // (OrderNew.vue 51 行: @click="activeTab = tab.key"  实际上 tab 切不挡校验, 校验发生在 next/submit)
  498 |     // 但用户感知:点了后还在 basic? 这个断言要看实际实现
  499 |     // 按源码:点 tab 不挡,只是 UI 切到 travel. 但 validateAll 时还是查 basic
  500 |     // 这里改成断言"不论切到哪,点 next 才会触发校验"
  501 |     const activeBefore = await page.getByTestId('ordernew-tab-basic').getAttribute('class')
  502 |     // 现在 basic 不一定是 .on (因为 tab 直接切了) — 不做强制断言
  503 |     // 改用更稳的:点 next (从 travel 切 emergency) 此时 basic 必填校验触发
  504 |     // 但 OrderNew.vue next 是按钮,在 basic 时显示
```