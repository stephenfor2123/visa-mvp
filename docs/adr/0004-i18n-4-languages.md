# ADR-0004: Internationalization — `vue-i18n` v9, four shipping locales

- **Status**: Accepted
- **Date**: 2026-06-15
- **Scope**: Web SPA, mini-program (subset), shared locale files

## Context

The visa product is being launched first in four markets: Simplified Chinese mainland (primary), Indonesia, Vietnam, and English-speaking expatriates / international applicants in the same regions. The product team needs:

- A single source of truth for user-facing strings, used by both the web SPA and the mini-program.
- Locale switching at runtime (no rebuild) — users can pick a language from the profile page.
- Pluralization and interpolation support (`{{count}} 天` vs `{{count}} day(s)`).
- A path for adding more locales (Japanese, Korean, Thai) without code changes.

### Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| **`vue-i18n` v9 + per-locale JSON files** | Idiomatic Vue, lazy-loadable locale chunks, pluralization rules, message-format compiler, `Intl.NumberFormat` integration. | Two integration steps (Vue plugin + runtime switch). |
| `i18next` + `react-i18next`-style adapter | Mature, broad ecosystem. | Vue adapter is community-maintained; weaker Composition API ergonomics. |
| Hand-rolled key/lookup table | Zero dependencies. | No plural rules, no lazy chunks, no fallback logic — re-implementing wheels we already get free. |

## Decision

We adopt **`vue-i18n@^9` with per-locale JSON files** under `frontend/shared/i18n/`.

- The four shipping locales for V2 are **`zh-CN`**, **`en`**, **`id`** (Indonesian), **`vi`** (Vietnamese). These map to the four files `zh-CN.json`, `en.json`, `id.json`, `vi.json`.
- Locale files are **shared** between the web SPA and the mini-program (mini-program wraps them in its own loader). One set of translations, two delivery channels.
- Locale switch is reactive: changing the Pinia `useI18nStore().locale` ref re-renders all `<el-*>` and `<i18n-t>` consumers without a page reload.
- Missing-key behavior is configured as `silentTranslationWarn: false` in dev (loud) and `silentFallbackWarn: true` in production — failures surface in CI but don't leak to users.
- Compliance-sensitive strings (refund policy, KYC consent, data processing notice) are loaded from a **separate legal namespace** and are flagged with a `__legal_review_pending__` marker until cleared by Legal — see `docs/LEGAL_REVIEW_NOTES.md`.
- The original ADR brief mentioned `ja` and `ko` as additional locales; those remain **post-V2 stretch goals** (see ADR-0004-NOTE-2026-06-15 below) and are not shipped in V2.

### ADR-0004-NOTE-2026-06-15 — locale set variance vs original brief

The original tasking referenced `zh-CN/en/ja/ko`, but market analysis and signed-off translation vendor coverage pin the V2 launch set to `zh-CN/en/id/vi`. Adding `ja`/`ko` is on the post-V2 backlog. **This ADR reflects the actually-shipping set.**

## Consequences

### Positive

- One source of truth across web + mini-program — translators update one file, both clients pick it up.
- `vue-i18n` v9 supports `Intl.NumberFormat` and `Intl.DateTimeFormat` out of the box; currency and date formatting follow the active locale.
- Lazy locale chunk loading keeps the initial web bundle small — `zh-CN` ships by default; the other three are code-split behind `() => import('@shared/i18n/en.json')`.
- Missing keys are loud in dev — easy to catch typos in CI.

### Negative / Trade-offs

- We must keep four files in sync. **Mitigation**: a small CI script (`scripts/i18n-key-audit.py`) diffs the key sets across locales and fails the build if any locale is missing a key present in `zh-CN` (the source-of-truth).
- Pluralization rules differ between `id`/`vi` (no plural form) and `zh-CN`/`en` (singular/plural). We use the `Intl.PluralRules` API which `vue-i18n` wires up automatically; no manual rules needed.
- Adding a new locale still requires translator turnaround + a new locale file + a new lazy chunk. This is the right shape — adding `ja`/`ko` later is mechanical.

### Reversibility

Low. The locale shape (nested JSON, `vue-i18n` message format) is a property of every translation file. Migrating to `i18next` would require a key-by-key re-export, not a structural rewrite.

## References

- `frontend/shared/i18n/zh-CN.json`, `en.json`, `id.json`, `vi.json` — shipping locale files.
- `frontend/web/src/i18n/index.ts` — `vue-i18n` plugin setup, locale loader, lazy-chunks.
- `frontend/web/src/stores/i18n.ts` — Pinia store driving runtime locale switching.
- `docs/LEGAL_REVIEW_NOTES.md` — Legal-review marker protocol for compliance text.