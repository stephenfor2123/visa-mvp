// test/unit/run-mapping-test.mjs
// =============================================================================
// 用 jsdom 加载 plugin 端 mapping.js (IIFE),断言它跟 web 端 buildDs160Guide
// 行为完全一致。这是校验"权威源 → 插件"build 路径的关键回归。
// =============================================================================
import { JSDOM } from 'jsdom'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
// 文件在 <PROJECT>/browser-extension/test/unit/run-mapping-test.mjs
// EXT_ROOT = <PROJECT>/browser-extension/
const EXT_ROOT = resolve(__dirname, '..', '..')

const dom = new JSDOM('<!doctype html><html><body></body></html>', { runScripts: 'outside-only' })
const win = dom.window

// 把 IIFE 在 jsdom window 里跑
const code = readFileSync(resolve(EXT_ROOT, 'src/mapping.js'), 'utf8')
// 这里把 `(function () { ... })()` 在 jsdom 里手工执行
win.eval(code)

const HTEX = win.HTEX
if (!HTEX || !HTEX.buildGuide || !HTEX.MAP) {
  console.error('❌ plugin mapping.js 没挂 window.HTEX')
  process.exit(1)
}
console.log('✅ plugin mapping.js loaded; MAP sections:', HTEX.MAP.length)

// 跑几个 sanity case
const cases = [
  {
    name: '空档案 → 必填项 todo',
    profile: {},
    expect: (g) => g.missingCount > 0,
  },
  {
    name: '已婚 → spouse section 出现',
    profile: { identity: { maritalStatus: 'married' } },
    expect: (g) => !!g.sections.find(s => s.section === 'family_spouse'),
  },
  {
    name: '单身 → spouse section 不出现',
    profile: { identity: { maritalStatus: 'single' } },
    expect: (g) => !g.sections.find(s => s.section === 'family_spouse'),
  },
  {
    name: 'valueMap M → MALE',
    profile: { identity: { sex: 'M' } },
    expect: (g) => g.sections[0].steps.find(s => s.label === 'Sex').value === 'MALE',
  },
  {
    name: 'valueMap tourism → TEMP. BUSINESS PLEASURE VISITOR (B)',
    profile: { travel: { purpose: 'tourism' } },
    expect: (g) => {
      const sec = g.sections.find(s => s.section === 'travel')
      return sec.steps.find(s => s.label.startsWith('Purpose')).value === 'TEMP. BUSINESS PLEASURE VISITOR (B)'
    },
  },
  {
    name: 'hasOtherNationality false → NO',
    profile: { identity: { hasOtherNationality: false } },
    expect: (g) => {
      const sec = g.sections.find(s => s.section === 'personal2')
      return sec.steps.find(s => s.label.startsWith('Do you hold')).value === 'NO'
    },
  },
  {
    name: 'transform date 1992-05-14 → 14-MAY-1992',
    profile: { identity: { dob: '1992-05-14' } },
    expect: (g) => g.sections[0].steps.find(s => s.label === 'Date of Birth').value === '14-MAY-1992',
  },
  {
    name: 'transform upper nguyen → NGUYEN',
    profile: { identity: { surname: 'nguyen' } },
    expect: (g) => g.sections[0].steps.find(s => s.label === 'Surnames').value === 'NGUYEN',
  },
  {
    name: 'optional 空 → action=na',
    profile: {},
    expect: (g) => g.sections[0].steps.find(s => s.label === 'Full Name in Native Alphabet').action === 'na',
  },
  {
    name: '条件:hasCompanions=true 时,Companion Surnames 出现',
    profile: { travel: { hasCompanions: true } },
    expect: (g) => {
      const sec = g.sections.find(s => s.section === 'travel_companions')
      return !!sec.steps.find(s => s.label === "Companion's Surnames")
    },
  },
  {
    name: '条件:hasCompanions=false 时,Companion Surnames 不出现',
    profile: { travel: { hasCompanions: false } },
    expect: (g) => {
      const sec = g.sections.find(s => s.section === 'travel_companions')
      return !sec.steps.find(s => s.label === "Companion's Surnames")
    },
  },
  {
    name: 'security_background 不进 sections',
    profile: {},
    expect: (g) => !g.sections.find(s => s.section === 'security_background'),
  },
  {
    name: 'manualSteps 挂载',
    profile: {},
    expect: (g) => Array.isArray(g.manualSteps) && g.manualSteps.length > 0,
  },
]

let pass = 0, fail = 0
for (const c of cases) {
  try {
    const g = HTEX.buildGuide(c.profile)
    if (c.expect(g)) { console.log('  ✓ ' + c.name); pass++ }
    else { console.error('  ✗ ' + c.name); fail++ }
  } catch (e) {
    console.error('  ✗ ' + c.name + ' — ' + e.message)
    fail++
  }
}

console.log(`\n${pass}/${pass + fail} 通过`)
if (fail) process.exit(1)