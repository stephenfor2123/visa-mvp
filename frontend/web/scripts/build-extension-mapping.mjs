#!/usr/bin/env node
// scripts/build-extension-mapping.mjs
// =============================================================================
// 把 web 端的 ds160FieldMap.js (权威源, ESM) 转换成浏览器插件用的 classic
// script IIFE,挂在 window.HTEX.MAP / window.HTEX.buildGuide。
//
// 同时把所有声明式 `when` 在构建时编译成 JS 函数,插件运行时零开销。
//
// 用法:
//   node scripts/build-extension-mapping.mjs           # 写文件
//   node scripts/build-extension-mapping.mjs --check   # 仅校验,不一致 exit 1
//
// 设计:此脚本只在 web 端跑,插件 IIFE 是它的产出物,不双向同步。
// =============================================================================
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve } from 'node:path'
import { createHash } from 'node:crypto'

const __dirname = dirname(fileURLToPath(import.meta.url))
// scripts/build-extension-mapping.mjs 位于 frontend/web/scripts/
// WEB_ROOT = frontend/web;PROJECT_ROOT = 项目根(包含 frontend/ 和 browser-extension/)
const WEB_ROOT = resolve(__dirname, '..')
const PROJECT_ROOT = resolve(WEB_ROOT, '..', '..')

const SRC = resolve(WEB_ROOT, 'src/data/ds160FieldMap.js')
const OUT = resolve(PROJECT_ROOT, 'browser-extension/src/mapping.js')
const CHECK = process.argv.includes('--check')

// 读取源 ESM 文件,把它当模块导入拿到 DS160_FIELD_MAP / buildDs160Guide
// 注意:ds160FieldMap.js 依赖 ./ds160When.js,文件 URL 要正确
const srcUrl = pathToFileURL(SRC).href
const { DS160_FIELD_MAP, DS160_VERSION, DS160_VERIFIED_DATE, DS160_MANUAL_STEPS, buildDs160Guide } =
  await import(srcUrl)

// 把声明式 when 编译成函数 + 内联 _looseEqual / _isNonEmpty / _get helpers
function compileWhenToFn(decl) {
  if (decl == null) return 'function (p) { return true }'
  if (decl === true) return 'function (p) { return true }'
  if (decl === false) return 'function (p) { return false }'
  if (Array.isArray(decl)) {
    return 'function (p) { return ' + decl.map(d => {
      if (typeof d === 'string') return '(_isNonEmpty(_get(p, ' + JSON.stringify(d) + ')))'
      return '(' + compileWhenToFn(d).replace(/^function \(p\) \{ return /, '').replace(/ \}$/, '') + ')'
    }).join(' && ') + ' }'
  }
  if (typeof decl !== 'object') return 'function (p) { return ' + JSON.stringify(Boolean(decl)) + ' }'
  const keys = Object.keys(decl)
  if (keys.length === 0) return 'function (p) { return true }'
  const op = keys[0], args = decl[op]
  switch (op) {
    case 'eq':
      return 'function (p) { return _looseEqual(_get(p, ' + JSON.stringify(args[0]) + '), ' + JSON.stringify(args[1]) + ') }'
    case 'ne':
      return 'function (p) { return !_looseEqual(_get(p, ' + JSON.stringify(args[0]) + '), ' + JSON.stringify(args[1]) + ') }'
    case 'exists':
      return 'function (p) { return _isNonEmpty(_get(p, ' + JSON.stringify(args) + ')) }'
    case 'notExists':
      return 'function (p) { return !_isNonEmpty(_get(p, ' + JSON.stringify(args) + ')) }'
    case 'and':
      return 'function (p) { return ' + args.map(a => '(' + compileWhenToFn(a).replace(/^function \(p\) \{ return /, '').replace(/ \}$/, '') + ')').join(' && ') + ' }'
    case 'or':
      return 'function (p) { return ' + args.map(a => '(' + compileWhenToFn(a).replace(/^function \(p\) \{ return /, '').replace(/ \}$/, '') + ')').join(' || ') + ' }'
    case 'not':
      return 'function (p) { return !(' + compileWhenToFn(args).replace(/^function \(p\) \{ return /, '').replace(/ \}$/, '') + ') }'
    default:
      throw new Error('build-extension-mapping: 未知 op ' + op)
  }
}

const MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']

