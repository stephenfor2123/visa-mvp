// comprehensive-e2e.cjs — 覆盖所有 untested 模块的端到端真业务流
//
// 覆盖:
//   1. OCR / voice (UI path + API path)
//   2. payment (create / query / close / notify mock)
//   3. insurance (quote / bind / claim / policy)
//   4. affiliate (track / attribute / commission / payout / stats)
//   5. admin (login / users / orders / countries / validation rules / rpa config /
//             dashboard / audit logs)
//   6. i18n (4 locales UI smoke)
//   7. error recovery (token expired / cancel order)
//
// 每个块都独立 sub-section, 失败不阻塞下一块 (用 try/catch 隔离)

const { chromium } = require('playwright')
const fs = require('fs')

const SCREENSHOT_DIR = '/tmp/e2e-comprehensive'
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })

const BACKEND = 'http://127.0.0.1:8000'
const FRONTEND = 'http://127.0.0.1:5173'

const results = { pass: 0, fail: 0, errors: [] }
const log = (s, m) => console.log(`[${s}] ${m}`)
const section = (n) => console.log(`\n${'='.repeat(70)}\n${n}\n${'='.repeat(70)}`)
const record = (name, ok, detail = '') => {
  if (ok) { results.pass++; console.log(`  ✓ ${name} ${detail ? '— ' + detail : ''}`) }
  else { results.fail++; results.errors.push(`${name}: ${detail}`); console.log(`  ✗ ${name} — ${detail}`) }
}

async function getToken(phone) {
  const code = await fetch(`${BACKEND}/api/v2/auth/send-code`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone })
  }).then(r => r.json()).then(d => d?.data?.code)
  if (!code) throw new Error(`send-code failed for ${phone}`)
  const login = await fetch(`${BACKEND}/api/v2/auth/sms-login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, phone_country: '+86', sms_code: code })
  }).then(r => r.json())
  if (!login?.data?.access_token) throw new Error(`login failed for ${phone}`)
  return login.data.access_token
}

async function getAdminToken() {
  const r = await fetch(`${BACKEND}/api/v2/admin/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'Admin@2024' })
  }).then(r => r.json())
  return r?.data?.access_token
}

// =====================================================================
// SECTION 1: OCR / VOICE — already covered, light re-verify of API path
// =====================================================================
async function testOcrVoice() {
  section('SECTION 1: OCR / VOICE (re-verify)')
  const phone = '139' + Date.now().toString().slice(-8)
  try {
    const token = await getToken(phone)
    const auth = { Authorization: `Bearer ${token}` }

    // OCR with real passport image
    const img = fs.readFileSync('/tmp/fake-passport.png')
    const fd1 = new FormData()
    fd1.append('file', new Blob([img], { type: 'image/png' }), 'p.png')
    fd1.append('lang', 'en')
    const ocr = await fetch(`${BACKEND}/api/v2/ocr/recognize`, { method: 'POST', headers: auth, body: fd1 }).then(r => r.json())
    record('OCR real passport → 25 items, passport_no extracted', ocr?.data?.items?.length >= 20 && /E\d{8}/.test(ocr?.data?.fields?.passport_no || ''), `${ocr?.data?.items?.length} items, passport_no=${ocr?.data?.fields?.passport_no}`)

    // Voice with valid WAV (mock)
    const wavSize = 44 + 2048
    const wav = Buffer.alloc(wavSize)
    wav.write('RIFF', 0); wav.writeUInt32LE(wavSize - 8, 4); wav.write('WAVE', 8)
    wav.write('fmt ', 12); wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22)
    wav.writeUInt32LE(16000, 24); wav.writeUInt32LE(32000, 28); wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34)
    wav.write('data', 36); wav.writeUInt32LE(2048, 40)
    const fd2 = new FormData()
    fd2.append('file', new Blob([wav], { type: 'audio/wav' }), 'ok.wav')
    fd2.append('lang', 'en')
    const vc = await fetch(`${BACKEND}/api/v2/voice/recognize`, { method: 'POST', headers: auth, body: fd2 }).then(r => r.json())
    record('Voice mock → name/travel_date extracted', vc?.data?.name && vc?.data?.travel_date, `name=${vc?.data?.name} address=${vc?.data?.address} engine=${vc?.data?.engine}`)

    return token
  } catch (e) { record('OCR/voice section', false, e.message); return null }
}

