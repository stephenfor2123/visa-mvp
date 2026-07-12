// auVisaEnums.js — 澳大利亚 Subclass 600 (Visitor) 官网枚举
import { DS160_COUNTRIES } from './ds160Enums.js'

export const AU_COUNTRIES = DS160_COUNTRIES

export const AU_SEX = {
  M: 'Male',
  F: 'Female',
}

export const AU_MARITAL_STATUS = {
  single: 'Single',
  married: 'Married',
  divorced: 'Divorced',
  widowed: 'Widowed',
  separated: 'Separated',
  'de facto': 'De facto',
}

export const AU_STREAM = {
  tourist: 'Tourist stream',
  business: 'Business Visitor stream',
  sponsored_family: 'Sponsored Family stream',
}

export const AU_REASON = {
  tourism: 'Tourism / holiday',
  visit_family: 'Visit family or friends',
  business: 'Business visitor activities',
  other: 'Other',
}

export const AU_EMPLOYMENT_STATUS = {
  employed: 'Employed',
  self_employed: 'Self-employed',
  student: 'Student',
  retired: 'Retired',
  unemployed: 'Unemployed',
  homemaker: 'Homemaker',
}

export const AU_DEVELOPED_VISA = {
  us_gb_schengen: 'Yes — US / UK / Schengen visa',
  other: 'Yes — other developed country visa',
  none: 'No',
}

export const AU_FUNDS_BUCKET = {
  above_3w: 'More than CNY 30,000',
  '1w_3w': 'CNY 10,000 – 30,000',
  below_1w: 'Less than CNY 10,000',
}

export const AU_YES_NO = { true: 'Yes', false: 'No', YES: 'Yes', NO: 'No' }
