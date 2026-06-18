// 真业务 e2e: OCR / voice / audit 端到端验证
// 测试目的: 这三块是 W19 提的 MVP 核心 (AI 采集 + 合规审计),
// 208 spec 没专项覆盖, 跑一遍找类似 rpa router 没注册的隐藏 bug
const fs = require('fs')
const path = require('path')

const SCREENSHOT_DIR = '/tmp/e2e-ai-audit-screens'
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR)

const log = (s, m) => console.log(`[${s}] ${m}`)

async function main() {
  // 1) Get a fresh JWT token (each run is a new user to avoid rate limits)
  const phone = '139' + Date.now().toString().slice(-8)
  log('AUTH', `registering phone=${phone}`)

  // send-code via API (no browser)
  const codeResp = await fetch('http://127.0.0.1:8000/api/v2/auth/send-code', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone })
  })
  const codeData = await codeResp.json()
  if (!codeData?.data?.code) {
    log('AUTH-FAIL', `send-code: ${JSON.stringify(codeData).slice(0, 200)}`)
    process.exit(1)
  }
  const code = codeData.data.code
  log('AUTH', `mock code: ${code}`)

  const loginResp = await fetch('http://127.0.0.1:8000/api/v2/auth/sms-login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, phone_country: '+86', sms_code: code })
  })
  const loginData = await loginResp.json()
  const token = loginData?.data?.access_token
  if (!token) {
    log('AUTH-FAIL', `login: ${JSON.stringify(loginData).slice(0, 200)}`)
    process.exit(1)
  }
  log('AUTH', `token acquired: ${token.slice(0, 20)}...`)
  const auth = { Authorization: `Bearer ${token}` }

  // 2) Create a test image with text resembling a passport
  // (using simple PIL-generated image since we just want OCR pipeline to run)
  const testImagePath = '/tmp/test-passport.png'

  // We need a real-looking image. Generate a simple PNG with text via Sharp/canvas?
  // Easier: use the existing 1x1 PNG and skip — the OCR engine should still
  // respond (with empty items / empty fields).
  // But to test the real extraction, let's generate a PNG with a passport_no
  // string visible to OCR.
  //
  // The simplest: use a real text-rendered PNG via canvas node lib if avail.
  // If not, just upload a plain image and verify the response shape.

  // Create a 1x1 PNG buffer as baseline (verifies pipeline plumbing)
  const tinyPng = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==',
    'base64'
  )
  fs.writeFileSync(testImagePath, tinyPng)
  log('IMG', `test image: ${testImagePath} (${tinyPng.length} bytes)`)

  // 3) Test OCR endpoint
  log('OCR', 'POST /api/v2/ocr/recognize')
  const formData = new FormData()
  const blob = new Blob([tinyPng], { type: 'image/png' })
  formData.append('file', blob, 'test.png')
  formData.append('lang', 'en')

  const ocrResp = await fetch('http://127.0.0.1:8000/api/v2/ocr/recognize', {
    method: 'POST', headers: auth, body: formData
  })
  const ocrStatus = ocrResp.status
  const ocrBody = await ocrResp.json()
  log('OCR', `status=${ocrStatus}`)
  log('OCR', `body: ${JSON.stringify(ocrBody).slice(0, 500)}`)

  // 4) Test voice endpoint
  log('VOICE', 'GET /api/v2/voice/config (introspection, no auth)')
  const vcResp = await fetch('http://127.0.0.1:8000/api/v2/voice/config')
  const vcBody = await vcResp.json()
  log('VOICE', `config status=${vcResp.status}`)
  log('VOICE', `supported_langs: ${JSON.stringify(vcBody?.data?.supported_langs)}`)
  log('VOICE', `min/max bytes: ${vcBody?.data?.min_audio_bytes} / ${vcBody?.data?.max_audio_bytes}`)

  log('VOICE', 'POST /api/v2/voice/recognize (too small audio → 2003)')
  const tooSmallAudio = Buffer.alloc(100) // < MIN_AUDIO_BYTES
  fs.writeFileSync('/tmp/test-tiny.webm', tooSmallAudio)
  const vForm = new FormData()
  vForm.append('file', new Blob([tooSmallAudio], { type: 'audio/webm' }), 'tiny.webm')
  vForm.append('lang', 'en')
  const vResp = await fetch('http://127.0.0.1:8000/api/v2/voice/recognize', {
    method: 'POST', headers: auth, body: vForm
  })
  const vStatus = vResp.status
  const vBody = await vResp.json()
  log('VOICE', `status=${vStatus} code=${vBody?.code} message="${(vBody?.message || '').slice(0, 100)}"`)

  log('VOICE', 'POST /api/v2/voice/recognize (bad lang → 2003)')
  const vForm2 = new FormData()
  vForm2.append('file', new Blob([Buffer.alloc(2048)], { type: 'audio/webm' }), 'ok.webm')
  vForm2.append('lang', 'klingon')
  const vResp2 = await fetch('http://127.0.0.1:8000/api/v2/voice/recognize', {
    method: 'POST', headers: auth, body: vForm2
  })
  const vBody2 = await vResp2.json()
  log('VOICE', `bad-lang status=${vResp2.status} code=${vBody2?.code} message="${(vBody2?.message || '').slice(0, 100)}"`)

  // 5) Test audit log via admin endpoint
  // Admin needs admin auth — first try with our user token (expect 401/403)
  log('AUDIT', 'GET /api/v2/admin/logs (regular user, expect 401/403)')
  const auditResp = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?page=1&page_size=20', {
    headers: auth
  })
  const auditStatus = auditResp.status
  const auditBody = await auditResp.json().catch(() => ({}))
  log('AUDIT', `status=${auditStatus} (expected 401/403 if no admin auth)`)

  // 6) Trigger an action that should write audit log, then verify it via admin
  // First, register a fresh action that goes through audit
  log('AUDIT', 'triggering an order create (which calls record_audit in order_service)')
  // We can't easily create an order without going through /orders/new, but
  // /api/v2/orders/create exists — let's check
  const ordResp = await fetch('http://127.0.0.1:8000/api/v2/orders', {
    method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      destination_id: 1,
      visa_type: 'tourism',
      material_ids: ['99999'],  // fake, will fail with NOT_FOUND
      applicant_data: { surname: 'TEST', given_name: 'USER' }
    })
  })
  log('AUDIT', `order create status=${ordResp.status}`)

  // 7) Try admin login with the demo admin account
  log('ADMIN', 'logging in as admin (Admin@2024)')
  // Admin uses a different auth flow — try the /admin/login endpoint
  const adminLoginResp = await fetch('http://127.0.0.1:8000/api/v2/admin/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'Admin@2024' })
  }).catch((e) => ({ ok: false, status: 0, _err: e.message }))
  log('ADMIN', `login status=${adminLoginResp.status}`)


  // 8) Voice with valid-sized WAV (mock engine returns deterministic result)
  log('VOICE-OK', 'POST /api/v2/voice/recognize (valid-size WAV → mock engine)')
  // Create a minimal valid WAV header + 2KB of audio data
  const wavSize = 44 + 2048
  const wavBuf = Buffer.alloc(wavSize)
  // RIFF header
  wavBuf.write('RIFF', 0)
  wavBuf.writeUInt32LE(wavSize - 8, 4)
  wavBuf.write('WAVE', 8)
  // fmt chunk
  wavBuf.write('fmt ', 12)
  wavBuf.writeUInt32LE(16, 16)  // chunk size
  wavBuf.writeUInt16LE(1, 20)   // PCM
  wavBuf.writeUInt16LE(1, 22)   // mono
  wavBuf.writeUInt32LE(16000, 24)  // sample rate
  wavBuf.writeUInt32LE(32000, 28)  // byte rate
  wavBuf.writeUInt16LE(2, 32)   // block align
  wavBuf.writeUInt16LE(16, 34)  // bits per sample
  // data chunk
  wavBuf.write('data', 36)
  wavBuf.writeUInt32LE(2048, 40)
  fs.writeFileSync('/tmp/test-ok.wav', wavBuf)
  log('VOICE-OK', `test wav: ${wavBuf.length} bytes`)
  const vForm3 = new FormData()
  vForm3.append('file', new Blob([wavBuf], { type: 'audio/wav' }), 'ok.wav')
  vForm3.append('lang', 'en')
  const vResp3 = await fetch('http://127.0.0.1:8000/api/v2/voice/recognize', {
    method: 'POST', headers: auth, body: vForm3
  })
  const vBody3 = await vResp3.json()
  log('VOICE-OK', `status=${vResp3.status} code=${vBody3?.code}`)
  log('VOICE-OK', `engine: ${vBody3?.data?.engine} name: ${vBody3?.data?.name} raw: ${(vBody3?.data?.raw_text || '').slice(0, 100)}`)


  // 9) Admin login + query audit logs
  log('ADMIN-LOGS', 'login as admin and query /admin/logs')
  const adminLoginResp2 = await fetch('http://127.0.0.1:8000/api/v2/admin/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'Admin@2024' })
  })
  const adminLoginBody = await adminLoginResp2.json()
  log('ADMIN-LOGS', `admin login: status=${adminLoginResp2.status} code=${adminLoginBody?.code}`)
  const adminToken = adminLoginBody?.data?.access_token || adminLoginBody?.data?.token
  if (adminToken) {
    log('ADMIN-LOGS', `admin token: ${adminToken.slice(0, 30)}...`)
    const logsResp = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?page=1&page_size=5', {
      headers: { Authorization: `Bearer ${adminToken}` }
    })
    const logsBody = await logsResp.json()
    log('ADMIN-LOGS', `logs status=${logsResp.status} code=${logsBody?.code}`)
    log('ADMIN-LOGS', `total=${logsBody?.data?.total} items=${logsBody?.data?.items?.length || 0}`)
    if (logsBody?.data?.items?.length) {
      const first = logsBody.data.items[0]
      log('ADMIN-LOGS', `first: action=${first.action} actor=${first.actor_type}:${first.actor_id} target=${first.target_type}:${first.target_id}`)
    }
  } else {
    log('ADMIN-LOGS', `no admin token. body: ${JSON.stringify(adminLoginBody).slice(0, 300)}`)
  }


  // 10) Get distinct audit action types to see what we are tracking
  log('AUDIT-ACTIONS', 'list all distinct actions in audit log')
  if (typeof adminToken !== 'undefined' && adminToken) {
    const allLogs = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?page=1&page_size=100', {
      headers: { Authorization: 'Bearer ' + adminToken }
    })
    const allBody = await allLogs.json()
    const actions = new Set()
    for (const item of allBody?.data?.items || []) actions.add(item.action)
    log('AUDIT-ACTIONS', `distinct actions: ${JSON.stringify([...actions].sort())}`)
    const targetTypes = new Set()
    for (const item of allBody?.data?.items || []) targetTypes.add(item.target_type || 'null')
    log('AUDIT-ACTIONS', `distinct target_types: ${JSON.stringify([...targetTypes].sort())}`)
  }


  // 11) Admin log filtering
  log('ADMIN-FILTER', 'filter by action=order.create')
  if (typeof adminToken !== 'undefined' && adminToken) {
    const f1 = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?action=order.create&page=1&page_size=3', {
      headers: { Authorization: 'Bearer ' + adminToken }
    })
    const f1body = await f1.json()
    log('ADMIN-FILTER', `status=${f1.status} code=${f1body?.code} total=${f1body?.data?.total}`)
    // Test user_id filter
    const f2 = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?target_type=order&page=1&page_size=3', {
      headers: { Authorization: 'Bearer ' + adminToken }
    })
    const f2body = await f2.json()
    log('ADMIN-FILTER', `target_type=order: total=${f2body?.data?.total}`)
    // Test invalid page
    const f3 = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?page=99999&page_size=20', {
      headers: { Authorization: 'Bearer ' + adminToken }
    })
    const f3body = await f3.json()
    log('ADMIN-FILTER', `page=99999: status=${f3.status} total=${f3body?.data?.total} items=${f3body?.data?.items?.length}`)
  }


  // 12) OCR with realistic passport image
  log('OCR-REAL', 'POST /api/v2/ocr/recognize (real passport image)')
  const realImage = fs.readFileSync('/tmp/fake-passport.png')
  log('OCR-REAL', `image size: ${realImage.length} bytes`)
  const ocrForm = new FormData()
  ocrForm.append('file', new Blob([realImage], { type: 'image/png' }), 'passport.png')
  ocrForm.append('lang', 'en')
  const ocrRealResp = await fetch('http://127.0.0.1:8000/api/v2/ocr/recognize', {
    method: 'POST', headers: auth, body: ocrForm
  })
  const ocrRealBody = await ocrRealResp.json()
  log('OCR-REAL', `status=${ocrRealResp.status} code=${ocrRealBody?.code}`)
  log('OCR-REAL', `items count: ${ocrRealBody?.data?.items?.length}`)
  log('OCR-REAL', `fields: ${JSON.stringify(ocrRealBody?.data?.fields).slice(0, 500)}`)
  // Save screenshot of the response for review
  fs.writeFileSync('/tmp/e2e-ai-audit-screens/ocr-real-response.json', JSON.stringify(ocrRealBody, null, 2))


  // 13) Get last 3 OCR + voice audit entries to verify payload detail
  if (typeof adminToken !== 'undefined' && adminToken) {
    const ocrLogs = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?action=ocr.recognize&page=1&page_size=2', {
      headers: { Authorization: 'Bearer ' + adminToken }
    })
    const ocrBody = await ocrLogs.json()
    log('AUDIT-PAYLOAD', `ocr.recognize last ${ocrBody?.data?.items?.length || 0}:`)
    for (const it of ocrBody?.data?.items || []) {
      log('AUDIT-PAYLOAD', `  ${it.action} actor=${it.actor_type}:${it.actor_id} payload=${JSON.stringify(it.payload).slice(0, 200)}`)
    }
    const voiceLogs = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?action=voice.recognize&page=1&page_size=2', {
      headers: { Authorization: 'Bearer ' + adminToken }
    })
    const voiceBody = await voiceLogs.json()
    log('AUDIT-PAYLOAD', `voice.recognize last ${voiceBody?.data?.items?.length || 0}:`)
    for (const it of voiceBody?.data?.items || []) {
      log('AUDIT-PAYLOAD', `  ${it.action} actor=${it.actor_type}:${it.actor_id} payload=${JSON.stringify(it.payload).slice(0, 200)}`)
    }
  }


  if (typeof adminToken !== 'undefined' && adminToken) {
    // Get all voice.recognize entries (failed + ok)
    const all = await fetch('http://127.0.0.1:8000/api/v2/admin/logs?action=voice.recognize&page=1&page_size=20', {
      headers: { Authorization: 'Bearer ' + adminToken }
    })
    const ab = await all.json()
    log('VOICE-ALL', `total voice.recognize: ${ab?.data?.total}`)
    let okCount = 0, errCount = 0
    for (const it of ab?.data?.items || []) {
      const p = typeof it.payload === 'string' ? JSON.parse(it.payload) : it.payload
      if (p?.result === 'ok') okCount++
      else errCount++
    }
    log('VOICE-ALL', `ok=${okCount} error=${errCount}`)
    if (errCount > 0) {
      const firstErr = ab.data.items.find(it => {
        const p = typeof it.payload === 'string' ? JSON.parse(it.payload) : it.payload
        return p?.result === 'error'
      })
      log('VOICE-ALL', `first error: payload=${JSON.stringify(firstErr.payload).slice(0, 200)}`)
    }
  }

  log('DONE', '--- SUMMARY ---')
  log('OCR', `${ocrStatus} (200=OK, expect fields+items envelope)`)
  log('VOICE-INTRO', `${vcResp.status} (200=OK)`)
  log('VOICE-TINY', `${vStatus} (expect 400 + code 2003)`)
  log('VOICE-LANG', `${vResp2.status} (expect 400 + code 2003)`)
  log('AUDIT-USER', `${auditStatus} (expect 401/403)`)
  log('ORDER-CREATE', `${ordResp.status} (expect 404 or 500 since material 99999 missing)`)
}

main().catch((e) => {
  console.error('FATAL:', e.stack || e.message || e)
  process.exit(1)
})
