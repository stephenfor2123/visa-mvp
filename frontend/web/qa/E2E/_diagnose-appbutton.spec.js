/**
 * DIAGNOSE — 找 OrderNew.vue submit 按钮 click 链断裂点
 * 一次性诊断脚本,不写断言,只输出 console + network。
 * 跑法:
 *   cd frontend/web && npx playwright test --config qa/qa-playwright.config.cjs qa/E2E/_diagnose-appbutton.spec.js --reporter=list
 */
import { test, expect } from '@playwright/test'

const MATERIAL_URL = /\/api\/v2\/materials\/(.+)$/
const ORDERS_URL = /\/api\/v2\/orders$/

function makePassportEnvelope(materialId) {
  return {
    code: '1000',
    message: 'OK',
    data: {
      material_id: materialId,
      id: materialId,
      material_type: 'passport',
      file_name: 'passport_demo.jpg',
      file_size: 412 * 1024,
      mime_type: 'image/jpeg',
      thumbnail_url: 'https://placehold.co/200x240/EAF0FE/2D5BFF?text=PASSPORT',
      ocr_status: 'done',
      ocr_result: {
        passport_no: 'E12345678',
        surname: 'SANTOSO',
        given_name: 'BUDI',
        sex: 'M',
        dob: '1990-05-12',
        nationality: 'ID',
        expiry: '2031-08-22'
      },
      created_at: '2026-06-11T00:00:00Z'
    }
  }
}

test('DIAGNOSE — submit click chain', async ({ page }) => {
  // 1) stub materials 让 OCR 预填生效
  await page.route(MATERIAL_URL, async (route) => {
    const url = route.request().url()
    const matId = url.split('/').pop().split('?')[0]
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(makePassportEnvelope(matId))
    })
  })

  // 2) stub POST /orders 接收并返 envelope
  let ordersCalls = 0
  await page.route(ORDERS_URL, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    ordersCalls += 1
    const body = JSON.parse(route.request().postData() || '{}')
    console.log('[stub] POST /api/v2/orders received:', JSON.stringify(body?.applicant_data || {}).slice(0, 200))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: '1000',
        message: 'OK',
        data: {
          order_no: 'V2-20260611-999999',
          user_id: 'u_demo',
          destination_id: body?.destination_id || 1,
          visa_type: body?.visa_type || 'tourism',
          status: 'created',
          total_amount: 0,
          currency: 'USD',
          material_ids: body?.material_ids || [],
          applicant_data: body?.applicant_data || {},
          destination_url: null,
          rpa_task_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      })
    })
  })

  // 3) 监听所有 console / pageerror / request / response
  page.on('console', (msg) => console.log(`[browser ${msg.type()}]`, msg.text()))
  page.on('pageerror', (e) => console.log('[browser pageerror]', e.message))
  page.on('request', (req) => {
    if (req.url().includes('/api/')) console.log(`[req] ${req.method()} ${req.url()}`)
  })
  page.on('response', (res) => {
    if (res.url().includes('/api/')) console.log(`[res] ${res.status()} ${res.url()}`)
  })

  // 4) 注入登录态
  await page.addInitScript(() => {
    localStorage.setItem('visa.lang', 'zh-CN')
    localStorage.setItem('visa.auth', JSON.stringify({
      accessToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.mock',
      refreshToken: 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1X2RlbW8ifQ.refresh',
      user: { id: 'u_demo', phoneCountry: '+86', phone: '13800000000', nickname: 'demo', languagePref: 'zh-CN', status: 'active', createdAt: '2026-06-11T00:00:00Z' }
    }))
  })
  await page.goto('/login', { waitUntil: 'domcontentloaded' })

  // 5) 访问 /orders/new
  await page.goto('/orders/new?material_ids=mat_diag&country=US&visa_type=tourism')
  await expect(page.getByTestId('ordernew-surname')).toHaveValue('SANTOSO', { timeout: 10_000 })

  // 6) attach listener:看 native button click 是否冒泡 + AppButton 上是否有 Vue listener
  const probe = await page.evaluate(() => {
    const btn = document.querySelector('button[data-testid="ordernew-submit"]')
    if (!btn) return { error: 'no submit button found' }
    const result = {
      tagName: btn.tagName,
      className: btn.className,
      disabled: btn.disabled,
      textContent: btn.textContent.trim().slice(0, 60),
      hasOnclickAttr: !!btn.onclick,
      attrs: Array.from(btn.attributes).map((a) => `${a.name}=${a.value.slice(0, 40)}`),
      // Vue 内部:__vueParentComponent 在 production build 是 null,但 dev build 有
      hasVueInternal: !!btn.__vueParentComponent,
      parentTag: btn.parentElement?.tagName,
      parentClass: btn.parentElement?.className,
      parentHasVueInternal: !!btn.parentElement?.__vueParentComponent,
      // 检查父级是否有 emit listener
      parentChildren: Array.from(btn.parentElement?.children || []).map((c) => c.tagName + '.' + c.className)
    }
    // attach one-shot listener for next click
    let nativeClicked = 0
    let parentClicked = 0
    btn.addEventListener('click', () => { nativeClicked += 1 }, { capture: false })
    btn.parentElement?.addEventListener('click', () => { parentClicked += 1 }, { capture: false })
    // 保存到 window 便于外部断言
    window.__diagProbe = { nativeClicked, parentClicked, btn }
    return result
  })
  console.log('[probe] DOM state:', JSON.stringify(probe, null, 2))

  // 7) 切到 emergency tab + 填字段
  await page.getByTestId('ordernew-tab-emergency').click()
  await page.getByTestId('ordernew-emergency-name').fill('SANTOSO ANI')
  await page.getByTestId('ordernew-emergency-phone').fill('+6281234567890')
  await page.getByTestId('ordernew-emergency-relation').selectOption('spouse')

  // 8) 真实 Playwright click (actionability 完整链)
  console.log('[action] calling btn.click() (real Playwright actionability)...')
  await page.getByTestId('ordernew-submit').click({ timeout: 5_000 })
  console.log('[action] click() returned')

  // 9) 等 2s 看 POST 是否发出
  await page.waitForTimeout(2_000)

  // 10) 看 listener 状态 + 实际 orders stub 接收次数 + 当前 URL
  const after = await page.evaluate(() => {
    const probe = window.__diagProbe || {}
    return {
      nativeClicked: probe.nativeClicked,
      parentClicked: probe.parentClicked,
      url: location.pathname,
      fullUrl: location.href,
      btnStillExists: !!document.querySelector('button[data-testid="ordernew-submit"]')
    }
  })
  console.log('[after] state:', JSON.stringify(after, null, 2))
  console.log('[after] orders stub call count:', ordersCalls)
})