# ExpenseFlow runbook

For the people on call during the SRE drill, and for judges. Every command runs from the
**repository root** unless it says otherwise. Where Windows PowerShell and Git Bash differ, both
are given. In PowerShell 5.1, `curl` means `Invoke-WebRequest`, so this runbook uses `curl.exe`.

Sources: `docker-compose.yml`, `backend/Dockerfile`, `backend/scripts/start.py`,
`deploy/prometheus/`, `deploy/grafana/`, `backend/app/observability.py`, `backend/app/health.py`,
`frontend/nginx.conf`, `frontend/Dockerfile`, `.github/workflows/ci.yml`, `CLAUDE.md`.

## 1. Service overview

Start order is enforced by health checks: `db` -> `api` -> `web` / `prometheus` -> `grafana`.

| Service (compose) | Container | Host port | Purpose | Health check |
|---|---|---|---|---|
| `db` | `manthan-db` | **5433** (5432 inside the network) | PostgreSQL 18, user/password/db `manthan` | `pg_isready -U manthan -d manthan` every 5s |
| `api` | `manthan-api` | 8000 | FastAPI: `/api/v1/*`, `/docs`, `/health`, `/health/ready`, `/metrics`. On start: wait for db, `alembic upgrade head`, load seed, run uvicorn | `curl --fail http://localhost:8000/health/ready` every 10s (start period 30s) |
| `web` | `manthan-web` | 8080 | nginx serving the built SPA; proxies `/api/` to `api:8000`; SPA fallback | `wget --spider http://127.0.0.1/` every 10s |
| `prometheus` | `manthan-prometheus` | 9090 | Scrapes `api:8000/metrics` every 15s (job `expenseflow-api`); loads `alerts.yml` | http://localhost:9090/targets |
| `grafana` | `manthan-grafana` | 3000 | Dashboards; Prometheus datasource provisioned (uid `prometheus`) | http://localhost:3000 (admin/admin unless `GRAFANA_ADMIN_*` set) |

Volumes: `db_data` (database), `receipts` (uploaded receipt files at `/app/uploads`).
The api container runs the built image: no source mount, no `--reload`. A backend code change
needs `docker compose up -d --build api`.

Seeded logins (username or email; password = username): `admin` / `finance.head@expenseflow.example`
(finance head), `manager` / `line.manager@expenseflow.example`, `auditor` /
`finance.auditor@expenseflow.example`, `employee` / `employee@expenseflow.example`.

## 2. Start, stop, rebuild

```sh
docker compose up --build              # whole stack, foreground
docker compose up -d --build           # whole stack, background
docker compose ps                      # state + health of each container
docker compose stop                    # stop, keep containers and data
docker compose down                    # remove containers, keep volumes (data)
docker compose down -v                 # DANGER: also deletes db_data and receipts (synthetic data only)
docker compose up -d --build api       # rebuild one service after a code change
docker compose up -d --build web
docker compose restart api             # restart one service (re-runs migrate + seed)
```

Logs (any service: `db`, `api`, `web`, `prometheus`, `grafana`):

```sh
docker compose logs api --since 10m
docker compose logs -f web             # follow
```

## 3. Migrations and seed

Both run **automatically** every time the api container starts (`backend/scripts/start.py`):
`alembic upgrade head`, then `backend/db/seed.sql` via `scripts/seed_db.py` (idempotent,
`ON CONFLICT DO NOTHING`; skip with `SEED_ON_START=false`). Policy rules and settings are not
seed data: the API inserts missing defaults at startup.

Run them by hand (the image contains `alembic/`, `alembic.ini`, `db/` and `scripts/`):

```sh
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_db
docker compose exec db psql -U manthan -d manthan -c "select version_num from alembic_version;"
```

Newest migration file: `backend/alembic/versions/0006_audit_hardening.py`.

From the host venv instead (API run locally, `backend/.env` pointing at port 5433):

```powershell
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head; .\.venv\Scripts\python.exe -m scripts.seed_db
```

Seed straight through psql (works with any image):

```powershell
Get-Content backend\db\seed.sql | docker compose exec -T db psql -U manthan -d manthan -v ON_ERROR_STOP=1   # PowerShell
```

