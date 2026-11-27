# ExpenseFlow – test plan

Team18, W2 Track A. Status as of 27 Nov 2026. Companion files:
[test-cases.md](test-cases.md) / [test-cases.csv](test-cases.csv) (executed cases) and
[defect-log.md](defect-log.md) (defects D1–D10 and known gaps).

## 1. Current results

| Suite | Tool | Result (latest run) |
|---|---|---|
| Backend unit + API | pytest, FastAPI TestClient, in-memory SQLite | **173 passing**; ruff + black clean |
| OpenAPI contract | pytest (`test_openapi_contract.py`) | Passing (part of the 173) |
| Frontend unit / integration | Vitest + Testing Library + MSW (jsdom) | **42 passing** in 9 files |
| End-to-end | Playwright 1.65, Chromium, MSW mocks | **10 passing** |
| Real-backend smoke | Playwright driven by a Node script against API + PostgreSQL | All checks passed (see test-cases MAN-01..06) |
| Dependency audit | `pnpm audit --prod` | No known vulnerabilities |

Problem-statement expectations and where they are met:

| Expectation | Where |
|---|---|
| Unit tests for every policy rule | `backend/tests/test_claims_policy.py`, `test_policy.py` (test-cases BE-01..BE-14) |
| Tests for approval thresholds and delegation | `backend/tests/test_approval_chain.py` (BE-15..BE-22), `frontend/src/routes/-delegations.test.tsx` |
| 10 written end-to-end cases | `frontend/e2e/app.spec.ts` (3) + `frontend/e2e/flows.spec.ts` (7) (E2E-01..E2E-10) |
| Defect log | [defect-log.md](defect-log.md) |
| Basic security checklist run | Section 9 below |

## 2. Scope

**In scope**

- Login (username or work email), session handling, role-based landing and route guards.
- Employee claims: list, draft, edit, receipt upload, submit (desktop and phone width).
- Policy engine: receipt threshold, meal daily limit, hotel per-night limits (tier-1 / other), local trip
  limit, duplicate detection, finance-head rule editing.
- Approval chain: amount thresholds, self-approval ban, approve / reject / send back, bulk approve,
  out-of-office delegation.
- Finance head: people management, policy rules, payout batches + CSV export, dashboard summary, audit trail
  with hash-chain verification.
- API contract (`docs/openapi.json`) kept in step with the code.

**Out of scope** (no API exists, or not attempted in the build window)

- Role dashboards for employee / manager / auditor (E1, M1, A0), duplicate review (A2), auditor history (A3),
  10% sample-audit flag.
- Load / performance testing, cross-browser E2E (Chromium only), accessibility audit, penetration testing.
- Real bank integration (payout export is a mock bank CSV).

## 3. Risks and how tests address them

| Risk | Mitigation |
|---|---|
| Wrong money decision at a boundary (₹500, ₹25,000, ₹1,00,000, per-night limits) | Boundary tests at exactly-the-limit and limit + 0.01 (BE-02, BE-07, BE-08, BE-15, BE-16) |
| Someone approves their own claim, or a stranger approves | BE-17, BE-22 |
| Delegation loops or delegation to a lower role | BE-21 |
| Frontend built against mocks drifts from the real API | Zod schemas mirror `openapi.json`; contract test; scripted real-backend run before each commit (this found D1, D2, D3) |
| Data leaks across roles | Role tests (BE-25, BE-28, FE-16, E2E-10); claim visibility rule in `backend/app/services/access.py` |
| Flaky tests hide real failures | D6 and D7 fixed / mitigated; CI retries E2E twice |

## 4. Test levels

| Level | What | Where |
|---|---|---|
| Backend unit + API | Each policy rule, thresholds, delegation, auth, users, validation, dashboard; FastAPI TestClient on in-memory SQLite | `backend/tests/*.py` |
| Contract | Generated OpenAPI equals committed `docs/openapi.json`; every operation has a summary and unique id | `backend/tests/test_openapi_contract.py` |
| Frontend integration | Each route rendered with the real router + TanStack Query; network mocked with MSW handlers | `frontend/src/routes/-*.test.tsx` |
| End-to-end | Real browser (Chromium), real built app, MSW mocks; two flows at 375px phone width | `frontend/e2e/*.spec.ts` |
| Real-backend smoke | Scripted Playwright against `docker compose` API + PostgreSQL; screenshots reviewed by the lead | Run locally before commits (script not committed) |
| Dependency check | `pnpm audit --prod --audit-level high` | Local + CI `web` job |

## 5. Environments

