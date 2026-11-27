# ExpenseFlow – defect log

Team18, W2 Track A. Status as of 27 Nov 2026. Related: [test-plan.md](test-plan.md), [test-cases.md](test-cases.md).

Severity: **High** = blocks a must-have flow or loses data; **Medium** = breaks a screen, a test suite or an
environment until fixed; **Low** = flaky or self-recovering.

| ID | Title | Severity | Area | Found by / how | Steps to reproduce | Root cause | Fix | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| D1 | `POST`/`PUT /claims` returns 500 for null or blank optional text | High | Backend (validation) | Lead's scripted real-backend browser run of the claim form; agent tests had passed against MSW mocks only | Save a draft with `vendor`, `description`, `city`, `receipt_number` or `title` set to `null` or `""` | `Field(max_length=…)` on `str \| None`: pydantic applied the length constraint to `None` → `TypeError` → 500 | Moved the constraint onto `str` inside the union (`StringConstraints`); null/blank become `None`, too-long text is a 422. 16 new tests failed before, pass after. Frontend also omits nulls. | Fixed | `bde6b80` fix: return 422, not 500, for null or blank optional claim text (PR #15); `test_schema_validation.py::test_saving_a_draft_with_null_and_blank_optional_fields_returns_201` |
| D2 | Users with an email as username cannot be created | High | Backend (users) | Integration of People (F4) with the real API: the add-person form sends the work email as username | As finance head, `POST /users` with username `a.person@expenseflow.example` | `UserCreate.username` pattern did not allow `@` | Pattern now allows `@` and `+`; OpenAPI regenerated | Fixed | `749a388` fix: allow work-email usernames when creating users (PR #15); `test_username_may_be_a_work_email`, `test_user_whose_username_is_their_work_email_can_be_added_and_log_in` |
| D3 | Seeded users cannot log in from the UI | High | Integration (auth) | Real-backend login run | Log in with `employee@expenseflow.example` / `employee` | UI field is "Work email" (team decision), but `/auth/login` matched `username` only | `/auth/login` matches username **or** email, case-insensitive; 3 tests added | Fixed | `309788f` feat: let users log in with their work email or username; `test_login_with_work_email_returns_token`, `..._ignores_case`, `..._and_wrong_password_is_refused` |
| D4 | Claim detail activity fails to parse new audit events | Medium | Frontend (schemas) | Reviewing the merged backend audit-trail change against frontend Zod schemas | Open a claim whose audit events have `actor_id`/`entity_id` = null or new fields | Backend `AuditEventOut` changed (nullable ids, new fields); frontend Zod schema was stricter | Updated schema to the new contract | Fixed | `010c53c` fix: accept the new audit event shape and add audit-trail and auditor dashboard nav |
| D5 | Every full-app render crashes in Vitest | Medium | Frontend tests | Running Vitest after toasts were mounted in the root layout | Render any route in a test after `10b3f92` | `sonner` toaster calls `window.matchMedia`, which jsdom does not provide | `matchMedia` stub in `frontend/src/test/setup.ts` | Fixed | `f940386` (adds the stub to `src/test/setup.ts`) |
| D6 | First route render per test file times out under parallel load | Low | Frontend tests | Flaky failures in full `pnpm test:run` | Run the whole suite on a busy machine | First render (lazy route + query) can exceed Testing Library's 1 s default | `asyncUtilTimeout` raised to 3000 ms | Fixed | `eab4ef5` test: raise async query timeout to stop first-render flakes |
| D7 | One Playwright case times out on a cold dev-server start | Low | E2E | Local E2E runs | Run `pnpm test:e2e` with an empty Vite cache | Vite dependency pre-bundling reloads the page during the first test | Passes on rerun; CI config retries twice (`retries: process.env.CI ? 2 : 0`) | Mitigated | `frontend/playwright.config.ts` |
| D8 | API crashes: "column users.department does not exist" | Medium | Environment (DB) | Starting the API after pulling `main` | Pull main, start API against an old local database | Local DB not migrated to 0004/0005 (and later 0006) | `alembic upgrade head` (command in test-plan section 7) | Fixed (process) | — |
| D9 | Web proxy returns 502 while the api container restarts | Low | Ops (nginx) | Real-backend run during an api rebuild | Restart `api`, call `/api/...` via :8080 within seconds | nginx has no upstream while api is down | None needed; recovers automatically once api is up | Accepted | — |
| D10 | `tsc -b` fails on a stale `routeTree.gen.ts` | Medium | Frontend (build) | Type-check after adding routes | Add a route file, run `tsc -b` before Vite has run | TanStack Router plugin regenerates the route tree only when Vite/Vitest runs | Run `pnpm test:run` or `pnpm dev`/`build` once before `tsc -b` | Workaround | — |

## Known gaps (not defects)

These are scope limits, not bugs; each is a known, accepted state at submission.

- **No 10% sample-audit flag:** the API has no endpoint or field for it, so no screen was built.
- **Department shows "Unassigned":** seeded users have no department, so dashboard spend-by-department groups
  them under "Unassigned".
- **15 audit rows predate the hash chain:** `/audit-logs/verify` reports them as `unchained_rows`; rows written
  after the chain was added verify as "Chain intact".
- **Payout preview shows `CLM-` claim codes, not `EXP-` references.**
- **Testing gaps** (listed in test-plan section 10): E2E not in CI; no backend tests for payout and audit-log
  endpoints; no automated 413/415 upload test; no cross-employee claim-visibility test; no Python dependency audit.
