/**
 * S6.4 (W41) E2E — Header dropdown 申请人列表 + /orders/new 一键导入
 *
 * 覆盖 3 个核心路径:
 *   D1: 登录后头部"我的申请"菜单: 无订单 → 显示"暂无申请人"
 *   D2: 登录后 + 已有订单(创建 N 单) → 菜单显示去重后的申请人姓名,纯展示无跳转
 *   D3: /orders/new 选完国家 → 一键导入按钮可见 → 弹窗 → 选申请人 → 字段预填
 */
import { test, expect } from '@playwright/test'

// 强制走 vite dev 5173 (workflow 起 vite 自带 /api 反代)
test.use({ baseURL: process.env.PW_BASE_URL || 'http://127.0.0.1:5173' })

// 强制 zh-CN
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('visa.lang', 'zh-CN') } catch (e) {}
  })
})

const PHONE_COUNTRY = '+86'
const PASSWORD = 'Test1234'

function uniqueId() {
  return Date.now().toString().slice(-8) + Math.floor(Math.random() * 10000).toString().padStart(4, '0')
}

async function postWithRetry(request, url, data, maxRetries = 5) {
  let lastRes
  for (let i = 0; i < maxRetries; i++) {
    lastRes = await request.post(url, { data })
    if (lastRes.status() < 400) return lastRes
    await new Promise((r) => setTimeout(r, 500 + i * 800))
  }
  return lastRes
}

// W41: use email+username register (this backend doesn't have /auth/send-code)
async function registerFreshUser(request) {
  const id = uniqueId()
  const username = `u${id}`
  const email = `${id}@test.local`
  await postWithRetry(
    request,
    'http://127.0.0.1:8000/api/v2/auth/register',
    { username, email, password: PASSWORD, language_pref: 'zh-CN' }
  )
  return { username, email }
}

async function loginAndGetAuth(request, email) {
  const res = await postWithRetry(
    request,
    'http://127.0.0.1:8000/api/v2/auth/login',
    { account: email, password: PASSWORD }
  )
  expect(res.status()).toBe(200)
  const body = await res.json()
  return {
    accessToken: body.data.access_token,
    refreshToken: body.data.refresh_token,
    user: body.data.user
  }
}

async function injectAuth(page, auth) {
  // 1) 走到任意页面让 origin 生效(localStorage 是 per-origin)
  await page.goto('/login')
  // 2) 写 localStorage
  await page.evaluate((d) => {
    localStorage.setItem('visa.auth', JSON.stringify(d))
  }, auth)
  // 3) reload 让 AppHeader.onMounted 里 auth.hydrate() 拿到 token,
  //    否则首次 mount 时 hydrate 已经在 store 初始化之前跑过了
  await page.reload({ waitUntil: 'networkidle' })
}

/**
 * Create an order via the real API. Returns the order_no.
 * Requires at least 1 material uploaded (API enforces material_ids.length >= 1).
 */
async function createOrder(request, token, applicant) {
  // Upload a fake material
  const jpegBytes = Buffer.from([
    0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00
  ])
  const upload = await request.post('http://127.0.0.1:8000/api/v2/materials/upload', {
    multipart: {
      file: {
        name: 'passport.jpg',
        mimeType: 'image/jpeg',
        buffer: jpegBytes
      },
      material_type: 'passport'
    },
    headers: { Authorization: `Bearer ${token}` }
  })
  expect(upload.status()).toBe(201)
  const materialId = (await upload.json()).data.material.id

  // Seed destination US
  // (assume existing test seed; otherwise create)
  const dest = await request.get('http://127.0.0.1:8000/api/v2/destinations')
  let destId = null
  if (dest.ok()) {
    const list = (await dest.json()).data || []
    const us = list.find((d) => d.country_code === 'US' && d.enabled)
    if (us) destId = us.id
  }
  if (!destId) {
    // Fallback: destination_id=1 (most test seeds start at 1)
    destId = 1
  }

  const create = await request.post('http://127.0.0.1:8000/api/v2/orders', {
    data: {
      destination_id: destId,
      visa_type: 'tourism',
      material_ids: [materialId],
      applicant_data: applicant
    },
    headers: { Authorization: `Bearer ${token}` }
  })
  expect(create.status(), `create order failed: ${await create.text()}`).toBe(201)
  return (await create.json()).data.order_no
}


// ============================================================
// D1: 头部菜单空态
// ============================================================
test.describe('W41 D1: 头部"我的申请"菜单 — 无订单时空态', () => {
  test('D1: 新用户登录后打开菜单,顶部申请人区显示"暂无申请人",底部 3 个工具入口正常', async ({ page, request }) => {
    const { email } = await registerFreshUser(request)
    const auth = await loginAndGetAuth(request, email)

    await injectAuth(page, auth)
    await page.goto('/home', { waitUntil: 'networkidle' })

    // Home.vue 用 scope="home"
    // 点开"我的申请"菜单
    await page.getByTestId('home-orders-trigger').click()
    await expect(page.getByTestId('home-orders-panel')).toBeVisible()

    // 顶部:申请人空态
    await expect(page.getByTestId('home-orders-applicants-empty')).toBeVisible()
    await expect(page.getByTestId('home-orders-applicants-empty')).toContainText('暂无申请人')

    // 底部:3 个工具入口 (申请材料按需求已砍掉,所以不应该出现)
    await expect(page.getByTestId('home-orders-all')).toBeVisible()
    await expect(page.getByTestId('home-orders-new')).toBeVisible()
    await expect(page.getByTestId('home-orders-profile')).toBeVisible()
    await expect(page.getByTestId('home-orders-materials')).toHaveCount(0)
  })
})


