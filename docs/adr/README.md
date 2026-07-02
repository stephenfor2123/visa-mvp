# Architecture Decision Records (ADR)

This directory holds the project's Architecture Decision Records. An ADR captures a
significant architectural choice, the context that forced it, the decision itself,
and the consequences we accepted by making it.

## How to read

- Files are named `NNNN-short-slug.md`, where `NNNN` is a zero-padded sequence number.
- Each ADR follows the **MADR**-style template (lightweight variant):
  1. **Status** — `Proposed` | `Accepted` | `Superseded by NNNN` | `Deprecated`.
  2. **Date** — `YYYY-MM-DD`.
  3. **Context** — what problem we're solving and what options were considered.
  4. **Decision** — what we chose.
  5. **Consequences** — positive, negative, reversibility.
- An ADR is immutable once `Accepted`. To change a decision, write a new ADR that
  supersedes it (e.g. `0006-…` with status `Superseded by 0006` on the old one, and
  `Supersedes 0001` on the new one).

## Numbering rules

- **Monotonically increasing** four-digit zero-padded sequence: `0001`, `0002`, …
- **Numbers are not reused.** If an ADR is rejected or withdrawn, its number is
  retired — do not reuse it for an unrelated topic.
- **Always reserve the next number** when opening a PR, even before the ADR is
  written — this avoids two contributors picking the same slot.
- **Superseding** an ADR does **not** free its number; the new ADR gets a new number
  and references the old one in its `Supersedes` field.
- **Out-of-band IDs** (`0001-NOTE-2026-06-15`) are permitted inside an ADR to mark
  post-acceptance corrections; they do not consume a number.

## Workflow

1. Copy `template.md` (if present) or use any recent ADR as a starting point.
2. Set `Status: Proposed` and assign the next number.
3. Open a PR titled `ADR-NNNN: <slug>`. Discuss in the PR.
4. On merge, change `Status` to `Accepted` (or `Superseded` / `Deprecated`).
5. Update `docs/adr/INDEX.md` (this file's neighbour, if present) with the new
   entry — title, status, one-line summary.

## Index (initial set, 2026-06-15)

| # | Title | Status | Date |
| --- | --- | --- | --- |
| 0001 | Backend framework — FastAPI (not Django) | Accepted | 2026-06-15 |
| 0002 | Frontend framework — Vue 3 + Element Plus | Accepted | 2026-06-15 |
| 0003 | Payment integration — MockPayment for V2, Stripe for V2.1 | Accepted | 2026-06-15 |
| 0004 | i18n — vue-i18n v9, four shipping locales (zh-CN/en/id/vi) | Accepted | 2026-06-15 |
| 0005 | Error handling — BizException + ErrorCode enum | Accepted | 2026-06-15 |
| 0006 | LLM material diagnosis (pre-payment) — design only, no provider selected | Proposed | 2026-07-01 |

## Notes

- These five ADRs cover the **initial** architectural baseline. They are deliberately
  short — each focuses on the decision and its trade-offs, not implementation details.
- Implementation details belong in `docs/API.md`, `docs/LEGAL_REVIEW_NOTES.md`, and
  inline code comments.
- ADRs are written for **future contributors**, not for the people who made the call.
  Bias toward explaining _why_, not _who_.