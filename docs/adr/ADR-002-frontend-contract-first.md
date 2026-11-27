# ADR-002: Build the frontend contract-first from openapi.json

- **Status:** Accepted
- **Date:** 2026-11-27
- **Deciders:** Abhayraj (frontend), Himanshu (backend lead), Rahul (UI/UX, QA)
- **Code:** `frontend/src/lib/api.ts`, `frontend/src/features/*/api.ts`, `frontend/src/routes`, `frontend/src/mocks`, `frontend/nginx.conf`

## Context

The backend and frontend were built at the same time by different people. Several screens had a design (Figma / `docs/design`) but no endpoint yet. Markdown API docs and `docs/openapi.json` sometimes disagreed. The frontend was built with parallel Claude Code sub-agents, each owning its own route and feature folder, so they needed a shared, typed API layer and shared test data before fanning out. The app has four roles that must see different screens.

## Decision

1. **`docs/openapi.json` is the source of truth.** It wins over the markdown docs on conflict. Every endpoint was listed and mapped to a design screen first; only screens whose API exists were built (E1/M1/A0 role dashboards, A2 duplicate review, A3 auditor history and the 10% sample flag were skipped).
2. **Hand-written Zod schemas + TanStack Query.** One `apiRequest()` in `src/lib/api.ts` handles the `/api/v1` prefix, bearer token, error envelope (`ApiError` with `code`, `status`, per-field `fields`) and validates every response with a Zod schema. Each feature has an `api.ts` with schemas that mirror the OpenAPI components and Query hooks.
3. **File-based routes (TanStack Router)** with a pathless `_authed` layout whose `beforeLoad` loads the session and redirects to `/login` when there is none. Role-specific sidebars in `AppShell`; per-screen role checks only hide UI, the API enforces permissions.
4. **MSW mocks shared by every test layer.** One handler file per feature in `src/mocks/handlers`, seeded Faker data. Vitest uses them through `mocks/node.ts`, Playwright E2E runs the dev server with `VITE_ENABLE_MOCKS=true` on its own port (5174), and local dev uses them only when that flag is set.
5. **Same-origin in every environment.** Vite proxies `/api` to `:8000` in dev; nginx in the `web` container serves `dist/` and proxies `/api/` and `/health` to `api:8000`. The browser never makes a cross-origin call, so the API needs no CORS setup.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Generated OpenAPI client (e.g. openapi-typescript / orval) | Saves typing, but the contract was changing daily on parallel branches and regenerating meant churn in every agent's files. Generated types also do not validate at runtime; Zod catches a backend that returns something different from the spec. Worth revisiting once the contract settles. |
| Redux Toolkit / RTK Query | More boilerplate for an app whose state is almost all server state; TanStack Query covers caching, invalidation and loading states. |
| Direct `fetch` in components | No shared error handling, token handling or response validation; each agent would have done it differently. |
| Cypress for E2E | Playwright runs headless Chromium in CI with less setup, supports phone viewports (375px cases) and the same MSW-backed dev server. |

## Consequences

- **Contract drift is caught at the boundary, not silently.** When the backend changed `AuditEventOut` (nullable `actor_id` / `entity_id` and new fields), the claim detail activity schema would have failed to parse; the schema was updated (defect D4). The cost: schemas are maintained by hand and can fall behind the spec.
- **Mocks can hide backend failures.** All agent tests passed against MSW while the real `POST /claims` returned 500 for null optional text (defect D1, fixed in PR #15). Mitigation: before every commit the lead ran a scripted real-browser check against the real backend (login, draft, receipt upload, submit, approvals, policy rules, dashboard, audit verify), in addition to Vitest, `tsc -b`, oxlint, Prettier, the build and Playwright.
- Parallel agents could work without conflicts because each owned its feature folder, route files, mock handler file and test file.
- Some designed screens are missing until their APIs exist.
- No CORS configuration to get wrong; the trade-off is that the SPA must always be served behind a proxy to the API.
