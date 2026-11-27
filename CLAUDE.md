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
  times with the mentors). Plan and checkpoints: `docs/work-plan.md`.

## Business rules

Policy limits are **seeded configuration, never hard-coded**. The card's rules plus the gap
decisions in `docs/work-plan.md` section 2 (G1-G20) apply once the lead signs them off;
record each decision here as it is made.

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
- **CI:** GitHub Actions - lint + tests
- **Observability:** Prometheus + Grafana in Docker
- **Run:** `docker compose up` must bring the whole stack up from a fresh clone, one command.

## Repository layout

Decision (lead, 2026-11-27): the API stays in `backend/` and the web app goes in
`frontend/`, side by side, instead of the template's `src/api` / `src/web`.

```
backend/            FastAPI app (app/), alembic/, its pytest suite (tests/), Dockerfile
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

- **Branches:** protected `main`; short-lived `feature/<thing>` and `fix/<thing>`.
  Merge only after one teammate reviews.
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

Workflow: `git pull --rebase origin main` before starting and before every push; work on a
short-lived `feature/<thing>` branch; one teammate reviews before merge.

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
