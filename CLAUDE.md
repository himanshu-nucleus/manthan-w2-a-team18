# CLAUDE.md

Project guidance for Claude Code. Required submission artifact for AI Manthan.

> Keep this file current during the build - judges read it and compare it to the repo.

## Project

- **Team:** team18 - Himanshu (backend, lead), Diksha (backend, DevOps/SRE),
  Rahul (UI/UX, QA, artifacts), Abhayraj (frontend)
- **Wave / Track:** W2 / **Track A - Application Development**
- **Repository:** `manthan-w2-a-team18`
- **Use case:** ExpenseFlow - expense claims with a policy engine, multi-level approvals,
  an auditor review queue and a payout export, replacing email threads and Excel.
- **Build window:** 5 hours. SRE drill at **T+3:30**, demo at **T+4:15** (confirm wall-clock
  times with the mentors). Plan and checkpoints: `docs/work-plan.md` and
  `docs/team-work-plan.xlsx` - kept locally on the lead's machine, gitignored, not in the repo.

## Business rules

Policy limits are **seeded configuration, never hard-coded**. The card's rules plus the gap
decisions in `docs/work-plan.md` section 2 (G1-G20) apply once the lead signs them off;
record each decision here as it is made.

### Decided

- **Personas** (`users.role`, DB CHECK constraint): `finance_head`, `employee`,
  `line_manager`, `finance_auditor`. `users.manager_id` links a user to their line manager.
- **Authentication (replaces G17 mock login, lead 2026-11-27):** username + password.
  `POST /api/v1/auth/login` returns a bearer token (signed with `SECRET_KEY` via
  `itsdangerous`, 8 h TTL). Passwords are PBKDF2-SHA256 hashes (`app/security.py`), never
  plain text. Every request re-reads the user, so deactivation takes effect immediately.
- **Default finance head:** `admin` / `admin`, created only by `backend/db/seed.sql`
  (dummy dev credential - change it anywhere shared).
- **User management:** only `finance_head` may `POST /api/v1/users` and `GET /api/v1/users`.
  It can create `employee`, `line_manager`, `finance_auditor` - never another
  `finance_head` (422). New passwords are at least 8 characters. Duplicate username/email ->
  409; unknown `manager_id` -> 422. Other roles -> 403; no/invalid token -> 401.
- **Login is the same for every persona** (`POST /api/v1/auth/login`); the role comes back
  in `user.role` and drives the frontend's landing page. Dev logins from `seed.sql`:
  `admin`/`admin` (finance_head), `manager`/`manager` (line_manager),
  `auditor`/`auditor` (finance_auditor), `employee`/`employee` (employee, reports to `manager`).
- **Own-record rule (lead, 2026-11-27):** `GET /api/v1/users/{id}` - `finance_head` may read
  any user; every other role may read **only themselves**. Another user's id -> **403**,
  checked before the lookup so existing and non-existent ids look the same.
- **JWT deferred (lead, 2026-11-27):** tokens stay itsdangerous-signed for now; JWT is added
  at the end of the build. All token code lives only in `app/security.py`
  (`create_access_token` / `read_access_token`), so the swap touches that one file - do not
  read or build tokens anywhere else.

## Non-negotiable gates

A breach removes the team from the award ranking.

1. **Synthetic or public data only.** Never put client or confidential data in the repo,
   in test data, or in a prompt.
2. **Open-source / free tools only.** No subscription tools. Jira and company AWS are not used.
3. **Code stays local** - on the laptop or in the company Git repository.
4. **No pre-built solution code.** Start from the starter template only. Process assets
   (this file, the skills in `.claude/skills/`, document templates) are prep and are allowed;
   pre-written domain/solution code is not.

## Environment - read before running anything

The laptops carry an older system-wide JDK 17, Node 22 and Python 3.12 that win on PATH.
**Every terminal must activate the hackathon toolchain first:**

```powershell
. $env:USERPROFILE\hackathon-tools\hackenv.ps1
```

It prints the three versions as confirmation. Pinned versions - do not substitute newer ones:

| Component | Version |
|---|---|
| Python | 3.13.17 (`py -3.13`) |
| Node.js | 26.13.1 |
| JDK (Temurin) | 21.0.13.1+2 |
| PostgreSQL | 18 (Docker image `postgres:18`) |
| Playwright | 1.65.1 |
| React / Vite | React 19 + Vite 7 |