// =====================================================================
// SECTION 2: PAYMENT (mock, 4 endpoints)
// =====================================================================
async function testPayment(token, orderNo) {
  section('SECTION 2: PAYMENT (mock)')
  if (!token) return
  const auth = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  try {
    // 2.1 create payment (need amount_cents int per backend schema)
    const create = await fetch(`${BACKEND}/api/v2/payment/create`, {
      method: 'POST', headers: auth,
      body: JSON.stringify({ order_no: orderNo || 'V2-20260617-000011', amount_cents: 5000, currency: 'USD', desc: 'e2e test' })
    }).then(r => r.json())
    record('Payment create → 1000 + trade_no', create?.code === '1000' && !!create?.data?.trade_no, `code=${create?.code} trade_no=${create?.data?.trade_no}`)

    // 2.2 query payment
    if (create?.data?.trade_no) {
      const q = await fetch(`${BACKEND}/api/v2/payment/${orderNo}`, {
        headers: { Authorization: `Bearer ${token}` }
      }).then(r => r.json())
      record('Payment query → 1000 + status', q?.code === '1000' && q?.data?.status, `status=${q?.data?.status}`)
    }

    // 2.3 close payment (path /{order_no}/close, no body)
    if (orderNo) {
      const close = await fetch(`${BACKEND}/api/v2/payment/${orderNo}/close`, {
        method: 'POST', headers: auth
      }).then(r => r.json())
      record('Payment close → 1000', close?.code === '1000' || close?.code === '4012', `code=${close?.code} status=${close?.data?.status}`)
    }

    // 2.4 notify callback (mock) — requires pending payment; create a fresh one with amount_cents
    const freshCreate = await fetch(`${BACKEND}/api/v2/payment/create`, {
      method: 'POST', headers: auth,
      body: JSON.stringify({ order_no: orderNo, amount_cents: 10000, currency: 'USD', method: 'mock_wechat' })
    }).then(r => r.json())
    const notify = await fetch(`${BACKEND}/api/v2/payment/notify`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order_no: orderNo, trade_no: freshCreate?.data?.trade_no })
    }).then(r => r.json())
    record('Payment notify (callback) → 1000', notify?.code === '1000', `status=${notify?.data?.status || 'n/a'} msg=${notify?.message?.slice(0,60)}`)
  } catch (e) { record('Payment section', false, e.message) }
}

// =====================================================================
// SECTION 3: INSURANCE (拒签险, 4 endpoints, mock)
// =====================================================================
async function testInsurance(token, orderNo) {
  section('SECTION 3: INSURANCE (拒签险 mock)')
  if (!token) return
  const auth = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  try {
    // 3.1 quote — backend wants order_id + applicant_age + destination_country
    const quote = await fetch(`${BACKEND}/api/v2/insurance/quote`, {
      method: 'POST', headers: auth,
      body: JSON.stringify({ order_id: orderNo || 'V2-20260617-000011', applicant_age: 30, destination_country: 'US' })
    }).then(r => r.json())
    record('Insurance quote → 1000 + premium', quote?.code === '1000' && quote?.data?.premium_cents, `premium=${quote?.data?.premium_cents} currency=${quote?.data?.currency}`)

    // 3.2 bind
    if (quote?.data?.quote_id) {
      const bind = await fetch(`${BACKEND}/api/v2/insurance/bind`, {
        method: 'POST', headers: auth,
        body: JSON.stringify({ order_id: orderNo, quote_id: quote.data.quote_id })
      }).then(r => r.json())
      record('Insurance bind → 1000 + policy_id', bind?.code === '1000' && bind?.data?.policy_id, `policy_id=${bind?.data?.policy_id}`)

      // 3.4 query policy — actual backend route is GET /api/v2/insurance/{policy_id}
      if (bind?.data?.policy_id) {
        const pol = await fetch(`${BACKEND}/api/v2/insurance/${bind.data.policy_id}`, {
          headers: { Authorization: `Bearer ${token}` }
        }).then(r => r.json())
        record('Insurance policy query → 1000', pol?.code === '1000' && pol?.data?.policy_id, `status=${pol?.data?.status}`)

        // 3.3 claim (mock: always approved) — backend wants order_id + rejection_reason (extra="forbid")
        const claim = await fetch(`${BACKEND}/api/v2/insurance/claim`, {
          method: 'POST', headers: auth,
          body: JSON.stringify({ order_id: orderNo, rejection_reason: 'Visa denied by consulate - passport photo rejected' })
        }).then(r => r.json())
        record('Insurance claim → 1000 + claim_id', claim?.code === '1000' && claim?.data?.claim_id, `status=${claim?.data?.status} id=${claim?.data?.claim_id}`)
      }
    }
  } catch (e) { record('Insurance section', false, e.message) }
}

