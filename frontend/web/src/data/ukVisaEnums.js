// ukVisaEnums.js — 英国 Standard Visitor 官网枚举
import { DS160_COUNTRIES } from './ds160Enums.js'

export const UK_COUNTRIES = DS160_COUNTRIES

export const UK_SEX = {
  M: 'Male',
  F: 'Female',
}

export const UK_MARITAL_STATUS = {
  single: 'Single',
  married: 'Married',
  divorced: 'Divorced',
  widowed: 'Widowed',
  separated: 'Separated',
  'civil partnership': 'Civil partnership',
}

export const UK_VISA_LENGTH = {
  '6_months': 'Up to 6 months',
  '2_years': '2 years',
  '5_years': '5 years',
  '10_years': '10 years',
}

export const UK_MAIN_REASON = {
  tourism: 'Tourism (including visiting family or friends)',
  business: 'Business (including meetings and conferences)',
  short_study: 'Short study (up to 6 months)',
  medical: 'Medical treatment',
  other: 'Other',
}

export const UK_FUNDS_PAYER = {
  self: 'Myself',
  employer: 'My employer',
  other_person: 'Someone else',
  sponsor: 'A sponsor in the UK',
}

export const UK_EMPLOYMENT_STATUS = {
  employed: 'Employed',
  self_employed: 'Self-employed',
  student: 'Student',
  retired: 'Retired',
  unemployed: 'Unemployed',
  homemaker: 'Homemaker',
}

export const UK_VISA_HISTORY = {
  never: 'No, I have never been issued a UK visa',
  clean: 'Yes, and I complied with the conditions',
  overstayed: 'Yes, but I overstayed or breached conditions',
}

export const UK_YES_NO = { true: 'Yes', false: 'No', YES: 'Yes', NO: 'No' }

export const UK_FUNDS_BUCKET = {
  above_5w: 'More than CNY 50,000',
  '1w_5w': 'CNY 10,000 – 50,000',
  below_1w: 'Less than CNY 10,000',
}
