# Claude usage journal

These entries cover the frontend and integration work on ExpenseFlow (team18) with Claude Code. All of it was done on 2026-11-27 on the `frontend` branch. Entries 2, 4, 5 and 6 are corrections. The process is summarised in [process-and-prompts.md](process-and-prompts.md).

---

## 1. Login page, plan first (2026-11-27)

- **Task:** Build the L1 login screen against `POST /auth/login` and `GET /auth/me`.
- **Prompt (summary):** "Create login page in frontend using this api."
- **What Claude did:** It read the L1 spec, the screenshot, `DESIGN.md` and the API, wrote a 6-step plan, and asked 3 decisions before writing code.
- **Outcome / verification:** The team chose "Work email, sent as username", localStorage for the token, and react-hook-form. Covered by the E2E cases in `app.spec`: a wrong password shows an error and keeps the email, and an employee signs in, survives a reload and signs out.
- **Lesson:** Asking a few targeted questions up front is cheaper than reworking code later.

## 2. Correction: shadcn CLI broke `cn` (2026-11-27)

- **Task:** Scaffold `frontend/` (React 19, Vite, Tailwind v4, shadcn on Base UI, Zod, TanStack Query, oxlint, Prettier, Vitest, Playwright, pnpm).
- **Prompt (summary):** "Create a frontend folder & initialize react + vite with tailwind, shadcn (base ui, phosphor)…"
- **What Claude did:** It ran `shadcn init` and later `shadcn add`.
- **Correction:** The CLI rewrote the `cn` import to point at a bogus npm package called `cn`. This happened on init and again on every `add`, and was caught in review. We replaced it with `clsx` + `tailwind-merge` utils and removed the package each time.
- **Outcome / verification:** `tsc -b` and `vite build` passed after the fix.
- **Lesson:** Read generated imports. From then on, only the lead ran the CLI, once, before any agents started.

## 3. Contract-first fan-out, round 1 (2026-11-27)

- **Task:** Build every screen that has an API.
- **Prompt (summary):** "Read docs/openapi.json & claims-api.md; if conflict the json wins. Use multiple sub agents… build only whose api is available."
- **What Claude did:** It mapped endpoints to screens and built the shared foundation: typed API modules, AppShell with a per-role sidebar, `StatusChip`, en-IN formatters, all shadcn components, placeholder routes and per-feature MSW files (`ae20379`). Then it launched 4 agents with strict file ownership.
- **Outcome / verification:** Commits `e730f2f`, `f940386`, `31011c2` and `5632588`. Each hand-back was checked with Vitest, `tsc -b`, oxlint, Prettier, the build and Playwright.
- **Lesson:** With a shared layer in place and no file owned by two agents, the agents could not overwrite each other's work.

## 4. Correction: real-backend run found a 500 that mocks hid (2026-11-27)

- **Task:** Verify the claim form (N1–N4, E3, E4) end to end.
- **Prompt (summary):** Lead-initiated real-browser run against the real backend, followed by "If you find any bug in backend then you fix it."
- **What Claude did:** The scripted Playwright run showed `POST /claims` returning 500 for null or blank optional text (D1). The agent's tests had passed against mocks only. Claude also found that usernames containing '@' were rejected (D2).
- **Correction:** Claude fixed both on `fix/backend-validation` (PR #15, `bde6b80`, `749a388`). The D1 cause: `Field(max_length)` on `str | None` made pydantic run the check on `None`. Separately, Claude sent the still-running claim-form agent a message about the server's receipt rules above ₹500 and the new field errors on `ApiError`.
- **Outcome / verification:** 16 new tests failed before the fix and passed after. On the real backend, a draft went through receipt upload and submit to PENDING_APPROVAL at 390px.
- **Lesson:** Passing mock tests is not enough. Every screen needs a real-backend run before it is committed.

## 5. Correction: email label vs username login (2026-11-27)

- **Task:** Log in as the seeded users through the UI.
- **Prompt (summary):** Round 2 brief: "backend login by email".
- **What Claude did:** It confirmed that the backend matched only on username, so seeded users could not log in through the "Work email" field (D3).
- **Correction:** The team kept the email label (a human decision), and Claude changed `/auth/login` to match username or email, case-insensitive (`309788f`).
- **Outcome / verification:** 3 new backend tests. Real-backend checks: a bad login returns 401 and a good one 200, and a login through the `web` :8080 proxy returns 200.
- **Lesson:** Check a UI field decision against what the API actually accepts.

## 6. Correction: E2E reused the dev server; CRLF broke Prettier (2026-11-27)

- **Task:** Grow the E2E suite to 10 cases (`1f54b85`).
- **Prompt (summary):** Round 2 brief: "7 more E2E".
- **What Claude did:** It wrote flows for the phone-width claim form, the hotel and receipt rules, bulk approve, send-back, the policy rule edit and People access.
- **Correction:** Playwright reused the developer's `pnpm dev` on port 5173, which served the real backend with no mocks, so the mock login returned 401. Fix: E2E now runs on port 5174 with `VITE_ENABLE_MOCKS=true`. Separately, Prettier failed on 26 files after a stash restore because of CRLF line endings. Fix: `frontend/.gitattributes` with `eol=lf`.
- **Outcome / verification:** 10 Playwright cases pass. CI retries twice for cold-start timeouts (D7).
- **Lesson:** Isolate test environments from the developer's environment, and pin line endings.

## 7. Round 3: dashboard summary and audit trail (2026-11-27)

- **Task:** Use the new backend endpoints merged into `main`.
- **Prompt (summary):** "Check the git history what updated… only build things whose APIs are available… run multiple sub agents."
- **What Claude did:** It merged `origin/main`. The user's `git pull` had left a merge staged but uncommitted (MERGE_HEAD), so Claude checked there were 0 conflicts and completed it (`81e2db7`). It fixed the changed `AuditEventOut` schema (D4, `010c53c`), then ran 2 agents: the dashboard on `GET /dashboard/summary` (`8b728cc`) and the audit trail with `/audit-logs/verify` (`78800d1`).
- **Outcome / verification:** 42 Vitest tests pass. On the real backend, the dashboard summary rendered and the audit verify showed "Chain intact".
- **Lesson:** After every pull, read the contract diff before building, because schema changes break parsing silently.