- **Backend tests:** Python 3.13, in-memory SQLite, no Docker needed.
- **Frontend tests:** Node + pnpm 11.16, jsdom, MSW.
- **E2E:** Vite dev server on its own port **5174** with `VITE_ENABLE_MOCKS=true` (so it never reuses a
  developer's `pnpm dev` on 5173 that talks to the real API — see correction C3).
- **Real backend:** `docker compose up --build` → PostgreSQL 18 (host :5433), API :8000, web (nginx) :8080,
  Prometheus :9090, Grafana :3000. Migrated with `alembic upgrade head`, seeded with `backend/db/seed.sql`.
- **CI:** `.github/workflows/ci.yml` on pull requests: backend job (lint, pytest with coverage) and `web` job
  (lint, format check, Vitest, build, `pnpm audit`). E2E is not run in CI yet.

## 6. Entry and exit criteria

**Entry:** the endpoint exists in `docs/openapi.json`; a design spec exists for the screen; the change builds.

**Exit (per change, before commit):** all of the following green —
`pytest`, ruff, black (backend); `pnpm lint`, `pnpm format:check`, `pnpm test:run`, `tsc -b`, `pnpm build`,
`pnpm test:e2e` (frontend); plus a real-backend browser check for any screen that calls a new endpoint.
No open High defect. Every must-have has at least one automated test.

## 7. How to run

```bash
# Backend (from backend/)
pytest -q                                  # all 173, incl. contract test
pytest -q tests/test_openapi_contract.py   # contract only
ruff check . && black --check .

# Frontend (from frontend/)
pnpm install
pnpm lint
pnpm format:check
pnpm test:run                              # Vitest, 42 tests
pnpm build
pnpm test:e2e                              # Playwright, 10 tests, starts its own server on :5174
pnpm audit --prod --audit-level high

# Real backend for manual / scripted checks (repo root)
docker compose up --build
docker compose run --rm --no-deps -v "$PWD/backend:/work" -w /work api alembic upgrade head
Get-Content backend\db\seed.sql | docker compose exec -T db psql -U manthan -d manthan   # PowerShell
```

Seeded logins (email or username): `finance.head@expenseflow.example` / `admin`,
`line.manager@…` / `manager`, `finance.auditor@…` / `auditor`, `employee@…` / `employee` (dev-only credentials).

## 8. Traceability: must-haves → tests

Must-haves 5, 6 and 7 are numbered as in our commit messages; 1–4 are our grouping of the remaining card scope.

| # | Must-have | Automated tests | Manual | Status |
|---|---|---|---|---|
| 1 | Employee submits claims with line items and receipts | `test_claims_policy.py` (receipt rules), `test_schema_validation.py`; `-claims.test.tsx` (6); E2E-04, E2E-05, E2E-06 | MAN-02 | Pass |
| 2 | Policy engine: configurable rules flag or block lines | `test_claims_policy.py` (receipt, meal, hotel, local, duplicate), `test_policy.py` (defaults, edit, audit); `-admin.test.tsx`, `-claim-detail.test.tsx`; E2E-09 | MAN-03, MAN-04 | Pass |
| 3 | Multi-level approvals by amount threshold | `test_approval_chain.py` (thresholds 25,000 / 1,00,000, auto-approve at 500, self-approval, 409s, send back); `-approvals.test.tsx`, `-claim-detail.test.tsx`; E2E-07, E2E-08 | MAN-03 | Pass |
| 4 | Delegation, roles and access | `test_approval_chain.py` (6 delegation-refusal tests, on-behalf approval, stranger 404), `test_users.py` (login, 401/403); `-delegations.test.tsx`, `-login.test.tsx`; E2E-01..03, E2E-10 | MAN-01 | Pass |
| 5 | Payout batches with bank CSV export (F2) | `-payouts.test.tsx` (3); `test_dashboard.py::test_ready_for_payout_counts_what_a_payout_batch_could_pay_now` | — | Pass (gap: no backend test file for payout endpoints) |
| 6 | Finance dashboard (`GET /dashboard/summary`) | `test_dashboard.py` (18); `-insights.test.tsx` (2) | MAN-04 | Pass |
| 7 | Append-only audit trail with integrity check (F5) | `test_approval_chain.py` (delegated approval audited), `test_policy.py` (policy change audited); `-audit-trail.test.tsx` (3) | MAN-04 ("Chain intact") | Pass (gap: no backend test for `/audit-logs` and `/audit-logs/verify`) |

## 9. Basic security checklist

Checked = verified in code and, where noted, by a test. Gap = not done or not tested.

| Item | Result | Evidence / note |
|---|---|---|
| Auth on every endpoint | Checked | Every router in `backend/app/api/` depends on the current user except login and health. Tests: no/forged token → 401 (`test_users.py`, `test_policy.py`, `test_dashboard.py`). Not every endpoint has its own 401 test. |
| Role checks return 403 | Checked | `test_non_finance_head_cannot_add_users`, `test_non_finance_head_cannot_change_the_policy`, `test_other_roles_cannot_read_the_dashboard`; UI hides admin screens (FE-16, E2E-10). |
| Employee sees only own claims | Checked (partial test) | One visibility rule in `backend/app/services/access.py`; a claim the caller may not see returns 404. Tested for a stranger manager (BE-22). **Gap:** no test for employee A reading employee B's claim. |
| No secrets committed | Checked | `.env` and `.env.*` gitignored; only `.env.example` files tracked. `admin/admin` is a documented dev-only seed credential. |
| Receipt type and size limits | Checked (code only) | `backend/app/services/attachments.py`: PDF/PNG/JPEG only, magic bytes must match, 5 MB max (`max_upload_bytes`), per-claim attachment cap; nginx `client_max_body_size 6m`. **Gap:** no automated test for 413/415. |
| Open-redirect guard on `?redirect=` | Checked | `safeRedirect` in `frontend/src/features/auth/session.ts` accepts only paths starting with `/` and not `//`; test `ignores an off-site ?redirect=`. |
| XSS | Checked | React escapes output; no `dangerouslySetInnerHTML` in `frontend/src`. |
| Token in localStorage | Gap (accepted trade-off) | Team decision for simplicity. A successful XSS could read the token; mitigated by 8 h token lifetime and no raw-HTML rendering. HttpOnly cookie would be the fix. |
| Passwords | Checked | PBKDF2-SHA256 hashes (`backend/app/security.py`); inactive users refused (`test_inactive_user_login_is_refused`). |
| Dependency audit | Checked (frontend) / Gap (backend) | `pnpm audit --prod`: no known vulnerabilities; runs in CI. No Python dependency audit (e.g. pip-audit) yet. |

## 10. Known testing gaps

- E2E runs locally only, not in CI; E2E uses MSW mocks, so it does not catch API drift (the real-backend
  smoke run covers that and is not automated in CI).
- No backend tests for payout and audit-log endpoints; no 413/415 upload tests; no cross-employee claim
  visibility test.
- Single browser (Chromium). No load tests.
