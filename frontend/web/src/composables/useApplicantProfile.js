// useApplicantProfile.js — 把散落的 wizard/OCR/表单数据收敛成 ApplicantProfile
// =============================================================================
// ApplicantProfile 是规则引擎/终审/DS-160 引导单+插件**共用的标准档案**。
// 这里做"多来源合并 + 日期归一"，产出干净的档案；缺的字段留空(引导单会标"待补")。
//
// 先单人:直接产出一个 profile;将来多人 = Order.applicants[]，这里不变。
// 无外部依赖(纯函数)，方便测试与在插件侧复用。
// =============================================================================

const _MONTHS = { JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6, JUL: 7, AUG: 8, SEP: 9, OCT: 10, NOV: 11, DEC: 12 }

// 把各种 OCR/表单日期尽量归一成 ISO 'YYYY-MM-DD'(引导单的日期 transform 要 ISO)
export function normalizeDate(raw) {
  if (!raw) return ''
  const s = String(raw).trim().toUpperCase()
  let m = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/) // YYYY-MM-DD
  if (m) return `${m[1]}-${String(+m[2]).padStart(2, '0')}-${String(+m[3]).padStart(2, '0')}`
  m = s.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/) // DD/MM/YYYY(越南/印尼常见)
  if (m) return `${m[3]}-${String(+m[2]).padStart(2, '0')}-${String(+m[1]).padStart(2, '0')}`
  m = s.match(/^(\d{1,2})[-\s]([A-Z]{3})[-\s](\d{4})$/) // DD MMM YYYY / DD-MMM-YYYY(护照/MRZ)
  if (m && _MONTHS[m[2]]) return `${m[3]}-${String(_MONTHS[m[2]]).padStart(2, '0')}-${String(+m[1]).padStart(2, '0')}`
  return '' // 认不出就留空，不硬塞(防误导)
}

const pick = (...vals) => {
  for (const v of vals) if (v != null && String(v).trim() !== '') return v
  return ''
}

/** Wizard YES/NO / boolean → true|false|'' (空=未填) */
export function coerceYesNo(raw) {
  if (raw === true || raw === false) return raw
  if (raw == null) return ''
  const s = String(raw).trim().toLowerCase()
  if (!s) return ''
  if (s === 'true' || s === 'yes' || s === 'y' || s === '1') return true
  if (s === 'false' || s === 'no' || s === 'n' || s === '0') return false
  return ''
}

const str = (v) => (v == null ? '' : String(v).trim())

/**
 * 合并来源 → ApplicantProfile（嵌套结构，与 ds160FieldMap profile 路径一致）。
 */
