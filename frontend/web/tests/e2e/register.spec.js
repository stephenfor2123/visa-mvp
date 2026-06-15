/**
 * S1 E2E — Web 端注册流程端到端
 *
 * 流程:
 *   1. 打开 /register
 *   2. 选区号 +62 (印尼)
 *   3. 填手机号 + 发送验证码(调后端 /api/v2/auth/send-code,验证后端打通)
 *   4. 填 mock 验证码 123456(后端 mock 模式接受任意 6 位)
 *   5. 填密码 Test1234 + 确认密码
 *   6. 勾选《用户协议》《隐私政策》
 *   7. 点注册 → 调后端 /api/v2/auth/register → 201 + JWT
 *   8. 断言:URL 跳转到 /login
 *
 * Idempotency:
 *   用 timestamp 后缀的手机号,避免与已有用户冲突。
 *   必填校验 / 密码不一致两个 negative case 验证表单校验生效。
 */
import { test, expect } from '@playwright/test'

function uniquePhoneId() {
  return Date.now().toString().slice(-8)
}
const PASSWORD = 'Test1234'
const MOCK_CODE = '123456'  // mock 模式后端接受任意 6 位

test.describe('S1 Web 注册端到端', () => {
  test('happy path: 填表 → 调后端 → 跳 /login', async ({ page, request }) => {
    // 1. 健康检查:确认后端在线
    const health = await request.get('http://127.0.0.1:8000/health')
    expect(health.ok()).toBeTruthy()

    // 2. 额外:直接调后端 /send-code,证明链路通(用一次性 phone 避免 60s 限流)
    const probePhone = uniquePhoneId()
    const probe = await request.post('http://127.0.0.1:8000/api/v2/auth/send-code', {
      data: { phone: probePhone, phone_country: '+62', purpose: 'register' }
    })
    expect(probe.ok()).toBeTruthy()
    const probeBody = await probe.json()
    expect(probeBody.code).toBe('1000')
    expect(probeBody.data.code).toMatch(/^\d{6}$/)

    // 3. 开注册页
    await page.goto('/register')
    await expect(page.getByTestId('reg-submit')).toBeVisible()

    // 4. 选区号 +62 + 填手机号(用全新号)
    await page.getByTestId('reg-country').selectOption('+62')
    const phone = uniquePhoneId()
    await page.getByTestId('reg-phone').fill(phone)

    // 5. 点"发送验证码"——调后端 send-code(后端会记录这个号,后续 register 能通过)
    await page.getByTestId('reg-send-code').click()
    // 等 toast 出现或 mock-hint 出现(轮询两者之一,任一出现即视为调通)
    await Promise.race([
      page.locator('.mock-hint b').waitFor({ state: 'visible', timeout: 8_000 }),
      page.locator('.app-toast').first().waitFor({ state: 'visible', timeout: 8_000 })
    ]).catch(() => {
      // 不强求:即使后端没返回 code,mock 模式也会接受任意 6 位
    })

    // 6. 填验证码(任务 spec 要求用 123456,mock 模式后端接受任意 6 位)
    await page.getByTestId('reg-sms').fill(MOCK_CODE)

    // 7. 密码 + 确认密码
    await page.getByTestId('reg-password').fill(PASSWORD)
    await page.getByTestId('reg-confirm-password').fill(PASSWORD)

    // 8. 勾选协议
    await page.getByTestId('reg-agreement').check()

    // 9. 提交
    await page.getByTestId('reg-submit').click()

    // 10. 断言跳到 /login
    await page.waitForURL(/\/login(\?|$)/, { timeout: 15_000 })
    await expect(page).toHaveURL(/\/login(\?|$)/)

    // 11. JWT 应当写进 localStorage (任务要求)
    // 不放在 visa.auth(否则 router guard 把 /login 当作已登录再重定向回 /home),
    // 单独存 visa.pending_jwt 留给后续 /login 自动填充或下次回访。
    const authRaw = await page.evaluate(() => localStorage.getItem('visa.pending_jwt'))
    expect(authRaw).toBeTruthy()
    const auth = JSON.parse(authRaw || '{}')
    expect(auth.accessToken).toMatch(/^eyJ/)  // JWT 前缀
    expect(auth.user).toBeTruthy()
    expect(auth.user.phone).toBe(phone)
  })

  test('form validation: 协议未勾选时点注册,显示错误', async ({ page }) => {
    await page.goto('/register')
    await page.getByTestId('reg-country').selectOption('+62')
    await page.getByTestId('reg-phone').fill(uniquePhoneId())
    await page.getByTestId('reg-sms').fill(MOCK_CODE)
    await page.getByTestId('reg-password').fill(PASSWORD)
    await page.getByTestId('reg-confirm-password').fill(PASSWORD)
    // 不勾选协议,直接点
    await page.getByTestId('reg-submit').click()
    await expect(page.locator('.agreement__error')).toBeVisible()
    // URL 不能跳走
    await page.waitForTimeout(500)
    expect(page.url()).toMatch(/\/register$/)
  })

  test('password mismatch: 两次密码不一致,显示错误', async ({ page }) => {
    await page.goto('/register')
    await page.getByTestId('reg-country').selectOption('+62')
    await page.getByTestId('reg-phone').fill(uniquePhoneId())
    await page.getByTestId('reg-sms').fill(MOCK_CODE)
    await page.getByTestId('reg-password').fill(PASSWORD)
    await page.getByTestId('reg-confirm-password').fill('Different1234')
    await page.getByTestId('reg-agreement').check()
    await page.getByTestId('reg-submit').click()
    await expect(page.locator('.app-input__error').first()).toBeVisible()
    expect(page.url()).toMatch(/\/register$/)
  })
})
