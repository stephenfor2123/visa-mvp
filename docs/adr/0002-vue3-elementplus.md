# ADR-0002: Frontend framework — Vue 3 + Element Plus

- **Status**: Accepted
- **Date**: 2026-06-15
- **Scope**: Web SPA (`frontend/web/`)

## Context

The visa MVP web client targets desktop and mobile browsers, ships a user-facing app **and** an admin console. Constraints:

- Small team (1–2 frontend engineers) — framework ergonomics and on-ramp matter.
- Heavy form density (multi-step visa application, materials upload, KYC, MFA, admin configuration).
- Must coexist with three language sites via `vue-i18n` (see ADR-0004).
- Admin pages need a rich component library (data tables, paginated lists, modals, drawers, tabs, date pickers) — building from scratch is not viable.

### Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Vue 3 + Element Plus | Composition API + `<script setup>`; Element Plus covers ~95 % of admin needs; excellent `vue-i18n` integration; mature `vite-plugin-vue`; smaller bundle than Ant Design Vue for equivalent components. | Element Plus design language is opinionated (Material-leaning) — we accept this. |
| React 18 + Ant Design | Larger ecosystem; Ant Design table is best-in-class. | Team has zero React experience; HOC vs hooks learning curve; `umi` vs `vite` adds tooling decisions. |
| Vue 3 + Naive UI / Arco | Lighter, more modern look. | Component coverage of complex admin widgets (cascader, transfer, virtual-select) is thinner; would require more custom work. |

## Decision

We adopt **Vue 3.4 + `<script setup>` + Vite + Element Plus 2.x**.

- **Composition API** is mandatory for new components. The Options API is permitted only in legacy views being refactored.
- **Element Plus** is the default component library for both user-facing and admin views. Custom design tokens are added in `frontend/web/src/styles/element-plus-theme.scss` for brand color overrides.
- **State**: Pinia stores (`frontend/web/src/stores/*`) for cross-page state (auth, order draft). Component-local state stays in `ref` / `reactive`.
- **Routing**: `vue-router` 4 with lazy-loaded routes; one router file (`frontend/web/src/router/index.js`).
- **Build**: `vite` 5; production bundle target ~`es2018`. Dev server HMR via `vite-plugin-vue`.
- **Testing**: Vitest + `@vue/test-utils` for unit, Playwright for E2E. (Vitest config: `frontend/web/vitest.config.ts`.)
- **Admin views** live under `frontend/web/src/views/admin/` and reuse the same Element Plus components — no separate admin framework.

## Consequences

### Positive

- One framework for user + admin; shared design tokens, shared `axios` client, shared `vue-i18n` instance.
- `<script setup>` SFCs are terse and readable; TypeScript inference works well with Vue 3.4's `defineProps<T>()` macro.
- Element Plus tree-shakes well — only imported components ship in the bundle (the bundle-size budget is documented in the Vite config).
- Vite dev server starts in <1 s on M-series Mac and Linux runners, well below the previous Webpack-equivalent baseline.

### Negative / Trade-offs

- Element Plus version upgrades occasionally break theme variable names — we pin to `^2.7` and run a smoke test (`frontend/web/tests/smoke/`) on every upgrade.
- Vue 3 ecosystem is mature but smaller than React's; some niche components (e.g. virtualized tree with drag-and-drop) we build ourselves.
- Locked into a Material-leaning design language; if a future brand refresh demands a more bespoke look, the cost is non-trivial (but still smaller than a React migration).

### Reversibility

Medium. The Pinia stores, `axios` clients, `vue-i18n` locale files, and Element Plus usage are framework-coupled but pattern-portable to React (with effort). Components themselves are pure Vue 3 SFCs.

## References

- `frontend/web/package.json` — `vue@^3.4`, `element-plus@^2.7`, `@vueuse/core`, `pinia`, `vue-i18n@^9`, `axios`.
- `frontend/web/src/views/Home.vue` — user-facing Composition API example.
- `frontend/web/src/views/admin/AdminDashboard.vue` — admin Element Plus usage example.
- `frontend/web/src/router/index.js` — vue-router 4 setup.