export function buildApplicantProfile({ form = {}, ocr = {}, travelPlan = {} } = {}) {
  const job = Array.isArray(form.employments) && form.employments[0] ? form.employments[0] : {}
  const edu = Array.isArray(form.educations) && form.educations[0] ? form.educations[0] : {}
  const stay = pick(form.stay_days)
  const arrival = normalizeDate(pick(form.arrival_date, travelPlan.departDate))
  const hasPlanRaw = coerceYesNo(form.has_plan)
  const hasPlan = hasPlanRaw === '' ? !!arrival : hasPlanRaw
  const hasEducationRaw = coerceYesNo(form.has_education)
  const hasEducation = hasEducationRaw === '' ? !!(pick(edu.school_name, form.school_name)) : hasEducationRaw

  return {
    identity: {
      surname: pick(form.surname, ocr.surname),
      givenName: pick(form.given_name, ocr.given_name),
      nativeName: pick(form.native_name),
      sex: pick(form.sex, ocr.sex),
      maritalStatus: pick(form.marital_status),
      dob: normalizeDate(pick(form.dob, ocr.dob)),
      birthCity: pick(form.birth_city),
      birthCountry: pick(form.birth_country, ocr.nationality),
      nationality: pick(form.nationality, ocr.nationality),
      nationalId: pick(form.national_id),
      hasOtherNationality: coerceYesNo(form.has_other_nationality),
      usSsn: pick(form.us_ssn),
      usTaxId: pick(form.us_tax_id),
    },
    passport: {
      type: pick(form.passport_type) || 'regular',
      number: pick(form.passport_no, ocr.passport_no),
      bookNumber: pick(form.passport_book_number),
      issueCountry: pick(form.passport_issue_country, ocr.nationality),
      issueCity: pick(form.passport_issue_city),
      issueDate: normalizeDate(pick(form.passport_issue_date)),
      expiry: normalizeDate(pick(form.passport_expiry, ocr.expiry)),
    },
    contact: {
      street: pick(form.home_street),
      city: pick(form.home_city),
      state: pick(form.home_state),
      postalCode: pick(form.home_postal),
      country: pick(form.home_country, ocr.nationality),
      phone: pick(form.phone, form.emergency_phone),
      email: pick(form.email),
    },
    travel: {
      purpose: pick(form.visa_type),
      hasPlan,
      arrivalDate: arrival,
      stayLength: stay ? `${stay} DAYS` : '',
      usAddress: pick(form.hotel_name, travelPlan.destination),
      payer: pick(form.payer) || 'self',
      hasCompanions: coerceYesNo(form.has_companions),
      companion: {
        surname: pick(form.companion_surname),
        givenName: pick(form.companion_given_name),
        relation: pick(form.companion_relation),
      },
    },
    previous: {
      hasVisited: coerceYesNo(form.previous_has_visited),
      lastVisitDate: normalizeDate(pick(form.previous_last_visit_date)),
      lastVisitStayDays: pick(form.previous_last_visit_stay_days),
      hasVisa: coerceYesNo(form.previous_has_visa),
      lastVisaDate: normalizeDate(pick(form.previous_last_visa_date)),
      lastVisaNumber: pick(form.previous_last_visa_number),
      hasRefused: coerceYesNo(form.previous_has_refused),
    },
    usContact: {
      personSurname: pick(form.us_contact_surname),
      personGivenName: pick(form.us_contact_given_name),
      orgName: pick(form.us_contact_org),
      relation: pick(form.us_contact_relation),
      street: pick(form.us_contact_street),
      city: pick(form.us_contact_city),
      state: pick(form.us_contact_state),
      zip: pick(form.us_contact_zip),
      phone: pick(form.us_contact_phone),
      email: pick(form.us_contact_email),
    },
    work: {
      occupation: pick(form.occupation, job.occupation),
      employer: pick(form.employer_name, job.employer_name),
      employerStreet: pick(form.employer_street, job.employer_address),
      employerCity: pick(form.employer_city),
      employerState: pick(form.employer_state),
      employerPostal: pick(form.employer_postal),
      employerCountry: pick(form.employer_country),
      employerPhone: pick(form.employer_phone),
      monthlySalary: pick(form.monthly_salary, job.monthly_salary),
      duties: pick(form.duties, job.duties),
      hasEducation,
      schoolName: pick(form.school_name, edu.school_name),
      courseOfStudy: pick(form.course_of_study, edu.course),
      schoolFrom: normalizeDate(pick(form.school_from, edu.from)),
      schoolTo: normalizeDate(pick(form.school_to, edu.to)),
      prevEmployer: pick(form.prev_employer),
    },
    family: {
      spouse: {
        surname: pick(form.spouse_surname),
        givenName: pick(form.spouse_given_name),
        dob: normalizeDate(pick(form.spouse_dob)),
        nationality: pick(form.spouse_nationality),
      },
      father: {
        surname: pick(form.father_surname),
        givenName: pick(form.father_given_name),
        dob: normalizeDate(pick(form.father_dob)),
        inUS: coerceYesNo(form.father_in_us),
      },
      mother: {
        surname: pick(form.mother_surname),
        givenName: pick(form.mother_given_name),
        dob: normalizeDate(pick(form.mother_dob)),
        inUS: coerceYesNo(form.mother_in_us),
      },
      hasUSRelatives: coerceYesNo(form.has_us_relatives),
      relative: {
        surname: pick(form.relative_surname),
        givenName: pick(form.relative_given_name),
        relation: pick(form.relative_relation),
        status: pick(form.relative_status),
      },
    },
    security: {
      acknowledged: coerceYesNo(form.security_acknowledged),
    },
  }
}