// ============================================================
// D2: 头部菜单有数据
// ============================================================
test.describe('W41 D2: 头部"我的申请"菜单 — 有订单时显示申请人姓名', () => {
  test('D2: 用户创建 3 单 (2 张三 / 1 李四) → 菜单显示 2 个申请人,纯姓名,无点击跳转', async ({ page, request }) => {
    const { email } = await registerFreshUser(request)
    const auth = await loginAndGetAuth(request, email)
    const token = auth.accessToken

    // 创建 3 个订单: 张三 x2 + 李四 x1
    await createOrder(request, token, { surname: '张', given_name: '三', passport_no: 'E11111' })
    await createOrder(request, token, { surname: '张', given_name: '三', passport_no: 'E11111' })
    await createOrder(request, token, { surname: '李', given_name: '四', passport_no: 'E22222' })

    await injectAuth(page, auth)
    await page.goto('/home', { waitUntil: 'networkidle' })

    // 点开"我的申请"菜单
    await page.getByTestId('home-orders-trigger').click()
    await expect(page.getByTestId('home-orders-panel')).toBeVisible()

    // 顶部:应该看到 2 个申请人容器
    await expect(page.getByTestId('home-orders-applicants')).toBeVisible()

    // 容器里应该有 张三 + 李四 两行
    const list = page.getByTestId('home-orders-applicants')
    await expect(list).toContainText('张三')
    await expect(list).toContainText('李四')

    // 必须是 <div role="presentation">, 不挂 href / router-link / click
    const items = await list.locator('[data-testid^="home-orders-applicant-app_"]').all()
    expect(items.length).toBe(2)

    for (const item of items) {
      const tagName = await item.evaluate((el) => el.tagName)
      expect(tagName).toBe('DIV')  // 不是 <a>
      const href = await item.getAttribute('href')
      expect(href).toBeNull()
    }

    // 点菜单外面会自动关闭(不是跳走)
    await page.locator('body').click({ position: { x: 10, y: 10 } })
    await expect(page.getByTestId('home-orders-panel')).toBeHidden()
    // 确认还在 /home, 没跳
    await expect(page).toHaveURL(/\/home/)
  })
})


// ============================================================
// D3: /orders/new 一键导入
// ============================================================
test.describe('W41 D3: /orders/new 一键导入', () => {
  test('D3: 用户已有 2 个申请人订单 → /orders/new 显示一键导入 → 选李四 → 字段预填', async ({ page, request }) => {
    const { email } = await registerFreshUser(request)
    const auth = await loginAndGetAuth(request, email)
    const token = auth.accessToken

    // 创建 2 个不同申请人
    await createOrder(request, token, { surname: '张', given_name: '三', passport_no: 'E11111' })
    await createOrder(request, token, { surname: '李', given_name: '四', passport_no: 'E22222' })

    await injectAuth(page, auth)

    // 进 /orders/new (指定 country=US, 必填字段都已经预填)
    await page.goto('/orders/new?country=US&visa_type=tourism', { waitUntil: 'networkidle' })

    // 等 watcher 触发申请人列表拉取
    // 一键导入按钮必须可见
    await expect(page.getByTestId('ordernew-one-click-import')).toBeVisible({ timeout: 10_000 })

    // 点开 → 弹窗
    await page.getByTestId('ordernew-one-click-import').click()
    await expect(page.getByTestId('ordernew-applicant-picker')).toBeVisible()

    // 弹窗里应该看到 2 个申请人 (张三 + 李四)
    const pickerList = page.getByTestId('ordernew-applicant-picker-list')
    await expect(pickerList).toBeVisible()
    await expect(pickerList).toContainText('张三')
    await expect(pickerList).toContainText('李四')

    // 选李四 (用稳定 id "app_李_四")
    await page.getByTestId('ordernew-applicant-picker-item-app_李_四').click()

    // 弹窗关闭
    await expect(page.getByTestId('ordernew-applicant-picker')).toBeHidden()

    // 表单字段被预填(activeTab 自动跳到 basic)
    // 后端聚合只返回 surname / given_name / passport_no,只填这 3 个基础字段
    const surname = await page.getByTestId('ordernew-surname').locator('input').inputValue()
    const given = await page.getByTestId('ordernew-given-name').locator('input').inputValue()
    const passport = await page.getByTestId('ordernew-passport-no').locator('input').inputValue()

    // surname + given 应该组合出 "李四"
    expect((surname + given).replace(/\s+/g, '')).toContain('李')
    expect((surname + given).replace(/\s+/g, '')).toContain('四')
    expect(passport).toContain('E22222')

    // 其他字段不应被预填(dob/sex/nationality 不在一键导入范围)
    const dob = await page.getByTestId('ordernew-dob').locator('input').inputValue()
    expect(dob).toBe('')
  })

  test('D3.2: 新用户(无订单)进 /orders/new → 一键导入按钮不显示', async ({ page, request }) => {
    const { email } = await registerFreshUser(request)
    const auth = await loginAndGetAuth(request, email)

    await injectAuth(page, auth)
    await page.goto('/orders/new?country=US&visa_type=tourism', { waitUntil: 'networkidle' })

    // 等一下,给 watcher 跑完
    await page.waitForTimeout(1500)

    // 一键导入按钮应该不在 DOM 里
    await expect(page.getByTestId('ordernew-one-click-import')).toHaveCount(0)
  })
})