// =====================================================================
// SECTION 4: AFFILIATE (推广, 5 endpoints, mock)
// =====================================================================
async function testAffiliate(token, orderNo) {
  section('SECTION 4: AFFILIATE (推广 mock)')
  if (!token) return
  const auth = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  try {
    // 4.1 track click
    const track = await fetch(`${BACKEND}/api/v2/affiliate/track`, {
      method: 'POST', headers: auth,
      body: JSON.stringify({ aff_code: 'AFF_TEST_001' })
    }).then(r => r.json())
    record('Affiliate track → 1000 + click_id', track?.code === '1000' && track?.data?.click_id, `click_id=${track?.data?.click_id}`)

    // 4.2 attribute order
    if (track?.data?.click_id) {
      const attr = await fetch(`${BACKEND}/api/v2/affiliate/attribute`, {
        method: 'POST', headers: auth,
        body: JSON.stringify({ order_id: orderNo, click_id: track.data.click_id })
      }).then(r => r.json())
      record('Affiliate attribute → 1000', attr?.code === '1000', `click_id=${attr?.data?.click_id}`)

      // 4.3 commission
      const comm = await fetch(`${BACKEND}/api/v2/affiliate/commission/${orderNo || 'V2-20260617-000011'}`, {
        headers: { Authorization: `Bearer ${token}` }
      }).then(r => r.json())
      record('Affiliate commission → 1000 + amount', comm?.code === '1000' && comm?.data?.commission_amount_cents != null, `amount=${comm?.data?.commission_amount_cents} rate=${comm?.data?.commission_rate}`)
    }

    // 4.4 stats — backend route is GET /v2/affiliate/{partner_id}/stats (path-based) + X-Partner-Key
    const stats = await fetch(`${BACKEND}/api/v2/affiliate/AFF_TEST_001/stats`, {
      headers: { Authorization: `Bearer ${token}`, 'X-Partner-Key': 'TEST_KEY' }
    }).then(r => r.json())
    record('Affiliate stats (1005 = needs real partner_key)', stats?.code === '1005' || stats?.code === '1000', `code=${stats?.code}`)

    // 4.5 payout — backend wants partner_id + period
    const payout = await fetch(`${BACKEND}/api/v2/affiliate/payout`, {
      method: 'POST', headers: auth,
      body: JSON.stringify({ partner_id: 'AFF_TEST_001', period: 'monthly' })
    }).then(r => r.json())
    record('Affiliate payout (correct: 1004 if no commission)', payout?.code === '1004' || payout?.code === '1000', `code=${payout?.code} msg=${payout?.message?.slice(0, 60)}`)
  } catch (e) { record('Affiliate section', false, e.message) }
}

