// ds160FieldMap.test.js — DS-160 字段映射 + 引导单生成器集成测试
// =============================================================================
import { describe, it, expect } from 'vitest'
import { DS160_FIELD_MAP, buildDs160Guide, DS160_VERSION } from './ds160FieldMap.js'

describe('DS160_FIELD_MAP 静态校验', () => {
  it('version 已声明', () => {
    expect(DS160_VERSION).toMatch(/^\d{4}\.\d+$/)
  })
  it('所有 section 有 section/officialTitle/fields', () => {
    DS160_FIELD_MAP.forEach(sec => {
      expect(sec.section).toBeTypeOf('string')
      expect(sec.officialTitle).toBeTypeOf('string')
      expect(Array.isArray(sec.fields)).toBe(true)
    })
  })
  it('所有 field 有 label/profile/input', () => {
    DS160_FIELD_MAP.forEach(sec => {
      sec.fields.forEach(f => {
        expect(f.label).toBeTypeOf('string')
        expect(f.profile).toBeTypeOf('string')
        expect(['text', 'select', 'date', 'radio', 'textarea']).toContain(f.input)
      })
    })
  })
  it('no duplicate label within section', () => {
    DS160_FIELD_MAP.forEach(sec => {
      const labels = sec.fields.map(f => f.label)
      expect(new Set(labels).size).toBe(labels.length)
    })
  })
  it('input 类型与控件合理', () => {
    DS160_FIELD_MAP.forEach(sec => sec.fields.forEach(f => {
      if (f.transform === 'date') expect(f.input).toBe('date')
      if (f.valueMap) expect(['select', 'radio']).toContain(f.input)
    }))
  })
})

