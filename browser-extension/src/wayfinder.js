// wayfinder.js — 寻路:定位藏很深的关键元素 + 高亮指引(classic → window.HTEX.way)
// =============================================================================
// locate(hints)  按文本/href/selector 找到目标元素(锚"用户看得见的东西"，抗改版)
// highlight(el)  滚动过去 + 亮框 + 浮标箭头，把埋得深的按钮"指给用户看"
// detectStep()   根据当前 URL 判断在旅程哪一步
// 只做"指路"，不替用户点政府站按钮(合规 + 安全)。
// =============================================================================
(function () {
  function norm(s) { return String(s || '').replace(/\s+/g, ' ').trim().toLowerCase() }
  function textMatch(a, b) { a = norm(a); b = norm(b); return !!a && !!b && (a === b || a.indexOf(b) !== -1) }

  var CLICKABLE = 'a, button, input[type=submit], input[type=button], [role=button]'

  // 按一组 hint 候选找元素;hint 支持 {selector} / {text} / {href}
  function locate(hints) {
    hints = hints || []
    for (var i = 0; i < hints.length; i++) {
      var h = hints[i]
      if (h.selector) { var bySel = document.querySelector(h.selector); if (bySel) return bySel }
      if (h.href) {
        var byHref = Array.prototype.slice.call(document.querySelectorAll('a[href]'))
          .filter(function (a) { return a.getAttribute('href').indexOf(h.href) !== -1 })[0]
        if (byHref) return byHref
      }
      if (h.text) {
        var cand = Array.prototype.slice.call(document.querySelectorAll(CLICKABLE)).filter(function (e) {
          var t = e.value || e.textContent || e.getAttribute('aria-label') || ''
          return textMatch(t, h.text)
        })
        // 偏好文本最短的(最贴近那个按钮，而不是包含它的大容器)
        cand.sort(function (a, b) { return (a.textContent || a.value || '').length - (b.textContent || b.value || '').length })
        if (cand[0]) return cand[0]
      }
    }
    return null
  }

  // 高亮 + 浮标。返回一个 dispose() 清除高亮。
  function highlight(el, message) {
    if (!el) return function () {}
    try { el.scrollIntoView({ behavior: 'smooth', block: 'center' }) } catch (e) {}
    var prevOutline = el.style.outline, prevOffset = el.style.outlineOffset
    el.style.outline = '3px solid #f97316'
    el.style.outlineOffset = '2px'

    var tip = document.createElement('div')
    tip.setAttribute('data-htex-tip', '1')
    tip.textContent = '👉 ' + (message || '点这里')
    tip.setAttribute('style', [
      'position:absolute;z-index:2147483647;background:#f97316;color:#fff',
      'padding:6px 10px;border-radius:8px;font:13px -apple-system,Segoe UI,sans-serif',
      'box-shadow:0 4px 14px rgba(0,0,0,.25);max-width:240px'
    ].join(';'))
    document.body.appendChild(tip)
    try {
      var r = el.getBoundingClientRect()
      tip.style.left = (window.scrollX + r.left) + 'px'
      tip.style.top = (window.scrollY + r.top - 40) + 'px'
    } catch (e) {}

    function dispose() {
      el.style.outline = prevOutline; el.style.outlineOffset = prevOffset
      if (tip.parentNode) tip.parentNode.removeChild(tip)
    }
    return dispose
  }

  // 判断当前在旅程哪一步
  function detectStep(journey, url, countryCode) {
    url = url || (window.location && window.location.href) || ''
    for (var i = 0; i < journey.steps.length; i++) {
      var st = journey.steps[i]
      if (st.match && st.match.test(url)) return st
      if (st.matchByApptSite) {
        var site = journey.apptSite(countryCode)
        if (site && url.indexOf(site.url.replace(/^https?:\/\//, '')) !== -1) return st
      }
    }
    return null
  }

  window.HTEX = window.HTEX || {}
  window.HTEX.way = { locate: locate, highlight: highlight, detectStep: detectStep }
})()
