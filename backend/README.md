# Backend — FastAPI starter

Plumbing only. **No domain logic, no business rules, no models.** Feature code is written
during the build window, on top of this.

## Quick start

```powershell
. $env:USERPROFILE\hackathon-tools\hackenv.ps1   # pinned Python/Node/JDK
cd backend

py -3.13 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

docker compose up -d db                           # PostgreSQL 18 on host port 5433
copy .env.example .env
uvicorn app.main:app --reload
```

Then:

| URL | What |
|---|---|
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/health | Liveness — never touches the DB |
| http://localhost:8000/health/ready | Readiness — 200 if the DB answers, 503 if not |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:8000/api/v1 | Versioned API root (no routes yet) |

Whole stack in containers: `docker compose up --build` from the repository root.

## Layout

```
app/
  main.py            create_app() factory + `app` ASGI entrypoint
  config.py          Settings (pydantic-settings), get_settings()
  database.py        engine, SessionLocal, Base, get_db dependency
  health.py          /health and /health/ready
  errors.py          AppError + one error envelope for every failure
  observability.py   Prometheus metrics + /metrics
  api/router.py      api_router — include feature routers here, wiring only
alembic/             migrations (env.py reads app settings)
tests/               conftest fixtures + health tests
```

## Adding a feature

1. Model in `app/models/<thing>.py`, inheriting `Base`; import it in `alembic/env.py`.
2. `alembic revision --autogenerate -m "add <thing>"`, review the file, `alembic upgrade head`.
3. Router in `app/api/<thing>.py`, included in `app/api/router.py`.
4. Raise `AppError` subclasses for expected failures so the error envelope stays consistent.
5. Tests in `tests/` — the name states the rule and the result.

## Port 5433, not 5432

Team laptops may already run a local PostgreSQL service on 5432. The container publishes on
**5433** instead.

The failure mode is sneaky: the container reports healthy and `docker exec ... psql` works,
because that runs *inside* the container — only host connections reach the wrong database.
`password authentication failed for user "manthan"` means you are talking to 5432.

Inside the compose network the app uses `db:5432` (container-internal). Only the host-published
port is 5433.

## Tests

```powershell
pytest                          # no database needed
ruff check . ; black --check .
```

The harness runs against in-memory SQLite with `get_db` overridden, so tests pass with no
database and CI needs no service container. Tests that genuinely need PostgreSQL get the
`integration` marker.

> SQLite and PostgreSQL differ where it matters most for this project — row locking,
> `SELECT ... FOR UPDATE`, constraint timing. **Any concurrency rule must have an
> `integration` test against real PostgreSQL.** A green SQLite suite proves nothing about a
> race condition.

## Conventions

- `snake_case` Python and SQL, `PascalCase` classes.
- Commits: `feat:` `fix:` `test:` `docs:` `ci:` `chore:`.
- `ruff check .` and `black --check .` pass before every commit.
- No secrets in the repo. `.env.example` holds dummy values; `.env` is gitignored.
- Synthetic or public data only.

## Dependencies

`requirements.txt` is a full lock, self-contained because the Docker build context is this
folder. It must stay in sync with `setup/requirements-hackathon.txt`. Changing a version is
a team decision — announce it, change both files, tell everyone to reinstall.
