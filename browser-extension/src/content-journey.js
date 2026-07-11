// content-journey.js — 寻路编排:检测当前在旅程哪一步 → 底部提示条 + 高亮关键按钮。
// 注入在 ceac.state.gov 与预约站。依赖 journey.js / wayfinder.js(manifest 排在前)。
(function () {
  if (window.__htexWayMounted) return
  window.__htexWayMounted = true
  var J = window.HTEX && window.HTEX.JOURNEY, W = window.HTEX && window.HTEX.way
  if (!J || !W) return

  // 国籍 → 国家码(取预约站用)
  function toCode(nat) {
    var m = { vietnam: 'VN', 'viet nam': 'VN', indonesia: 'ID', china: 'CN', 'people\'s republic of china': 'CN' }
    return m[String(nat || '').trim().toLowerCase()] || String(nat || '').toUpperCase().slice(0, 2)
  }

  function showBar(step, nextSite) {
    var bar = document.createElement('div')
    bar.setAttribute('style', [
      'position:fixed;left:16px;bottom:16px;z-index:2147483647;max-width:360px',
      'background:#111;color:#fff;padding:12px 14px;border-radius:12px',
      'font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.25)'
    ].join(';'))
    bar.innerHTML = '<div style="font-weight:600;margin-bottom:4px">Htex 领路 · ' + step.title + '</div>' +
      '<div style="color:#d1d5db">' + step.hint + '</div>'
    if (nextSite) {
      var b = document.createElement('button')
      b.textContent = '带我去下一步:' + nextSite.name + (nextSite.verified ? '' : '(链接待核实)')
      b.setAttribute('style', 'margin-top:8px;padding:6px 10px;border:0;border-radius:8px;background:#f97316;color:#fff;cursor:pointer')
      b.onclick = function () { window.open(nextSite.url, '_blank') }
      bar.appendChild(b)
    }
    var x = document.createElement('span')
    x.textContent = '×'; x.setAttribute('style', 'position:absolute;top:8px;right:12px;cursor:pointer;color:#9ca3af')
    x.onclick = function () { bar.remove() }
    bar.appendChild(x)
    document.body.appendChild(bar)
  }

  chrome.runtime.sendMessage({ type: 'HTEX_GET_PROFILE' }, function (resp) {
    var cc = resp && resp.profile && resp.profile.identity ? toCode(resp.profile.identity.nationality) : null
    var step = W.detectStep(J, location.href, cc)
    if (!step) return
    // 下一步站点(若下一步是按国家的预约站)
    var nextSite = null
    if (step.nextId) {
      var next = J.steps.filter(function (s) { return s.id === step.nextId })[0]
      if (next && next.matchByApptSite && cc) nextSite = J.apptSite(cc)
    }
    showBar(step, nextSite)
    // 高亮本页藏很深的关键按钮
    if (step.locate && step.locate.length) {
      var el = W.locate(step.locate)
      if (el) W.highlight(el, step.hint)
    }
  })
})()
