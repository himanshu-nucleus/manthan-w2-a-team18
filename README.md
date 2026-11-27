# manthan-w2-a-team18 – ExpenseFlow

Expense claims with a policy engine, multi-level approvals, an auditor review queue and a
payout export. AI Manthan Wave 2, Track A.

## One-command start

Needs only Docker Desktop. From a fresh clone:

```powershell
docker compose up --build
```

That builds the backend and frontend images and starts everything in order. Nothing else
to run: the API container applies the database migrations (`alembic upgrade head`),
loads the synthetic seed data (`backend/db/seed.sql`) and inserts the default policy rules
before it starts serving. Every step is idempotent, so restarting is safe.

| URL | What |
|---|---|
| http://localhost:8080 | **ExpenseFlow web app** (calls the API through `/api`) |
| http://localhost:8000/docs | API (Swagger UI) |
| http://localhost:8000/health | Liveness |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:9090 | Prometheus (alerts under *Alerts*) |
| http://localhost:3000 | Grafana (dev login `admin` / `admin`, override in `.env`) |

Dev logins (synthetic, password = username): `admin` (finance head), `auditor`,
`manager`, `employee`.

PostgreSQL is published on host port **5433** (not 5432).

Start over with an empty database (synthetic data only):

```powershell
docker compose down -v
```

## Tests

```powershell
cd backend
pytest
ruff check . ; black --check .
```

CI (`.github/workflows/ci.yml`) runs lint, tests and a `pip-audit` dependency check on pull requests.

## Layout

See `CLAUDE.md` for the repository layout, team ownership and rules; `docs/work-plan.md`
(kept locally by the lead, not in the repo)
for the plan, gaps, risks and checkpoints.
