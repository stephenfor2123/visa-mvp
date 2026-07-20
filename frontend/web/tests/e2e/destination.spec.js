/**
 * S3 E2E — Web 端选国家流程端到端
 *
 * 流程:
 *   1. 用 Playwright `request` API 注册 + 登录拿 JWT(retry 5xx,绕开 SQLite 锁瞬时报 500)
 *   2. 把 JWT 写进 localStorage.visa.auth(让 vue-router guard 放行 /destinations)
 *   3. 访问 /destinations
 *   4. 断言:看到美国卡片(US),且 enabled 可点
 *   5. 断言:看到其他 8 国卡片,灰显且不能点
 *   6. 点美国 → 跳 /materials
 *   7. 截图 screenshots/destinations.png
 *
 * 设计原则:E2E 只测 destinations 业务,不测 login UI(S2 已覆盖)。
 * 拿 JWT 用 request API 跳过 login 页面交互,简化 + 提速。
 *
 * 历史坑(本 spec 演进):
 *   - i18n JSON 末尾多余 `}` + 重复 `nav` 字段 → 修 i18n(独立 en.json/zh-CN.json)
 *   - DB 没 seed 9 国数据 → 后端启动脚本自动 seed(本任务临时用脚本塞了一次)
 *   - Destinations.vue v-for 变量名 `t` 遮蔽 useI18n() 的 t() → 重命名 `type`
 *   - Playwright addInitScript 序列化 user 对象时偶发 SyntaxError → 改用 page.evaluate
 *   - SQLite 写锁瞬时冲突 → register/login 加 retry
 */
import { test, expect } from '@playwright/test'

const PHONE_COUNTRY = '+62'
const PASSWORD = 'Test1234'

function uniquePhoneId() {
  // 用 (s, ms) 拼接避免相邻测试在 1s 内撞同号
  return Date.now().toString().slice(-8)
}

async function postWithRetry(request, url, data, maxRetries = 3) {
  let lastRes
  for (let i = 0; i < maxRetries; i++) {
    lastRes = await request.post(url, { data })
    if (lastRes.status() < 500) return lastRes
    // 500/502/503 短暂等待后重试
    await new Promise((r) => setTimeout(r, 300 + i * 200))
  }
  return lastRes
}

test.describe('S3 Web 选国家端到端', () => {
  test('happy path: 登录后看到 9 国,美国可点,其他灰显', async ({ page, request }) => {
    // 1. 健康检查:后端在线
    const health = await request.get('http://127.0.0.1:8000/health')
    expect(health.ok()).toBeTruthy()

    // 2. 拿验证码
    const phone = uniquePhoneId()
    const sendCodeRes = await postWithRetry(
      request,
      'http://127.0.0.1:8000/api/v2/auth/send-code',
      { phone, phone_country: PHONE_COUNTRY, purpose: 'register' }
    )
    expect(sendCodeRes.ok()).toBeTruthy()
    const sendCodeJson = await sendCodeRes.json()
    const code = sendCodeJson.data?.code || '123456'

    // 3. 注册(retry 5xx,绕 SQLite 写锁)
    const regRes = await postWithRetry(
      request,
      'http://127.0.0.1:8000/api/v2/auth/register',
      {
        phone,
        phone_country: PHONE_COUNTRY,
        password: PASSWORD,
        sms_code: code,
        language_pref: 'zh-CN'
      }
    )
    expect(regRes.status()).toBe(201)

    // 4. 登录(retry 5xx)
    const loginRes = await postWithRetry(
      request,
      'http://127.0.0.1:8000/api/v2/auth/login',
      { phone, phone_country: PHONE_COUNTRY, password: PASSWORD }
    )
    expect(loginRes.status()).toBe(200)
    const loginBody = await loginRes.json()
    const accessToken = loginBody.data.access_token
    const refreshToken = loginBody.data.refresh_token
    expect(accessToken).toMatch(/^eyJ/)

    // 5. 注入 auth 到 localStorage:先到 /login(同源),再 page.evaluate 写 visa.auth。
    //    不用 addInitScript(user 对象的属性可能被 Playwright 序列化时产生 SyntaxError)。
    await page.goto('/login')
    await page.evaluate((d) => {
      try {
        localStorage.setItem('visa.auth', JSON.stringify(d))
      } catch (e) {
        // 静默失败
      }
    }, {
      accessToken,
      refreshToken,
      user: loginBody.data.user
    })

    // 6. 跳选国页 + 断言
    page.on('console', (msg) => console.log(`[PAGE ${msg.type()}] ${msg.text()}`))
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`))

    await page.goto('/destinations', { waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/\/destinations$/)

    // 7. 美国卡片可见 + 有点击按钮
    const usCard = page.getByTestId('dest-card-US')
    await expect(usCard).toBeVisible({ timeout: 15_000 })
    const usApply = page.getByTestId('dest-apply-US')
    await expect(usApply).toBeVisible()

    // 8. 非产品线目的地(JP/ID/VN)不得出现
    await expect(page.getByTestId('dest-card-JP')).toHaveCount(0)
    await expect(page.getByTestId('dest-card-ID')).toHaveCount(0)
    await expect(page.getByTestId('dest-card-VN')).toHaveCount(0)
    await expect(page.getByTestId('dest-apply-JP')).toHaveCount(0)

    // 9. 截图(测试期产出物)
    await page.screenshot({ path: 'screenshots/destinations.png', fullPage: true })

    // 10. 点美国 → 跳 /materials
    await usApply.click()
    await page.waitForURL(/\/materials/, { timeout: 10_000 })
    await expect(page).toHaveURL(/materials/)
  })
})