Images already pulled locally: `postgres:18`, `prom/prometheus`, `grafana/grafana`.

Python packages are locked in `setup/requirements-hackathon.txt`. **Never upgrade a pinned
version or add a dependency unilaterally** - it is a team decision and a lock-file change.

### Database

```
postgresql+psycopg://manthan:manthan@localhost:5433/manthan
```

Start it from the repository root with `docker compose up -d db` (container `manthan-db`).

### Schema and dummy data (verified 2026-11-27)

- **Schema = Alembic only** (`backend/alembic/versions/`). Never create tables at startup or
  in SQL files. Migrations run from the host venv (the Docker image has no Alembic):
  `cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head`
- **Dummy data = `backend/db/seed.sql`.** Idempotent (`ON CONFLICT DO NOTHING`), synthetic
  only; append a section per new table at the end of the file. Run it from the repo root
  after migrating:
  `Get-Content backend\db\seed.sql | docker compose exec -T db psql -U manthan -d manthan -v ON_ERROR_STOP=1`
- Tests do not use either: they build the schema from the ORM models on in-memory SQLite.

### Running the backend locally (verified 2026-11-27)

```powershell
. $env:USERPROFILE\hackathon-tools\hackenv.ps1
docker compose up -d db
cd backend
py -3.13 -m venv .venv                      # first time only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env                      # first time only; .env is gitignored
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If the Docker stack is up, its `manthan-api` container already holds port 8000; run the
local venv app on `--port 8001` instead.

The venv must match `requirements.txt` exactly (73 pins, all exact). Re-run the
`pip install -r requirements.txt` line after anyone changes the lock; never `pip install`
a package without adding its pin there (team decision).

`GET /health` -> 200 (liveness, no DB). `GET /health/ready` -> 200 with the DB up, 503 without.

**Known issue:** with the DB stopped, `/health/ready` hangs for more than 15s instead of
returning 503 quickly (no DB connect timeout). Fix before the SRE drill.

**Host port is 5433, not 5432.** Some laptops run their own PostgreSQL 15 service on 5432.
The container still reports healthy and `docker exec ... psql` still works, because that
runs inside the container - only host connections hit the wrong database. A
`password authentication failed for user "manthan"` error means you are on 5432.

## Stack

- **Frontend:** React 19 + Vite
- **Backend:** FastAPI on Python 3.13
- **Database:** PostgreSQL 18 in Docker
- **Tests:** pytest (unit + API), Playwright (UI), Locust (performance)
- **CI:** GitHub Actions - lint + tests + dependency check, on **pull requests only** (not on
  push). Run `ruff`, `black --check` and `pytest` locally before pushing.
- **Observability:** Prometheus + Grafana in Docker
- **Run:** `docker compose up` must bring the whole stack up from a fresh clone, one command.

## Repository layout

Decision (lead, 2026-11-27): the API stays in `backend/` and the web app goes in
`frontend/`, side by side, instead of the template's `src/api` / `src/web`.

```
backend/            FastAPI app (app/), alembic/, its pytest suite (tests/), Dockerfile
  app/models/       SQLAlchemy models (import each in app/models/__init__.py)
  app/schemas/      Pydantic request/response models
  app/api/          routers (auth, users) + dependencies.py (current user, role checks)
  db/seed.sql       idempotent synthetic seed data
  scripts/export_openapi.py  writes docs/openapi.json
