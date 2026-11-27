# Frontend activity log: ExpenseFlow (team18, Track A)

**Date:** 27 Nov 2026 · **Owner:** Abhayraj (frontend), working with Claude Code (Claude Opus 5.5)
**Branch:** `frontend` → PRs into protected `main` (#1, #5, #10, #13, #15, #19)

This log lists what was built, in order, with the commits that delivered each step. Times are commit times (IST).

## Summary

| | |
|---|---|
| Screens shipped | 13 routes covering 22 design screens (L1, E2, E3–E5, N1–N4, M2–M4, A1, F0, F2–F5) |
| Must-haves covered in the UI | 1 claim capture · 2 policy results · 3 approval chain, send back, delegation · 4 auditor queue + bulk approve · 5 payout + CSV · 6 dashboard · 7 audit trail |
| Tests | 42 frontend unit/integration · 10 Playwright E2E · backend suite green (173 at last merge) |
| Backend bugs found and fixed | 2 (null/blank text → 500; `@` rejected in usernames), plus login by email |
| Team deliverables | Architecture, 3 ADRs, test plan, 65 test cases, defect log, runbook, RCA template, LLD, process and prompts, Claude journal, reusable skill |

## Timeline

### 1. Project setup (14:33 – 15:33)
- Scaffolded `frontend/`: React 19, Vite, TypeScript, Tailwind v4, shadcn/ui on Base UI with Phosphor icons, Zod, TanStack Query, oxlint, Prettier, Vitest, Playwright, pnpm. `f62c742`
- Added TanStack Router (file routes), MSW mocks, Faker, the shadcn and agent-browser MCP servers, and five agent skills (shadcn, web design guidelines, React best practices, shadcn component discovery and review). `94ff1f2`
- **Correction:** the shadcn CLI rewrote the `cn` helper import to an unrelated npm package. Replaced it with `clsx` + `tailwind-merge`; this came up again on every `shadcn add`.

### 2. Backend health check and first login (15:33 – 16:59)
- Started `db` + `api` in Docker, ran the migrations, hit `/health` and `/health/ready` (including the 503 path with the DB stopped).
- Inserted a dummy user with SQL (password hashed by the app's own `hash_password`) and checked login and `/auth/me` against the API.
- **Login page (L1)** built to the Figma spec after a plan and three decisions from Abhayraj: work email sent as `username`, token in localStorage, react-hook-form. `d46431c`, `e34739c`
- Fixed Prettier failures caused by CRLF line endings (`.gitattributes`), and moved E2E to its own port so it never reuses the real-backend dev server.

### 3. Role screens: shared foundation, then 4 parallel agents (17:10 – 17:39)
- **Foundation (lead):** typed API modules for every endpoint (Zod from `openapi.json`), app shell with a sidebar per role, status chips, ₹ and date formatters, all shadcn components installed once, a placeholder route per screen, MSW handlers split per feature. `ae20379`, `10b3f92`
- Testing the real backend showed submit needs a receipt number and file above ₹500; the API client now exposes per-field 422 errors. `4f2f5a7`
- Agents, each owning its own files:
  - Claim detail with side-by-side receipt viewer, approval timeline, audit, comments and approve / send back / reject. `f940386`
  - Approvals queue with filters and bulk approve, plus out-of-office delegation. `31011c2`
  - Policy rules and People (the finance head creates users; there is no signup). `5632588`
  - My claims list and mobile-friendly claim form. `e730f2f`
- Fixed flaky first-render tests and stubbed `window.matchMedia` for the toast container. `eab4ef5`

### 4. Backend bugs found by testing the real backend (17:48)
- **D1:** `POST /claims` returned **500** for null or blank optional text (a Pydantic length check ran on `None`). Fixed with 16 tests that fail before and pass after. `bde6b80`
- **D2:** usernames rejected `@`, so the finance head couldn't create email-login users. Fixed, contract regenerated. `749a388` (PR #15)

### 5. Remaining must-haves: 5 parallel agents (18:09 – 18:22)
- New statuses `DUPLICATE` and `PAID`, `local` category, payout fields, nav. `1706929`
- Web app added to Docker Compose (nginx :8080, `/api` proxy) and a CI frontend job with `pnpm audit`. `64f1cd4`
- Login accepts username **or** email, so seeded users can sign in. `309788f`
- **Payout batches (F2):** preview, create batch → Paid, download CSV. `8d89f0a`
- **Seven more E2E flows**, 10 in total, including two at 375px phone width. `1f54b85`

### 6. New backend APIs from `main` (18:33 – 18:42)
- Merged `main`; caught a contract change: audit events now have nullable `actor_id` / `entity_id`, which would have broken claim detail. Fixed. `010c53c`
- **Dashboard** driven by `GET /dashboard/summary`: KPIs compared with last month, spend by month, category and **department**, needs-action items, recent events. `8b728cc`
- **Audit trail (F5):** search the whole trail, see each change (old → new), verify the hash chain. `78800d1`

### 7. Team deliverables (18:56)
- `docs/architecture.md` and ADR-001 to ADR-003. `59ad0c9`
- `docs/test-plan.md`, `docs/test-cases.md` and `.csv`, `docs/defect-log.md`. `785abeb`
- `docs/runbook.md`, `docs/rca-template.md`, `docs/lld-frontend.md`. `69c1c11`
- `docs/process-and-prompts.md`, `docs/claude-journal.md`, `.claude/skills/contract-first-screens/`. `c6421a9`

### 8. Merges with `main`
- Resolved conflicts where `main` had independently landed login-by-email (#20) and the web image (#21): kept `main`'s versions.
- Resolved the CI workflow conflict with #22: kept both the PostgreSQL `startup` job and the `web` job.
- PR #19 merged the screens and deliverables; the branch was then brought level with `main` again (0 behind) for the next PR.

## How the work was done
1. **Plan first.** Read the spec, API and design, then propose a plan and ask for the decisions only a person can make.
2. **Contract first.** `docs/openapi.json` wins on conflicts; screens were built only where an API existed.
3. **Shared foundation, then parallel agents** that each own separate files, with no shared edits, installs or git.
4. **Verify every hand-back:** unit tests, type check, lint, format, build, E2E, then a scripted browser run against the **real backend**.
5. **Small conventional commits**, committed as each piece finished.

## Not built (no API yet)
- 10% sample-audit flag (must-have 4 detail).
- Employee and line-manager dashboards (E1, M1); the summary endpoint serves finance roles only.
- Duplicate review (A2) and auditor history (A3).

## Demo logins (seeded, email or username)
`finance.head@expenseflow.example` / `admin` · `line.manager@expenseflow.example` / `manager` · `finance.auditor@expenseflow.example` / `auditor` · `employee@expenseflow.example` / `employee`
