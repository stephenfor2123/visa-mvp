// popup.js — v0.2: 12-digit code redemption flow

// ---------- DOM refs ----------
const $code   = document.getElementById('code')
const $redeem = document.getElementById('redeem')
const $status = document.getElementById('status')
const $viewIdle  = document.getElementById('view-idle')
const $viewReady = document.getElementById('view-ready')
const $readyName = document.getElementById('ready-name')
const $readyOrderId = document.getElementById('ready-order-id')
const $readyFp = document.getElementById('ready-fp')
const $readyMappingV = document.getElementById('ready-mapping-v')
const $readyMappingVd = document.getElementById('ready-mapping-vd')
const $clear = document.getElementById('clear')
const $openDs160 = document.getElementById('openDs160')
const $apiBase = document.getElementById('apiBase')
const $readySubmitted = document.getElementById('ready-submitted')

// ---------- Status helpers ----------
function setStatus(text, kind = 'idle') {
  $status.textContent = text
  $status.className = 'status ' + kind
}

// ---------- Code input sanitization ----------
// Visible-form input is dashed/spacey; strip to base30 chars and uppercase.
function sanitize(s) {
  return (s || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase()
}

function updateRedeemEnabled() {
  const ok = sanitize($code.value).length === 12
  $redeem.disabled = !ok
  $code.classList.toggle('invalid', $code.value && !ok)
}

$code.addEventListener('input', () => {
  // Auto-format: insert dashes every 4 chars for readability (visual only).
  const raw = sanitize($code.value).slice(0, 12)
  if (raw.length <= 4)        $code.value = raw
  else if (raw.length <= 8)   $code.value = raw.slice(0, 4) + '-' + raw.slice(4)
  else                        $code.value = raw.slice(0, 4) + '-' + raw.slice(4, 8) + '-' + raw.slice(8)
  updateRedeemEnabled()
})

// ---------- Backend call ----------
function redeem() {
  const code = sanitize($code.value)
  if (code.length !== 12) {
    setStatus('code 必须是 12 位字符', 'warn')
    return
  }
  $redeem.disabled = true
  setStatus('正在向 Htex 后端兑换…', 'info')

  chrome.runtime.sendMessage(
    { type: 'HTEX_REDEEM_CODE', code },
    (resp) => {
      if (chrome.runtime.lastError) {
        setStatus('后台消息失败: ' + chrome.runtime.lastError.message, 'err')
        $redeem.disabled = false
        return
      }
      if (!resp) {
        setStatus('后端无响应', 'err')
        $redeem.disabled = false
        return
      }
      if (!resp.ok) {
        // Map error codes to actionable messages.
        const code2msg = {
          '11001': 'code 不存在, 请检查拼写',
          '11002': 'code 已被撤销, 请回 Htex 拿新 code',
          '11003': '档案已更新, 请回 Htex 拿新 code',
          '11004': 'code 格式不正确 (12 位 base30)',
          '11005': '档案字段不完整, 请先在 Htex 补完资料',
          '11006': '订单状态不允许生成 code',
          '1009': '操作太频繁, 请稍后再试',
        }
        const hint = code2msg[resp.code] || ('兑换失败: ' + (resp.message || resp.code))
        setStatus(hint, 'err')
        $redeem.disabled = false
        return
      }
      // Success — switch to ready view.
      showReady(resp.meta)
    }
  )
}

$redeem.addEventListener('click', redeem)

// Pressing Enter in the input is a shortcut for clicking Redeem.
$code.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !$redeem.disabled) redeem()
})

// ---------- Ready view ----------
function showReady(meta) {
  $viewIdle.classList.add('hidden')
  $viewReady.classList.remove('hidden')

  const profile = meta.profile || {}
  const ident = profile.identity || {}
  const name = ((ident.surname || '') + ' ' + (ident.givenName || '')).trim() || '(未命名)'
  $readyName.textContent = name
  $readyOrderId.textContent = meta.order_id || '?'
  $readyFp.textContent = (meta.fingerprint || '').slice(0, 12) + '…'
  $readyMappingV.textContent = meta.mapping_version || '?'
  $readyMappingVd.textContent = meta.mapping_verified_date == null
    ? 'null (待核对真表)'
    : meta.mapping_verified_date

  // DS-160 提交确认状态(用户在确认页点过"我已提交完成"才有)
  chrome.runtime.sendMessage({ type: 'HTEX_GET_SUBMITTED', orderId: meta.order_id }, (r) => {
    if (!$readySubmitted) return
    if (r && r.submitted) {
      $readySubmitted.textContent = '🎉 DS-160 已确认提交 · ' + new Date(r.submittedAt).toLocaleString()
      $readySubmitted.classList.remove('hidden')
      $readySubmitted.className = 'status ok'
    } else {
      $readySubmitted.classList.add('hidden')
    }
  })
}

$clear.addEventListener('click', () => {
  if (!confirm('确定清除已存的档案资料?\n\n清除后插件将无法在 DS-160 页面上填表, 你需要回 Htex 重新生成 code 再来 redeem。')) return
  chrome.runtime.sendMessage({ type: 'HTEX_CLEAR_PROFILE' }, () => {
    // Reset to idle view.
    $viewReady.classList.add('hidden')
    $viewIdle.classList.remove('hidden')
    $code.value = ''
    updateRedeemEnabled()
    setStatus('已清除。粘贴新 code 继续。', 'idle')
  })
})

// W48 v0.2 UX1: 一键跳转美签网站 (新标签页)
$openDs160.addEventListener('click', () => {
  $openDs160.disabled = true
  const original = $openDs160.textContent
  $openDs160.textContent = '正在打开...'
  chrome.runtime.sendMessage({ type: 'HTEX_OPEN_DS160' }, (resp) => {
    $openDs160.disabled = false
    $openDs160.textContent = original
    if (chrome.runtime.lastError || !resp || !resp.ok) {
      setStatus('打开失败: ' + (resp && resp.message || chrome.runtime.lastError && chrome.runtime.lastError.message || '未知错误'), 'err')
      return
    }
    // Close popup — the new tab is the user's destination.
    window.close()
  })
})

// ---------- Bootstrap ----------
function bootstrap() {
  chrome.runtime.sendMessage({ type: 'HTEX_GET_API_BASE' }, (baseResp) => {
    if ($apiBase && baseResp && baseResp.apiBase) {
      $apiBase.value = baseResp.apiBase
    }
  })
  if ($apiBase) {
    $apiBase.addEventListener('change', () => {
      const v = ($apiBase.value || '').trim()
      if (v) chrome.runtime.sendMessage({ type: 'HTEX_SET_API_BASE', apiBase: v })
    })
  }
  chrome.runtime.sendMessage({ type: 'HTEX_GET_META' }, (resp) => {
    if (chrome.runtime.lastError) {
      setStatus('后台消息失败: ' + chrome.runtime.lastError.message, 'err')
      return
    }
    if (resp && resp.meta) {
      showReady(resp.meta)
    } else {
      setStatus('等待输入 code…', 'idle')
      updateRedeemEnabled()
    }
  })
}

bootstrap()