/**
 * MaterialWizard 表单 → 订单 applicant_data（扁平 snake_case，后端 load_applicant_profile 再转嵌套）。
 * @param {object} form — wizard reactive form
 * @param {object} [opts]
 * @param {object} [opts.dna] — Does Not Apply 勾选状态
 * @param {string} [opts.itineraryText]
 */
export function buildApplicantDataPayload(form = {}, { dna = {}, itineraryText = '' } = {}) {
  const omitIfDna = (field, value) => (dna[field] ? '' : value)
  const job = Array.isArray(form.employments) && form.employments[0] ? form.employments[0] : null
  const edu = Array.isArray(form.educations) && form.educations[0] ? form.educations[0] : null

  const payload = {
    surname: str(form.surname).toUpperCase(),
    given_name: str(form.given_name).toUpperCase(),
    native_name: omitIfDna('native_name', str(form.native_name)),
    sex: str(form.sex),
    marital_status: str(form.marital_status),
    dob: str(form.dob),
    birth_city: str(form.birth_city),
    birth_country: str(form.birth_country),
    nationality: str(form.nationality),
    has_other_nationality: omitIfDna('has_other_nationality', str(form.has_other_nationality)),
    other_nationality: omitIfDna('other_nationality', str(form.other_nationality)),
    national_id: omitIfDna('national_id', str(form.national_id)),
    us_ssn: omitIfDna('us_ssn', str(form.us_ssn)),
    us_tax_id: omitIfDna('us_tax_id', str(form.us_tax_id)),
    home_street: str(form.home_street),
    home_city: str(form.home_city),
    home_state: omitIfDna('home_state', str(form.home_state)),
    home_postal: omitIfDna('home_postal', str(form.home_postal)),
    home_country: str(form.home_country),
    phone: str(form.phone),
    email: str(form.email),
    passport_no: str(form.passport_no).toUpperCase(),
    passport_type: str(form.passport_type) || 'regular',
    passport_book_number: omitIfDna('passport_book_number', str(form.passport_book_number)),
    passport_issue_country: str(form.passport_issue_country),
    passport_issue_city: omitIfDna('passport_issue_city', str(form.passport_issue_city)),
    passport_issue_date: omitIfDna('passport_issue_date', str(form.passport_issue_date)),
    passport_expiry: str(form.passport_expiry),
    visa_type: str(form.visa_type),
    arrival_date: str(form.arrival_date),
    departure_date: str(form.departure_date),
    stay_days: dna.stay_days ? '' : (form.stay_days == null || form.stay_days === '' ? '' : Number(form.stay_days)),
    flight_no: omitIfDna('flight_no', str(form.flight_no)),
    hotel_name: omitIfDna('hotel_name', str(form.hotel_name)),
    itinerary_text: str(itineraryText),
    has_companions: str(form.has_companions),
    companion_surname: omitIfDna('companion_surname', str(form.companion_surname).toUpperCase()),
    companion_given_name: omitIfDna('companion_given_name', str(form.companion_given_name).toUpperCase()),
    companion_relation: omitIfDna('companion_relation', str(form.companion_relation)),
    previous_has_visited: str(form.previous_has_visited),
    previous_last_visit_date: omitIfDna('previous_last_visit_date', str(form.previous_last_visit_date)),
    previous_last_visit_stay_days: omitIfDna('previous_last_visit_stay_days', str(form.previous_last_visit_stay_days)),
    previous_has_visa: str(form.previous_has_visa),
    previous_last_visa_date: omitIfDna('previous_last_visa_date', str(form.previous_last_visa_date)),
    previous_last_visa_number: omitIfDna('previous_last_visa_number', str(form.previous_last_visa_number).toUpperCase()),
    previous_has_refused: str(form.previous_has_refused),
    us_contact_surname: omitIfDna('us_contact_surname', str(form.us_contact_surname).toUpperCase()),
    us_contact_given_name: omitIfDna('us_contact_given_name', str(form.us_contact_given_name).toUpperCase()),
    us_contact_org: omitIfDna('us_contact_org', str(form.us_contact_org)),
    us_contact_relation: omitIfDna('us_contact_relation', str(form.us_contact_relation)),
    us_contact_street: omitIfDna('us_contact_street', str(form.us_contact_street)),
    us_contact_city: omitIfDna('us_contact_city', str(form.us_contact_city)),
    us_contact_state: omitIfDna('us_contact_state', str(form.us_contact_state)),
    us_contact_zip: omitIfDna('us_contact_zip', str(form.us_contact_zip)),
    us_contact_phone: omitIfDna('us_contact_phone', str(form.us_contact_phone)),
    us_contact_email: omitIfDna('us_contact_email', str(form.us_contact_email)),
    spouse_surname: omitIfDna('spouse_surname', str(form.spouse_surname).toUpperCase()),
    spouse_given_name: omitIfDna('spouse_given_name', str(form.spouse_given_name).toUpperCase()),
    spouse_dob: omitIfDna('spouse_dob', str(form.spouse_dob)),
    spouse_nationality: omitIfDna('spouse_nationality', str(form.spouse_nationality)),
    father_surname: omitIfDna('father_surname', str(form.father_surname).toUpperCase()),
    father_given_name: omitIfDna('father_given_name', str(form.father_given_name).toUpperCase()),
    father_dob: omitIfDna('father_dob', str(form.father_dob)),
    father_in_us: str(form.father_in_us),
    mother_surname: omitIfDna('mother_surname', str(form.mother_surname).toUpperCase()),
    mother_given_name: omitIfDna('mother_given_name', str(form.mother_given_name).toUpperCase()),
    mother_dob: omitIfDna('mother_dob', str(form.mother_dob)),
    mother_in_us: str(form.mother_in_us),
    has_us_relatives: str(form.has_us_relatives),
    relative_surname: omitIfDna('relative_surname', str(form.relative_surname).toUpperCase()),
    relative_given_name: omitIfDna('relative_given_name', str(form.relative_given_name).toUpperCase()),
    relative_relation: omitIfDna('relative_relation', str(form.relative_relation)),
    relative_status: omitIfDna('relative_status', str(form.relative_status)),
    occupation: omitIfDna('occupation', str(form.occupation)),
    has_education: edu ? 'YES' : str(form.has_education),
    school_name: str(edu?.school_name || form.school_name),
    course_of_study: str(edu?.course || form.course_of_study),
    school_from: str(edu?.from || form.school_from),
    school_to: str(edu?.to || form.school_to),
    employer_name: str(job?.employer_name || form.employer_name),
    employer_street: str(job?.employer_address || form.employer_street),
    monthly_salary: str(job?.monthly_salary || form.monthly_salary),
    duties: str(job?.duties || form.duties),
    prev_employer: str(form.prev_employer),
    security_acknowledged: str(form.security_acknowledged),
    payer: 'self',
    dna: { ...dna },
    emergency_contact: {
      name: str(form.emergency_name),
      phone: str(form.emergency_phone),
      relation: str(form.emergency_relation),
    },
  }

  if (Array.isArray(form.employments) && form.employments.length) {
    payload.employments = form.employments.map((j) => ({ ...j }))
  }
  if (Array.isArray(form.educations) && form.educations.length) {
    payload.educations = form.educations.map((e) => ({ ...e }))
  }

  return payload
}

// 从 localStorage 读 wizard 各来源，合并成 profile(浏览器里用)
export function readApplicantProfileFromStorage() {
  const read = (k) => { try { return JSON.parse(localStorage.getItem(k) || 'null') } catch { return null } }
  const ocrCache = read('visa.wizard.ocrCache') || {}
  const ocr = Object.values(ocrCache).find((f) => f && f.passport_no) || {}
  const travelPlan = read('visa.wizard.travelPlan') || {}
  const form = read('visa.order.form') || {}
  return buildApplicantProfile({ form, ocr, travelPlan })
}