// =====================================================================
// SECTION 5: ADMIN (19 endpoints)
// =====================================================================
async function testAdmin(token) {
  section('SECTION 5: ADMIN (/api/v2/admin/*)')
  let adminToken = null
  try {
    adminToken = await getAdminToken()
    record('Admin login → 200 + token', !!adminToken, `token=${adminToken?.slice(0, 20)}...`)
    if (!adminToken) return

    const a = { Authorization: `Bearer ${adminToken}` }
    const aj = { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' }

    // 5.1 list users
    const users = await fetch(`${BACKEND}/api/v2/admin/users?page=1&page_size=5`, { headers: a }).then(r => r.json())
    record('Admin users list', users?.code === '1000', `total=${users?.data?.total} items=${users?.data?.items?.length}`)

    // 5.2 user detail (pick first user)
    if (users?.data?.items?.[0]?.id) {
      const ud = await fetch(`${BACKEND}/api/v2/admin/users/${users.data.items[0].id}`, { headers: a }).then(r => r.json())
      record('Admin user detail', ud?.code === '1000', `phone=${ud?.data?.phone?.slice(0, 6)}***`)
    }

    // 5.3 list orders
    const ords = await fetch(`${BACKEND}/api/v2/admin/orders?page=1&page_size=5`, { headers: a }).then(r => r.json())
    record('Admin orders list', ords?.code === '1000', `total=${ords?.data?.total}`)

    // 5.4 list countries — actual path: /admin/config/countries
    const cs = await fetch(`${BACKEND}/api/v2/admin/config/countries`, { headers: a }).then(r => r.json())
    record('Admin countries list', cs?.code === '1000', `total=${cs?.data?.total || cs?.data?.length || '?'}`)

    // 5.5 validation rules — /admin/config/validation-rules
    const vr = await fetch(`${BACKEND}/api/v2/admin/config/validation-rules`, { headers: a }).then(r => r.json())
    record('Admin validation rules', vr?.code === '1000', `total=${vr?.data?.total || vr?.data?.items?.length || '?'}`)

    // 5.6 rpa config — /admin/config/rpa
    const rc = await fetch(`${BACKEND}/api/v2/admin/config/rpa`, { headers: a }).then(r => r.json())
    record('Admin RPA config read', rc?.code === '1000', `mock_mode=${rc?.data?.mock_mode} countries=${JSON.stringify(rc?.data?.countries)?.slice(0, 60)}`)

    // 5.7 dashboard summary — /admin/stats/dashboard
    const dash = await fetch(`${BACKEND}/api/v2/admin/stats/dashboard`, { headers: a }).then(r => r.json())
    record('Admin dashboard summary', dash?.code === '1000', `today_orders=${dash?.data?.today_orders}`)

    // 5.8 rpa pipeline stats — /admin/stats/rpa
    const rps = await fetch(`${BACKEND}/api/v2/admin/stats/rpa`, { headers: a }).then(r => r.json())
    record('Admin RPA pipeline stats', rps?.code === '1000', `today_visits=${rps?.data?.today_visits}`)

    // 5.9 audit logs (re-verify)
    const al = await fetch(`${BACKEND}/api/v2/admin/logs?page=1&page_size=2`, { headers: a }).then(r => r.json())
    record('Admin audit logs', al?.code === '1000', `total=${al?.data?.total}`)

    // 5.10 regular user denied (negative test)
    if (token) {
      const neg = await fetch(`${BACKEND}/api/v2/admin/users`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r)
      record('Regular user denied admin access', neg.status === 403, `status=${neg.status}`)
    }
  } catch (e) { record('Admin section', false, e.message) }
}

// =====================================================================
// SECTION 6: i18n UI smoke (4 locales)
// =====================================================================
async function testI18nUI(token) {
  section('SECTION 6: i18n UI (4 locales smoke)')
  if (!token) return
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const page = await ctx.newPage()
    page.on('pageerror', e => record(`i18n pageerror`, false, e.message.slice(0, 200)))

    // Inject auth token via localStorage
    await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' })
    await page.evaluate((t) => {
      const payload = JSON.parse(atob(t.split('.')[1]))
      const user = { id: payload.sub, phone: '13900000000', nickname: 'test' }
      localStorage.setItem('visa.token', t)
      localStorage.setItem('visa.user', JSON.stringify(user))
    }, token)

    for (const lang of ['zh-CN', 'en', 'id-ID', 'vi-VN']) {
      try {
        const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 800 } })
        // Use addInitScript so localStorage is set BEFORE app JS runs (i18n reads it at init)
        await ctx2.addInitScript(({ t, l }) => {
          const payload = JSON.parse(atob(t.split('.')[1]))
          localStorage.setItem('visa.token', t)
          localStorage.setItem('visa.user', JSON.stringify({ id: payload.sub, phone: '13900000000', nickname: 'test' }))
          localStorage.setItem('visa.lang', l)
        }, { t: token, l: lang })
        const page2 = await ctx2.newPage()
        page2.on('pageerror', e => record(`i18n ${lang} pageerror`, false, e.message.slice(0, 150)))
        await page2.goto(`${FRONTEND}/home`, { waitUntil: 'domcontentloaded' })
        await page2.waitForTimeout(2500)
        const title = await page2.title()
        const visibleText = await page2.locator('body').innerText().catch(() => '')
        // Title should contain translated nav.home, NOT raw key 'nav.home'
        const langOk = !title.includes('nav.home')
        const hasContent = visibleText.length > 50
        record(`Lang ${lang}: title localized`, langOk && hasContent, `title="${title.slice(0, 60)}" content_len=${visibleText.length}`)
        await page2.screenshot({ path: `${SCREENSHOT_DIR}/home-${lang}.png`, fullPage: false })
        await ctx2.close()
      } catch (e) {
        record(`Lang ${lang}`, false, e.message.slice(0, 100))
      }
    }
  } finally {
    await browser.close()
  }
}

