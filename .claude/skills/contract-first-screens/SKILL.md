---
name: contract-first-screens
description: Use this skill when building several UI screens from an OpenAPI contract with parallel sub-agents. It applies when a repo has an API spec (such as docs/openapi.json) and design specs for many screens, and you want to fan the work out to agents without merge conflicts or invented endpoints. The skill covers mapping endpoints to screens, building a shared foundation once, briefing agents who each own their own files, verifying every hand-back (including a run against the real backend), and committing one screen at a time.
---

# Contract-first screens with parallel sub-agents

This skill was first used on ExpenseFlow (team18), where the login screen came first and the other screens with an API were built from `docs/openapi.json` in 3 rounds of sub-agents. The steps are generic. ExpenseFlow details are marked *Example*.

## When to use

- You have an API contract and more screens than one agent should build in one sitting.
- The backend is still moving, so screens must follow the contract and not the prose docs.
- You can run the real backend locally for a smoke test.

Do not use this skill for a single screen; just plan it and build it.

## Inputs

- The OpenAPI file, which wins over markdown docs when they conflict.
- Design specs per screen, plus a design system doc (*Example:* `docs/design/screens/*.md`, `frontend/DESIGN.md`).
- The frontend stack and the commands that verify it (test, type-check, lint, format, build, E2E).
- Seeded logins for each role on the real backend.

## Procedure

1. **Map endpoints to screens.** List every operation in the contract. Put each one against a design screen in a table: route, design id, endpoints, role.
2. **Skip screens without an API.** Do not invent endpoints or fake data in production code. List the skipped screens in the plan. *Example:* role dashboards E1/M1/A0, duplicate review A2 and auditor history A3 were skipped.
3. **Plan and get human decisions.** Write a short plan. Ask only the questions that change behaviour, such as field semantics, token storage or the form library. Wait for answers.
4. **Build the shared foundation yourself, before fan-out:**
   - typed API modules + Zod (or equivalent) schemas mirroring the contract, one per feature;
   - the app shell and per-role navigation;
   - shared chips, badges and formatters (currency, dates, locale);
   - **every UI component installed once** (no agent runs a CLI or package install);
   - a placeholder route file for each screen, so the router tree is final;
   - **one mock handler file per feature**, registered centrally, so agents never edit the same mock file.
   Commit the foundation on its own.
5. **Brief one agent per screen group** with the template below. Give each agent a list of files it owns that does not overlap with any other agent's list. Run agents in parallel.
6. **Correct agents mid-flight.** If you learn a contract fact while agents are running (for example a validation rule the server enforces), send it to the affected agent at once.
7. **Verify every hand-back** with the checklist below. Do not trust the agent's own report.
8. **Run a smoke test against the real backend.** Script a real browser (for example Playwright via node) against the running API with mocks off. Sign in as each role, walk the main path, and take screenshots at phone and desktop widths. Fix or route back anything that fails. If the bug is in the backend, fix it there with tests, or raise it.
9. **Commit one screen per commit** with a conventional prefix (`feat:`, `fix:`, `test:`).
10. **Repeat** when new endpoints land: pull, diff the contract, update schemas first, then start the next round.

## Agent brief template

```text
GOAL
Build <screen name> (<design id>) at route <route>.

STACK
<framework, router, data layer, schema lib, form lib, UI kit + icons, mock lib, test lib>

ALREADY BUILT FOR YOU - USE THESE, DO NOT RECREATE
- API functions + schemas: <path>
- Shell / nav: <path>
- Shared UI and formatters: <names + paths>
- Installed UI components: <list>
- Placeholder route: <path>

API FACTS (from <openapi file>, which wins on conflict)
- <METHOD /path> -> <shape>; errors: <codes>; caller role: <role>
- <server-side validation rules>

DESIGN SPEC
<paths>

YOU OWN ONLY THESE FILES
- <route files>
- <feature folder>
- <mock handler file for this feature>
- <test file for this feature>

DO NOT
- edit any other file (ask in your report if you need a shared change)
- run UI-kit CLIs, package installs, build, e2e or git

VERIFY BEFORE REPORTING
<test command for your file>; <type-check>; <lint>; <format check on your files>

REPORT BACK
Files created/changed, tests added and their result, gaps or contract questions.
```

## Verification checklist (lead, after each hand-back)

- [ ] The agent touched only the files it owns (`git status` / `git diff --stat`).
- [ ] The full unit/integration suite passes, not just the agent's own file.
- [ ] The type-check passes (*Example:* `tsc -b`).
- [ ] Lint and format checks pass (*Example:* `pnpm lint`, `pnpm format:check`).
- [ ] The production build passes.
- [ ] E2E passes on an isolated port with mocks on.
- [ ] The real-backend browser run passes for each role that uses the screen, at phone and desktop widths.
- [ ] Every endpoint the screen calls exists in the contract.
- [ ] The commit contains one screen, with a conventional message.

## Pitfalls (seen on ExpenseFlow)

- **UI-kit CLI rewrites imports.** The shadcn CLI pointed `cn` at a bogus npm package `cn`, on init and again on every `add`. Check generated imports, remove the stray package, and keep CLI use to the lead only.
- **Mocks hide backend bugs.** Agent tests passed against MSW while `POST /claims` returned 500 for null optional text. Only the real-backend run caught it.
- **Field semantics drift.** The UI said "Work email" but the backend matched username only, so seeded users could not log in. Check every login or identity field against the real API.
- **E2E reuses the dev server.** Playwright attached to the developer's `pnpm dev` on 5173, which ran without mocks. Give E2E its own port (*Example:* 5174) and force mocks on.
- **CRLF line endings.** A stash restore with `core.autocrlf` broke Prettier on 26 files. Add `.gitattributes` with `eol=lf`.
- **Schema changes after a pull.** A changed audit event shape (nullable fields, new fields) broke parsing. Diff the contract after every pull and update the schemas first.
- **jsdom gaps and timing.** Toasts needed `window.matchMedia`, and first renders under parallel load exceeded the 1 s default. Stub it in the test setup and raise the async timeout.
- **A stale generated route tree** can fail the type-check before the router plugin regenerates it. Run the dev server or tests once first.
- **The database is not migrated after a pull.** Run migrations before blaming the frontend.