// 转成可序列化结构(when 函数化 + 丢掉 note/transform 等无关 plugin 字段保留 input/valueMap)
const mapForExt = DS160_FIELD_MAP.map(sec => ({
  section: sec.section,
  officialTitle: sec.officialTitle,
  manual: !!sec.manual,
  note: sec.note,
  // when 编译成函数字符串,IIFE 里直接 eval
  whenSrc: sec.when ? compileWhenToFn(sec.when) : null,
  fields: sec.fields.map(f => ({
    label: f.label,
    profile: f.profile,
    input: f.input,
    transform: f.transform,
    valueMap: f.valueMap,
    optional: !!f.optional,
    note: f.note,
    whenSrc: f.when ? compileWhenToFn(f.when) : null,
  })),
}))

// IIFE 输出 — 完全 self-contained,不再 import 任何东西
const output = `// mapping.js — DS-160 字段映射 + 引导单生成(插件版,classic script)
// =============================================================================
// ⚠️ 自动生成 — 不要手改。请改 frontend/web/src/data/ds160FieldMap.js 后跑:
//    cd frontend/web && node scripts/build-extension-mapping.mjs
// =============================================================================
(function () {
  var VERSION = ${JSON.stringify(DS160_VERSION)}
  var VERIFIED_DATE = ${JSON.stringify(DS160_VERIFIED_DATE)}
  var MONTHS = ${JSON.stringify(MONTHS)}

  // ---- when helpers (跟 ds160When.js 行为一致) ----
  function _get(o, p) {
    if (o == null) return undefined
    return String(p).split('.').reduce(function (a, k) { return a == null ? undefined : a[k] }, o)
  }
  function _isNonEmpty(v) {
    if (v === undefined || v === null) return false
    if (typeof v === 'string') return v.trim() !== ''
    if (typeof v === 'boolean') return true
    if (typeof v === 'number') return !Number.isNaN(v)
    if (Array.isArray(v)) return v.length > 0
    if (typeof v === 'object') return Object.keys(v).length > 0
    return true
  }
  function _boolCoerce(v) {
    if (typeof v === 'boolean') return v
    if (typeof v === 'string') {
      var s = v.trim().toLowerCase()
      if (s === 'true' || s === 'yes' || s === '1') return true
      return false
    }
    return Boolean(v)
  }
  function _looseEqual(a, b) {
    if (a === b) return true
    if (a == null && b == null) return true
    if (typeof a === 'boolean' || typeof b === 'boolean') return _boolCoerce(a) === _boolCoerce(b)
    if (typeof a === 'number' || typeof b === 'number') {
      var na = Number(a), nb = Number(b)
      if (!Number.isNaN(na) && !Number.isNaN(nb)) return na === nb
    }
    if (typeof a === 'string' && typeof b === 'string') {
      return a.trim().toLowerCase() === b.trim().toLowerCase()
    }
    return false
  }

  // ---- field map (when 编译成函数) ----
  var MAP = ${JSON.stringify(mapForExt, null, 2)
    // 函数字符串要可 eval — 还原 \n
    .replace(/\\\\n/g, '\\n')
    .replace(/\\\\"/g, '\\"')}

  // ---- 日期归一 ----
  function _toDs160Date(raw) {
    var m = String(raw).trim().match(/^(\\d{4})[-/.](\\d{1,2})[-/.](\\d{1,2})$/)
    if (!m) return String(raw)
    var mon = MONTHS[+m[2] - 1]
    if (!mon) return String(raw)
    return String(+m[3]).padStart(2, '0') + '-' + mon + '-' + m[1]
  }
  function _getField(o, p) { return _get(o, p) }
  function _isEmpty(v) { return !_isNonEmpty(v) }

  function _isEmpty(v) { return !_isNonEmpty(v) }

  function _coerceBoolForValueMap(raw) {
    if (raw === true || raw === false) return raw
    var s = String(raw).trim().toLowerCase()
    if (s === 'true' || s === 'yes' || s === 'y' || s === '1') return true
    if (s === 'false' || s === 'no' || s === 'n' || s === '0') return false
    return raw
  }

  function _resolveValueMap(raw, valueMap) {
    if (!valueMap || _isEmpty(raw)) return raw
    if (valueMap[raw] !== undefined) return valueMap[raw]
    if (valueMap[String(raw)] !== undefined) return valueMap[String(raw)]
    var coerced = _coerceBoolForValueMap(raw)
    if (coerced !== raw && valueMap[coerced] !== undefined) return valueMap[coerced]
    var up = String(raw).trim().toUpperCase()
    var vals = Object.keys(valueMap).map(function (k) { return valueMap[k] })
    for (var i = 0; i < vals.length; i++) {
      if (String(vals[i]).toUpperCase() === up) return vals[i]
    }
    for (var j = 0; j < vals.length; j++) {
      var vu = String(vals[j]).toUpperCase()
      if (vu.indexOf(up) !== -1 || up.indexOf(vu) !== -1) return vals[j]
    }
    return raw
  }

  // ---- 字段解析 ----
  function resolveField(field, profile) {
    var raw = _getField(profile, field.profile)
    if (_isEmpty(raw)) {
      if (field.optional) return { label: field.label, profile: field.profile, input: field.input, action: 'na', value: 'Does Not Apply', missing: false, optional: true, note: field.note }
      return { label: field.label, profile: field.profile, input: field.input, action: 'todo', value: null, missing: true, optional: false, note: field.note }
    }
    var value = _resolveValueMap(raw, field.valueMap)
    if (field.transform === 'upper') value = String(value).toUpperCase()
    else if (field.transform === 'date') value = _toDs160Date(value)
    return { label: field.label, profile: field.profile, input: field.input, action: 'fill', value: value, missing: false, optional: !!field.optional, note: field.note }
  }

  // ---- 编译 when 函数字符串 → 真函数 ----
  // src 形如 "function (p) { return _looseEqual(...) }"
  // 提取函数体含 return,包进 new Function 即可
  function _compileWhenSrc(src) {
    var open = src.indexOf('{')
    var close = src.lastIndexOf('}')
    var body = src.substring(open + 1, close)
    return new Function('p', '_get', '_isNonEmpty', '_looseEqual', '_boolCoerce', body)
  }

  // ---- 引导单生成 ----
  function buildGuide(profile) {
    profile = profile || {}
    var missingCount = 0
    var sections = MAP
      .map(function (sec) {
        // 把 whenSrc 编译成真函数
        var secWhen = sec.whenSrc ? _compileWhenSrc(sec.whenSrc) : null
        var secPass = !sec.manual && (!secWhen || secWhen(profile, _get, _isNonEmpty, _looseEqual, _boolCoerce))
        if (!secPass) return null
        var steps = sec.fields
          .filter(function (f) {
            if (!f.whenSrc) return true
            var fn = _compileWhenSrc(f.whenSrc)
            return fn(profile, _get, _isNonEmpty, _looseEqual, _boolCoerce)
          })
          .map(function (f) {
            var s = resolveField(f, profile)
            if (s.missing) missingCount++
            return s
          })
        return { section: sec.section, officialTitle: sec.officialTitle, manual: sec.manual, steps: steps }
      })
      .filter(function (s) { return s !== null })
    return {
      meta: { version: VERSION, verifiedDate: VERIFIED_DATE },
      sections: sections,
      manualSteps: ${JSON.stringify(DS160_MANUAL_STEPS)},
      missingCount: missingCount,
    }
  }

  window.HTEX = window.HTEX || {}
  window.HTEX.MAP = MAP
  window.HTEX.buildGuide = buildGuide
})()
`

if (CHECK) {
  // 校验模式:对比现有文件 + sha256
  let existing
  try { existing = readFileSync(OUT, 'utf8') } catch (e) {
    console.error('❌ mapping.js 不存在,请先跑 build')
    process.exit(1)
  }
  const hashExist = createHash('sha256').update(existing).digest('hex')
  const hashNew = createHash('sha256').update(output).digest('hex')
  if (hashExist !== hashNew) {
    console.error('❌ browser-extension/src/mapping.js 已过期')
    console.error('   existing sha256: ' + hashExist)
    console.error('   expected sha256: ' + hashNew)
    console.error('   跑: cd frontend/web && node scripts/build-extension-mapping.mjs')
    process.exit(1)
  }
  console.log('✅ mapping.js 与 ds160FieldMap.js 同步')
} else {
  writeFileSync(OUT, output, 'utf8')
  const hash = createHash('sha256').update(output).digest('hex')
  console.log('✅ 已生成 ' + OUT)
  console.log('   sha256: ' + hash)
}