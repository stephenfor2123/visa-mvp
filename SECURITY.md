# Security Policy

> **TL;DR** — Found a vulnerability? Email `security@example.com` (PGP optional, see below).
> We respond within **24h for critical**, **7 days for high**, **30 days for medium**.

---

## 1. Supported Versions

We actively maintain the following release lines of the Visa MVP platform
(backend FastAPI service, web frontend, iOS / Flutter client, WeChat mini-program
and supporting tooling under this repository):

| Version  | Status            | Security patches         | End-of-life           |
|----------|-------------------|--------------------------|-----------------------|
| **v2.x** | ✅ Active         | Yes — current            | TBD                   |
| v1.x     | ⚠️ Critical-only  | Critical / High only     | 2026-12-31 (planned)  |
| v0.x     | ❌ End-of-life    | No                       | 2025-06-30 (reached)  |
| pre-v0   | ❌ Not supported  | No                       | n/a                   |

Any release older than the lines above is **out of scope** for new security
advisories. Please upgrade to a supported line before reporting a vulnerability
that may already be fixed upstream — duplicate reports on EOL versions will be
acknowledged but not patched.

> **Source of truth** — the active development branch (`main`) and any tag
> matching `v2.*` (semver). The latest release is tracked in
> [`docs/API.md`](docs/API.md) and the project `CHANGELOG`.

---

## 2. Reporting a Vulnerability

We accept vulnerability reports through **two** channels. Please use **only one**
of them per report — choose whichever you are more comfortable with.

### 2.1 Private Email (preferred)

📧 **security@example.com**

- Subject line prefix: `[SECURITY]`
- Please include:
  1. Component / module affected (backend, web, iOS, mini-program, …)
  2. Version / commit hash / tag
  3. Reproduction steps or PoC (screenshots, cURL, scripts — attachments OK)
  4. Impact assessment (your view of severity; we may re-rate)
  5. Your name / handle if you want to be credited in the Acknowledgements
     section below
- We **do not** require PGP for the initial report. If we need to exchange
  large or sensitive artefacts we will publish a PGP key in our reply.

> Replace `security@example.com` with the address your organisation has
> provisioned before publishing this file. Until that mailbox exists, please
> use the GitHub Advisories channel below.

### 2.2 GitHub Security Advisories

Open a private security advisory directly on the repository:

1. Go to the repository page on GitHub.
2. Click **Security** → **Report a vulnerability** → **Open a new advisory**.
3. Fill in the template; submit privately.

GitHub will notify the maintainer team privately; we triage from there.
This channel is preferred over public Issues / Discussions.

### 2.3 What **not** to do

- ❌ Do **not** open a public GitHub Issue, Discussion or PR for a
  not-yet-patched vulnerability.
- ❌ Do **not** post reproduction details on social media, blogs, or
  mailing lists until coordinated disclosure (see §5) is complete.
- ❌ Do **not** run automated scanners that generate high traffic against
  our staging / production endpoints without prior notice.

### 2.4 Out-of-scope reports

The following are **not** considered security vulnerabilities for this project
and will be closed without triage SLA:

- Reports against a version listed as End-of-life (see §1).
- Reports requiring physical access to a victim's device.
- Reports of self-XSS or content-injection on attacker-controlled input.
- Rate-limiting findings on unauthenticated public marketing pages.
- Missing security headers on purely static demo / preview HTML.
- "Best practice" findings with no demonstrable security impact (e.g.
  `httponly` on a cookie that stores no credential).
- Reports about dependencies that are already patched in the supported
  versions listed in §1 — please verify and then file an Issue, not an
  advisory.

---

## 3. Severity Classification

We adopt a four-tier scale aligned with CVSS 3.1, with operational impact
overrides. Final severity is set by the maintainer team, not by the reporter.

| Severity  | Examples                                                                                  | First-response SLA | Patch target |
|-----------|-------------------------------------------------------------------------------------------|--------------------|--------------|
| **Critical** | Remote unauthenticated RCE; auth bypass exposing all user data; payment bypass (e.g. Stripe webhook signature forgery that allows free paid services). | **24 hours**     | ≤ 7 days     |
| **High**     | Authenticated RCE; SQLi / SSRF against internal services; arbitrary file read/write under app user; PII leak of >1k users. | **7 days**       | ≤ 30 days    |
| **Medium**   | Stored XSS with non-trivial impact; CSRF on state-changing money endpoints; privilege escalation user→admin. | **30 days**      | ≤ 90 days    |
| **Low**      | Reflected XSS on internal-only routes; information disclosure of non-sensitive internals; missing rate limiting on low-value endpoints. | **90 days**      | Next minor   |

> The SLA clock starts from the **first** acknowledgement (see §4). If we
> cannot reproduce within the first-response window we will say so and re-aim
> the clock from confirmation.

---

## 4. Response Workflow

Our coordinated response follows five steps:

1. **Acknowledge** — Within the SLA above, we send a reply confirming receipt,
   the channel used, and the initial severity rating.
2. **Triage & reproduce** — A maintainer builds a minimal reproducer, assigns
   a CVE-style identifier internally (`VISA-MVP-YYYY-NNN`), and confirms
   severity. We may request additional information or a private call.