docs/openapi.json   API contract - generated, the frontend's single source for the API
frontend/           React 19 + Vite app (to be created)
tests/e2e/          Playwright UI tests
docs/               artifacts: adr/, runbook.md, rca-*.md, claude-journal.md, LLD, ideation
deploy/             prometheus/, grafana/ config mounted by the root compose file
.github/workflows/  CI (lint, tests, dependency check)
.claude/skills/     team skills
docker-compose.yml  whole stack: `docker compose up --build`
README.md           one-command start instructions
CLAUDE.md           this file
```

## Engineering standards

- **Branches:** protected `main`; integration branch `pre-main`; one short-lived branch per
  layer and entity of work, merged into `pre-main` after one teammate reviews. See
  [Branching](#branching---one-branch-per-layer-and-entity) below.
- **Commits:** imperative, one change each, prefixed `feat:` `fix:` `test:` `docs:` `ci:` `chore:`
- **Formatting:** Black + Ruff (Python), Prettier + ESLint (JS). Must pass before commit.
  No unused or commented-out code.
- **Naming:** `snake_case` Python and SQL, `camelCase` JavaScript, `PascalCase` classes.
  Descriptive English names.
- **Tests:** the name states the rule and the result (`test_late_cancel_is_refused`).
  Every must-have has a test. One command runs them all.
- **Secrets:** none in the repo. `.env.example` with dummy values; real values in `.env` (gitignored).

## How to work with Claude here

- **Plan first.** For anything non-trivial, produce a short plan and have a human approve it
  before code is written. Plan-first workflow is explicitly scored.
- **Humans decide.** Claude drafts and executes; a person reviews and signs off. Do not merge
  output nobody has read.
- **Verify before shipping.** Do not claim a test passes without running it. If something is
  untested or skipped, say so.
- **Every API change regenerates the OpenAPI contract.** `docs/openapi.json` is the
  frontend's **single point of contact** for the API - no other endpoint list exists. Whenever
  an endpoint is added, changed or removed, in the same change:
  1. Give the route a one-line `summary` stating what it does **and who may call it**
     (e.g. `"Create an employee, line manager or finance auditor (finance_head only)"`),
     a `response_model`, `responses=error_responses(...)` for every error status it can
     return, and a unique function name (it becomes the `operationId`).
  2. Regenerate: `cd backend; .\.venv\Scripts\python.exe -m scripts.export_openapi`
  3. Commit `docs/openapi.json` with the code. Never hand-edit it.

  `tests/test_openapi_contract.py` fails if the committed file is stale or an operation has
  no summary, so CI enforces this.
- **Record it.** After each meaningful unit of work, add an entry with the `usage-journal`
  skill - especially when you corrected Claude. 5-8 entries, at least one correction.
- **Never** force-push, rewrite shared history, push without being asked, commit secrets or
  real data, or weaken a test to make it pass.

## Working in parallel - four people, one repo

Four people editing one repo for five hours will collide unless paths are owned. **Stay
inside the paths for the role you are working as**, and do not reformat, refactor or
"tidy" files owned by someone else even if they look wrong - raise it in chat instead.

| Member | Role | Owns |
|---|---|---|
| Himanshu | Backend-1 + lead / architect | `backend/` domain core (claims, policy, approvals, audit), `backend/alembic/`, `docs/adr/`, `CLAUDE.md`, `README.md` |
| Diksha | Backend-2 + DevOps / SRE | `backend/` auditor, payout, dashboard, seed; `deploy/`, `docker-compose.yml`, `.github/workflows/` |
| Rahul | UI/UX + QA + artifacts | `docs/design/`, `docs/test-*`, `tests/e2e/`, `.claude/skills/`, Excel backlog / test cases / defect log |
| Abhayraj | Frontend | `frontend/` |

High-conflict shared files - announce before editing: `setup/requirements-hackathon.txt`,
`package.json`, `docker-compose.yml`, the database schema.

Workflow: `git pull --rebase origin pre-main` before starting and before every push; work on
your own layer/entity branch (below); one teammate reviews before merge into `pre-main`.

## Branching - one branch per layer and entity

```
main        protected; demo-ready only. Updated from pre-main by the lead after the
            integrated stack passes tests and a fresh-clone start.
