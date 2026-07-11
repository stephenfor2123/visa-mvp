// ds160When.js — DS-160 字段映射的条件表达式 DSL + 评估器
// =============================================================================
// 用途:让 ds160FieldMap.js 里的 `when` 字段从"函数式"变成"声明式",
//      既能跨环境序列化(web ESM ↔ 插件 classic),又能:
//
//   1. 在 web 端用 evaluateWhen() 直接评估(运行时开销很小,引导单只渲染一次)
//   2. 在构建脚本里 compileWhenToFn() 编译成 JS 函数,写进插件 IIFE,
//      插件运行时零开销
//
// DSL 形状(递归):
//   { eq:    ['path.to.field', value] }
//   { ne:    ['path.to.field', value] }
//   { exists:    ['path.to.field'] }
//   { notExists: ['path.to.field'] }
//   { and:   [decl, decl, ...] }
//   { or:    [decl, decl, ...] }
//   { not:   decl }
//   true                          // 常量真
//   false                         // 常量假
//   null/undefined                // = 总是真(无 when)
// =============================================================================

// 把点分路径从对象里取值
function _get(o, p) {
  if (o == null) return undefined
  return String(p).split('.').reduce(function (a, k) { return a == null ? undefined : a[k] }, o)
}

// 判断"是否非空"(用于 exists/notExists)
function _isNonEmpty(v) {
  if (v === undefined || v === null) return false
  if (typeof v === 'string') return v.trim() !== ''
  if (typeof v === 'boolean') return true
  if (typeof v === 'number') return !Number.isNaN(v)
  if (Array.isArray(v)) return v.length > 0
  if (typeof v === 'object') return Object.keys(v).length > 0
  return true
}

// 评估一个声明式 → boolean
//   profile 申请档案对象
//   decl    DSL 节点
export function evaluateWhen(decl, profile) {
  if (decl == null) return true // 没 when = 总是真
  if (decl === true) return true
  if (decl === false) return false

  if (Array.isArray(decl)) {
    // 数组 = 隐式 and;数组里的字符串当作 exists(path)
    return decl.every(function (d) {
      if (typeof d === 'string') return evaluateWhen({ exists: d }, profile)
      return evaluateWhen(d, profile)
    })
  }
  if (typeof decl !== 'object') return Boolean(decl)

  var keys = Object.keys(decl)
  if (keys.length === 0) return true
  if (keys.length > 1) {
    // 多个 key 不在 DSL 语法里 → 拒识
    throw new Error('ds160When: 声明式只能有一个顶层 key,得到 ' + JSON.stringify(keys))
  }
  var op = keys[0]
  var args = decl[op]

  switch (op) {
    case 'eq':
      if (!Array.isArray(args) || args.length !== 2) throw new Error('ds160When: eq 需要 [path, value]')
      var av = _get(profile, args[0])
      var bv = args[1]
      // 严格等值 + 大小写不敏感字符串 + 布尔/数字宽松
      return _looseEqual(av, bv)
    case 'ne':
      if (!Array.isArray(args) || args.length !== 2) throw new Error('ds160When: ne 需要 [path, value]')
      return !_looseEqual(_get(profile, args[0]), args[1])
    case 'exists':
      if (typeof args !== 'string') throw new Error('ds160When: exists 需要 path 字符串')
      return _isNonEmpty(_get(profile, args))
    case 'notExists':
      if (typeof args !== 'string') throw new Error('ds160When: notExists 需要 path 字符串')
      return !_isNonEmpty(_get(profile, args))
    case 'and':
      if (!Array.isArray(args)) throw new Error('ds160When: and 需要数组')
      return args.every(function (d) { return evaluateWhen(d, profile) })
    case 'or':
      if (!Array.isArray(args)) throw new Error('ds160When: or 需要数组')
      return args.some(function (d) { return evaluateWhen(d, profile) })
    case 'not':
      return !evaluateWhen(args, profile)
    default:
      throw new Error('ds160When: 未知操作符 ' + op)
  }
}

// 宽松等值:支持 boolean<->string、字符串大小写不敏感、数字宽松
function _looseEqual(a, b) {
  if (a === b) return true
  if (a == null && b == null) return true
  if (typeof a === 'boolean' || typeof b === 'boolean') {
    return _boolCoerce(a) === _boolCoerce(b)
  }
  if (typeof a === 'number' || typeof b === 'number') {
    var na = Number(a), nb = Number(b)
    if (!Number.isNaN(na) && !Number.isNaN(nb)) return na === nb
  }
  if (typeof a === 'string' && typeof b === 'string') {
    return a.trim().toLowerCase() === b.trim().toLowerCase()
  }
  return false
}
function _boolCoerce(v) {
  if (typeof v === 'boolean') return v
  if (typeof v === 'string') {
    var s = v.trim().toLowerCase()
    if (s === 'true' || s === 'yes' || s === '1') return true
    if (s === 'false' || s === 'no' || s === '0' || s === '') return false
  }
  if (typeof v === 'number') return v !== 0
  return Boolean(v)
}

// =============================================================================
// 把声明式编译成 JS 函数字符串(用于构建脚本注入到插件 IIFE 里)
//   compileWhenToFn(decl)  → 字符串 "function (p) { return ... }"
//   编译产物只调用 evaluateWhen,逻辑一致、零分支抖动
// =============================================================================
export function compileWhenToFn(decl) {
  var body = _compileExpr(decl)
  return 'function (p) { return ' + body + ' }'
}

function _compileExpr(decl) {
  if (decl == null) return 'true'
  if (decl === true) return 'true'
  if (decl === false) return 'false'
  if (Array.isArray(decl)) {
    return '(' + decl.map(function (d) {
      if (typeof d === 'string') return _compileExpr({ exists: d })
      return _compileExpr(d)
    }).join(' && ') + ')'
  }
  if (typeof decl !== 'object') return JSON.stringify(Boolean(decl))
  var keys = Object.keys(decl)
  if (keys.length === 0) return 'true'
  var op = keys[0], args = decl[op]
  switch (op) {
    case 'eq':
      return '_looseEqual(_get(p, ' + JSON.stringify(args[0]) + '), ' + JSON.stringify(args[1]) + ')'
    case 'ne':
      return '!_looseEqual(_get(p, ' + JSON.stringify(args[0]) + '), ' + JSON.stringify(args[1]) + ')'
    case 'exists':
      if (typeof args !== 'string') throw new Error('ds160When: exists 需要 path 字符串')
      return '_isNonEmpty(_get(p, ' + JSON.stringify(args) + '))'
    case 'notExists':
      if (typeof args !== 'string') throw new Error('ds160When: notExists 需要 path 字符串')
      return '!_isNonEmpty(_get(p, ' + JSON.stringify(args) + '))'
    case 'and':
      return '(' + args.map(_compileExpr).join(' && ') + ')'
    case 'or':
      return '(' + args.map(_compileExpr).join(' || ') + ')'
    case 'not':
      return '!(' + _compileExpr(args) + ')'
    default:
      throw new Error('ds160When: 未知操作符 ' + op)
  }
}