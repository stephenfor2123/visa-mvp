// ds160When.test.js — when DSL 评估器单测
// =============================================================================
import { describe, it, expect } from 'vitest'
import { evaluateWhen, compileWhenToFn } from './ds160When.js'

describe('evaluateWhen', () => {
  const profile = {
    identity: {
      surname: 'NGUYEN',
      givenName: 'VAN AN',
      sex: 'M',
      maritalStatus: 'married',
      nationality: 'Vietnam',
      hasOtherNationality: false,
    },
    passport: { type: 'regular', number: 'B12345678' },
    travel: {
      purpose: 'tourism',
      hasCompanions: true,
      companion: { surname: 'TRAN' },
    },
    family: {
      spouse: { surname: 'TRAN' },
      father: { surname: 'NGUYEN' },
      hasUSRelatives: false,
    },
    work: { hasEducation: true, schoolName: 'HCMUS' },
  }

  describe('null/undefined/常量', () => {
    it('null = 总是真', () => {
      expect(evaluateWhen(null, profile)).toBe(true)
      expect(evaluateWhen(undefined, profile)).toBe(true)
    })
    it('true/false 字面量', () => {
      expect(evaluateWhen(true, profile)).toBe(true)
      expect(evaluateWhen(false, profile)).toBe(false)
    })
    it('空对象 = 总是真', () => {
      expect(evaluateWhen({}, profile)).toBe(true)
    })
  })

  describe('eq', () => {
    it('字符串等值', () => {
      expect(evaluateWhen({ eq: ['identity.maritalStatus', 'married'] }, profile)).toBe(true)
      expect(evaluateWhen({ eq: ['identity.maritalStatus', 'single'] }, profile)).toBe(false)
    })
    it('布尔严格', () => {
      expect(evaluateWhen({ eq: ['travel.hasCompanions', true] }, profile)).toBe(true)
      expect(evaluateWhen({ eq: ['identity.hasOtherNationality', false] }, profile)).toBe(true)
    })
    it('字符串/布尔宽松', () => {
      // 档案里 false → 字符串 'false' 应判等
      expect(evaluateWhen({ eq: ['identity.hasOtherNationality', 'false'] }, profile)).toBe(true)
      expect(evaluateWhen({ eq: ['identity.hasOtherNationality', 'no'] }, profile)).toBe(true)
    })
    it('缺字段 = undefined', () => {
      expect(evaluateWhen({ eq: ['identity.doesNotExist', 'x'] }, profile)).toBe(false)
    })
  })

  describe('ne', () => {
    it('不等', () => {
      expect(evaluateWhen({ ne: ['identity.maritalStatus', 'single'] }, profile)).toBe(true)
    })
  })

  describe('exists / notExists', () => {
    it('exists 命中', () => {
      expect(evaluateWhen({ exists: 'family.spouse.surname' }, profile)).toBe(true)
    })
    it('exists 漏空字符串', () => {
      const p = { family: { spouse: { surname: '' } } }
      expect(evaluateWhen({ exists: 'family.spouse.surname' }, p)).toBe(false)
    })
    it('exists 漏未定义字段', () => {
      expect(evaluateWhen({ exists: 'family.spouse.surname' }, {})).toBe(false)
    })
    it('notExists', () => {
      expect(evaluateWhen({ notExists: 'identity.doesNotExist' }, profile)).toBe(true)
    })
    it('exists 对布尔', () => {
      expect(evaluateWhen({ exists: 'travel.hasCompanions' }, profile)).toBe(true)
    })
  })

  describe('and / or / not', () => {
    it('and', () => {
      const decl = { and: [
        { eq: ['identity.maritalStatus', 'married'] },
        { exists: 'family.spouse.surname' },
      ]}
      expect(evaluateWhen(decl, profile)).toBe(true)
    })
    it('and 一假即假', () => {
      const decl = { and: [
        { eq: ['identity.maritalStatus', 'married'] },
        { exists: 'family.spouse.doesNotExist' },
      ]}
      expect(evaluateWhen(decl, profile)).toBe(false)
    })
    it('or', () => {
      const decl = { or: [
        { eq: ['identity.maritalStatus', 'single'] },
        { eq: ['identity.maritalStatus', 'married'] },
      ]}
      expect(evaluateWhen(decl, profile)).toBe(true)
    })
    it('not', () => {
      expect(evaluateWhen({ not: { eq: ['identity.maritalStatus', 'single'] } }, profile)).toBe(true)
      expect(evaluateWhen({ not: { eq: ['identity.maritalStatus', 'married'] } }, profile)).toBe(false)
    })
  })

  describe('嵌套', () => {
    it('and + or + not', () => {
      const decl = { and: [
        { or: [
          { eq: ['identity.maritalStatus', 'married'] },
          { eq: ['identity.maritalStatus', 'single'] },
        ]},
        { not: { eq: ['identity.sex', 'F'] } },
      ]}
      expect(evaluateWhen(decl, profile)).toBe(true)
    })
  })

  describe('错误检测', () => {
    it('未知 op 抛错', () => {
      expect(() => evaluateWhen({ wat: 1 }, profile)).toThrow(/未知操作符/)
    })
    it('eq 参数错抛错', () => {
      expect(() => evaluateWhen({ eq: ['only.path'] }, profile)).toThrow(/eq 需要/)
    })
    it('多顶层 key 抛错', () => {
      expect(() => evaluateWhen({ eq: ['a', 'b'], ne: ['c', 'd'] }, profile)).toThrow(/只能有一个/)
    })
  })

  describe('compileWhenToFn', () => {
    it('编译产物是合法函数', () => {
      const fnSrc = compileWhenToFn({ eq: ['identity.maritalStatus', 'married'] })
      expect(fnSrc).toMatch(/^function \(p\) \{ return/)
    })
    it('编译产物跟 evaluateWhen 行为一致', () => {
      // 构造一个沙盒:helpers + body
      const helpers = `
        function _get(o,p){if(o==null)return undefined;return String(p).split('.').reduce(function(a,k){return a==null?undefined:a[k]},o)}
        function _isNonEmpty(v){if(v==null)return false;if(typeof v==='string')return v.trim()!=='';if(typeof v==='boolean')return true;if(typeof v==='number')return !Number.isNaN(v);return true}
        function _looseEqual(a,b){if(a===b)return true;if(typeof a==='boolean'||typeof b==='boolean'){return _boolCoerce(a)===_boolCoerce(b)}if(typeof a==='string'&&typeof b==='string')return a.trim().toLowerCase()===b.trim().toLowerCase();return false}
        function _boolCoerce(v){if(typeof v==='boolean')return v;if(typeof v==='string'){var s=v.trim().toLowerCase();if(s==='true'||s==='yes'||s==='1')return true;return false}return Boolean(v)}
      `
      const decls = [
        { eq: ['identity.maritalStatus', 'married'] },
        { and: [
          { eq: ['identity.maritalStatus', 'married'] },
          { or: [
            'family.spouse.surname',
            { eq: ['travel.hasCompanions', true] },
          ]},
        ]},
        { not: { eq: ['identity.sex', 'F'] } },
        { exists: 'work.schoolName' },
      ]
      decls.forEach(decl => {
        const fnSrc = compileWhenToFn(decl)
        const body = fnSrc.replace(/^function \(p\) \{ return /, '').replace(/ \}$/, '')
        const code = helpers + '\nreturn function(p){return ' + body + '}'
        const compiled = new Function(code)()
        expect(compiled(profile)).toBe(evaluateWhen(decl, profile))
      })
    })
  })
})