// payments-and-insurance-smoke.cjs
//
// 验证前端 payment/insurance api wrapper 跟后端真实路由对齐:
//   - GET /api/v2/payment/{order_no} (无 /status/)
//   - POST /api/v2/payment/{order_no}/close (无 /cancel/)
//   - POST /api/v2/payment/create (含 amount_cents)
//   - POST /api/v2/payment/notify
//   - POST /api/v2/insurance/quote
//   - POST /api/v2/insurance/bind
//   - GET  /api/v2/insurance/{policy_id} (无 /policy/)
//   - POST /api/v2/insurance/claim (order_id + rejection_reason, no policy_id)

const FRONTEND = 'http://127.0.0.1:5173'
const BACKEND = 'http://127.0.0.1:8000'

async function postJson(url, body, token) {
  return await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(body)
  }).then(r => r.json())
}

async function getJson(url, token) {
  return await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  }).then(r => r.json())
}

async function go() {
  // Login
  const login = await postJson(`${BACKEND}/api/v2/auth/login`, { phone: '138001380001', password: '123456', phone_country: '+86' })
  if (login.code !== '1000') {
    console.log('FAIL login:', JSON.stringify(login).slice(0, 200))
    process.exit(1)
  }
  const token = login.data.access_token
  console.log(`[AUTH] token len=${token.length}`)

  let pass = 0, fail = 0
  function record(name, ok, info = '') {
    if (ok) { pass++; console.log(`  ✓ ${name} ${info}`) }
    else { fail++; console.log(`  ✗ ${name} ${info}`) }
  }

  // ==== 1. PAYMENT wrapper alignment ====
  console.log('\n[PAYMENT]')

  // 1.1 create payment (need real order)
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=', 'base64')
  const fd1 = new FormData()
  fd1.append('file', new Blob([png], { type: 'image/png' }), 'tiny.png')
  fd1.append('material_type', 'passport')
  const up = await fetch(`${BACKEND}/api/v2/materials/upload`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd1
  }).then(r => r.json())
  const mid = up?.data?.material?.id
  if (!mid) { console.log('FAIL upload:', JSON.stringify(up).slice(0, 200)); process.exit(1) }

  const newOrd = await postJson(`${BACKEND}/api/v2/orders`, {
    destination_id: 1, visa_type: 'tourism', material_ids: [mid]
  }, token)
  if (newOrd.code !== '1000') { console.log('FAIL create order:', JSON.stringify(newOrd).slice(0, 200)); process.exit(1) }
  const orderNo = newOrd.data.order_no
  console.log(`  setup: order=${orderNo} material=${mid}`)

  // 1.1 create payment with amount_cents
  const create = await postJson(`${BACKEND}/api/v2/payment/create`, {
    order_no: orderNo, amount_cents: 5000, currency: 'USD', method: 'mock_wechat', desc: 'e2e smoke'
  }, token)
  record('payment create → 1000', create.code === '1000', `trade_no=${create.data?.trade_no?.slice(0, 20)}...`)

  // 1.2 query status via REAL path /v2/payment/{order_no} (no /status/)
  const status = await getJson(`${BACKEND}/api/v2/payment/${orderNo}`, token)
  record('payment status via /{order_no} (no /status/)', status.code === '1000', `status=${status.data?.status}`)

  // 1.3 close via REAL path /v2/payment/{order_no}/close (no /cancel/)
  const close = await postJson(`${BACKEND}/api/v2/payment/${orderNo}/close`, {}, token)
  record('payment close via /{order_no}/close (no /cancel/)', close.code === '1000', `status=${close.data?.status}`)

  // 1.4 notify callback (use a fresh create since close makes it not pending)
  const newCreate = await postJson(`${BACKEND}/api/v2/payment/create`, {
    order_no: orderNo, amount_cents: 5000, currency: 'USD', method: 'mock_wechat'
  }, token)
  const notify = await postJson(`${BACKEND}/api/v2/payment/notify`, {
    order_no: orderNo, trade_no: newCreate.data?.trade_no
  })
  record('payment notify → 1000', notify.code === '1000', `msg=${notify.message?.slice(0, 50)}`)

  // ==== 2. INSURANCE wrapper alignment ====
  console.log('\n[INSURANCE]')

  // 2.1 quote — backend wants order_id + applicant_age + destination_country
  const quote = await postJson(`${BACKEND}/api/v2/insurance/quote`, {
    order_id: orderNo, applicant_age: 30, destination_country: 'US'
  }, token)
  record('insurance quote', quote.code === '1000' && quote.data?.premium_cents, `premium=${quote.data?.premium_cents}`)

  // 2.2 bind
  const bind = await postJson(`${BACKEND}/api/v2/insurance/bind`, {
    order_id: orderNo, quote_id: quote.data?.quote_id
  }, token)
  record('insurance bind', bind.code === '1000' && bind.data?.policy_id, `policy_id=${bind.data?.policy_id}`)

  // 2.3 query via REAL path /v2/insurance/{policy_id} (no /policy/)
  const pol = await getJson(`${BACKEND}/api/v2/insurance/${bind.data?.policy_id}`, token)
  record('insurance policy via /{policy_id} (no /policy/)', pol.code === '1000' && pol.data?.policy_id, `status=${pol.data?.status}`)

  // 2.4 claim — order_id + rejection_reason (extra='forbid' so no policy_id/reason)
  const claim = await postJson(`${BACKEND}/api/v2/insurance/claim`, {
    order_id: orderNo, rejection_reason: 'Visa denied by consulate'
  }, token)
  record('insurance claim', claim.code === '1000' && claim.data?.claim_id, `claim_id=${claim.data?.claim_id} status=${claim.data?.status}`)

  // ==== 3. OLD WRONG paths must 404 ====
  console.log('\n[OLD WRONG PATHS — expect 404/400]')
  const oldStatus = await fetch(`${BACKEND}/api/v2/payment/status/${orderNo}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  record('OLD /v2/payment/status/{order_no} → 404', oldStatus.status === 404, `status=${oldStatus.status}`)

  const oldCancel = await fetch(`${BACKEND}/api/v2/payment/cancel/${orderNo}`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }
  })
  record('OLD /v2/payment/cancel/{order_no} → 404', oldCancel.status === 404, `status=${oldCancel.status}`)

  const oldRetry = await fetch(`${BACKEND}/api/v2/payment/retry/${orderNo}`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }
  })
  record('OLD /v2/payment/retry/{order_no} → 404', oldRetry.status === 404, `status=${oldRetry.status}`)

  const oldPol = await fetch(`${BACKEND}/api/v2/insurance/policy/${bind.data?.policy_id}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  record('OLD /v2/insurance/policy/{policy_id} → 404', oldPol.status === 404, `status=${oldPol.status}`)

  console.log(`\n========================================`)
  console.log(`FINAL: ${pass} pass, ${fail} fail`)
  console.log(`========================================`)
  process.exit(fail > 0 ? 1 : 0)
}

go().catch(e => { console.error('CRASH:', e); process.exit(2) })
