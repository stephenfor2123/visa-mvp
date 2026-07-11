// fillEngine.js — DS-160 页面填充引擎(classic script → window.HTEX.fill)
// =============================================================================
// 策略:**锚字段标签**，不依赖官网会变的 ASP.NET 元素 ID。
//   对每个 step:按 label 文本在页面上定位对应的输入框 → 按类型填值 →
//   派发 input/change 事件(ASP.NET/前端框架靠事件联动) → 返回逐项结果。
//
// 定位顺序(从强到弱):
//   1. <label>文本匹配 → for=id → #id
//   2. 含该文本的单元格/元素 → 同 <tr> 行内的 input/select/textarea
//   3. 含该文本元素之后最近的表单控件
// 找不到就标 not_found，交给面板提示用户手填 —— 绝不乱填别的框。
// =============================================================================
(function () {
  function norm(s) { return String(s || '').replace(/\s+/g, ' ').trim().toLowerCase() }

  // label 文本可能带 * / 冒号 / 破折号，做宽松包含匹配
  function labelMatches(text, target) {
    var a = norm(text), b = norm(target)
    if (!a || !b) return false
    return a === b || a.indexOf(b) !== -1 || b.indexOf(a) !== -1
  }

  function controlsIn(root) {
    return Array.prototype.slice.call(root.querySelectorAll('input, select, textarea'))
      .filter(function (el) {
        var t = (el.type || '').toLowerCase()
        return t !== 'hidden' && t !== 'submit' && t !== 'button' && !el.disabled
      })
  }

  // 按 label 找到主输入控件
  function findControl(labelText) {
    // 1. <label for=...>
    var labels = Array.prototype.slice.call(document.querySelectorAll('label'))
    for (var i = 0; i < labels.length; i++) {
      if (labelMatches(labels[i].textContent, labelText)) {
        var forId = labels[i].getAttribute('for')
        if (forId) { var byId = document.getElementById(forId); if (byId) return byId }
        var inside = controlsIn(labels[i].parentNode || labels[i])
        if (inside.length) return inside[0]
      }
    }
    // 2/3. 任意含该文本的元素 → 同行(tr) 或其后最近控件
    var all = Array.prototype.slice.call(document.querySelectorAll('td, th, span, div, p, label'))
    for (var j = 0; j < all.length; j++) {
      var node = all[j]
      if (node.children.length > 3) continue // 跳过大容器，找最贴近的文本节点
      if (!labelMatches(node.textContent, labelText)) continue
      var row = node.closest ? node.closest('tr') : null
      if (row) { var inRow = controlsIn(row); if (inRow.length) return inRow[0] }
      // 其后最近控件
      var sib = node.nextElementSibling
      while (sib) { var c = controlsIn(sib); if (c.length) return c[0]; sib = sib.nextElementSibling }
    }
    return null
  }

  function fire(el, type) { el.dispatchEvent(new Event(type, { bubbles: true })) }

  function setText(el, value) {
    var proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement : window.HTMLInputElement
    var setter = Object.getOwnPropertyDescriptor(proto.prototype, 'value').set
    setter.call(el, value)
    fire(el, 'input'); fire(el, 'change')
  }

  function setSelect(el, value) {
    var opts = Array.prototype.slice.call(el.options)
    // 先精确(避免 MALE 被 FEMALE 子串命中)，再退子串
    var hit = opts.filter(function (o) { return norm(o.textContent) === norm(value) || norm(o.value) === norm(value) })[0]
    if (!hit) hit = opts.filter(function (o) { return labelMatches(o.textContent, value) })[0]
    if (!hit) return false
    el.value = hit.value; fire(el, 'change')
    return true
  }

  // radio/checkbox:在同一命名组里找 label 匹配 value 的那个(YES/NO 等)
  function setChoice(el, value) {
    var name = el.name
    var group = name ? Array.prototype.slice.call(document.getElementsByName(name)) : [el]
    // 先精确匹配 value，再退子串(避免 NO 被别的选项误配)
    for (var pass = 0; pass < 2; pass++) {
      for (var i = 0; i < group.length; i++) {
        var r = group[i]
        var lbl = r.closest && r.closest('label') ? r.closest('label')
          : (r.id ? document.querySelector('label[for="' + r.id + '"]') : null)
        var txt = lbl ? lbl.textContent : (r.value || '')
        var exact = norm(txt) === norm(value) || norm(r.value) === norm(value)
        if (pass === 0 ? exact : labelMatches(txt, value)) {
          r.checked = true; fire(r, 'click'); fire(r, 'change'); return true
        }
      }
    }
    return false
  }

  // 在若干选项里按候选值精确命中一个 option
  function pickOption(sel, candidates) {
    var opts = Array.prototype.slice.call(sel.options)
    for (var i = 0; i < candidates.length; i++) {
      var cand = candidates[i]
      var hit = opts.filter(function (o) { return norm(o.textContent) === norm(cand) || norm(o.value) === norm(cand) })[0]
      if (hit) { sel.value = hit.value; fire(sel, 'change'); return true }
    }
    return false
  }

// 真 DS-160 的日期是 Day/Month/Year 三个控件(月是 select JAN..DEC;
// Day 是 select 1-31 / 文本框;Year 是 select 4 位 / 文本框)。
// 从字段所在行里按"内容"识别三个控件(而非 ID),分别填 —— 抗官网改版。
// 任何一项只要有一个对应控件(sibling),就视为 OK。
function fillDate(step, anchorEl) {
  var row = (anchorEl.closest && anchorEl.closest('tr')) || anchorEl.parentNode
  var m = String(step.value).match(/^(\d{1,2})-([A-Z]{3})-(\d{4})$/)
  if (!m) { // 不是 DD-MMM-YYYY:退回单控件填
    if (anchorEl.tagName.toLowerCase() === 'select') return pickOption(anchorEl, [step.value]) ? okStep(step) : nf(step)
    setText(anchorEl, step.value); return okStep(step)
  }
  var day = m[1], mon = m[2], year = m[3]

  // 收集所有控件 — 包括 anchor 自身(它可能是 day/month/year 之一)
  var allInRow = controlsIn(row)
  // 显式区分:含 JAN..DEC 的 select = month;纯数字 select = day(1-31);4位 select = year
  var monthSel = null, daySel = null, yearSel = null
  var dayInput = null, yearInput = null
  var monthInput = null
  allInRow.forEach(function (el) {
    if (el.tagName.toLowerCase() === 'select') {
      var opts = Array.prototype.slice.call(el.options).map(function (o) { return norm(o.textContent) + ' ' + norm(o.value) }).join(' ')
      if (/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/.test(opts) && !monthSel) monthSel = el
      else if (/^\d+$/.test(opts.replace(/\s+/g, '')) && opts.length < 200 && !daySel) daySel = el
      else if (!yearSel) yearSel = el
    }
  })
  // 文本框:可能是 day 或 year;按 size 区分;size<=4 当 day,否则 year
  var textInputs = allInRow.filter(function (el) {
    return el.tagName.toLowerCase() === 'input' && (el.type === 'text' || el.type === 'number')
  })
  textInputs.forEach(function (el) {
    var sz = (el.size || el.getAttribute('size') || '').toString()
    var maxlen = (el.maxLength || el.getAttribute('maxlength') || '').toString()
    if ((sz && +sz <= 4) || (maxlen && +maxlen <= 4)) {
      if (!dayInput) dayInput = el
    } else {
      if (!yearInput) yearInput = el
    }
  })

  // 填 day:优先用 day select,其次 day input
  var dayOk = false
  if (daySel) dayOk = pickOption(daySel, [day, String(+day), String(+day).padStart(2, '0')])
  else if (dayInput) { setText(dayInput, day); dayOk = true }
  else if (anchorEl && anchorEl.tagName.toLowerCase() === 'input' && anchorEl !== daySel) {
    // anchor 本身就是 day input (label 锚到这个 input)
    setText(anchorEl, day); dayOk = true
  }
  // 填 month
  var monOk = monthSel ? pickOption(monthSel, [mon]) : false
  // 填 year:优先 year input(4位文本框),其次 year select
  var yearOk = false
  if (yearInput) { setText(yearInput, year); yearOk = true }
  else if (textInputs.length) {
    // fallback:最后那个文本框是 year
    var last = textInputs[textInputs.length - 1]
    if (last !== dayInput) { setText(last, year); yearOk = true }
  }
  else if (yearSel) yearOk = pickOption(yearSel, [year])

  if (dayOk && monOk && yearOk) {
    try { (monthSel || daySel || anchorEl).style.outline = '2px solid #22c55e' } catch (e) {}
    return { label: step.label, status: 'filled', value: step.value }
  }
  return { label: step.label, status: 'not_found',
    reason: '日期三连框只填到 ' + [dayOk ? '日' : '', monOk ? '月' : '', yearOk ? '年' : ''].filter(Boolean).join('/') + '，请手动补齐' }
}
  function okStep(step) { return { label: step.label, status: 'filled', value: step.value } }
  function nf(step) { return { label: step.label, status: 'not_found', reason: '控件类型不匹配' } }

  // 填一个 step；返回 {label, status, value}
  function fillOne(step) {
    if (step.action === 'todo') return { label: step.label, status: 'manual', reason: '待补:App 里没这项数据' }
    var el = findControl(step.label)
    if (!el) return { label: step.label, status: 'not_found', reason: '页面上没找到这个框(可能不在本页/官网改版)' }

    // Does Not Apply:找该字段附近的 NA 复选框
    if (step.action === 'na') {
      var row = el.closest ? el.closest('tr') : document
      var na = row ? Array.prototype.slice.call(row.querySelectorAll('input[type=checkbox]'))
        .filter(function (c) {
          var lbl = c.id ? document.querySelector('label[for="' + c.id + '"]') : null
          return lbl && /does not apply|n\/a/i.test(lbl.textContent)
        })[0] : null
      if (na) { na.checked = true; fire(na, 'click'); fire(na, 'change'); return { label: step.label, status: 'na', value: 'Does Not Apply' } }
      return { label: step.label, status: 'manual', reason: '可选项，请自行勾 Does Not Apply' }
    }

    // 日期字段:三连下拉/文本框拆填
    if (step.input === 'date') return fillDate(step, el)

    var tag = el.tagName.toLowerCase()
    var ok
    if (tag === 'select') ok = setSelect(el, step.value)
    else if (el.type === 'radio' || el.type === 'checkbox') ok = setChoice(el, step.value)
    else { setText(el, step.value); ok = true }

    if (ok) { try { el.style.outline = '2px solid #22c55e' } catch (e) {} return { label: step.label, status: 'filled', value: step.value } }
    return { label: step.label, status: 'not_found', reason: '控件类型不匹配或选项对不上:' + step.value }
  }

  function summarize(results) {
    return results.reduce(function (a, r) { a[r.status] = (a[r.status] || 0) + 1; return a }, {})
  }

  // 填当前页能填的所有 step;section 参数可选(限定只填某页)
  function fillGuide(guide, sectionKey) {
    var results = []
    guide.sections.forEach(function (sec) {
      if (sectionKey && sec.section !== sectionKey) return
      sec.steps.forEach(function (s) { results.push(Object.assign({ section: sec.officialTitle }, fillOne(s))) })
    })
    return { results: results, summary: summarize(results) }
  }

  function debounce(fn, ms) {
    var t
    return function () { clearTimeout(t); t = setTimeout(fn, ms) }
  }
  function allSteps(guide) {
    var out = []
    guide.sections.forEach(function (sec) { sec.steps.forEach(function (s) { out.push({ step: s, section: sec.officialTitle }) }) })
    return out
  }

  // 自动跟填:先填一遍，然后监听 DOM。DS-160 里选某些下拉会 postback 冒出新字段，
  // 新字段出现时把之前 not_found 的 step 再补填一次，直到都填上或超时。
  // onUpdate(report) 每次变化回调，供面板刷新。
  function autoFill(guide, opts) {
    opts = opts || {}
    var watchMs = opts.watchMs || 5000
    var steps = allSteps(guide)
    var first = fillGuide(guide)
    if (opts.onUpdate) opts.onUpdate(first)

    // 需要"等新字段出现"再试的:当前 not_found 的(可能还没渲染出来)
    var byLabel = {}
    first.results.forEach(function (r) { byLabel[r.label] = r })
    function pending() {
      return steps.filter(function (x) { var r = byLabel[x.step.label]; return r && r.status === 'not_found' })
    }
    if (!pending().length) return first

    var obs
    var retry = debounce(function () {
      var did = false
      pending().forEach(function (x) {
        var r = fillOne(x.step)
        if (r.status !== byLabel[x.step.label].status) {
          byLabel[x.step.label] = Object.assign({ section: x.section }, r); did = true
        }
      })
      if (did && opts.onUpdate) {
        var results = steps.map(function (x) { return byLabel[x.step.label] })
        opts.onUpdate({ results: results, summary: summarize(results) })
      }
      if (!pending().length && obs) obs.disconnect()
    }, 250)

    obs = new (window.MutationObserver || MutationObserver)(retry)
    obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'hidden'] })
    setTimeout(function () { if (obs) obs.disconnect() }, watchMs)
    return first
  }

  window.HTEX = window.HTEX || {}
  window.HTEX.fill = fillGuide
  window.HTEX.autoFill = autoFill
  window.HTEX.findControl = findControl // 导出便于测试
})()
