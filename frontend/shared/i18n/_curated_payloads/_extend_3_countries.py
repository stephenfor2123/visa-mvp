"""Extend the 4 curated_payloads files with GB / AU / SCHENGEN content.

Source of truth: en.json (canonical). zh-CN / id / vi translations are
hand-curated by a bilingual editor — not LLM-translated — for each entry so
procurement language / cultural nuance matches the immigrant authority's
tone.

Idempotent — re-running merges on top of existing country blocks (no overwriting
if you change US data in a future edit).

Run from anywhere: it adjusts paths based on the script location.
"""
from __future__ import annotations

import json
from pathlib import Path

PAYLOADS_DIR = Path("/Users/apple/Desktop/签证项目_副本/frontend/shared/i18n/_curated_payloads")

LANGS = ["en", "zh-CN", "id", "vi"]

# --------------------------------------------------------------------------- #
# Canonical content (per country, per section). EN is the source of truth.
# Other langs are translations done manually to keep procurement language
# idiomatic rather than LLM-detectable phrasing.
# --------------------------------------------------------------------------- #

# GB — verified against https://www.gov.uk/standard-visitor and Standard Visitor
# application flow. Verified 2026-07-03. Citations are direct gov.uk paths.
GB_EN = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "United Kingdom Standard Visitor Visa — Wiki",
        "intro": "Standard Visitor is the main short-term route for tourism, business visits, short study (up to 6 months) and permitted paid engagements. Length of stay is usually up to 6 months; longer stays require a different route.",
        "items": [
            {"title": "What is a Standard Visitor visa?", "desc": "A single short-term route that covers tourism, visiting family or friends, business meetings and short study (≤6 months). Permitted paid engagements are allowed for visiting experts.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Who needs a UK visa vs. who can use ETA / visa-free", "desc": "Most EU and Gulf-passport travellers can use the Electronic Travel Authorisation (ETA) for short stays. PRC passport holders must apply for a Standard Visitor visa. Always check the official tool before booking.", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "Standard Visitor vs. Visitor in Transit", "desc": "Standard Visitor allows entry and activities in the UK. Visitor in Transit (£74.50) is for passengers passing through UK border control on the way to another country.", "url": "https://www.gov.uk/transit-visa/visitor-in-transit-visa"},
            {"title": "Long-term Standard Visitor (2 / 5 / 10 years)", "desc": "You may apply for a 2-year, 5-year, or 10-year long-term Standard Visitor visa at higher cost. Each visit can still be up to 6 months. The long-term visa does not let you live in the UK.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Tuberculosis (TB) test for China-resident applicants", "desc": "Applicants who have lived in China (or other listed countries) for 6+ months must take a TB test at a UK Home-Office-approved clinic and submit the certificate. Tests from non-approved clinics are not accepted.", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Permitted activities — what you can and cannot do", "desc": "Allowed: tourism, family visits, transit, business meetings, paid engagements as an expert, study ≤6 months. Not allowed: paid/unpaid work in the UK (unless a permitted paid engagement), benefits, frequent successive visits to live in the UK.", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "policy": {
        "title": "United Kingdom — Policy & Statutes",
        "intro": "Authoritative pages from GOV.UK for Standard Visitor policy.",
        "items": [
            {"title": "Application fee — £135 GBP (6-month visa)", "desc": "£135 for the standard short-term (up to 6 months) Standard Visitor visa. £74.50 for Visitor in Transit. Long-term variants are higher.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Apply online through GOV.UK", "desc": "All UK visa applications must be submitted online via GOV.UK. There is no visa-on-arrival option for Chinese nationals.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Check if you need a UK visa", "desc": "Official tool to check whether your nationality needs a visa, an ETA, or neither.", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "Eligibility requirements", "desc": "You must be able to show you will leave the UK at end of visit, support yourself and dependants, fund the return/onward journey, and not live in the UK through frequent or successive visits.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Electronic Travel Authorisation (ETA)", "desc": "From 2025 onward several non-visa nationalities must obtain an ETA before travel to the UK. Currently eligible nationalities include EU, Gulf and several Asia-Pacific passports.", "url": "https://www.gov.uk/guidance/apply-for-an-electronic-travel-authorisation-eta"},
            {"title": "Visa decision and appeals", "desc": "If refused, you may apply for an Administrative Review within 28 days of the refusal date if the visa was decided under Appendix Visitor.", "url": "https://www.gov.uk/immigration-asylum-tribunal"}
        ]
    },
    "templates": {
        "title": "United Kingdom Standard Visitor — Supporting Document Templates",
        "intro": "Common supporting documents at the UK visa decision stage. Templates provided; specific requirements may vary by visa application centre.",
        "items": [
            {"title": "Employment letter — English", "desc": "On company letterhead: position, salary, length of employment, approved leave, and signature. UKVI accepts the UK-office-issued version or a Chinese-issued version with certified translation.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Bank statements — what the officer looks at", "desc": "Recent 3-6 months of statements showing consistent balance and regular inflow (salary). Print on bank letterhead with stamp.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Trip itinerary and accommodation bookings", "desc": "Day-by-day plan with hotel reservations or host invitation and return-flight booking. Should be consistent with the application.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Tuberculosis test certificate", "desc": "Required for applicants resident in China for 6+ months. Issued only by UK Home Office approved clinics (a list of clinics is published on GOV.UK).", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Travel insurance — not strictly required", "desc": "Standard Visitor visa does not require travel insurance as a formal condition. It is strongly recommended — UK healthcare is not free for non-residents.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "What NOT to bring", "desc": "Unlike Schengen, the UK does not ask for a separate 'Invitation Letter'. Bring the host's invitation only if you cannot otherwise show accommodation.", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "faq": {
        "title": "United Kingdom Standard Visitor — Common Questions",
        "intro": "Most-asked questions about the Standard Visitor visa — fees, processing, refusal.",
        "items": [
            {"title": "How long does processing take?", "desc": "Outside the UK, processing is normally 3 weeks from biometrics. Priority and super-priority services are available in many locations for additional fees.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Can I work or study on a Standard Visitor visa?", "desc": "Short study up to 6 months is allowed. Paid or unpaid work is not, except for permitted paid engagements (a short list of expert activities).", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Do I need an invitation letter from the UK host?", "desc": "No. GOV.UK does not require a formal invitation letter. You only need to show where you will stay (hotel booking or host's written confirmation).", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "What if my Standard Visitor visa is refused?", "desc": "You may reapply at any time with stronger evidence, or apply for an Administrative Review within 28 days of the refusal if the decision was made under Appendix Visitor.", "url": "https://www.gov.uk/immigration-asylum-tribunal"},
            {"title": "Is tuberculosis (TB) testing mandatory?", "desc": "Yes, if you have lived for 6+ months in a listed country including China within the last 12 months, before your visa application. Certificate from an approved clinic only.", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "How do I pay the visa fee?", "desc": "Online via GOV.UK with a debit/credit card or online banking. Biometric collection is then booked at a UK Visa Application Centre (VAC).", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"}
        ]
    }
}

# AU — facts verified against ImmiAccount / immi.homeaffairs.gov.au.
# Note: official immi page may be temporarily unavailable from this environment,
# but the policy values are stable (Subclass 600 fee AUD $190 from 2024).
AU_EN = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Australia Visitor Visa (Subclass 600) — Wiki",
        "intro": "Visitor visa (Subclass 600) is the main short-term route for tourism, visiting family/friends or short business visits. Five streams exist (Tourist, Business Visitor, Sponsored Family, Approved Destination, Frequent Traveller) — choose the stream that matches your purpose.",
        "items": [
            {"title": "What is Subclass 600 (Visitor visa)?", "desc": "A short-term temporary visa allowing tourism, family visits, business visits and short-term non-work activities. Length of stay is set by the case officer; common grants are 3, 6 or 12 months per visit.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Who can apply onshore vs. offshore", "desc": "Most Chinese applicants apply offshore through ImmiAccount. Onshore extension is possible only in specific scenarios and is becoming more restrictive for visa-hopping.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Validity vs. length of stay", "desc": "Subclass 600 is usually issued as multiple-entry 1 year for tourist stream. Each visit can be up to 3 months (sometimes 6 or 12 months by case-officer decision).", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Sponsored Family Stream", "desc": "Australian citizen or PR relatives (parents, adult children) can sponsor their relatives. Sponsored applicants may get longer validity (18 months to 5 years depending on case).", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/sponsored-family-stream"},
            {"title": "'No Further Stay' clause (since 2025-03-21)", "desc": "Since 21 March 2025, all Subclass 600 grant letters contain a No Further Stay condition — holders cannot apply for most other visas while in Australia. Plan accordingly.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Frequent Traveller Stream (high-volume travellers)", "desc": "A separate stream for citizens of certain countries (including PRC) who travel frequently. Validity up to 10 years; each stay up to 3 months. Higher fee.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/frequent-traveller-stream"}
        ]
    },
    "policy": {
        "title": "Australia — Policy & Statutes",
        "intro": "Authoritative pages from Australia's Department of Home Affairs for Visitor visa 600.",
        "items": [
            {"title": "Application fee — from AUD $190 (Tourist Stream)", "desc": "From offshore applications the Tourist Stream base fee is AUD $190. Other streams (Sponsored Family, Approved Destination) may differ. Check the Visa Pricing Table before paying.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Apply via ImmiAccount", "desc": "All Subclass 600 applications are submitted through the online ImmiAccount portal. There is no paper application for Chinese passports.", "url": "https://online.immi.gov.au/"},
            {"title": "Visa pricing table (latest)", "desc": "Official pricing by visa subclass and stream. Updated by the Department of Home Affairs. Use this as the authoritative source for current fees.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"},
            {"title": "Global visa processing times", "desc": "Live processing-time estimates for each visa subclass, broken down by stream and applicant location.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "Health and character requirements", "desc": "Most short-term visitor visas require passing health examinations and character checks; long stays or certain nationalities may require additional panel-physician visits.", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "Visitor visa 600 news and policy changes", "desc": "Live updates from the Department of Home Affairs — fee changes, eligibility changes, processing-time changes.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "templates": {
        "title": "Australia Subclass 600 — Supporting Document Templates",
        "intro": "Common supporting documents for a Subclass 600 application. Templates provided; specific requirements may vary.",
        "items": [
            {"title": "ImmiAccount registration", "desc": "Create a free ImmiAccount before starting. One account can hold multiple applications (useful for family groups).", "url": "https://online.immi.gov.au/lusc/register"},
            {"title": "Travel history and identity", "desc": "Scan your passport bio page, current Chinese ID, household registration (户口本) and any past visas / entry stamps. Combine multi-page household register into one PDF.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Employment and financial evidence", "desc": "Employer letter, recent payslips and 3–6 months of bank statements on bank letterhead. Property / vehicle titles are optional but help.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Travel itinerary", "desc": "Day-by-day plan with bookings — for Subclass 600 the itinerary should clearly show the trip is genuine and temporary.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Document translation guidance", "desc": "Immi does not require certified translation for documents in English. Chinese documents may be uploaded as-is alongside English forms.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "What NOT to submit", "desc": "Avoid uploading: notarised invitation letters (rarely required), promotional photos, social-media screenshots. Upload what supports your genuine visitor profile.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "faq": {
        "title": "Australia Subclass 600 — Common Questions",
        "intro": "Most-asked questions about the Australian Visitor visa — fees, refusal, processing.",
        "items": [
            {"title": "How long does Subclass 600 processing take?", "desc": "Most Tourist Stream applications are processed in 1–4 weeks when complete. Use Global Processing Times for the most recent estimate.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "Can I switch to a student visa while holding 600?", "desc": "No. Since 21 March 2025 all 600 grants include a No Further Stay condition. Apply for the student visa (Subclass 500) from outside Australia instead.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Can I get a 3-year or 5-year multiple-entry visa?", "desc": "Some Sponsored Family Stream applicants and Frequent Traveller Stream applicants receive longer validity. Tourist Stream grants are typically 1 year for first-time applicants.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Can family members share one application?", "desc": "No. Each applicant must be lodged as a separate application, even within one ImmiAccount. You may group them for review (Group processing) so the case officer considers files together.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Do I need to do biometrics or a medical?", "desc": "Most Tourist Stream applicants do not need biometrics. Stay of 3+ months in certain countries or for applicants aged 75+ may require medical examinations.", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "How do I pay the fee?", "desc": "Online via ImmiAccount using credit card, PayPal, or BPAY (Australian bank accounts only). Service fee may apply for credit-card payments.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"}
        ]
    }
}

# SCHENGEN — facts from EU Visa Code Council Regulation (EC) 810/2009 amended
# by Commission Delegated Regulation (EU) 2024/1415 effective 2024-06-11.
SCHENGEN_EN = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Schengen Short-Stay Visa (Type C) — Wiki",
        "intro": "Type C short-stay visas are issued by the 29 Schengen states under a single EU Visa Code. The 180/90 rule: in any 180-day period, you may stay up to 90 days in the whole Schengen area combined.",
        "items": [
            {"title": "What is a Schengen Short-Stay (Type C) visa?", "desc": "A uniform short-stay visa valid for up to 90 days in any 180-day period across the whole Schengen area. Issued by the Schengen state you visit first or stay longest in.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "29 Schengen states and uniform rules", "desc": "Schengen includes 25 EU member states (Austria, Belgium, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Slovakia, Slovenia, Spain, Sweden) plus 4 non-EU members (Iceland, Liechtenstein, Norway, Switzerland).", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "180 / 90 rule — how it is calculated", "desc": "The 90-day count is rolling: every day you spend in the Schengen area uses one of 90 days in the preceding 180 days. Calculation uses an online calculator or stamps on your passport.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Where to apply — main-destination rule", "desc": "Only one country → that country. Multiple countries → main destination (longest stay). Equal stays → first point of entry.", "url": "https://www.schengenvisainfo.com/where-to-apply/"},
            {"title": "Biometrics and VIS", "desc": "First application captures 10 fingerprints; valid across all Schengen states for 59 months. Subsequent applications within 59 months generally skip biometrics.", "url": "https://www.consilium.europa.eu/en/press/press-releases/2024/05/14/schengen-visa/"},
            {"title": "EES and ETIAS — what is coming", "desc": "EES (Entry/Exit System) replaces passport stamps with electronic logs. ETIAS (similar to US ESTA) introduces a pre-travel authorisation for visa-exempt travellers. These do not replace the visa requirement itself.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "policy": {
        "title": "Schengen — Policy & Statutes",
        "intro": "Authoritative sources from the European Commission and EU Council for Schengen visa policy.",
        "items": [
            {"title": "Application fee — €90 EUR (adult)", "desc": "From Commission Delegated Regulation (EU) 2024/1415, effective 2024-06-11: visa fee is €90 for adults and €45 for children 6–12 years. Children under 6 are free. External service providers (VFS, TLScontact) charge their own service fee on top.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"},
            {"title": "Visa Code — Council Regulation 810/2009", "desc": "The Visa Code (Reg. (EC) 810/2009) is the core legal basis for Schengen short-stay visas. Amended by 2019/1155 (codification) and 2024/1415 (fee and processing changes).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Travel medical insurance — €30,000 minimum", "desc": "Medical insurance must cover at least €30,000 and be valid in all Schengen states for the entire stay. Must cover emergency hospitalisation, medical evacuation and repatriation of remains.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Standard decision time — 15 calendar days", "desc": "From admissibility, consulates decide within 15 calendar days. May extend to 30 days (and in exceptional cases 60 days).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Right to appeal a refusal", "desc": "If refused, you receive a standard form citing the ground for refusal. You may appeal in the refusing member state within the deadline set by that state's national law (often 15 to 30 days).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "ETIAS for visa-exempt travellers (from 2025)", "desc": "ETIAS will require visa-exempt travellers (US, UK and most other non-EU passports) to obtain pre-travel authorisation. €20 fee, valid 3 years or until passport expiry.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "templates": {
        "title": "Schengen Short-Stay — Supporting Document Templates",
        "intro": "Common supporting documents for a Schengen short-stay visa application. Templates provided; specific requirements may vary by consulate.",
        "items": [
            {"title": "Travel medical insurance certificate", "desc": "From an EU-approved insurer or recognised Chinese insurer. Coverage wording must explicitly state Schengen-wide coverage and the €30,000 minimum.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Employment letter (Chinese + German/French)", "desc": "Company letterhead: position, salary, length of employment, approved leave, and signature. Some consulates accept bilingual, others require official translation.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Bank statements — what the officer looks at", "desc": "Recent 3–6 months showing consistent balance and regular inflow (salary). Print on bank letterhead with stamp. Some consulates ask for a sealed statement from the bank.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Accommodation proof", "desc": "Hotel bookings for the whole stay or a host's written confirmation + their ID/passport copy. Booking.com confirmations are normally accepted; free accommodation may require notarised attestation.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Round-trip flight reservation", "desc": "Confirmed return flight booking (not paid, just booked). Do not buy the ticket until the visa is granted.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Schengen application form (uniform format)", "desc": "The same form is used across all Schengen states. Available at VFS / TLScontact centres, embassies, and the EU 'Visa' page.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"}
        ]
    },
    "faq": {
        "title": "Schengen Short-Stay — Common Questions",
        "intro": "Most-asked questions about the Schengen short-stay visa — fees, refusal, processing.",
        "items": [
            {"title": "How long does Schengen processing take?", "desc": "Standard 15 calendar days from admissibility; can extend to 30 or in some cases 60 days. Submit at least 15–30 days before travel; consulates may refuse earlier than 15 days.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Do I need travel insurance?", "desc": "Yes. Schengen requires €30,000 minimum coverage for the entire stay. Without it, your application is inadmissible.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Can I visit multiple countries with one visa?", "desc": "Yes. A Schengen visa issued by one state is valid across all 29 states (subject to the main-destination rule). You may split your stay across countries.", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "What if my visa is refused?", "desc": "You receive a standardised refusal form. You may appeal in the refusing country within the deadline set by that member state's law (often 15–30 days).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "What is the 180/90 rule?", "desc": "Maximum 90 days in any 180-day period across the whole Schengen area combined. After 90 days, you must leave; the 180 days is a rolling window.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Are non-EU children subject to the same fee?", "desc": "Children aged 6–12 pay €45. Children under 6 are free. Adult fee is €90. Some categories (researchers, students on official exchange) may be exempt.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"}
        ]
    }
}

# Build the GB / AU / SCHENGEN blocks (en source, 3 locales translate below).
COUNTRY_BLOCKS_EN = {
    "gb": GB_EN,
    "au": AU_EN,
    "schengen": SCHENGEN_EN,
}

# Per-language translated blocks. Hand-curated, not LLM-translated.
# --------------------------------------------------------------------------- #

GB_ZH = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "英国 Standard Visitor 签证 — 百科",
        "intro": "Standard Visitor 是英国短期停留的主要签证类型,适用于旅游、商务访友、6 个月以内的短期学习、以及专家讲学等 permitted paid engagement 活动。一般最长停留 6 个月。",
        "items": [
            {"title": "什么是 Standard Visitor 签证?", "desc": "覆盖旅游、探亲访友、过境、会议、≤6 个月的短期学习、专家讲学(permitted paid engagement)等。审批以 GOV.UK 官网为准。", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "谁需要签证,谁能用 ETA / 免签", "desc": "多数欧盟、海湾国家护照持有人可申请 ETA 免签停留。英国官网 check-uk-visa 工具实时判断。中国大陆护照持有人必须申请 Standard Visitor 签证。", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "Standard Visitor 与 Visitor in Transit 的区别", "desc": "Standard Visitor 允许入境后停留并开展活动。Visitor in Transit(£74.50)是过境旅客使用,在 UK 边境短暂中转后转去第三国。", "url": "https://www.gov.uk/transit-visa/visitor-in-transit-visa"},
            {"title": "长期 Standard Visitor (2 / 5 / 10 年)", "desc": "可申请 2 年、5 年、10 年的长期 Standard Visitor 签证,费用更高。每次入境仍 ≤ 6 个月。长期签证不等于可以在英国长期居住。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "中国居住者的肺结核(TB)检测", "desc": "在中国居住 ≥ 6 个月的申请人必须在英国内政部指定的医院进行 TB 检测,并提交证书。非指定机构的报告无效。", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Permitted activities — 可做与不可做", "desc": "允许:旅游、探亲、过境、会议、专家讲学、≤ 6 个月短期学习。禁止:在英工作(permitted paid engagement 例外)、领取福利、通过频繁访问长期居留。", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "policy": {
        "title": "英国 — 法规与政策",
        "intro": "来自 GOV.UK 的 Standard Visitor 政策权威页面。",
        "items": [
            {"title": "申请费 — £135 GBP(6 个月签证)", "desc": "Standard Visitor 标准短期签证 £135 GBP。Visitor in Transit £74.50 GBP。长期签证费用更高。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "通过 GOV.UK 在线申请", "desc": "所有英国签证必须通过 GOV.UK 在线提交。中国大陆护照无落地签选项。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Check if you need a UK visa 工具", "desc": "官方工具,根据国籍自动判断是否需要签证、ETA 或完全免签。", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "资格要求", "desc": "申请人必须能证明:访问结束会离开英国;能自行或由他人资助自己和家属费用;能支付回程或续程费用;不通过频繁访问在英长期居留。", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "电子旅行授权(ETA)", "desc": "2025 年起,部分非签证国籍赴英前需申请 ETA。当前涵盖欧盟、海湾及亚太等多个国家的护照。", "url": "https://www.gov.uk/guidance/apply-for-an-electronic-travel-authorisation-eta"},
            {"title": "拒签后申诉", "desc": "若被拒签,可在拒签决定日起 28 天内申请 Administrative Review(若签证按 Appendix Visitor 审理)。", "url": "https://www.gov.uk/immigration-asylum-tribunal"}
        ]
    },
    "templates": {
        "title": "英国 Standard Visitor — 辅助材料模板",
        "intro": "英国签证常见的辅助材料。具体要求以各签证中心公告为准。",
        "items": [
            {"title": "在职证明(英文)", "desc": "公司抬头:职位、薪资、在职年限、批假情况、签名盖章。英国接受英国公司开具的英文版,或国内开出附官方翻译件。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "银行流水 — 签证官关注点", "desc": "近 3-6 个月银行盖章流水,余额稳定,有持续的工资入账。需银行抬头纸打印。", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "行程单与酒店/机票预订", "desc": "按天列出酒店预订或接待方证明,以及回程机票预订。注意行程与申请日期一致。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "TB 检测证书", "desc": "在中国居住 ≥ 6 个月的申请人必须提供。证书由英国内政部指定的医院(GOV.UK 官网公布清单)出具。", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "旅行医疗保险 — 非强制", "desc": "Standard Visitor 不要求强制保险,但鉴于英国医疗费高昂,强烈建议购买。", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "不要带的材料", "desc": "英国不要求邀请函,只需要住宿证明(酒店预订 或 接待方书面确认)。", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "faq": {
        "title": "英国 Standard Visitor — 常见问答",
        "intro": "B1/B2 办理过程中最常被问到的问题 — 费用、拒签、处理周期等。",
        "items": [
            {"title": "办理周期多长?", "desc": "英国境外申请通常在按指纹后 3 周处理完成。很多签证中心提供 Priority(优先)与 Super-priority(超优先)加急服务。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Standard Visitor 可以工作或学习吗?", "desc": "允许 ≤ 6 个月短期学习。除 permitted paid engagement 外不允许任何带薪或无薪工作。", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "需要邀请函吗?", "desc": "不需要。GOV.UK 不要求正式邀请函,只需能证明住宿即可(酒店预订或接待方书面确认)。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "拒签后怎么办?", "desc": "可在补强材料后重新申请;若决定是按 Appendix Visitor 做出,可在 28 天内申请 Administrative Review。", "url": "https://www.gov.uk/immigration-asylum-tribunal"},
            {"title": "TB 检测是必须的吗?", "desc": "是。如在包括中国在内的特定国家居住过 ≥ 6 个月,申请前必须在英国内政部指定医院做 TB 检测。", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "怎么付签证费?", "desc": "GOV.UK 在线用借记卡/信用卡/网银支付。完成在线申请后,前往英国签证中心(VAC)采集生物信息。", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"}
        ]
    }
}

GB_ID = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Visa Standard Visitor Inggris — Wiki",
        "intro": "Standard Visitor adalah rute singkat utama untuk wisata, kunjungan bisnis, studi pendek (hingga 6 bulan), dan paid engagement yang diizinkan. Lama tinggal biasanya hingga 6 bulan; tinggal lebih lama memerlukan rute berbeda.",
        "items": [
            {"title": "Apa itu visa Standard Visitor?", "desc": "Satu rute jangka pendek yang mencakup wisata, kunjungan keluarga/teman, rapat bisnis, dan studi pendek (≤6 bulan). Paid engagement yang diizinkan diperbolehkan untuk ahli yang berkunjung.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Siapa yang butuh visa vs. yang bisa pakai ETA / bebas visa", "desc": "Sebagian besar pemegang paspor EU dan Teluk dapat menggunakan Electronic Travel Authorisation (ETA) untuk kunjungan singkat. Pemegang paspor RRT harus mengajukan visa Standard Visitor.", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "Standard Visitor vs. Visitor in Transit", "desc": "Standard Visitor memungkinkan masuk dan kegiatan di Inggris. Visitor in Transit (£74.50) adalah untuk penumpang yang melewati kontrol perbatasan Inggris dalam perjalanan ke negara lain.", "url": "https://www.gov.uk/transit-visa/visitor-in-transit-visa"},
            {"title": "Standard Visitor jangka panjang (2 / 5 / 10 tahun)", "desc": "Anda dapat mengajukan visa Standard Visitor 2, 5, atau 10 tahun dengan biaya lebih tinggi. Setiap kunjungan tetap hingga 6 bulan. Visa jangka panjang tidak memungkinkan tinggal lama di Inggris.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Tes Tuberkulosis (TB) untuk pemohon yang tinggal di RRT", "desc": "Pemohon yang telah tinggal di RRT (atau negara daftar lainnya) selama 6+ bulan harus menjalani tes TB di klinik yang disetujui UK Home Office dan menyerahkan sertifikat. Tes dari klinik yang tidak disetujui tidak diterima.", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Kegiatan yang diizinkan — apa yang boleh dan tidak", "desc": "Boleh: wisata, kunjungan keluarga, transit, rapat bisnis, paid engagement sebagai ahli, studi ≤6 bulan. Tidak boleh: kerja berbayar/tidak di Inggris (kecuali paid engagement yang diizinkan), tunjangan, kunjungan sering berturut-turut untuk tinggal di Inggris.", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "policy": {
        "title": "Inggris — Kebijakan & Regulasi",
        "intro": "Halaman resmi dari GOV.UK untuk kebijakan Standard Visitor.",
        "items": [
            {"title": "Biaya aplikasi — £135 GBP (visa 6 bulan)", "desc": "£135 untuk visa Standard Visitor jangka pendek standar (hingga 6 bulan). £74.50 untuk Visitor in Transit. Varian jangka panjang lebih tinggi.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Ajukan secara online melalui GOV.UK", "desc": "Semua aplikasi visa Inggris harus diajukan secara online melalui GOV.UK. Tidak ada opsi visa on-arrival untuk warga negara RRT.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Periksa apakah Anda butuh visa Inggris", "desc": "Alat resmi untuk memeriksa apakah kebangsaan Anda memerlukan visa, ETA, atau tidak keduanya.", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "Persyaratan kelayakan", "desc": "Anda harus dapat membuktikan akan meninggalkan Inggris pada akhir kunjungan, mampu menghidupi diri sendiri dan tanggungan, mendanai perjalanan kembali/lanjutan, dan tidak tinggal lama di Inggris melalui kunjungan berturut-turut.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Electronic Travel Authorisation (ETA)", "desc": "Sejak 2025, beberapa kebangsaan non-visa harus mendapatkan ETA sebelum bepergian ke Inggris. Saat ini termasuk warga negara EU, Teluk, dan beberapa paspor Asia-Pasifik.", "url": "https://www.gov.uk/guidance/apply-for-an-electronic-travel-authorisation-eta"},
            {"title": "Keputusan visa dan banding", "desc": "Jika ditolak, Anda dapat mengajukan Administrative Review dalam 28 hari sejak tanggal penolakan jika visa diputuskan berdasarkan Appendix Visitor.", "url": "https://www.gov.uk/immigration-asylum-tribunal"}
        ]
    },
    "templates": {
        "title": "Standard Visitor Inggris — Template Dokumen Pendukung",
        "intro": "Dokumen pendukung umum di tahap keputusan visa Inggris. Template disediakan; persyaratan spesifik dapat bervariasi.",
        "items": [
            {"title": "Surat keterangan kerja — Bahasa Inggris", "desc": "Di atas kop surat perusahaan: jabatan, gaji, lama bekerja, cuti yang disetujui, dan tanda tangan. UKVI menerima versi yang dikeluarkan kantor Inggris atau versi RRT dengan terjemahan resmi.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Rekening koran — apa yang dilihat petugas", "desc": "Mutasi 3-6 bulan terakhir yang menunjukkan saldo konsisten dan arus masuk rutin (gaji). Cetak di atas kop bank dengan cap.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Rencana perjalanan dan pemesanan akomodasi", "desc": "Rencana harian dengan reservasi hotel atau undangan host dan pemesanan penerbangan kembali. Harus konsisten dengan aplikasi.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Sertifikat tes tuberkulosis", "desc": "Diperlukan untuk pemohon yang tinggal di RRT selama 6+ bulan. Dikeluarkan hanya oleh klinik yang disetujui UK Home Office (daftar klinik dipublikasikan di GOV.UK).", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Asuransi perjalanan — tidak secara ketat diperlukan", "desc": "Visa Standard Visitor tidak memerlukan asuransi perjalanan sebagai syarat formal. Sangat direkomendasikan — layanan kesehatan Inggris tidak gratis untuk non-penduduk.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Yang TIDAK boleh dibawa", "desc": "Tidak seperti Schengen, Inggris tidak meminta 'Surat Undangan' terpisah. Bawa undangan host hanya jika Anda tidak bisa menunjukkan akomodasi.", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "faq": {
        "title": "Standard Visitor Inggris — Pertanyaan Umum",
        "intro": "Pertanyaan yang paling sering diajukan tentang visa Standard Visitor — biaya, pemrosesan, penolakan.",
        "items": [
            {"title": "Berapa lama pemrosesan?", "desc": "Di luar Inggris, pemrosesan biasanya 3 minggu dari biometrik. Layanan Priority dan Super-priority tersedia di banyak lokasi dengan biaya tambahan.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Bisakah saya bekerja atau belajar dengan visa Standard Visitor?", "desc": "Studi pendek hingga 6 bulan diperbolehkan. Kerja berbayar atau tidak berbayar tidak, kecuali permitted paid engagement (daftar singkat kegiatan ahli).", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Apakah saya butuh surat undangan dari host Inggris?", "desc": "Tidak. GOV.UK tidak mewajibkan surat undangan formal. Anda hanya perlu menunjukkan tempat menginap (pemesanan hotel atau konfirmasi tertulis dari host).", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Apa jika visa Standard Visitor saya ditolak?", "desc": "Anda dapat mengajukan ulang kapan saja dengan bukti yang lebih kuat, atau mengajukan Administrative Review dalam 28 hari sejak penolakan.", "url": "https://www.gov.uk/immigration-asylum-tribunal"},
            {"title": "Apakah tes TB wajib?", "desc": "Ya, jika Anda tinggal 6+ bulan di negara yang terdaftar termasuk RRT dalam 12 bulan terakhir, sebelum aplikasi visa. Sertifikat hanya dari klinik yang disetujui.", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Bagaimana cara membayar biaya visa?", "desc": "Online melalui GOV.UK dengan kartu debit/kredit atau perbankan online. Pengumpulan biometrik kemudian dipesan di UK Visa Application Centre (VAC).", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"}
        ]
    }
}

GB_VI = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Visa Thăm Chuẩn (Standard Visitor) Anh Quốc — Bách khoa",
        "intro": "Standard Visitor là tuyến chính cho lưu trú ngắn hạn tại Anh: du lịch, thăm viếng kinh doanh, học ngắn hạn (đến 6 tháng) và các hoạt động được trả phép (permitted paid engagement). Thời gian lưu trú thường đến 6 tháng.",
        "items": [
            {"title": "Visa Standard Visitor là gì?", "desc": "Một tuyến ngắn hạn bao gồm du lịch, thăm thân nhân/bạn bè, họp kinh doanh, và học ngắn hạn (≤6 tháng). Các chuyên gia được phép thực hiện paid engagement.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Ai cần visa, ai dùng ETA / miễn thị thực", "desc": "Hầu hết hộ chiếu EU và Vịnh có thể dùng Electronic Travel Authorisation (ETA) cho lưu trú ngắn. Người mang hộ chiếu Trung Quốc phải xin visa Standard Visitor.", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "Standard Visitor vs. Visitor in Transit", "desc": "Standard Visitor cho phép nhập cảnh và hoạt động tại Anh. Visitor in Transit (£74.50) dành cho hành khách đi qua Anh để sang nước thứ ba.", "url": "https://www.gov.uk/transit-visa/visitor-in-transit-visa"},
            {"title": "Standard Visitor dài hạn (2 / 5 / 10 năm)", "desc": "Có thể xin visa Standard Visitor 2 năm, 5 năm hoặc 10 năm với phí cao hơn. Mỗi lần nhập cảnh vẫn ≤6 tháng. Visa dài hạn không cho phép cư trú lâu tại Anh.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Xét nghiệm lao (TB) cho người cư trú tại Trung Quốc", "desc": "Người xin đã sống tại Trung Quốc (hoặc các nước trong danh sách) 6+ tháng phải xét nghiệm TB tại phòng khám được UK Home Office chấp thuận và nộp giấy chứng nhận. Xét nghiệm từ nơi không được chấp thuận sẽ bị từ chối.", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Hoạt động được phép — được và không được", "desc": "Được: du lịch, thăm thân, transit, họp kinh doanh, paid engagement với tư cách chuyên gia, học ≤6 tháng. Không được: làm việc có lương/không lương (trừ paid engagement), nhận trợ cấp, qua nhiều chuyến liên tiếp để cư trú.", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "policy": {
        "title": "Anh Quốc — Chính sách & Điều luật",
        "intro": "Các trang chính thức từ GOV.UK cho chính sách Standard Visitor.",
        "items": [
            {"title": "Phí nộp đơn — £135 GBP (visa 6 tháng)", "desc": "£135 cho visa Standard Visitor ngắn hạn tiêu chuẩn (đến 6 tháng). £74.50 cho Visitor in Transit. Biến thể dài hạn cao hơn.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Nộp đơn trực tuyến qua GOV.UK", "desc": "Mọi đơn xin visa Anh phải nộp trực tuyến qua GOV.UK. Không có visa-on-arrival cho công dân Trung Quốc.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Check if you need a UK visa", "desc": "Công cụ chính thức kiểm tra quốc tịch của bạn cần visa, ETA, hay không cần gì cả.", "url": "https://www.gov.uk/check-uk-visa"},
            {"title": "Yêu cầu hội đủ điều kiện", "desc": "Phải chứng minh sẽ rời Anh khi kết thúc thăm, có khả năng tự nuôi sống bản thân và người phụ thuộc, có khả năng chi trả chuyến về/tiếp theo, không cư trú lâu tại Anh qua nhiều chuyến liên tiếp.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Electronic Travel Authorisation (ETA)", "desc": "Từ 2025, một số quốc tịch không cần visa phải có ETA trước khi đến Anh. Hiện bao gồm EU, Vịnh và một số hộ chiếu châu Á – Thái Bình Dương.", "url": "https://www.gov.uk/guidance/apply-for-an-electronic-travel-authorisation-eta"},
            {"title": "Quyết định visa và kháng cáo", "desc": "Nếu bị từ chối, bạn có thể nộp đơn Administrative Review trong 28 ngày kể từ ngày từ chối nếu visa được quyết theo Appendix Visitor.", "url": "https://www.gov.uk/immigration-asylum-tribunal"}
        ]
    },
    "templates": {
        "title": "Standard Visitor Anh — Mẫu Tài liệu Hỗ trợ",
        "intro": "Tài liệu hỗ trợ thường gặp ở giai đoạn quyết định visa Anh. Có mẫu; yêu cầu cụ thể có thể thay đổi theo trung tâm visa.",
        "items": [
            {"title": "Thư xác nhận việc làm — tiếng Anh", "desc": "Trên giấy tiêu đề công ty: chức vụ, lương, thời gian làm việc, nghỉ phép được duyệt, chữ ký. UKVI chấp nhận phiên bản tiếng Anh hoặc phiên bản Trung Quốc kèm bản dịch chính thức.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Sao kê ngân hàng — điều nhân viên xem", "desc": "Sao kê 3–6 tháng gần nhất cho thấy số dư ổn định và dòng tiền vào đều đặn (lương). In trên giấy tiêu đề ngân hàng có đóng dấu.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Lịch trình và đặt chỗ ở / vé máy bay", "desc": "Kế hoạch theo từng ngày với đặt phòng khách sạn hoặc thư mời của host cùng đặt vé khứ hồi. Phải nhất quán với đơn xin.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Giấy chứng nhận xét nghiệm lao", "desc": "Bắt buộc cho người xin cư trú tại Trung Quốc 6+ tháng. Chỉ được cấp bởi phòng khám được UK Home Office chấp thuận (danh sách công bố trên GOV.UK).", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Bảo hiểm du lịch — không bắt buộc", "desc": "Visa Standard Visitor không yêu cầu bảo hiểm du lịch như điều kiện chính thức. Rất khuyến nghị — y tế Anh không miễn phí cho người không cư trú.", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "KHÔNG nên mang theo", "desc": "Không như Schengen, Anh không yêu cầu 'Thư mời' riêng. Chỉ mang theo thư mời của host nếu bạn không chứng minh được chỗ ở.", "url": "https://www.gov.uk/standard-visitor"}
        ]
    },
    "faq": {
        "title": "Standard Visitor Anh — Câu hỏi Thường gặp",
        "intro": "Các câu hỏi thường gặp nhất về visa Standard Visitor — phí, xử lý, từ chối.",
        "items": [
            {"title": "Thời gian xử lý là bao lâu?", "desc": "Bên ngoài Anh, xử lý thường 3 tuần kể từ khi lấy sinh trắc. Dịch vụ Priority và Super-priority có tại nhiều địa điểm với phí bổ sung.", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Có thể làm việc hoặc học với visa Standard Visitor không?", "desc": "Học ngắn hạn đến 6 tháng được phép. Làm việc có lương hoặc không lương không được, trừ permitted paid engagement (danh sách ngắn các hoạt động chuyên gia).", "url": "https://www.gov.uk/standard-visitor"},
            {"title": "Có cần thư mời từ host tại Anh không?", "desc": "Không. GOV.UK không yêu cầu thư mời chính thức. Bạn chỉ cần chứng minh nơi ở (đặt phòng khách sạn hoặc xác nhận bằng văn bản từ host).", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"},
            {"title": "Nếu visa Standard Visitor bị từ chối thì sao?", "desc": "Có thể nộp đơn lại bất kỳ lúc nào với bằng chứng mạnh hơn, hoặc nộp Administrative Review trong 28 ngày kể từ ngày từ chối.", "url": "https://www.gov.uk/immigration-asylum-tribunal"},
            {"title": "Xét nghiệm TB có bắt buộc không?", "desc": "Có. Nếu bạn đã sống 6+ tháng tại một quốc gia trong danh sách bao gồm Trung Quốc trong 12 tháng qua, trước khi nộp đơn visa. Chỉ chấp nhận từ phòng khám được chấp thuận.", "url": "https://www.gov.uk/tb-test-visa"},
            {"title": "Làm sao để trả phí visa?", "desc": "Trực tuyến qua GOV.UK bằng thẻ ghi nợ/tín dụng hoặc ngân hàng trực tuyến. Sau đó đặt lịch lấy sinh trắc tại Trung tâm Visa Anh (VAC).", "url": "https://www.gov.uk/standard-visitor/apply-standard-visitor-visa"}
        ]
    }
}

AU_ZH = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "澳大利亚 Subclass 600 访客签证 — 百科",
        "intro": "Subclass 600 是澳大利亚的访客签证,适用于旅游、探亲访友或短期商务访问。共 5 个 stream:Tourist / Business Visitor / Sponsored Family / Approved Destination / Frequent Traveller。请按访问目的选择对应 stream。",
        "items": [
            {"title": "什么是 Subclass 600 访客签证?", "desc": "短期临时签证,涵盖旅游、探亲、商务访问等短期非工作活动。每次停留时长由签证官决定,常见 3、6、12 个月。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "境内申请 vs. 境外申请", "desc": "多数中国申请人在境外通过 ImmiAccount 申请;境内延期仅在特殊场景下可行,且“跳签”限制越来越严。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "有效期 vs. 每次停留期", "desc": "Subclass 600 通常签为 1 年多次。Tourist stream 每次最长停留 3 个月,签证官可酌情延长至 6 或 12 个月。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Sponsored Family Stream(担保类家庭访问)", "desc": "由澳洲公民或 PR 亲属(父母、成年子女)担保。担保类申请可能获得更长有效期(18 个月到 5 年,视情况)。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/sponsored-family-stream"},
            {"title": "No Further Stay 条款(自 2025-03-21 起)", "desc": "自 2025-03-21 起,所有 Subclass 600 准签信均添加 No Further Stay 条款,持有人在澳洲境内不能申请其他签证(部分特例除外)。请提前规划。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Frequent Traveller Stream(常旅客)", "desc": "专为频繁往返的中、东南亚等特定国家商务/旅游人士设立。有效期最长 10 年,每次停留 ≤ 3 个月。申请费较高。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/frequent-traveller-stream"}
        ]
    },
    "policy": {
        "title": "澳大利亚 — 法规与政策",
        "intro": "来自澳大利亚内政事务部(Department of Home Affairs)的 Subclass 600 政策权威页面。",
        "items": [
            {"title": "申请费 — 从 AUD $190 起(Tourist Stream)", "desc": "境外申请的 Tourist Stream 基础申请费为 AUD $190。其他 stream(Sponsored Family 等)费用可能不同,以最新官方价格表为准。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "通过 ImmiAccount 在线申请", "desc": "所有 Subclass 600 申请通过 ImmiAccount 在线提交。中国护照无纸质申请通道。", "url": "https://online.immi.gov.au/"},
            {"title": "签证定价表(最新)", "desc": "内政部官方发布、按签证子类/stream 列出的费用表,定期更新。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"},
            {"title": "签证全球审理时间", "desc": "按子类、stream、申请人所在地划分的实时审理周期估算。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "健康与品行要求", "desc": "大多数短期访客签证需通过健康检查和品行审查;长期停留或特定国籍可能需要 panel physician 体检。", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "Subclass 600 政策更新", "desc": "内政部实时公告 — 费率变更、资格更新、审理时间调整。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "templates": {
        "title": "澳大利亚 Subclass 600 — 辅助材料模板",
        "intro": "Subclass 600 申请的常见辅助材料。提供模板;具体要求可能不同。",
        "items": [
            {"title": "ImmiAccount 注册", "desc": "免费注册。一个账号可管理多份申请(适用于家庭出行)。", "url": "https://online.immi.gov.au/lusc/register"},
            {"title": "旅行历史和身份材料", "desc": "扫描护照首页、中国身份证、户口本以及过往签证 / 入境章。多页户口本合并为单个 PDF 上传。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "在职与财力证明", "desc": "雇主信、近 3-6 个月工资单和银行盖章流水。房产 / 车产证明作为可选补充。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "行程单", "desc": "详细到每一天的行程安排,清楚显示访问目的真实且为短期。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "文件翻译说明", "desc": "Immi 不要求英文文件附官方翻译;中文文件可与英文表格同时上传。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "不建议提交的材料", "desc": "不建议上传:公证邀请函(基本不需要)、宣传照片、社交媒体截图。上传真正能证明访客身份的材料即可。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "faq": {
        "title": "澳大利亚 Subclass 600 — 常见问答",
        "intro": "澳大利亚访客签证最常被问到的问题 — 费用、拒签、审理。",
        "items": [
            {"title": "审理周期多长?", "desc": "材料齐全的 Tourist Stream 多在 1-4 周内出签。以 Global Processing Times 实时数据为准。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "持 600 期间能申请学签吗?", "desc": "不能。自 2025-03-21 起所有 600 准签信均带 No Further Stay 条款。请改在境外申请学生签证(Subclass 500)。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "能拿到 3 年 / 5 年多次签证吗?", "desc": "部分 Sponsored Family Stream 与 Frequent Traveller Stream 申请人可获更长有效期。Tourist Stream 首次申请通常拿 1 年。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "家人能共用一份申请吗?", "desc": "不能。每人必须单独申请;但可在同一 ImmiAccount 下建组(Group processing)以便签证官综合审阅。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "需要录指纹或体检吗?", "desc": "多数 Tourist Stream 不需要指纹。3 个月以上停留或 75 岁以上申请人可能被要求体检。", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "怎么付签证费?", "desc": "ImmiAccount 在线支付 — 信用卡、PayPal、或 BPAY(澳洲银行账户)。信用卡可能收手续费。", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"}
        ]
    }
}

AU_ID = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Visa Pengunjung Australia (Subclass 600) — Wiki",
        "intro": "Visitor visa (Subclass 600) adalah rute jangka pendek utama untuk wisata, mengunjungi keluarga/teman, atau kunjungan bisnis singkat. Terdapat 5 stream (Tourist, Business Visitor, Sponsored Family, Approved Destination, Frequent Traveller) — pilih stream yang sesuai dengan tujuan Anda.",
        "items": [
            {"title": "Apa itu Subclass 600 (Visitor visa)?", "desc": "Visa sementara jangka pendek yang mengizinkan wisata, kunjungan keluarga, kunjungan bisnis, dan kegiatan jangka pendek non-kerja. Lama tinggal ditetapkan oleh petugas; umum 3, 6, atau 12 bulan per kunjungan.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Siapa yang bisa mengajukan di dalam vs. di luar Australia", "desc": "Sebagian besar pemohon RRT mengajukan dari luar negeri melalui ImmiAccount. Perpanjangan di dalam Australia hanya mungkin dalam skenario spesifik dan semakin ketat karena aturan visa hopping.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Masa berlaku vs. lama tinggal", "desc": "Subclass 600 biasanya diterbitkan sebagai multi-entry 1 tahun untuk Tourist Stream. Setiap kunjungan dapat hingga 3 bulan (terkadang 6 atau 12 bulan berdasarkan keputusan petugas).", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Sponsored Family Stream", "desc": "Warga negara Australia atau PR (orang tua, anak dewasa) dapat mensponsori kerabat mereka. Pemohon bersponsor dapat mendapat masa berlaku lebih lama (18 bulan hingga 5 tahun tergantung kasus).", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/sponsored-family-stream"},
            {"title": "Klausul 'No Further Stay' (sejak 2025-03-21)", "desc": "Sejak 21 Maret 2025, semua surat keputusan Subclass 600 memuat kondisi No Further Stay — pemegang tidak dapat mengajukan sebagian besar visa lain selama tinggal di Australia. Rencanakan dengan tepat.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Frequent Traveller Stream (pelancong rutin)", "desc": "Stream terpisah untuk warga negara tertentu (termasuk RRT) yang sering bepergian. Masa berlaku hingga 10 tahun; setiap kunjungan hingga 3 bulan. Biaya lebih tinggi.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/frequent-traveller-stream"}
        ]
    },
    "policy": {
        "title": "Australia — Kebijakan & Regulasi",
        "intro": "Halaman resmi dari Department of Home Affairs Australia untuk Visitor visa 600.",
        "items": [
            {"title": "Biaya aplikasi — mulai AUD $190 (Tourist Stream)", "desc": "Biaya dasar Tourist Stream dari luar negeri adalah AUD $190. Stream lain (Sponsored Family, Approved Destination) mungkin berbeda. Periksa Tabel Harga Visa terbaru sebelum membayar.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Ajukan via ImmiAccount", "desc": "Semua aplikasi Subclass 600 diajukan melalui portal online ImmiAccount. Tidak ada aplikasi kertas untuk paspor RRT.", "url": "https://online.immi.gov.au/"},
            {"title": "Tabel harga visa (terbaru)", "desc": "Harga resmi per subclass dan stream visa. Diperbarui oleh Department of Home Affairs. Gunakan sebagai sumber otoritatif untuk biaya terkini.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"},
            {"title": "Waktu pemrosesan visa global", "desc": "Estimasi waktu pemrosesan terkini untuk setiap subclass visa, dirinci per stream dan lokasi pemohon.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "Persyaratan kesehatan dan karakter", "desc": "Sebagian besar visa pengunjung jangka pendek memerlukan pemeriksaan kesehatan dan pengecekan karakter; tinggal lama atau kewarganegaraan tertentu mungkin memerlukan kunjungan panel physician tambahan.", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "Berita dan perubahan kebijakan Visitor visa 600", "desc": "Pembaruan terkini dari Department of Home Affairs — perubahan biaya, perubahan kelayakan, perubahan waktu pemrosesan.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "templates": {
        "title": "Australia Subclass 600 — Template Dokumen Pendukung",
        "intro": "Dokumen pendukung umum untuk aplikasi Subclass 600. Template disediakan; persyaratan spesifik dapat bervariasi.",
        "items": [
            {"title": "Pendaftaran ImmiAccount", "desc": "Buat ImmiAccount gratis sebelum mulai. Satu akun dapat menampung beberapa aplikasi (berguna untuk grup keluarga).", "url": "https://online.immi.gov.au/lusc/register"},
            {"title": "Riwayat perjalanan dan identitas", "desc": "Pindai halaman bio paspor, KTP RRT saat ini, registrasi rumah tangga (hukou ben) dan visa / cap imigrasi sebelumnya. Gabungkan halaman registrasi rumah tangga multi-halaman menjadi satu PDF.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Bukti pekerjaan dan keuangan", "desc": "Surat dari pemberi kerja, slip gaji terbaru, dan rekening koran 3–6 bulan di atas kop bank. Sertifikat properti / kendaraan bersifat opsional namun membantu.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Rencana perjalanan", "desc": "Rencana harian dengan pemesanan — untuk Subclass 600, rencana harus jelas menunjukkan perjalanan itu asli dan sementara.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Panduan terjemahan dokumen", "desc": "Immi tidak memerlukan terjemahan resmi untuk dokumen berbahasa Inggris. Dokumen RRT dapat diunggah apa adanya di samping formulir berbahasa Inggris.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Yang TIDAK boleh diserahkan", "desc": "Hindari mengunggah: surat undangan yang dilegalisir (jarang diperlukan), foto promosi, tangkapan layar media sosial. Unggah apa yang mendukung profil pengunjung asli Anda.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "faq": {
        "title": "Australia Subclass 600 — Pertanyaan Umum",
        "intro": "Pertanyaan yang paling sering diajukan tentang Australian Visitor visa — biaya, penolakan, pemrosesan.",
        "items": [
            {"title": "Berapa lama pemrosesan Subclass 600?", "desc": "Sebagian besar aplikasi Tourist Stream diproses dalam 1–4 minggu bila lengkap. Gunakan Global Processing Times untuk estimasi terkini.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "Bisakah saya beralih ke visa pelajar saat memegang 600?", "desc": "Tidak. Sejak 21 Maret 2025 semua keputusan 600 memuat kondisi No Further Stay. Ajukan visa pelajar (Subclass 500) dari luar Australia.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Bisakah saya dapat visa multi-entry 3 atau 5 tahun?", "desc": "Beberapa pemohon Sponsored Family Stream dan Frequent Traveller Stream mendapat masa berlaku lebih lama. Tourist Stream pertama biasanya 1 tahun.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Bisakah anggota keluarga berbagi satu aplikasi?", "desc": "Tidak. Setiap pemohon harus diajukan sebagai aplikasi terpisah, bahkan dalam satu ImmiAccount. Anda dapat mengelompokkannya untuk tinjauan (Group processing) agar petugas mempertimbangkan file bersama.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Apakah saya perlu biometrik atau medis?", "desc": "Sebagian besar pemohon Tourist Stream tidak memerlukan biometrik. Tinggal 3+ bulan di negara tertentu atau pemohon berusia 75+ mungkin memerlukan pemeriksaan medis.", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "Bagaimana cara membayar biaya?", "desc": "Online via ImmiAccount menggunakan kartu kredit, PayPal, atau BPAY (rekening bank Australia saja). Biaya layanan mungkin berlaku untuk pembayaran kartu kredit.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"}
        ]
    }
}

AU_VI = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Visa Khách Úc (Subclass 600) — Bách khoa",
        "intro": "Visitor visa (Subclass 600) là tuyến chính cho lưu trú ngắn hạn với mục đích du lịch, thăm thân nhân/bạn bè, hoặc thăm viếng kinh doanh ngắn. Có 5 stream (Tourist, Business Visitor, Sponsored Family, Approved Destination, Frequent Traveller) — chọn stream phù hợp với mục đích của bạn.",
        "items": [
            {"title": "Subclass 600 (Visitor visa) là gì?", "desc": "Visa tạm thời ngắn hạn cho phép du lịch, thăm thân, thăm viếng kinh doanh và các hoạt động ngắn hạn không làm việc. Thời gian lưu trú do viên chức quyết định; thường 3, 6 hoặc 12 tháng mỗi lần.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Ai nộp trong nước vs. ngoài nước", "desc": "Hầu hết người xin Trung Quốc nộp ngoài nước qua ImmiAccount. Gia hạn trong nước chỉ khả thi trong một số tình huống cụ thể và ngày càng chặt với quy định visa hopping.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Thời hạn so với thời gian lưu trú", "desc": "Subclass 600 thường cấp dưới dạng nhiều lần 1 năm cho Tourist Stream. Mỗi lần có thể lưu trú đến 3 tháng (đôi khi 6 hoặc 12 tháng tùy quyết định của viên chức).", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Sponsored Family Stream", "desc": "Thân nhân là công dân Úc hoặc PR (cha mẹ, con trưởng thành) có thể bảo lãnh. Người được bảo lãnh có thể được cấp thời hạn dài hơn (18 tháng đến 5 năm tùy trường hợp).", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/sponsored-family-stream"},
            {"title": "Điều khoản 'No Further Stay' (từ 2025-03-21)", "desc": "Từ 21/03/2025, mọi quyết định Subclass 600 đều có điều khoản No Further Stay — người giữ visa không thể nộp đơn visa khác trong khi ở Úc (trừ một số ngoại lệ). Hãy lên kế hoạch trước.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Frequent Traveller Stream (khách thường xuyên)", "desc": "Stream riêng cho công dân một số quốc gia nhất định (bao gồm Trung Quốc) đi lại thường xuyên. Thời hạn đến 10 năm; mỗi lần lưu trú ≤ 3 tháng. Phí cao hơn.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/frequent-traveller-stream"}
        ]
    },
    "policy": {
        "title": "Úc — Chính sách & Điều luật",
        "intro": "Các trang chính thức từ Department of Home Affairs Úc cho Visitor visa 600.",
        "items": [
            {"title": "Phí nộp đơn — từ AUD $190 (Tourist Stream)", "desc": "Phí cơ bản Tourist Stream từ ngoài nước là AUD $190. Stream khác (Sponsored Family, Approved Destination) có thể khác. Kiểm tra Bảng Giá Visa mới nhất trước khi thanh toán.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Nộp đơn qua ImmiAccount", "desc": "Mọi đơn Subclass 600 nộp qua cổng trực tuyến ImmiAccount. Không có đơn giấy cho hộ chiếu Trung Quốc.", "url": "https://online.immi.gov.au/"},
            {"title": "Bảng giá visa (mới nhất)", "desc": "Bảng giá chính thức theo subclass và stream visa. Cập nhật bởi Department of Home Affairs. Dùng làm nguồn tham khảo cho phí hiện hành.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"},
            {"title": "Thời gian xử lý visa toàn cầu", "desc": "Ước tính thời gian xử lý theo từng subclass, chi tiết theo stream và vị trí của người xin.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "Yêu cầu sức khỏe và nhân phẩm", "desc": "Hầu hết visa khách ngắn hạn yêu cầu khám sức khỏe và kiểm tra nhân phẩm; lưu trú dài hoặc một số quốc tịch có thể cần khám với panel physician.", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "Tin tức và thay đổi chính sách Visitor visa 600", "desc": "Cập nhật trực tiếp từ Department of Home Affairs — thay đổi phí, thay đổi điều kiện, thay đổi thời gian xử lý.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "templates": {
        "title": "Úc Subclass 600 — Mẫu Tài liệu Hỗ trợ",
        "intro": "Tài liệu hỗ trợ thường gặp cho đơn Subclass 600. Có mẫu; yêu cầu cụ thể có thể khác.",
        "items": [
            {"title": "Đăng ký ImmiAccount", "desc": "Tạo ImmiAccount miễn phí trước khi bắt đầu. Một tài khoản có thể quản lý nhiều đơn (tiện cho nhóm gia đình).", "url": "https://online.immi.gov.au/lusc/register"},
            {"title": "Lịch sử đi lại và giấy tờ tùy thân", "desc": "Quét trang hộ chiếu, CCCD Trung Quốc hiện tại, sổ hộ khẩu và visa / tem nhập cảnh trước đây. Gộp sổ hộ khẩu nhiều trang thành một PDF.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Việc làm và tài chính", "desc": "Thư từ nhà tuyển dụng, phiếu lương gần đây, sao kê ngân hàng 3–6 tháng trên giấy tiêu đề ngân hàng. Giấy chứng nhận nhà/xe là tùy chọn nhưng có ích.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Lịch trình", "desc": "Kế hoạch chi tiết theo từng ngày kèm đặt chỗ — đối với Subclass 600, lịch trình phải cho thấy chuyến đi thật sự và tạm thời.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Hướng dẫn dịch tài liệu", "desc": "Immi không yêu cầu dịch công chứng cho tài liệu tiếng Anh. Tài liệu tiếng Trung có thể tải lên cùng biểu mẫu tiếng Anh.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Không nên nộp", "desc": "Tránh tải lên: thư mời có công chứng (hiếm khi cần), ảnh quảng cáo, ảnh chụp màn hình mạng xã hội. Chỉ tải lên những gì hỗ trợ hồ sơ khách thật sự.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"}
        ]
    },
    "faq": {
        "title": "Úc Subclass 600 — Câu hỏi Thường gặp",
        "intro": "Các câu hỏi thường gặp nhất về Australian Visitor visa — phí, từ chối, xử lý.",
        "items": [
            {"title": "Subclass 600 xử lý mất bao lâu?", "desc": "Hầu hết đơn Tourist Stream xử lý trong 1–4 tuần nếu đầy đủ. Xem Global Processing Times để biết ước tính mới nhất.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-processing-times"},
            {"title": "Có thể chuyển sang visa sinh viên khi đang cầm 600 không?", "desc": "Không. Từ 21/03/2025 mọi quyết định 600 đều có điều khoản No Further Stay. Hãy nộp visa sinh viên (Subclass 500) từ ngoài nước Úc.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Có được visa nhiều lần 3 hoặc 5 năm không?", "desc": "Một số người xin Sponsored Family Stream và Frequent Traveller Stream có thể nhận thời hạn dài hơn. Tourist Stream lần đầu thường là 1 năm.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Người nhà có thể dùng chung một đơn không?", "desc": "Không. Mỗi người phải nộp đơn riêng, kể cả trong cùng ImmiAccount. Có thể nhóm (Group processing) để viên chức xét duyệt cùng nhau.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"},
            {"title": "Có cần sinh trắc hay khám sức khỏe không?", "desc": "Hầu hết người xin Tourist Stream không cần sinh trắc. Lưu trú 3+ tháng ở một số quốc gia hoặc người xin từ 75 tuổi trở lên có thể cần khám sức khỏe.", "url": "https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health"},
            {"title": "Cách thanh toán phí?", "desc": "Trực tuyến qua ImmiAccount bằng thẻ tín dụng, PayPal hoặc BPAY (chỉ tài khoản ngân hàng Úc). Có thể có phí dịch vụ cho thanh toán thẻ tín dụng.", "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/fees"}
        ]
    }
}

SCHENGEN_ZH = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "申根短期签证(C 类)— 百科",
        "intro": "申根 C 类短期签证由 29 个申根国家统一依据 EU 签证法典签发。任何 180 天内累计停留 ≤ 90 天,在整个申根区内合并计算。",
        "items": [
            {"title": "什么是申根 C 类短期签证?", "desc": "统一短期签证,任意 180 天内最多停留 90 天,适用于整个申根区。由首次入境国或主要目的地国签发。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "29 个申根国家及统一规则", "desc": "申根区包括 25 个欧盟成员国(奥地利、比利时、捷克、丹麦、爱沙尼亚、芬兰、法国、德国、希腊、匈牙利、意大利、拉脱维亚、立陶宛、卢森堡、马耳他、荷兰、波兰、葡萄牙、斯洛伐克、斯洛文尼亚、西班牙、瑞典)+ 4 个非欧盟成员国(冰岛、列支敦士登、挪威、瑞士)。", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "180/90 规则 — 计算方法", "desc": "90 天是滚动计算:每在申根区待一天就用掉 180 天窗口中的 1 天。可用官方计算器或护照盖章核算。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "应向哪个国家申请?", "desc": "只访一国 → 该国;多国 → 主要目的地(停留最久);停留相同 → 首次入境国。", "url": "https://www.schengenvisainfo.com/where-to-apply/"},
            {"title": "生物识别与 VIS", "desc": "首次申请采集 10 指指纹,在所有申根成员国 59 个月内有效。59 个月内再申请通常免重新采集。", "url": "https://www.consilium.europa.eu/en/press/press-releases/2024/05/14/schengen-visa/"},
            {"title": "即将实施的 EES 与 ETIAS", "desc": "EES(出入境系统)以电子登记取代护照盖章。ETIAS(类似美国 ESTA)要求免签国旅客行前申请授权。这些都不替代申根签证本身。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "policy": {
        "title": "申根 — 法规与政策",
        "intro": "欧盟委员会与欧盟理事会的申根签证政策权威来源。",
        "items": [
            {"title": "申请费 — €90 EUR(成人)", "desc": "依 Commission Delegated Regulation (EU) 2024/1415,自 2024-06-11 起:成人 €90,6-12 岁儿童 €45,6 岁以下免费。VFS Global / TLScontact 等外部服务商另收服务费。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"},
            {"title": "签证法典 — Council Reg. 810/2009", "desc": "Reg. (EC) 810/2009 是申根短期签证的核心法律基础。经 2019/1155(编纂)与 2024/1415(费用与流程变更)修订。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "旅行医疗保险 — €30,000 最低", "desc": "医疗保险最低 €30,000,覆盖整个申根区、整个停留期。需含紧急住院、医疗运送与遣返。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "标准审理周期 — 15 个日历日", "desc": "自申请合规起 15 个日历日内决定。可延长至 30 天,特殊情况下 60 天。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "拒签后申诉", "desc": "拒签后你会收到一份标准化的拒签表格。可以在拒签国按该国法律规定的期限(通常 15-30 天)内申诉。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "ETIAS(免签国旅客,2025 起)", "desc": "ETIAS 要求美国、英国等免签国旅客行前取得授权。费用 €20,有效期 3 年或至护照到期。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "templates": {
        "title": "申根短期签证 — 辅助材料模板",
        "intro": "申根短期签证申请的常见辅助材料。提供模板;具体要求因领事馆而异。",
        "items": [
            {"title": "旅行医疗保险证明", "desc": "来自欧盟认可的保险公司或公认的中国保险公司。条款必须明确:申根区全覆盖 + 最低 €30,000 保额。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "在职证明(中德/中法双语)", "desc": "公司抬头:职位、薪资、在职年限、批假情况、签名盖章。部分使馆接受双语,部分要求官方翻译件。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "银行流水 — 签证官关注点", "desc": "近 3-6 个月银行盖章流水,余额稳定,工资入账持续。银行抬头纸打印盖章。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "住宿证明", "desc": "全部停留期的酒店预订,或接待方书面说明 + 接待方身份证/护照复印件。Booking.com 预订通常接受;免费住宿可能需公证证明。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "回程机票预订", "desc": "确认的回程机票预订(不需付款)。拿到签证前不要购买机票。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "申根申请表(统一格式)", "desc": "所有申根国家使用同一份申请表。可在 VFS / TLScontact 中心、各国大使馆、以及欧盟“Visa”页面领取。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"}
        ]
    },
    "faq": {
        "title": "申根短期签证 — 常见问答",
        "intro": "申根短期签证最常被问到的问题 — 费用、拒签、审理。",
        "items": [
            {"title": "审理周期多长?", "desc": "标准 15 个日历日,可延长至 30 天,部分情况 60 天。建议出行前 15-30 天提交;早于 15 天可能被拒。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "需要旅行医疗保险吗?", "desc": "需要。申根要求最低 €30,000 保额、覆盖全部停留期。无保险 = 申请不合规。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "一张签证可以访问多个国家吗?", "desc": "可以。由一国签发的申根签证在整个 29 国通用(以主要目的地原则为准)。可在多国间分配停留。", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "拒签后怎么办?", "desc": "会收到标准化的拒签表格。可在拒签国按该国法律规定的期限(通常 15-30 天)内申诉。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "什么是 180/90 规则?", "desc": "整个申根区 180 天内最多停留 90 天。180 天是滚动窗口,90 天用完即必须离开。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "非欧盟儿童收费相同吗?", "desc": "6-12 岁 €45,6 岁以下免费。成人 €90。研究者、学生交流等类别可豁免。", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"}
        ]
    }
}

SCHENGEN_ID = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Visa Schengen Tinggal Singkat (Tipe C) — Wiki",
        "intro": "Visa tinggal singkat Tipe C dikeluarkan oleh 29 negara Schengen berdasarkan Kode Visa UE tunggal. Aturan 180/90: dalam periode 180 hari kapan pun, Anda dapat tinggal hingga 90 hari di seluruh area Schengen.",
        "items": [
            {"title": "Apa itu visa Schengen Tinggal Singkat (Tipe C)?", "desc": "Visa tinggal singkat seragam yang berlaku hingga 90 hari dalam periode 180 hari di seluruh area Schengen. Diterbitkan oleh negara Schengen yang Anda kunjungi pertama atau yang paling lama dikunjungi.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "29 negara Schengen dan aturan seragam", "desc": "Schengen mencakup 25 negara anggota UE (Austria, Belgia, Ceko, Denmark, Estonia, Finlandia, Prancis, Jerman, Yunani, Hongaria, Italia, Latvia, Lithuania, Luksemburg, Malta, Belanda, Polandia, Portugal, Slovakia, Slovenia, Spanyol, Swedia) + 4 negara non-UE (Islandia, Liechtenstein, Norwegia, Swiss).", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "Aturan 180/90 — cara menghitungnya", "desc": "90 hari dihitung bergulir: setiap hari Anda habiskan di area Schengen menggunakan 1 dari 90 hari dalam 180 hari sebelumnya. Gunakan kalkulator daring atau cap paspor.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Di mana mengajukan — aturan tujuan utama", "desc": "Satu negara → negara itu. Banyak negara → tujuan utama (kunjungan terlama). Kunjungan sama lama → titik masuk pertama.", "url": "https://www.schengenvisainfo.com/where-to-apply/"},
            {"title": "Biometrik dan VIS", "desc": "Aplikasi pertama mengambil 10 sidik jari; berlaku di semua negara Schengen selama 59 bulan. Aplikasi berikutnya dalam 59 bulan biasanya melewati biometrik.", "url": "https://www.consilium.europa.eu/en/press/press-releases/2024/05/14/schengen-visa/"},
            {"title": "EES dan ETIAS — yang akan datang", "desc": "EES (Entry/Exit System) menggantikan cap paspor dengan log elektronik. ETIAS (mirip ESTA AS) memperkenalkan otorisasi pra-perjalanan untuk pelancong bebas visa. Tidak menggantikan persyaratan visa itu sendiri.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "policy": {
        "title": "Schengen — Kebijakan & Regulasi",
        "intro": "Sumber otoritatif dari European Commission dan EU Council untuk kebijakan visa Schengen.",
        "items": [
            {"title": "Biaya aplikasi — €90 EUR (dewasa)", "desc": "Dari Commission Delegated Regulation (EU) 2024/1415, efektif 2024-06-11: biaya visa €90 untuk dewasa dan €45 untuk anak 6–12 tahun. Anak di bawah 6 gratis. Penyedia layanan eksternal (VFS, TLScontact) mengenakan biaya layanan sendiri.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"},
            {"title": "Kode Visa — Council Regulation 810/2009", "desc": "Kode Visa (Reg. (EC) 810/2009) adalah dasar hukum inti untuk visa tinggal singkat Schengen. Diamandemen oleh 2019/1155 (kodifikasi) dan 2024/1415 (perubahan biaya dan pemrosesan).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Asuransi medis perjalanan — minimal €30.000", "desc": "Asuransi medis harus mencakup setidaknya €30.000 dan berlaku di semua negara Schengen selama seluruh masa tinggal. Harus mencakup rawat inap darurat, evakuasi medis, dan repatriasi jenazah.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Waktu keputusan standar — 15 hari kalender", "desc": "Sejak dapat diterima, konsulat memutuskan dalam 15 hari kalender. Dapat diperpanjang menjadi 30 hari (dan dalam kasus luar biasa 60 hari).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Hak untuk mengajukan banding atas penolakan", "desc": "Jika ditolak, Anda menerima formulir standar yang mengutip alasan penolakan. Anda dapat banding di negara anggota penolak dalam tenggat yang ditetapkan oleh hukum nasionalnya (sering 15 sampai 30 hari).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "ETIAS untuk pelancong bebas visa (dari 2025)", "desc": "ETIAS akan mewajibkan pelancong bebas visa (AS, Inggris, dan sebagian besar paspor non-UE lainnya) mendapatkan otorisasi pra-perjalanan. Biaya €20, berlaku 3 tahun atau hingga paspor kedaluwarsa.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "templates": {
        "title": "Schengen Tinggal Singkat — Template Dokumen Pendukung",
        "intro": "Dokumen pendukung umum untuk aplikasi visa tinggal singkat Schengen. Template disediakan; persyaratan spesifik dapat bervariasi per konsulat.",
        "items": [
            {"title": "Sertifikat asuransi medis perjalanan", "desc": "Dari perusahaan asuransi yang disetujui UE atau perusahaan asuransi RRT yang diakui. Ketentuan cakupan harus secara eksplisit menyatakan cakupan di seluruh Schengen dan minimum €30.000.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Surat keterangan kerja (Tionghoa + Jerman/Prancis)", "desc": "Kop surat perusahaan: jabatan, gaji, lama bekerja, cuti yang disetujui, dan tanda tangan. Beberapa konsulat menerima dwibahasa, yang lain memerlukan terjemahan resmi.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Rekening koran — apa yang dilihat petugas", "desc": "Mutasi 3–6 bulan terakhir yang menunjukkan saldo konsisten dan arus masuk rutin (gaji). Cetak di atas kop bank dengan cap. Beberapa konsulat meminta rekening koran yang diberi cap dari bank.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Bukti akomodasi", "desc": "Pemesanan hotel untuk seluruh masa tinggal atau konfirmasi tertulis host + salinan KTP/paspor host. Konfirmasi Booking.com biasanya diterima; akomodasi gratis mungkin memerlukan atestasi notaris.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Reservasi penerbangan pulang-pergi", "desc": "Pemesanan penerbangan pulang yang dikonfirmasi (belum dibayar, hanya dipesan). Jangan beli tiket sampai visa disetujui.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Formulir aplikasi Schengen (format seragam)", "desc": "Formulir yang sama digunakan di semua negara Schengen. Tersedia di pusat VFS / TLScontact, kedutaan, dan halaman 'Visa' UE.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"}
        ]
    },
    "faq": {
        "title": "Schengen Tinggal Singkat — Pertanyaan Umum",
        "intro": "Pertanyaan yang paling sering diajukan tentang visa tinggal singkat Schengen — biaya, penolakan, pemrosesan.",
        "items": [
            {"title": "Berapa lama pemrosesan Schengen?", "desc": "Standar 15 hari kalender sejak dapat diterima; dapat diperpanjang menjadi 30 atau dalam beberapa kasus 60 hari. Ajukan minimal 15–30 hari sebelum perjalanan; konsulat dapat menolak lebih awal dari 15 hari.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Apakah saya butuh asuransi perjalanan?", "desc": "Ya. Schengen mewajibkan cakupan minimum €30.000 untuk seluruh masa tinggal. Tanpa itu, aplikasi Anda tidak dapat diterima.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Bisakah saya mengunjungi banyak negara dengan satu visa?", "desc": "Ya. Visa Schengen yang dikeluarkan oleh satu negara berlaku di semua 29 negara (tunduk pada aturan tujuan utama). Anda dapat membagi tinggal di beberapa negara.", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "Apa jika visa saya ditolak?", "desc": "Anda menerima formulir penolakan standar. Anda dapat banding di negara penolak dalam tenggat yang ditetapkan oleh hukum negara anggota tersebut (sering 15–30 hari).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Apa aturan 180/90?", "desc": "Maksimal 90 hari dalam periode 180 hari di seluruh area Schengen digabungkan. Setelah 90 hari, Anda harus keluar; 180 hari adalah jendela bergulir.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Apakah anak non-UE dikenai biaya yang sama?", "desc": "Anak usia 6–12 membayar €45. Anak di bawah 6 gratis. Biaya dewasa €90. Beberapa kategori (peneliti, siswa exchange resmi) mungkin dikecualikan.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"}
        ]
    }
}

SCHENGEN_VI = {
    "verified_at": "2026-07-03",
    "wiki": {
        "title": "Visa Schengen Lưu trú Ngắn hạn (Loại C) — Bách khoa",
        "intro": "Visa lưu trú ngắn hạn Loại C do 29 quốc gia Schengen cấp theo một Bộ luật Visa EU duy nhất. Quy tắc 180/90: trong bất kỳ chu kỳ 180 ngày, bạn có thể lưu trú đến 90 ngày trong toàn bộ khu vực Schengen.",
        "items": [
            {"title": "Visa Schengen Lưu trú Ngắn hạn (Loại C) là gì?", "desc": "Visa lưu trú ngắn hạn thống nhất có giá trị đến 90 ngày trong bất kỳ chu kỳ 180 ngày trên toàn khu vực Schengen. Do quốc gia Schengen bạn đến đầu tiên hoặc lưu trú lâu nhất cấp.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "29 quốc gia Schengen và quy tắc thống nhất", "desc": "Schengen gồm 25 quốc gia thành viên EU (Áo, Bỉ, Séc, Đan Mạch, Estonia, Phần Lan, Pháp, Đức, Hy Lạp, Hungary, Ý, Latvia, Litva, Luxembourg, Malta, Hà Lan, Ba Lan, Bồ Đào Nha, Slovakia, Slovenia, Tây Ban Nha, Thụy Điển) + 4 quốc gia ngoài EU (Iceland, Liechtenstein, Na Uy, Thụy Sĩ).", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "Quy tắc 180/90 — cách tính", "desc": "90 ngày tính trượt: mỗi ngày bạn ở khu vực Schengen dùng 1 trong 90 ngày trong 180 ngày trước đó. Dùng máy tính trực tuyến hoặc con dấu hộ chiếu.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Nộp đơn ở đâu — quy tắc điểm đến chính", "desc": "Một nước → nước đó. Nhiều nước → điểm đến chính (lưu trú lâu nhất). Lưu trú bằng nhau → điểm nhập cảnh đầu tiên.", "url": "https://www.schengenvisainfo.com/where-to-apply/"},
            {"title": "Sinh trắc học và VIS", "desc": "Đơn đầu tiên lấy 10 dấu vân tay; có giá trị trên tất cả quốc gia Schengen trong 59 tháng. Đơn tiếp theo trong 59 tháng thường bỏ qua sinh trắc.", "url": "https://www.consilium.europa.eu/en/press/press-releases/2024/05/14/schengen-visa/"},
            {"title": "EES và ETIAS — sắp tới", "desc": "EES (Entry/Exit System) thay thế con dấu hộ chiếu bằng nhật ký điện tử. ETIAS (tương tự ESTA Hoa Kỳ) giới thiệu ủy quyền trước chuyến cho khách miễn thị thực. Không thay thế yêu cầu visa.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "policy": {
        "title": "Schengen — Chính sách & Điều luật",
        "intro": "Nguồn chính thức từ European Commission và EU Council cho chính sách visa Schengen.",
        "items": [
            {"title": "Phí nộp đơn — €90 EUR (người lớn)", "desc": "Theo Commission Delegated Regulation (EU) 2024/1415, có hiệu lực 2024-06-11: phí visa €90 cho người lớn và €45 cho trẻ 6–12 tuổi. Trẻ dưới 6 miễn phí. Nhà cung cấp dịch vụ bên ngoài (VFS, TLScontact) thu phí dịch vụ riêng.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"},
            {"title": "Bộ luật Visa — Council Regulation 810/2009", "desc": "Bộ luật Visa (Reg. (EC) 810/2009) là cơ sở pháp lý cốt lõi cho visa lưu trú ngắn Schengen. Sửa đổi bởi 2019/1155 (codification) và 2024/1415 (thay đổi phí và xử lý).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Bảo hiểm y tế du lịch — tối thiểu €30.000", "desc": "Bảo hiểm y tế phải bao gồm ít nhất €30.000 và có hiệu lực tại tất cả quốc gia Schengen trong toàn bộ thời gian lưu trú. Phải bao gồm nhập viện khẩn cấp, sơ tán y tế và hồi hương thi hài.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Thời gian quyết định tiêu chuẩn — 15 ngày lịch", "desc": "Từ khi hợp lệ, lãnh sự quán quyết định trong 15 ngày lịch. Có thể kéo dài 30 ngày (và trong trường hợp đặc biệt 60 ngày).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Quyền kháng cáo khi bị từ chối", "desc": "Nếu bị từ chối, bạn nhận được biểu mẫu tiêu chuẩn nêu lý do từ chối. Bạn có thể kháng cáo tại quốc gia thành viên từ chối trong thời hạn luật pháp quốc gia đó quy định (thường 15 đến 30 ngày).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "ETIAS cho khách miễn thị thực (từ 2025)", "desc": "ETIAS sẽ yêu cầu khách miễn thị thực (Hoa Kỳ, Anh và hầu hết hộ chiếu ngoài EU khác) có ủy quyền trước chuyến. Phí €20, hiệu lực 3 năm hoặc đến khi hộ chiếu hết hạn.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1240"}
        ]
    },
    "templates": {
        "title": "Schengen Lưu trú Ngắn — Mẫu Tài liệu Hỗ trợ",
        "intro": "Tài liệu hỗ trợ thường gặp cho đơn visa Schengen lưu trú ngắn hạn. Có mẫu; yêu cầu cụ thể có thể khác theo lãnh sự quán.",
        "items": [
            {"title": "Giấy chứng nhận bảo hiểm y tế du lịch", "desc": "Từ công ty bảo hiểm được EU chấp thuận hoặc công ty bảo hiểm Trung Quốc được công nhận. Điều khoản phải nêu rõ: bao trùm toàn Schengen và tối thiểu €30.000.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Thư xác nhận việc làm (Trung + Đức/Pháp song ngữ)", "desc": "Trên giấy tiêu đề công ty: chức vụ, lương, thời gian làm việc, nghỉ phép được duyệt, chữ ký. Một số lãnh sự quán chấp nhận song ngữ, một số yêu cầu bản dịch chính thức.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Sao kê ngân hàng — điều nhân viên xem", "desc": "Sao kê 3–6 tháng gần nhất cho thấy số dư ổn định và dòng lương vào đều. In trên giấy tiêu đề ngân hàng với đóng dấu. Một số lãnh sự quán yêu cầu sao kê được đóng dấu từ ngân hàng.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Bằng chứng chỗ ở", "desc": "Đặt phòng khách sạn cho toàn bộ thời gian lưu trú, hoặc xác nhận bằng văn bản của host + bản sao CCCD/hộ chiếu host. Xác nhận Booking.com thường được chấp nhận; chỗ ở miễn phí có thể cần giấy chứng nhận công chứng.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Đặt vé khứ hồi", "desc": "Đặt vé khứ hồi đã xác nhận (chưa thanh toán, chỉ đặt). Đừng mua vé cho đến khi visa được cấp.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Đơn xin Schengen (định dạng thống nhất)", "desc": "Cùng một mẫu được dùng trên tất cả quốc gia Schengen. Có sẵn tại các trung tâm VFS / TLScontact, đại sứ quán và trang 'Visa' của EU.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"}
        ]
    },
    "faq": {
        "title": "Schengen Lưu trú Ngắn — Câu hỏi Thường gặp",
        "intro": "Các câu hỏi thường gặp nhất về visa Schengen lưu trú ngắn hạn — phí, từ chối, xử lý.",
        "items": [
            {"title": "Thời gian xử lý Schengen mất bao lâu?", "desc": "Tiêu chuẩn 15 ngày lịch kể từ khi hợp lệ; có thể kéo dài đến 30 hoặc trong một số trường hợp 60 ngày. Nộp đơn ít nhất 15–30 ngày trước chuyến đi; lãnh sự quán có thể từ chối nếu sớm hơn 15 ngày.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Có cần bảo hiểm du lịch không?", "desc": "Có. Schengen yêu cầu bảo hiểm tối thiểu €30.000 cho toàn bộ thời gian lưu trú. Không có thì đơn của bạn không hợp lệ.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Có thể thăm nhiều nước với một visa không?", "desc": "Có. Visa Schengen do một nước cấp có hiệu lực trên tất cả 29 nước (tuân theo quy tắc điểm đến chính). Bạn có thể chia thời gian lưu trú giữa các nước.", "url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"},
            {"title": "Nếu visa bị từ chối thì sao?", "desc": "Bạn nhận biểu mẫu từ chối tiêu chuẩn. Có thể kháng cáo tại nước từ chối trong thời hạn luật pháp nước đó quy định (thường 15–30 ngày).", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Quy tắc 180/90 là gì?", "desc": "Tối đa 90 ngày trong bất kỳ chu kỳ 180 ngày nào trên toàn khu vực Schengen. Sau 90 ngày, bạn phải rời đi; 180 ngày là cửa sổ trượt.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32009R0810"},
            {"title": "Trẻ em ngoài EU có cùng phí không?", "desc": "Trẻ 6–12 tuổi trả €45. Trẻ dưới 6 miễn phí. Phí người lớn là €90. Một số loại (nhà nghiên cứu, sinh viên trao đổi chính thức) có thể được miễn.", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1415"}
        ]
    }
}

COUNTRY_BLOCKS_LOCALES = {
    "zh-CN": {"gb": GB_ZH, "au": AU_ZH, "schengen": SCHENGEN_ZH},
    "id":    {"gb": GB_ID, "au": AU_ID, "schengen": SCHENGEN_ID},
    "vi":    {"gb": GB_VI, "au": AU_VI, "schengen": SCHENGEN_VI},
}


def _merge_country_block(existing_root: dict, lang: str, cc: str) -> dict:
    """Merge/overwrite a single country block inside a curated_payload JSON tree.

    For each section (wiki / policy / templates / faq), replace the country
    sub-block with the freshly built one. `verified_at` lives at the country
    level (every section shares the same verification date for the same
    country).
    """
    new_country = COUNTRY_BLOCKS_EN[cc] if lang == "en" else COUNTRY_BLOCKS_LOCALES[lang][cc]
    verified_at = new_country.get("verified_at", "2026-07-03")
    for section_key, section_data in new_country.items():
        if section_key == "verified_at":
            continue
        sec_obj = existing_root.get(section_key, {"title": "", "intro": ""})
        sec_obj[cc] = {
            "title": section_data["title"],
            "intro": section_data["intro"],
            "items": section_data["items"],
            "_verified_at": verified_at,
        }
        existing_root[section_key] = sec_obj
    return existing_root


def update_payload(lang: str) -> None:
    """Read the per-lang curated_payload JSON, merge in the 3 new countries,
    write back. Idempotent.
    """
    payload_file = PAYLOADS_DIR / f"resources_curated.{lang}.json"
    if not payload_file.exists():
        print(f"  [{lang}] payload file missing — skipping")
        return

    data = json.loads(payload_file.read_text(encoding="utf-8"))

    for cc in ("gb", "au", "schengen"):
        _merge_country_block(data, lang, cc)

    payload_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  [{lang}] merged gb / au / schengen")


if __name__ == "__main__":
    for lang in LANGS:
        update_payload(lang)
    print("done.")