pre-main    integration branch. Every work branch is cut from it and merged back into it.
<work>      one branch per layer + entity, named below. Short-lived: merge within ~1 hour.
```

**Name:** `<type>/<layer>-<entity>[-<detail>]` - lowercase, hyphen-separated.

| Part | Values |
|---|---|
| `type` | `feature` (new work), `fix` (bug or defect-log item), `chore` (tooling, no behaviour change), `docs` (artifacts only) |
| `layer` | `be` backend API + domain (`backend/app/`), `db` migrations + seed (`backend/alembic/`, `backend/db/`), `fe` frontend (`frontend/`), `qa` tests + test artifacts (`tests/e2e/`, `docs/test-*`), `ops` compose, CI, monitoring (`deploy/`, `docker-compose.yml`, `.github/workflows/`), `docs` design + documents (`docs/`) |
| `entity` | `auth`, `users`, `claims`, `policy`, `approvals`, `delegation`, `audit`, `auditor-queue`, `payout`, `dashboard`, `seed`, `ci`, `monitoring`, `platform` |

Examples:

| Branch | Owner | Scope |
|---|---|---|
| `feature/be-claims` | Himanshu | claims API: draft, lines, receipt upload, submit |
| `feature/be-policy` | Himanshu | policy engine + rule tests |
| `feature/db-claims` | Himanshu | Alembic migration for claims, lines, receipts |
| `feature/be-payout` | Diksha | payout batch + CSV export |
| `feature/db-seed` | Diksha | 150 employees, 3,000 claims in `backend/db/seed.sql` |
| `feature/ops-monitoring` | Diksha | Prometheus alerts + Grafana dashboard |
| `feature/fe-claims` | Abhayraj | claim form, my claims, claim detail |
| `feature/fe-approvals` | Abhayraj | approver inbox, actions, receipt viewer |
| `feature/qa-e2e-approvals` | Rahul | Playwright cases for the approval chain |
| `docs/docs-adr` | Rahul / Himanshu | ADR-001 and ADR-002 |
| `fix/be-policy-meal-boundary` | whoever found it | defect-log item; reference its ID in the commit |

Rules:

- **One layer per branch.** A backend endpoint and the screen that uses it are two branches
  (`feature/be-claims`, `feature/fe-claims`). A schema change goes on its own `db-` branch
  and merges before the `be-` branch that needs it.
- **One entity per branch.** Do not mix claims and payout work on one branch; open a new one.
- **Cut from and merge into `pre-main` only.** Never branch from or merge into `main`
  directly, and never merge one work branch into another.
- **Before merging:** `git pull --rebase origin pre-main`, tests and lint pass, one teammate
  has reviewed. Delete the branch after merge.
- **Backend branches that touch an endpoint** regenerate and commit `docs/openapi.json` in
  the same branch, so the contract is correct the moment it lands in `pre-main`.

### Frontend integration

- **Single point of contact: `docs/openapi.json` on `pre-main`.** It holds every path,
  method, one-line summary (what + who may call it), request/response schema, error
  responses, auth scheme and `operationId`. `fe-` branches integrate against it and nothing
  else. To browse it, open http://localhost:8000/docs (the same contract, live) or import
  the file into any OpenAPI viewer. Generating a typed client from it is fine, but the
  generator is a new npm dependency - team decision first.
- If an endpoint the screen needs is not in that file yet, build against fixtures that
  match the planned shape and ask the backend owner; do not guess a path or edit backend
  code from an `fe-` branch.
- Merge an `fe-` branch into `pre-main` only after the `be-` branch for its endpoints has
  merged, and check the screen against the running API, not fixtures.

## Team skills

| Skill | Use it for |
|---|---|
| `usage-journal` | Journal entries after each unit of work |
| `adr-writer` | The two required ADRs |
| `test-case-author` | Excel test cases + pytest/Playwright stubs + defect log |
| `rca-runbook` | The 15:30 SRE drill - timeline, RCA, runbook |

Also available: `init`, `artifact-design` (wireframes/UI), `artifact-diagramming` (C4),
`dataviz` (dashboards), `xlsx` (backlog, test cases), `pptx` (presentation),
`docx` (ideation, LLD, runbook), `code-review`, `security-review`, `run`.

## Submission checklist

- [ ] Repository with README and **one-command start**
- [ ] Architecture diagram (C4 context + container) and **two ADRs**
- [ ] API contract
- [ ] Wireframes and final screens
- [ ] Stories backlog with acceptance criteria (Excel)
- [ ] Test plan, executed test cases, **defect log**
- [ ] `CLAUDE.md` + **one reusable asset** (submit a `.claude/skills/` skill)
- [ ] **Claude usage journal**, 5-8 entries, >=1 correction
- [ ] Runbook + RCA from the SRE drill
- [ ] Ideation document and LLD
- [ ] Five-minute demo
