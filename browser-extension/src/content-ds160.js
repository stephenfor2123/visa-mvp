// content-ds160.js — 注入在 ceac.state.gov/genniv/*。
// 取暂存档案 → 生成引导单 → 悬浮面板 → 用户点"填充本页"→ HTEX.fill 填 + 报告。
// 依赖 mapping.js / fillEngine.js(manifest 里排在本文件之前,window.HTEX 已就绪)。
//
// W48 v0.2 changes:
//   - Read profile from HTEX_GET_META (popup stores {profile, fingerprint, order_id, mapping_version})
//   - Top of panel now shows order id + fingerprint prefix for traceability
//   - Login prompt: when DS-160 is on the auth page, prompt user to log in themselves
//     (extension does NOT handle credentials — see DESIGN-v0.2.md §1 红线)
(function () {
  if (window.__htexPanelMounted) return
  window.__htexPanelMounted = true

  function el(tag, style, text) {
    var e = document.createElement(tag)
    if (style) e.setAttribute('style', style)
    if (text != null) e.textContent = text
    return e
  }

  // ---- session 进度读写 ----
  var PROGRESS_KEY = 'htex_ds160_progress'
  function loadProgress(cb) {
    try { chrome.runtime.sendMessage({ type: 'HTEX_GET_PROGRESS' }, function (r) { cb(r && r.progress || {}) }) }
    catch (e) { cb({}) }
  }
  function saveProgress(progress, cb) {
    try { chrome.runtime.sendMessage({ type: 'HTEX_SAVE_PROGRESS', progress: progress }, function () { cb && cb() }) }
    catch (e) { cb && cb() }
  }

  // ---- W48 v0.2 UX2: page-mode detector ----
  // DS-160 has 3 distinct page kinds before/around the fillable form:
  //   setup   — Getting Started (create AAID, choose location, set security Q)
  //   login   — Sign in to your Application (existing AAID + password)
  //   email   — Pre-form email collection (DS-160 collects your email here)
  //   form    — Personal 1 / Passport / Travel / ... (where we fill)
  //
  // The plugin should:
  //   setup/login/email → show a soft yellow hint, no panel, no auto-fill
  //   form             → mount the fill panel as normal
  //
  // Heuristics are URL + DOM based so they survive the official site's
  // markup changes.  If we misclassify we just show the wrong hint — the
  // worst case is "no panel" which the user can resolve by reloading.
  function detectPageMode() {
    var url = location.href
    var body = (document.body && document.body.innerHTML) || ''
    var text = (document.body && document.body.textContent || '').toLowerCase()

    // Submitted confirmation page: after Sign & Submit, CEAC shows a
    // confirmation page (barcode + "print confirmation").  Detect it FIRST
    // (it may also contain words that match other modes' heuristics).
    // Conservative markers — worst case we miss it and the user just doesn't
    // see the "mark as submitted" banner.
    if (/confirmation/i.test(url) && /ceac\.state\.gov/i.test(url)) return 'submitted'
    if (/your application (has been|was) (successfully )?submitted/i.test(text)) return 'submitted'
    if (/application.{0,40}successfully submitted/i.test(text)) return 'submitted'
    if (/print confirmation/i.test(text) && /confirmation/i.test(text) && !/sign and submit/i.test(text)) return 'submitted'

    // Sign-in: URL or DOM contains auth markers
    if (/ceac\.state\.gov.*(login|signin|sign-in|auth)/i.test(url)) return 'login'
    if (/name=["']?(applicationID|userId|password)/i.test(body)) return 'login'
    if (/sign[\s_-]?in to your application/i.test(text)) return 'login'
    if (/forgot[\s_-]?your[\s_-]?application/i.test(text)) return 'login'

    // Getting Started (new application setup): "Choose a Location", "Security Question"
    if (/choose[\s_-]?a[\s_-]?(location|post|consulate)/i.test(text)) return 'setup'
    if (/security[\s_-]?question/i.test(text) && /security[\s_-]?answer/i.test(text)) return 'setup'
    if (/create[\s_-]?a[\s_-]?new[\s_-]?application/i.test(text)) return 'setup'
    if (/start[\s_-]?a[\s_-]?new[\s_-]?application/i.test(text)) return 'setup'

    // Pre-form email collection: a single Email Address field at the top
    // of the page, no other DS-160 sections visible.  We check for "Email
    // Address" label AND absence of typical fill-page labels.
    var hasEmailLabel = /email[\s_-]?address/i.test(body)
    var hasFillLabel = /(surnames|given names|sex|marital status|date of birth)/i.test(text)
    if (hasEmailLabel && !hasFillLabel) return 'email'

    return 'form'
  }

  // ---- 提交确认页:绿色横幅 + 一键"我已提交完成" ----
  // 红线不变:插件不替用户点 Sign & Submit;只在检测到确认页后请用户自己确认。
  function showSubmittedBanner() {
    chrome.runtime.sendMessage({ type: 'HTEX_GET_META' }, function (resp) {
      var meta = resp && resp.meta
      var orderId = meta && meta.order_id

      var banner = el('div', [
        'position:fixed;left:16px;top:16px;z-index:2147483647;max-width:360px',
        'background:#ecfdf5;color:#065f46;padding:14px 16px;border-radius:12px',
        'font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif',
        'box-shadow:0 8px 22px rgba(0,0,0,.18);border:1px solid #a7f3d0'
      ].join(';'))
      banner.appendChild(el('div', 'font-weight:600;margin-bottom:4px;font-size:14px', '🎉 看起来 DS-160 已提交成功'))

      function renderConfirmed(submittedAt, synced, syncError) {
        banner.innerHTML = ''
        banner.appendChild(el('div', 'font-weight:600;margin-bottom:4px;font-size:14px', '✅ 已记录:DS-160 提交完成'))
        var detail = '确认时间 ' + new Date(submittedAt).toLocaleString() +
          '\n请截图/打印确认页(含条形码),面签要带。下一步:去预约站交 MRV 费 + 约面签。'
        if (synced) detail += '\n\n☁️ 已同步到 Htex 订单'
        else if (syncError) detail += '\n\n⚠️ 本地已记录,同步 Htex 失败:' + syncError
        banner.appendChild(el('div', 'color:#047857', detail))
        banner.style.whiteSpace = 'pre-line'
        addDismiss()
      }

      function addDismiss() {
        var x = el('span', 'position:absolute;top:6px;right:10px;cursor:pointer;color:#065f46;font-size:18px', '×')
        x.onclick = function () { try { banner.remove() } catch (e) {} }
        banner.appendChild(x)
      }

      // 已经确认过 → 直接显示已完成态
      chrome.runtime.sendMessage({ type: 'HTEX_GET_SUBMITTED', orderId: orderId }, function (r) {
        if (r && r.submitted) {
          renderConfirmed(r.submittedAt, r.synced, r.syncError)
          document.body.appendChild(banner)
          return
        }

        banner.appendChild(el('div', 'color:#047857;white-space:pre-line',
          '请核对本页是否显示确认码/条形码。\n确认无误后点下面按钮,插件会记录你已完成提交(只记时间,不上传确认码)。'))
        var btn = el('button', [
          'margin-top:10px;padding:8px 14px;border:0;border-radius:8px;cursor:pointer',
          'background:#059669;color:#fff;font-size:13px;font-weight:600'
        ].join(';'), '✓ 我已提交完成')
        btn.onclick = function () {
          btn.disabled = true
          chrome.runtime.sendMessage({ type: 'HTEX_MARK_SUBMITTED', orderId: orderId }, function (r2) {
            if (r2 && r2.ok) renderConfirmed(r2.submittedAt, r2.synced, r2.syncError)
            else { btn.disabled = false }
          })
        }
        banner.appendChild(btn)
        addDismiss()
        document.body.appendChild(banner)
      })
    })
  }

  function maybeShowPageHint() {
    var mode = detectPageMode()
    if (mode === 'form') return  // fill panel will mount normally
    if (mode === 'submitted') { showSubmittedBanner(); return }

    var messages = {
      login: {
        icon: '🔒',
        title: 'Htex 不替你登录',
        body: '请用你自己的 DS-160 Application ID + 密码登录。插件只填字段, 不碰密码。',
      },
      setup: {
        icon: '🆕',
        title: '这是 Getting Started 页 (创建新申请)',
        body: '选申请地点、创建 Application ID、设安全问题 — 这些步骤必须由你在 DS-160 官网上自己完成。\n填完创建后, 进到第一个填表页 (Personal Info 1) 时 Htex 面板会自动激活。',
      },
      email: {
        icon: '📧',
        title: '这是邮箱收集页',
        body: '请输入你要关联 DS-160 的邮箱地址 — 这一步你自己填, 插件不代填邮箱 (隐私 + 安全)。\n填完后点 Continue, 进到 Personal Info 1 时 Htex 面板会自动激活。',
      },
    }
    var m = messages[mode]
    if (!m) return

    var hint = el('div', [
      'position:fixed;left:16px;top:16px;z-index:2147483647;max-width:340px',
      'background:#fef3c7;color:#92400e;padding:12px 16px;border-radius:12px',
      'font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;',
      'box-shadow:0 8px 22px rgba(0,0,0,.18)',
      'white-space:pre-line'
    ].join(';'))
    hint.appendChild(el('div', 'font-weight:600;margin-bottom:4px;font-size:14px', m.icon + ' ' + m.title))
    hint.appendChild(el('div', null, m.body))
    document.body.appendChild(hint)
    // Stays until user clicks × — this isn't a transient toast.
    var dismiss = el('span', 'position:absolute;top:6px;right:10px;cursor:pointer;color:#92400e;font-size:18px', '×')
    dismiss.onclick = function () { try { hint.remove() } catch (e) {} }
    hint.appendChild(dismiss)
  }
  maybeShowPageHint()

  var panel = el('div', [
    'position:fixed;top:16px;right:16px;z-index:2147483647;width:340px;max-height:82vh;overflow:auto',
    'background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.18)',
    'font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:#111'
  ].join(';'))

  var head = el('div', 'padding:12px 14px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:flex-start')
  var headLeft = el('div')
  headLeft.appendChild(el('strong', 'font-size:14px;display:block', 'Htex · DS-160 辅助填充'))
  var subtitle = el('div', 'color:#6b7280;font-size:11px;margin-top:2px', '')
  headLeft.appendChild(subtitle)
  // W48 v0.2 — order_id + fingerprint strip
  var metaStrip = el('div', 'color:#9ca3af;font-size:10px;margin-top:3px;font-family:ui-monospace,monospace', '')
  headLeft.appendChild(metaStrip)
  head.appendChild(headLeft)
  var close = el('span', 'cursor:pointer;color:#999;font-size:18px;margin-left:8px', '×')
  close.onclick = function () { panel.remove() }
  head.appendChild(close)
  panel.appendChild(head)

  var body = el('div', 'padding:12px 14px')
  panel.appendChild(body)

  function status(msg, color) { var s = el('div', 'margin:6px 0;color:' + (color || '#555'), msg); return s }

  // W48 v0.2 — read meta instead of just profile; extract profile from meta.
  chrome.runtime.sendMessage({ type: 'HTEX_GET_META' }, function (resp) {
    body.innerHTML = ''
    // W48 v0.2 UX2: only mount the fill panel on actual form pages.
    // setup / login / email pages already showed their own hint banner above;
    // we don't want to ALSO render the panel there.
    if (detectPageMode() !== 'form') return
    var meta = resp && resp.meta
    var profile = meta && meta.profile
    if (!profile) {
      body.appendChild(status('还没收到你的资料。请回 Htex 订单详情页拿 12 位 code,在插件弹窗里 Redeem。', '#b45309'))
      document.body.appendChild(panel)
      return
    }
    var guide = window.HTEX.buildGuide(profile)
    var name = ((profile.identity && (profile.identity.surname || '') + ' ' + (profile.identity.givenName || '')).trim()) || '(未命名)'
    var nat = (profile.identity && profile.identity.nationality) || '?'
    subtitle.textContent = name + ' · ' + nat + ' · DS-160 v' + guide.meta.version + (guide.meta.verifiedDate ? '·核对 ' + guide.meta.verifiedDate : '·未核对')
    metaStrip.textContent = '订单 #' + (meta.order_id || '?') + ' · 指纹 ' + (meta.fingerprint || '').slice(0, 12) + '…'
    if (guide.missingCount > 0) {
      body.appendChild(status('⚠️ 有 ' + guide.missingCount + ' 项待补(App 里没数据)', '#b45309'))
    }

    // ---- 跨页累计进度条 ----
    var progressBar = el('div', 'margin:8px 0 12px')
    body.appendChild(progressBar)

    function renderProgressBar(progress) {
      var total = guide.sections.length
      var done = guide.sections.filter(function (s) { return progress[s.section] }).length
      var pct = total ? Math.round((done / total) * 100) : 0
      progressBar.innerHTML = ''
      progressBar.appendChild(el('div', 'font-size:11px;color:#6b7280;margin-bottom:4px',
        '跨页进度 ' + done + '/' + total + ' 节 (' + pct + '%)'))
      var track = el('div', 'height:6px;background:#e5e7eb;border-radius:4px;overflow:hidden')
      var fill = el('div', 'height:100%;background:#16a34a;border-radius:4px;width:' + pct + '%')
      track.appendChild(fill)
      progressBar.appendChild(track)
    }

    // ---- 顶部动作:本节/全部填充 ----
    var actions = el('div', 'display:flex;gap:6px;margin:8px 0')
    var fillAllBtn = el('button', [
      'flex:1;padding:9px;border:0;border-radius:8px;cursor:pointer',
      'background:#111;color:#fff;font-size:13px'
    ].join(';'), '⚡ 填充本页所有字段')
    actions.appendChild(fillAllBtn)
    body.appendChild(actions)

    // 自动跟填
    var autoWrap = el('label', 'display:flex;align-items:center;gap:6px;margin:0 0 10px;color:#6b7280;cursor:pointer;font-size:12px')
    var autoChk = el('input'); autoChk.type = 'checkbox'; autoChk.checked = true
    autoWrap.appendChild(autoChk)
    autoWrap.appendChild(el('span', null, '自动跟填(选了下拉冒出新字段时继续补)'))
    body.appendChild(autoWrap)

    // ---- section 列表 ----
    var sectionsWrap = el('div', 'margin:6px 0')
    body.appendChild(sectionsWrap)

    loadProgress(function (progress) {
      renderProgressBar(progress)
      function renderSections() {
        sectionsWrap.innerHTML = ''
        guide.sections.forEach(function (sec) {
          var row = el('div', [
            'display:flex;align-items:center;gap:6px;padding:6px 0',
            'border-bottom:1px dashed #e5e7eb'
          ].join(';'))
          var badge = el('span', [
            'display:inline-block;min-width:18px;padding:1px 6px;text-align:center',
            'border-radius:10px;font-size:10px;color:#fff'
          ].join(';'), progress[sec.section] ? '✓' : '○')
          badge.style.background = progress[sec.section] ? '#16a34a' : '#9ca3af'
          row.appendChild(badge)
          var title = el('span', 'flex:1;font-size:12px;color:#374151', sec.officialTitle)
          row.appendChild(title)
          var btn = el('button', [
            'padding:4px 10px;border:0;border-radius:6px;cursor:pointer',
            'background:#f3f4f6;color:#111;font-size:11px'
          ].join(';'), '填充这节')
          btn.onclick = function () { runFill(sec.section) }
          row.appendChild(btn)
          sectionsWrap.appendChild(row)
        })
      }
      renderSections()

      function runFill(sectionKey) {
        var doIt = function () {
          var fn = autoChk.checked ? window.HTEX.autoFill : window.HTEX.fill
          var args = sectionKey ? [guide, sectionKey] : [guide]
          var report = fn.apply(null, args.concat(autoChk.checked ? [{ onUpdate: handleReport, watchMs: 5000 }] : []))
          if (!autoChk.checked) handleReport(report)
          // 标进度(任何一项 filled 或 na 都算这节已动手)
          var any = report.results.some(function (r) { return r.status === 'filled' || r.status === 'na' })
          if (any) {
            progress[sectionKey || '*all*'] = Date.now()
            saveProgress(progress, function () {
              renderProgressBar(progress)
              renderSections()
            })
          }
        }
        doIt()
      }

      fillAllBtn.onclick = function () { runFill(null) }
    })

    // ---- 折叠报告 ----
    var reportWrap = el('div', 'margin:10px 0 0;padding-top:8px;border-top:1px solid #f0f0f0')
    body.appendChild(reportWrap)
    var reportHeader = el('div', 'cursor:pointer;user-select:display:flex;justify-content:space-between;align-items:center', '')
    reportHeader.appendChild(el('span', 'font-size:12px;color:#374151;font-weight:600', '📋 填充报告(点开/折叠)'))
    var reportToggle = el('span', 'font-size:11px;color:#9ca3af', '▾')
    reportHeader.appendChild(reportToggle)
    reportWrap.appendChild(reportHeader)
    var reportBody = el('div', 'display:none;margin-top:6px')
    reportWrap.appendChild(reportBody)
    var reportOpen = false
    reportHeader.onclick = function () {
      reportOpen = !reportOpen
      reportBody.style.display = reportOpen ? 'block' : 'none'
      reportToggle.textContent = reportOpen ? '▴' : '▾'
    }

    function handleReport(report) {
      // 顶栏统计
      reportBody.innerHTML = ''
      var s = report.summary || {}
      reportBody.appendChild(status(
        '已填 ' + (s.filled || 0) + ' · DoesNotApply ' + (s.na || 0) +
        ' · 没找到 ' + (s.not_found || 0) + ' · 待补 ' + (s.manual || 0),
        '#111'))
      // 全列出(成功 + 失败)
      report.results.forEach(function (r) {
        var color = '#9ca3af'
        if (r.status === 'filled') color = '#16a34a'
        else if (r.status === 'na') color = '#0ea5e9'
        else if (r.status === 'manual') color = '#b45309'
        else if (r.status === 'not_found') color = '#9ca3af'
        var icon = r.status === 'filled' ? '✓'
          : r.status === 'na' ? '○'
          : r.status === 'manual' ? '⚠'
          : '✗'
        var line = el('div', 'margin:2px 0;color:' + color + ';font-size:11px', '')
        line.appendChild(document.createTextNode(icon + ' ' + (r.section ? '[' + r.section + '] ' : '') + r.label))
        if (r.value) line.appendChild(document.createTextNode(' → ' + r.value))
        if (r.reason) line.appendChild(document.createTextNode(' (' + r.reason + ')'))
        reportBody.appendChild(line)
      })
      // 自动展开让人看到结果
      if (!reportOpen) {
        reportOpen = true
        reportBody.style.display = 'block'
        reportToggle.textContent = '▴'
      }
    }

    document.body.appendChild(panel)
  })
})()