// ui-smoke.cjs — 走遍前端所有主要页面 + OCR/voice UI 路径
// 检查每页能否渲染 + 关键元素是否在 + 截图
const { chromium } = require('playwright')
const fs = require('fs')

const SCREENSHOT_DIR = '/tmp/e2e-ui-smoke'
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })

const FRONTEND = 'http://127.0.0.1:5173'
const BACKEND = 'http://127.0.0.1:8000'

const results = { pass: 0, fail: 0, errors: [] }
const log = (s, m) => console.log(`[${s}] ${m}`)
const record = (name, ok, detail = '') => {
  if (ok) { results.pass++; console.log(`  ✓ ${name} ${detail ? '— ' + detail : ''}`) }
  else { results.fail++; results.errors.push(`${name}: ${detail}`); console.log(`  ✗ ${name} — ${detail}`) }
}

async function getToken(phone) {
  const code = await fetch(`${BACKEND}/api/v2/auth/send-code`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone })
  }).then(r => r.json()).then(d => d?.data?.code)
  if (!code) throw new Error(`send-code failed`)
  const login = await fetch(`${BACKEND}/api/v2/auth/sms-login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, phone_country: '+86', sms_code: code })
  }).then(r => r.json())
  if (!login?.data?.access_token) throw new Error(`login failed`)
  return login.data.access_token
}

async function seedUser(ctx, token) {
  // W19-3 fix: auth store reads from 'visa.auth' (JSON {user, accessToken, refreshToken}),
  // not separate 'visa.token' / 'visa.user' keys
  await ctx.addInitScript((t) => {
    const payload = JSON.parse(atob(t.split('.')[1]))
    localStorage.setItem('visa.auth', JSON.stringify({
      user: { id: payload.sub, phone: '13900000000', nickname: 'smoke' },
      accessToken: t,
      refreshToken: ''
    }))
    localStorage.setItem('visa.lang', 'zh-CN')
  }, token)
}

async function checkPage(page, name, path, mustHaveSelectors = []) {
  try {
    await page.goto(`${FRONTEND}${path}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)
    const visibleText = (await page.locator('body').innerText().catch(() => '')).slice(0, 200)
    const finalUrl = page.url()
    // if redirected to /login we treat as failed
    const redirected = finalUrl.includes('/login') && !path.startsWith('/login')
    if (redirected) {
      record(`Page ${name} (${path})`, false, `redirected to ${finalUrl}`)
      return false
    }
    // check selectors
    const missing = []
    for (const sel of mustHaveSelectors) {
      const c = await page.locator(sel).count()
      if (c === 0) missing.push(sel)
    }
    const fname = `${name}-${path.replace(/\//g, '_') || 'home'}.png`
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${fname}`, fullPage: false })
    if (missing.length === 0) {
      record(`Page ${name}`, true, `${path} — content_len=${visibleText.length}`)
      return true
    } else {
      record(`Page ${name}`, false, `${path} missing: ${missing.join(', ')}`)
      return false
    }
  } catch (e) {
    record(`Page ${name}`, false, `${path} — ${e.message.slice(0, 100)}`)
    return false
  }
}

async function main() {
  console.log('=' .repeat(70))
  console.log('UI 全面 smoke test')
  console.log('=' .repeat(70))

  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  try {
    const phone = '139' + Date.now().toString().slice(-8)
    const token = await getToken(phone)
    log('AUTH', `user token acquired`)

    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    await seedUser(ctx, token)
    const page = await ctx.newPage()
    page.on('pageerror', e => log('PAGEERR', e.message.slice(0, 200)))

    // ===== SECTION 1: All main pages =====
    log('1', 'All main pages')
    await checkPage(page, 'Home', '/home', ['body'])
    await checkPage(page, 'Destinations', '/destinations', ['body'])
    await checkPage(page, 'Materials', '/materials', ['[data-testid="mat-tabs"], .mat-tabs'])
    await checkPage(page, 'Orders', '/orders', ['body'])
    await checkPage(page, 'Profile', '/profile', ['body'])
    await checkPage(page, 'Agreement', '/agreement', ['body'])

    // ===== SECTION 2: OCR UI path =====
    log('2', 'OCR UI path: upload → recognize → see fields')
    const r = await checkPage(page, 'Materials (PDF tab)', '/materials?country=US&type=tourism', [
      '[data-testid="mat-tab-photo"]', '[data-testid="mat-tab-pdf"]', '[data-testid="mat-tab-voice"]'
    ])
    // dump all data-testids on this page
    const allTids = await page.locator('[data-testid]').evaluateAll(els =>
      [...new Set(els.map(e => e.getAttribute('data-testid')))]
    ).catch(()=>[])
    log('DEBUG', `all testids on /materials?country=US: ${allTids.slice(0,30).join(', ')}`)
    // Click PDF tab to switch
    try {
      await page.locator('[data-testid="mat-tab-pdf"]').click()
      await page.waitForTimeout(500)
      const fileInput = page.locator('[data-testid="mat-uploader"] input[type="file"]')
      const fakePassport = '/tmp/fake-passport.png'
      if (!fs.existsSync(fakePassport)) {
        // regenerate
        require('child_process').execSync(
          `python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (800, 600), color='white')
