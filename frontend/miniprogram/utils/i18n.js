// utils/i18n.js
// 轻量 i18n:支持 zh-CN / en / id / vi 4 语种(对齐 web 端 + 扩展印尼/越南)
// 微信小程序没有原生 i18n,自实现一份 (key 路径以 "." 分隔,fallback zh-CN)
class I18n {
  constructor(locale) {
    this.locale = locale || 'zh-CN'
    this.dicts = {
      'zh-CN': require('../i18n/zh-CN.json'),
      'en': require('../i18n/en.json'),
      'id': require('../i18n/id.json'),
      'vi': require('../i18n/vi.json')
    }
  }

  setLocale(locale) {
    this.locale = locale
  }

  // 查 key: "login.title" → dicts[locale].login.title
  t(key, vars) {
    const dict = this.dicts[this.locale] || this.dicts['zh-CN']
    const fallbackDict = this.dicts['zh-CN']
    const parts = key.split('.')
    let val = dict
    for (const p of parts) {
      if (val && typeof val === 'object' && p in val) {
        val = val[p]
      } else {
        val = undefined
        break
      }
    }
    if (val === undefined) {
      // 兜底 zh-CN
      val = fallbackDict
      for (const p of parts) {
        if (val && typeof val === 'object' && p in val) {
          val = val[p]
        } else {
          val = key  // 兜底兜底:返回 key 自身,避免页面 crash
          break
        }
      }
    }
    if (typeof val === 'string' && vars) {
      return val.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? String(vars[k]) : m))
    }
    return val
  }
}

module.exports = { I18n }
