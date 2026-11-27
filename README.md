# manthan-w2-a-team18 – ExpenseFlow

Expense claims with a policy engine, multi-level approvals, an auditor review queue and a
payout export. AI Manthan Wave 2, Track A.

## One-command start

```powershell
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:8000/docs | API (Swagger UI) |
| http://localhost:8000/health | Liveness |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:9090 | Prometheus (alerts under *Alerts*) |
| http://localhost:3000 | Grafana (dev login `admin` / `admin`, override in `.env`) |

PostgreSQL is published on host port **5433** (not 5432).

## Tests

```powershell
cd backend
pytest
ruff check . ; black --check .
```

CI (`.github/workflows/ci.yml`) runs lint, tests and a `pip-audit` dependency check on every push.

## Layout

See `CLAUDE.md` for the repository layout, team ownership and rules; `docs/work-plan.md`
(kept locally by the lead, not in the repo)
for the plan, gaps, risks and checkpoints.