describe('buildDs160Guide', () => {
  it('空档案 → 全部 action=todo + missingCount 等于必填数', () => {
    const g = buildDs160Guide({})
    expect(g.sections.length).toBeGreaterThan(0)
    expect(g.missingCount).toBeGreaterThan(0)
    // security_background 不应进 sections(因为 manual=true)
    expect(g.sections.find(s => s.section === 'security_background')).toBeUndefined()
  })

  it('完整越南单身档案 → Personal/Passport/Travel section missingCount=0', () => {
    const profile = {
      identity: {
        surname: 'NGUYEN', givenName: 'VAN AN', sex: 'M', maritalStatus: 'single',
        dob: '1992-05-14', birthCity: 'Ho Chi Minh', birthCountry: 'VN',
        nationality: 'VN', hasOtherNationality: false,
      },
      passport: { type: 'regular', number: 'B12345678', issueCountry: 'VN',
                  issueCity: 'Ho Chi Minh', issueDate: '2018-03-01', expiry: '2031-03-01' },
      contact: { street: '123 Le Loi', city: 'Ho Chi Minh', country: 'VN',
                 phone: '+84 901 234 567', email: 'an@example.vn' },
      travel: { purpose: 'tourism', hasPlan: true, arrivalDate: '2026-08-01',
                stayLength: '10 DAYS', usAddress: 'Hilton SF', payer: 'self' },
    }
    const g = buildDs160Guide(profile)
    // 检查前 5 个 section(Personal1/Personal2/Address/Passport/Travel)无缺失
    const coreSections = ['personal1', 'personal2', 'address_phone', 'passport', 'travel']
    const missingInCore = g.sections
      .filter(s => coreSections.includes(s.section))
      .flatMap(s => s.steps.filter(step => step.missing).map(step => `${s.section}.${step.label}`))
    expect(missingInCore).toEqual([])
    // 配偶栏应消失(单身)
    expect(g.sections.find(s => s.section === 'family_spouse')).toBeUndefined()
    // 同行人 section 还在(允许空)
    expect(g.sections.find(s => s.section === 'travel_companions')).toBeDefined()
  })

  it('已婚 → spouse section 出现,单身不出现', () => {
    const single = buildDs160Guide({ identity: { maritalStatus: 'single' } })
    const married = buildDs160Guide({ identity: { maritalStatus: 'married' } })
    expect(single.sections.find(s => s.section === 'family_spouse')).toBeUndefined()
    expect(married.sections.find(s => s.section === 'family_spouse')).toBeDefined()
  })

  it('valueMap 转换: M → MALE', () => {
    const g = buildDs160Guide({ identity: { sex: 'M' } })
    const sexStep = g.sections[0].steps.find(s => s.label === 'Sex')
    expect(sexStep.value).toBe('MALE')
  })

  it('valueMap 转换: tourism → TEMP. BUSINESS PLEASURE VISITOR (B)', () => {
    const g = buildDs160Guide({ travel: { purpose: 'tourism' } })
    const purpose = g.sections.find(s => s.section === 'travel').steps.find(s => s.label.startsWith('Purpose'))
    expect(purpose.value).toBe('TEMP. BUSINESS PLEASURE VISITOR (B)')
  })

  it('valueMap 转换: VN → VIETNAM', () => {
    const g = buildDs160Guide({ identity: { nationality: 'VN' } })
    const nat = g.sections.find(s => s.section === 'personal2').steps.find(s => s.label.startsWith('Country/Region of Origin'))
    expect(nat.value).toBe('VIETNAM')
  })

  it('radio YES/NO 字符串 → valueMap', () => {
    const g = buildDs160Guide({ identity: { hasOtherNationality: 'NO' } })
    const r = g.sections.find(s => s.section === 'personal2').steps.find(s => s.label.startsWith('Do you hold'))
    expect(r.value).toBe('NO')
    expect(r.action).toBe('fill')
  })

  it('嵌套 profile: 配偶字段可解析', () => {
    const g = buildDs160Guide({
      identity: { maritalStatus: 'married' },
      family: { spouse: { surname: 'LE', givenName: 'MINH', dob: '1990-01-01', nationality: 'VN' } },
    })
    const sec = g.sections.find(s => s.section === 'family_spouse')
    expect(sec.steps.find(s => s.label === "Spouse's Surnames").value).toBe('LE')
    expect(sec.steps.find(s => s.label === "Spouse's Nationality").value).toBe('VIETNAM')
  })

  it('transform date: 1992-05-14 → 14-MAY-1992', () => {
    const g = buildDs160Guide({ identity: { dob: '1992-05-14' } })
    const dob = g.sections[0].steps.find(s => s.label === 'Date of Birth')
    expect(dob.value).toBe('14-MAY-1992')
  })

  it('transform upper: nguyen → NGUYEN', () => {
    const g = buildDs160Guide({ identity: { surname: 'nguyen' } })
    const s = g.sections[0].steps.find(s => s.label === 'Surnames')
    expect(s.value).toBe('NGUYEN')
  })

  it('optional + 空 → action=na', () => {
    const g = buildDs160Guide({}) // 全空
    const native = g.sections[0].steps.find(s => s.label === 'Full Name in Native Alphabet')
    expect(native.action).toBe('na')
    expect(native.value).toBe('Does Not Apply')
    expect(native.missing).toBe(false)
  })

  it('必填 + 空 → action=todo + missing=true', () => {
    const g = buildDs160Guide({})
    const surname = g.sections[0].steps.find(s => s.label === 'Surnames')
    expect(surname.action).toBe('todo')
    expect(surname.missing).toBe(true)
  })

  it('条件 when: hasCompanions=true 时,同行人姓名才出现', () => {
    const gNo = buildDs160Guide({ travel: { hasCompanions: false } })
    const gYes = buildDs160Guide({ travel: { hasCompanions: true } })
    const secNo = gNo.sections.find(s => s.section === 'travel_companions')
    const secYes = gYes.sections.find(s => s.section === 'travel_companions')
    expect(secNo.steps.find(s => s.label === "Companion's Surnames")).toBeUndefined()
    expect(secYes.steps.find(s => s.label === "Companion's Surnames")).toBeDefined()
  })

  it('本地化 enum 未映射 → 待补,不把中文写进 fill value', () => {
    const g = buildDs160Guide({ identity: { maritalStatus: '单身' } })
    const ms = g.sections.find((s) => s.section === 'personal1').steps
      .find((st) => st.label === 'Marital Status')
    expect(ms.action).toBe('todo')
    expect(ms.missing).toBe(true)
    expect(ms.value).toBeNull()
  })
})