d = ImageDraw.Draw(img)
font = None
for p in ['/System/Library/Fonts/Helvetica.ttc']:
    try: font = ImageFont.truetype(p, 22); break
    except: pass
if not font: font = ImageFont.load_default()
d.text((20, 20), 'PASSPORT', fill='black', font=font)
d.text((20, 80), 'Surname: ZHANG', fill='black', font=font)
d.text((20, 130), 'Given Name: SAN', fill='black', font=font)
d.text((20, 180), 'Nationality: CHINESE', fill='black', font=font)
d.text((20, 230), 'Sex: M', fill='black', font=font)
d.text((20, 280), 'Date of Birth: 15 JAN 1990', fill='black', font=font)
d.text((20, 330), 'Passport No: E12345678', fill='black', font=font)
d.text((20, 380), 'Date of Expiry: 15 MAY 2031', fill='black', font=font)
img.save('${fakePassport}')
"`, { stdio: 'inherit' })
      }
      await fileInput.setInputFiles(fakePassport)
      await page.waitForTimeout(5000)
      const itemCount = await page.locator('[data-testid^="mat-item-"]').count()
      log('OCR-UI', `after upload, mat items: ${itemCount}`)
      record('OCR UI: upload + see item', itemCount >= 1, `items=${itemCount}`)
    } catch (e) {
      record('OCR UI', false, e.message.slice(0, 150))
    }

    // ===== SECTION 3: Voice UI path =====
    log('3', 'Voice UI path: record audio → see fields')
    try {
      await page.locator('[data-testid="mat-tab-voice"]').click()
      await page.waitForTimeout(800)
      const voicePanel = await page.locator('[data-testid="mat-voice-recorder"], [data-testid="mat-voice-panel"]').count()
      record('Voice UI: voice tab shows recorder', voicePanel >= 1, `panel=${voicePanel}`)
      // try clicking start record (will likely fail without mic permission in headless, but check button exists)
      const recordBtn = page.locator('[data-testid="vrec-toggle"]')
      const btnCount = await recordBtn.count()
      record('Voice UI: record button present', btnCount >= 1, `count=${btnCount}`)
    } catch (e) {
      record('Voice UI', false, e.message.slice(0, 150))
    }

    // ===== SECTION 4: OrderNew (filled form) =====
    log('4', 'OrderNew page renders')
    // Need to have a material to link
    await checkPage(page, 'OrderNew (no mat)', '/orders/new?country=US&visa_type=tourism', [
      '[data-testid="ordernew-section-basic"]'
    ])

    // ===== SECTION 5: Admin login UI =====
    log('5', 'Admin login page')
    const ctxAdmin = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    await ctxAdmin.addInitScript(() => {
      localStorage.removeItem('visa.token')
      localStorage.removeItem('visa.user')
      localStorage.setItem('visa.lang', 'zh-CN')
    })
    const pageAdmin = await ctxAdmin.newPage()
    await pageAdmin.goto(`${FRONTEND}/admin/login`, { waitUntil: 'domcontentloaded' }).catch(() => {})
    await pageAdmin.waitForTimeout(1000)
    const adminForm = await pageAdmin.locator('input[type="password"], input[type="text"]').count()
    record('Admin login page renders', adminForm >= 1, `inputs=${adminForm}`)
    await pageAdmin.screenshot({ path: `${SCREENSHOT_DIR}/admin-login.png` })
    await ctxAdmin.close()

    // ===== SECTION 6: PaymentResult page =====
    log('6', 'PaymentResult page renders')
    await checkPage(page, 'PaymentResult', '/payment/result?orderId=V2-20260617-000011&status=pending', [
      'body'
    ])

  } finally {
    await browser.close()
  }

  console.log('\n' + '='.repeat(70))
  console.log(`FINAL: ${results.pass} pass, ${results.fail} fail`)
  console.log('='.repeat(70))
  if (results.fail > 0) {
    console.log('\nFAILED:')
    for (const e of results.errors) console.log('  - ' + e)
    process.exit(1)
  }
}

main().catch(e => { console.error('FATAL:', e); process.exit(1) })