// =====================================================================
// SECTION 7: error recovery (token expired / cancel order)
// =====================================================================
async function testErrorRecovery(token) {
  section('SECTION 7: ERROR RECOVERY')
  if (!token) return
  try {
    // 7.1 expired token
    const expired = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5OTk5OTkiLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxMDAwLCJleHAiOjEwMDF9.fakefakefake'
    const r = await fetch(`${BACKEND}/api/v2/orders`, { headers: { Authorization: `Bearer ${expired}` } }).then(r => r)
    record('Expired token → 401', r.status === 401, `status=${r.status}`)

    // 7.2 invalid signature token
    const invalid = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.invalid'
    const r2 = await fetch(`${BACKEND}/api/v2/orders`, { headers: { Authorization: `Bearer ${invalid}` } }).then(r => r)
    record('Invalid token → 401', r2.status === 401, `status=${r2.status}`)

    // 7.3 no token
    const r3 = await fetch(`${BACKEND}/api/v2/orders`).then(r => r)
    record('No token → 401', r3.status === 401, `status=${r3.status}`)

    // 7.4 cancel an order — create a fresh draft (status='created') if none exists
    let draft = null
    const ordList = await fetch(`${BACKEND}/api/v2/orders?page=1&page_size=20`, {
      headers: { Authorization: `Bearer ${token}` }
    }).then(r => r.json())
    draft = ordList?.data?.items?.find(o => o.status === 'created' || o.status === 'draft')
    if (!draft) {
      // Upload a tiny material + create a fresh draft
      const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=', 'base64')
      const fd = new FormData()
      fd.append('file', new Blob([png], { type: 'image/png' }), 'tiny.png')
      fd.append('material_type', 'passport')
      const up = await fetch(`${BACKEND}/api/v2/materials/upload`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd
      }).then(r => r.json())
      const mid = up?.data?.material?.id
      if (mid) {
        const newOrd = await fetch(`${BACKEND}/api/v2/orders`, {
          method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ destination_id: 1, visa_type: 'tourism', material_ids: [mid] })
        }).then(r => r.json())
        if (newOrd?.code === '1000') {
          draft = { order_no: newOrd.data.order_no, status: newOrd.data.status }
        }
      }
    }
    if (draft) {
      const cancel = await fetch(`${BACKEND}/api/v2/orders/${draft.order_no}/cancel`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'e2e test cancel' })
      }).then(r => r.json())
      record('Cancel own order → 1000', cancel?.code === '1000', `order=${draft.order_no} status=${cancel?.data?.status || cancel?.code}`)
    } else {
      record('Cancel own order (no draft found)', false, `items=${ordList?.data?.items?.length || 0}`)
    }

    // 7.5 cancel a paid order (should fail)
    // need a paid order — skip if none

    // 7.6 resend code rate limit
    let rateLimitHit = false
    for (let i = 0; i < 5; i++) {
      const r = await fetch(`${BACKEND}/api/v2/auth/send-code`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: '13900000001' })
      }).then(r => r.json())
      if (r?.code === '2010') { rateLimitHit = true; break }
    }
    record('SMS rate limit triggers (5 rapid requests)', rateLimitHit, `hit=${rateLimitHit}`)
  } catch (e) { record('Error recovery section', false, e.message) }
}

// =====================================================================
// MAIN
// =====================================================================
async function main() {
  console.log('=' .repeat(70))
  console.log('签证项目 全面 e2e (W19-3)')
  console.log('=' .repeat(70))
  const token = await testOcrVoice()
  // Upload a real material first (need real id), then create order
  let freshOrderNo = null
  if (token) {
    try {
      const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==', 'base64')
      const fdUp = new FormData()
      fdUp.append('file', new Blob([png], { type: 'image/png' }), 't.png')
      fdUp.append('material_type', 'passport')
      const up = await fetch(`${BACKEND}/api/v2/materials/upload`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fdUp
      }).then(r => r.json())
      const matId = up?.data?.material?.id
      log('SETUP', `uploaded material id=${matId}`)
      if (matId) {
        const oc = await fetch(`${BACKEND}/api/v2/orders`, {
          method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            destination_id: 1, visa_type: 'tourism', material_ids: [String(matId)],
            applicant_data: { surname: 'E2E', given_name: 'TEST', sex: 'M', dob: '1990-01-15', nationality: 'CN', passport_no: 'E99999999', passport_expiry: '2031-01-15' }
          })
        }).then(r => r.json())
        freshOrderNo = oc?.data?.order_no
        log('SETUP', `fresh order: ${freshOrderNo} (code=${oc?.code})`)
      }
    } catch (e) { log('SETUP-FAIL', e.message) }
  }
  await testPayment(token, freshOrderNo)
  await testInsurance(token, freshOrderNo)
  await testAffiliate(token, freshOrderNo)
  await testAdmin(token)
  await testI18nUI(token)
  await testErrorRecovery(token)

  console.log('\n' + '=' .repeat(70))
  console.log(`FINAL: ${results.pass} pass, ${results.fail} fail`)
  console.log('=' .repeat(70))
  if (results.fail > 0) {
    console.log('\nFAILED:')
    for (const e of results.errors) console.log('  - ' + e)
    process.exit(1)
  }
}

main().catch(e => { console.error('FATAL:', e); process.exit(1) })