3. **Develop fix** — A patch is developed on a private branch. Tests are
   added (or updated) to cover the regression. A security regression test
   is required for `Critical` and `High`.
4. **Pre-release coordination** — For `Critical` and `High`, we share the
   fix with the reporter at least **72 hours** before public release so they
   can verify the patch and prepare their own advisory.
5. **Public release** — We publish the fix in a tagged release, push the
   `SECURITY.md` Acknowledgements entry, and publish a GHSA if the report
   came in via GitHub Advisories. See §5 for timing.

We may reject or close reports that:

- Cannot be reproduced after reasonable good-faith effort.
- Are duplicates of an advisory already acknowledged in §7.
- Concern unsupported versions (§1).

---

## 5. Coordinated Disclosure Policy

We follow a **90-day** coordinated disclosure timeline, aligned with industry
norms (Google Project Zero, CERT/CC).

| Day | Action                                                                                  |
|-----|-----------------------------------------------------------------------------------------|
| 0   | Report received.                                                                         |
| ≤1  | Acknowledgement + initial severity (SLA per §3).                                         |
| ≤7  | Internal triage complete; reproduction confirmed; fix branch opened.                    |
| ≤90 | Public release of the fix + advisory, **regardless of whether a fix is ready**.         |
| >90 | If we cannot ship a fix in 90 days we ask the reporter for an extension (up to 30 days). |

After the public release we publish:

- A short advisory summary in [`CHANGELOG.md`](CHANGELOG.md) and the GitHub
  release notes.
- A GHSA on GitHub Security Advisories (if the report came in via that
  channel, or if we open it ourselves on the reporter's behalf with consent).
- An entry in §7 Acknowledgements below (unless the reporter opts out).

---

## 6. Safe-Harbour & Legal

We will **not** pursue legal action against, request law-enforcement
investigation of, or restrict your account for, activity that:

- Is performed in good faith to test the vulnerability.
- Avoids privacy violations, data destruction, and service disruption.
- Stops as soon as a vulnerability is confirmed and stops short of any
  exploit that could harm users (no exfiltration of real user data, no
  modification of production state, no spam or phishing).
- Reports the issue promptly and follows §5 disclosure timing.

This safe-harbour applies to the current latest release and to the supported
lines in §1 only. It does not authorise testing against production data of
other tenants, third-party services we integrate with (e.g. Stripe, Twilio,
Aliyun SMS), or any infrastructure not owned by this project.

---

## 7. Acknowledgements

We thank the following reporters for responsibly disclosed vulnerabilities
(sorted by report date, newest first). Reporter names appear here only with
their consent.

| Date       | Identifier          | Severity | Component         | Reporter          |
|------------|---------------------|----------|-------------------|-------------------|
| _no entries yet_ |               |          |                   |                   |

> To add yourself: reply to the acknowledgement email or include your
> preferred name/handle in the original report. You may opt out at any time.

---

## 8. Known Issues

Issues we have already publicly disclosed and **do not** need a new report
for. Please check this list before filing — duplicates will be redirected
here.

- _No published known-security issues at this time._

When a known issue is published, it will appear here with: identifier,
severity, affected versions, fix version, and a link to the GHSA / advisory.

Planned-disclosure channel for newly fixed issues: `CHANGELOG.md` under the
`### Security` heading + GitHub Security Advisories + the Acknowledgements
table above.

---

## 9. Project-Specific Threat Model Notes

These are areas where the project has historically seen (or expects) reports;
they are **in scope**, but we list them so reporters can focus their effort.

- **Authentication & sessions** — JWT issuance, refresh, revocation; SMS
  one-time-passcode delivery via the `SMS_CHANNEL` adapter; rate limiting on
  `/auth/*` endpoints; Google OAuth (`/auth/google` — Google id_token
  signature verification against `GOOGLE_CLIENT_ID`, sub-based auto-registration,
  email linking to existing password accounts, disabled-account handling).
- **Payment integration** — Stripe webhook signature verification, idempotency
  keys, refund and dispute flows. See
  [`docs/stripe-credentials-setup.md`](docs/stripe-credentials-setup.md).
- **Materials upload** — file type / magic-byte validation, size limits,
  pre-signed URL expiry (`expires_in=300`), virus-scanning hooks (planned).
- **OCR / RPA pipeline** — sandboxed execution of the OCR worker, captcha
  solver isolation, outbound network restrictions.
- **i18n / localisation** — translation file integrity, locale negotiation,
  Unicode handling on user-visible strings.
- **Affiliate / partner attribution** — `aff_code` validation, double-count
  prevention, webhook idempotency. See the W9-W11 worklog entries in
  [`C_WORKLOG.md`](C_WORKLOG.md).
- **Admin / back-office** — RBAC enforcement, audit log integrity, IP
  allow-listing for the admin UI.

---

## 10. Contact Summary

| Channel                              | Use for                                          |
|--------------------------------------|--------------------------------------------------|
| `security@example.com`               | Private disclosure (default).                    |
| GitHub **Security → Advisories**     | Same — alternative channel.                      |
| GitHub **Issues**                    | Only for already-disclosed / fixed issues.       |
| General project issues / PRs         | **Do not** use for security reports.             |

---

_Last updated: 2026-06-15. This file is normative — when in doubt, the email
acknowledgement from a maintainer overrides any text here._