```sh
docker compose exec -T db psql -U manthan -d manthan -v ON_ERROR_STOP=1 < backend/db/seed.sql              # Git Bash
```

## 4. Health and metrics

| Endpoint | Meaning | Expected |
|---|---|---|
| `GET http://localhost:8000/health` | Liveness. Never touches the DB. | 200 `{"status":"ok",...}` |
| `GET http://localhost:8000/health/ready` | Readiness. Runs `select 1`. Used by the compose healthcheck. | 200 `{"status":"ready","database":"ok"}`; 503 `{"status":"degraded","database":"unavailable"}` |
| `GET http://localhost:8000/metrics` | Prometheus text format | metrics below |

nginx proxies only `/api/`; `/health*` and `/metrics` are reached on port 8000 directly.
To test the web -> api path: `curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:8080/api/v1/auth/me`
(Git Bash: `-o /dev/null`). **401** = proxy and api fine (no token sent); **502/504** = api not reachable.

Metrics the API exports today (`backend/app/observability.py`). Labels use the route template
(`/api/v1/claims/{claim_id}`), not raw ids.

| Metric | Type | Labels | Use |
|---|---|---|---|
| `http_requests_total` | counter | `method`, `path`, `status` | traffic, 5xx rate |
| `http_request_duration_seconds` | histogram (buckets 5 ms ... 5 s) | `method`, `path` | p95 latency per route (server-side page/API latency) |
| `http_requests_in_progress` | gauge | `method` | concurrency |

```sh
curl.exe -s http://localhost:8000/metrics | Select-String http_request    # PowerShell
curl -s http://localhost:8000/metrics | grep http_request                  # Git Bash
```

