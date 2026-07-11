// journey.js — 美签"流程寻路"配置(数据驱动，classic script → window.HTEX.JOURNEY)
// =============================================================================
// 插件用它:检测用户在哪一步 → 顶部提示 → 高亮该页藏很深的关键按钮 → 指向下一步。
// 与字段映射同样纪律:锚"按钮文本/链接"，带 verifiedDate，URL 会变 → 以官网为准。
//
// ⚠️ v0:预约站/交费 URL 因国家而异且会变，下面 byCountry 里是**待核实占位**，
//    正式用前按国家逐个核对(verifiedDate 目前 null)。DS-160 入口相对稳定。
// =============================================================================
(function () {
  // 各国的面签预约站不同(CGI ustraveldocs / usvisa-info 视国家而定，需核实)
  var APPT_SITE_BY_COUNTRY = {
    VN: { url: 'https://www.ustraveldocs.com/vn/', name: '预约站(越南)', verified: false },
    ID: { url: 'https://www.ustraveldocs.com/id/', name: '预约站(印尼)', verified: false },
    CN: { url: 'https://www.ustraveldocs.com/cn-zh/', name: '预约站(中国)', verified: false },
  }

  var STEPS = [
    {
      id: 'ds160', title: '① 填写 DS-160',
      match: /ceac\.state\.gov\/genniv/i,
      url: 'https://ceac.state.gov/genniv/',
      hint: '这里填 DS-160。先选使领馆 → 点开始 → 填完务必记下 Application ID 和确认码。',
      // 要高亮的关键按钮(按文本/值锚定，多给几个候选防措辞变化)
      locate: [{ text: 'Start an Application' }, { text: 'START APPLICATION' }, { text: '开始申请' }],
      nextId: 'fee_appt',
    },
    {
      id: 'fee_appt', title: '② 交 MRV 费 + 约面签',
      // 站点按国家取(见 APPT_SITE_BY_COUNTRY)
      matchByApptSite: true,
      hint: '在预约站:先交 MRV 签证费(约 $185)→ 用 DS-160 确认码 → 选使领馆和时间约面签。',
      locate: [{ text: 'Schedule Appointment' }, { text: 'New Application' }, { text: 'Continue' }],
      nextId: 'interview',
    },
    {
      id: 'interview', title: '③ 面签',
      hint: '带齐:DS-160 确认页、预约信、护照、照片、材料包。按预约时间到使领馆。',
      locate: [],
      nextId: null,
    },
  ]

  function apptSite(countryCode) {
    return APPT_SITE_BY_COUNTRY[String(countryCode || '').toUpperCase()] || null
  }

  window.HTEX = window.HTEX || {}
  window.HTEX.JOURNEY = { version: '2026.1', verifiedDate: null, steps: STEPS, apptSite: apptSite }
})()
