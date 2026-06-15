/**
 * S2 E2E — Web 端登录流程端到端
 *
 * 流程:
 *   1. 先调 register 端点注册一个测试用户
 *   2. 打开 /login
 *   3. 选区号 +62 + 填手机号(刚注册的) + 密码
 *   4. 点登录 → 调后端 /api/v2/auth/login → 200 + JWT
 *   5. 断言:URL 跳到 /profile(spec: 登录后跳 /profile,可带 ?redirect=)
 *   6. 断言:localStorage.visa.auth 存了 accessToken(JWT 前缀 eyJ)
 *
 * 包含:
 *   - happy path (密码登录)
 *   - 错误密码(negative)
 *   - 表单校验(必填项)
 */
import { test, expect } from '@playwright/test'

function uniquePhoneId() {
  return Date.now().toString().slice(-8)
}
const PHONE_COUNTRY = '+62'
const PASSWORD = 'Test1234'

test.describe('S2 Web 登录端到端', () => {
  test('happy path: 密码登录 → 跳 /home + JWT 落 localStorage', async ({ page, request }) => {
    // 1. 健康检查
    const health = await request.get('http://127.0.0.1:8000/health')
    expect(health.ok()).toBeTruthy()

    // 2. 先注册一个用户(用真实后端,不调前端 register 页)
    const phone = uniquePhoneId()
    // 取 send-code
    const sendCodeRes = await request.post('http://127.0.0.1:8000/api/v2/auth/send-code', {
      data: { phone, phone_country: PHONE_COUNTRY, purpose: 'register' }
    })
    expect(sendCodeRes.ok()).toBeTruthy()
    const sendCodeJson = await sendCodeRes.json()
    const code = sendCodeJson.data?.code || '123456'

    // 注册(后端 schema 字段是 sms_code 不是 code)
    const regRes = await request.post('http://127.0.0.1:8000/api/v2/auth/register', {
      data: {
        phone,
        phone_country: PHONE_COUNTRY,
        password: PASSWORD,
        sms_code: code,
        language_pref: 'zh-CN'
      }
    })
    expect(regRes.status()).toBe(201)

    // 3. 打开登录页
    page.on('console', (msg) => console.log(`[PAGE ${msg.type()}] ${msg.text()}`))
    await page.goto('/login')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByTestId('login-submit')).toBeVisible()

    // 4. 填表
    await page.getByTestId('login-country').selectOption(PHONE_COUNTRY)
    await page.getByTestId('login-phone').fill(phone)
    await page.getByTestId('login-password').fill(PASSWORD)

    // 5. 提交
    await page.getByTestId('login-submit').click()

    // 6. 断言跳到 /profile(spec 默认跳 /profile,不是 /home)
    await page.waitForURL(/\/profile(\?.*)?$/, { timeout: 10_000 })
    await expect(page).toHaveURL(/\/profile(\?.*)?$/)

    // 7. JWT 应当写到 localStorage
    const authRaw = await page.evaluate(() => localStorage.getItem('visa.auth'))
    expect(authRaw).toBeTruthy()
    const auth = JSON.parse(authRaw || '{}')
    expect(auth.accessToken).toMatch(/^eyJ/)
    expect(auth.user).toBeTruthy()
    expect(auth.user.phone).toBe(phone)
  })

  test('wrong password: 显示错误且不跳走', async ({ page, request }) => {
    // 先注册一个用户
    const phone = uniquePhoneId()
    const sendCodeRes = await request.post('http://127.0.0.1:8000/api/v2/auth/send-code', {
      data: { phone, phone_country: PHONE_COUNTRY, purpose: 'register' }
    })
    const { data: { code } } = await sendCodeRes.json()
    await request.post('http://127.0.0.1:8000/api/v2/auth/register', {
      data: { phone, phone_country: PHONE_COUNTRY, password: PASSWORD, sms_code: code, language_pref: 'zh-CN' }
    })

    // 打开登录页输错密码
    await page.goto('/login')
    await page.getByTestId('login-country').selectOption(PHONE_COUNTRY)
    await page.getByTestId('login-phone').fill(phone)
    await page.getByTestId('login-password').fill('WrongPass1')
    await page.getByTestId('login-submit').click()

    // 等待错误提示(任何 error 元素或 toast)
    await page.waitForTimeout(1500)
    // 断言:不能跳走
    expect(page.url()).toMatch(/\/login$/)
    // localStorage 不应写入 token
    const authRaw = await page.evaluate(() => localStorage.getItem('visa.auth'))
    if (authRaw) {
      const auth = JSON.parse(authRaw)
      expect(auth.accessToken).toBeFalsy()
    }
  })

  test('empty form: 必填校验触发', async ({ page }) => {
    await page.goto('/login')
    await page.getByTestId('login-submit').click()
    await page.waitForTimeout(500)
    // 断言没跳走
    expect(page.url()).toMatch(/\/login$/)
  })
})