Useful PromQL (paste in http://localhost:9090/graph or a Grafana panel):

```promql
# p95 latency per route
histogram_quantile(0.95, sum by (le, path) (rate(http_request_duration_seconds_bucket{job="expenseflow-api"}[5m])))
# 5xx ratio
sum(rate(http_requests_total{job="expenseflow-api",status=~"5.."}[5m])) / clamp_min(sum(rate(http_requests_total{job="expenseflow-api"}[5m])), 1e-9)
# approvals queue endpoint p95
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{path="/api/v1/approvals/pending"}[5m])))
```

### Gaps against the SRE expectations (say so in the drill)

- **No queue-size or approval-age metric.** There is no pending-approvals gauge and no
  `oldest_pending_approval_age_seconds` in the code. `deploy/prometheus/alerts.yml` says that alert
  "is added once the API exports oldest_pending_approval_age_seconds (owner: Backend-2 / SRE)".
  Until then, use the SQL in playbook 6.6.
- **No Grafana dashboard is provisioned.** `deploy/grafana/provisioning/` holds only the
  Prometheus datasource. Build panels from the PromQL above, or add a dashboard JSON plus a
  `dashboards/` provider.
- **Page latency** is measured server-side only (API latency per route); no browser timing metric.
- **No Alertmanager** in compose: alerts are visible at http://localhost:9090/alerts only.

## 5. Alerts (`deploy/prometheus/alerts.yml`, group `expenseflow-api`)

| Alert | Expression (summary) | For | Severity |
|---|---|---|---|
| `ApiDown` | `up{job="expenseflow-api"} == 0` | 1m | critical |
| `ApiHighLatencyP95` | p95 of `http_request_duration_seconds` over 5m > 0.5 s | 5m | warning |
| `ApiHighErrorRate` | 5xx / all requests over 5m > 5% | 5m | warning |
| *(oldest pending approval)* | **not present** - see gaps above | - | - |

After editing `alerts.yml` or `prometheus.yml`: `docker compose restart prometheus`.

## 6. Incident playbooks

Each one: **Symptoms -> Check -> Fix -> Verify.**

### 6.1 API 500 on every request after pulling (unmigrated DB, D8)

- **Symptoms:** UI errors everywhere; `ApiHighErrorRate` fires; `/health` is 200 but `/api/v1/*`
  is 500. Logs contain e.g. `column users.department does not exist`. Happens when new migrations
  arrive but the DB was not upgraded (old api image, or the API run from the host venv).
- **Check:**
  ```sh
  docker compose logs api --since 10m | Select-String "does not exist|alembic|Error"   # PowerShell
  docker compose logs api --since 10m | grep -E "does not exist|alembic|Error"         # Git Bash
  docker compose exec db psql -U manthan -d manthan -c "select version_num from alembic_version;"
  ```
  Compare with the newest file in `backend/alembic/versions/`.
- **Fix:** rebuild so the image holds the new migrations; the entrypoint applies them:
  `docker compose up -d --build api`. Or apply directly: `docker compose exec api alembic upgrade head`.
  Host venv: `cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head`.
  If a migration itself fails, the api never becomes healthy and `web` will not start - read the
  traceback in `docker compose logs api` and escalate to the backend lead.
- **Verify:** `alembic_version` shows the newest revision; `docker compose ps` shows api `healthy`;
  sign-in and `/claims` load; the 5xx ratio returns to 0.

### 6.2 Web returns 502 (api restarting, D9)

- **Symptoms:** `http://localhost:8080/api/...` returns 502 Bad Gateway, usually for a few seconds.
- **Check:** `docker compose ps` (is `manthan-api` restarting or unhealthy?);
  `docker compose logs api --since 10m`; `docker compose logs web --since 10m`.
- **Fix:** if the api is just restarting (rebuild, `restart`, crash loop recovering), wait - it
  recovers on its own. If it stays down, fix the startup error in the api logs (often 6.1 or 6.3).
  If the api is healthy but nginx still answers 502: `docker compose restart web`.
- **Verify:** `curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:8080/api/v1/auth/me` prints 401.

### 6.3 DB connection refused / wrong port (5432 vs 5433)

- **Symptoms:** host tools or the local venv API fail with `connection refused`, or
  `password authentication failed for user "manthan"` (that one means you reached a laptop's own
  PostgreSQL on 5432). In compose, the api logs `Database not reachable yet; retrying` and gives up
  after 60s.
- **Check:**
  ```powershell
  docker compose ps db
  Get-NetTCPConnection -LocalPort 5432,5433 -State Listen      # PowerShell
  ```
  ```sh
  netstat -ano | grep -E ":543[23] "                            # Git Bash
  ```
  `DATABASE_URL` in `backend/.env` must be `postgresql+psycopg://manthan:manthan@localhost:5433/manthan`.
  Inside compose the API uses `db:5432` - that is correct, do not change it.
- **Fix:** `docker compose up -d db`; point host clients (venv, pgAdmin) at **5433**.
  If the api gave up waiting: `docker compose restart api`.
- **Verify:** `curl.exe -s http://localhost:8000/health/ready` returns `"database":"ok"`.

### 6.4 /health/ready slow with the DB down

- **Symptoms:** with `db` stopped, `/health/ready` takes more than 15s instead of returning 503
  (known issue in `CLAUDE.md`). The engine in `backend/app/database.py` sets `pool_pre_ping=True`
  but no connect timeout. The compose healthcheck (timeout 5s) then marks the api `unhealthy`.
- **Check:**
  ```sh
  curl.exe -s -w "\n%{http_code} %{time_total}s\n" http://localhost:8000/health/ready
  docker compose ps
  ```
- **Fix (now):** `docker compose start db`; wait for `healthy` in `docker compose ps`.
  **Fix (code, owner: backend):** add a connect timeout to `create_engine`, e.g.
  `connect_args={"connect_timeout": 3}` (psycopg), plus a test.
- **Verify:** DB up -> 200 quickly; DB stopped -> 503 within a few seconds.

### 6.5 Login always returns 401 (username vs email, D3)

- **Symptoms:** "The username or password is incorrect." for seeded users.
- **Check:** are users seeded?
  ```sh
  docker compose exec db psql -U manthan -d manthan -c "select username, email, role, is_active from users;"
  ```
  Call the API directly:
  ```powershell
  Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -ContentType application/json -Body '{"username":"employee@expenseflow.example","password":"employee"}'
  ```
  ```sh
  curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"employee@expenseflow.example","password":"employee"}'
  ```
  Then the same with `"username":"employee"`.
- **Fix:** no users -> `docker compose exec api python -m scripts.seed_db`. Username works but
  email fails -> the api runs code from before the login-by-email fix (`/auth/login` matches
  username or email, case-insensitive): pull `main`, `docker compose up -d --build api`.
  Unknown user, wrong password and inactive user all return the same 401 by design.
- **Verify:** the call returns an `access_token`; UI sign-in lands on `/claims` (employee).

### 6.6 Approvals queue growing / oldest pending approval

- **Symptoms:** claims stuck in `PENDING_APPROVAL`. No alert fires for this today (see gaps).
- **Check:**
  ```sh
  # queue size and oldest pending step per approver role
  docker compose exec db psql -U manthan -d manthan -c "select approver_role, count(*), min(created_at) as oldest, now() - min(created_at) as age from approval_steps where status = 'PENDING' group by approver_role;"
  # who the pending steps are assigned to
  docker compose exec db psql -U manthan -d manthan -c "select s.assigned_approver_id, u.username, count(*) from approval_steps s left join users u on u.id = s.assigned_approver_id where s.status = 'PENDING' group by 1, 2 order by 3 desc;"
  # active delegations today
  docker compose exec db psql -U manthan -d manthan -c "select delegator_id, delegate_id, from_date, to_date from delegations where active and current_date between from_date and to_date;"
  ```
  `created_at` is when the step row was created, which can be before it became PENDING, so the
  age is an upper bound. Also check `/api/v1/approvals/pending` p95 in Prometheus.
- **Fix:** approver away with no delegation -> they set one on `/delegations` ("Out of office").
  Approver available -> ask them to clear the queue (select + bulk approve on `/approvals`).
- **Verify:** the count falls and the oldest age drops on re-running the first query.

### 6.7 Receipt upload returns 413

- **Symptoms:** uploading a receipt fails with 413.
- **Check:** file size. nginx allows `client_max_body_size 6m`; the API caps receipts at 5 MB
  (`max_upload_bytes` in `backend/app/config.py`). An nginx 413 is an HTML page (seen in
  `docker compose logs web --since 10m`); an API 413 is the JSON error envelope with `max_upload_bytes`.
- **Fix:** ask for a file under 5 MB. Do not raise the nginx limit alone; change both together if
  the limit policy changes.
- **Verify:** a file under 5 MB uploads and opens in the receipt viewer.

### 6.8 Frontend blank page

- **Symptoms:** `http://localhost:8080` is white.
- **Check:** browser devtools console and network (404 on `/assets/*.js`? failing `/api` calls?);
  `docker compose logs web --since 10m`; `docker compose ps web`.
- **Fix:** rebuild the image (it runs `pnpm build` inside): `docker compose up -d --build web`,
  then hard-reload the browser. If the build fails, reproduce locally:
  `cd frontend; pnpm install; pnpm build`. A stale `src/routeTree.gen.ts` can break `tsc` (D10):
  run `pnpm test:run` or `pnpm dev` once to regenerate it.
- **Verify:** the login page renders, sign-in works, no console errors.

### 6.9 CI `web` job failing

CI runs on pull requests only. The web job runs, in `frontend/`: `pnpm lint`, `pnpm format:check`,
`pnpm test:run`, `pnpm build`, `pnpm audit --prod --audit-level high`.

- **Check:** open the failed step in the PR's Actions log; run the same command locally.
- **Fix:**
  - Prettier fails on many files -> CRLF line endings (C4). `frontend/.gitattributes` forces LF;
    renormalise with `git add --renormalize frontend`, then `pnpm format`.
  - Formatting only -> `pnpm format` and commit.
  - Lint -> `pnpm lint:fix`, fix the rest by hand.
  - Audit -> upgrade the flagged package (team decision: it is a lockfile change).
  - Playwright is not part of CI; run `pnpm test:e2e` locally.
- **Verify:** all five commands pass locally; re-run the PR checks.

## 7. Escalation and contacts (by role)

| Area | Role | Person |
|---|---|---|
| Backend, migrations, API errors | Backend lead | Himanshu |
| Docker, Prometheus/Grafana, alerts, CI | Backend 2 / DevOps-SRE | Diksha |
| Frontend, `web` image and nginx, SPA errors | Frontend | Abhayraj |
| Reproduction, QA evidence, drill artifacts | UI/UX, QA | Rahul |

Order: on-call person for the area, then the backend lead. Record every incident with
`docs/rca-template.md`.
