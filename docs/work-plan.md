# ExpenseFlow – Work Plan, Risks, Gaps and Ownership

Track A · Wave 2 · team18 · drafted 27 Nov 2026, 14:25 IST (T+0:25)

Sources: use-case card *Track A – ExpenseFlow*, *AI Manthan Masterclass* deck,
*AI Manthan – Evaluation Guidelines*, team `CLAUDE.md`, `docs/BUILD-PLAN.md`.

> **Clock assumption – confirm with the mentors now.** This plan uses **T0 = 14:00**
> (the repo was created at 14:00) and the deck's clock: drill at **T+3:30 = 17:30**, demo at
> **T+4:15 = 18:15**. `CLAUDE.md` says "drill 15:30, demo 16:15". If those are literal
> wall-clock times you have ~1 hour to the drill: skip straight to the **Emergency cut** at
> the end of section 6.

---

## 1. The work in one page

**Problem:** expenses go through email + Excel, so policy breaches and duplicate receipts get
paid and managers take days. Build: claim capture → policy engine → multi-level approval →
auditor queue → payout CSV → dashboard, with an append-only audit trail.

**Personas → views:** Employee · Line manager · Finance auditor · Finance head (also admin).

| # | Must-have | Size | Hard part |
|---|---|---|---|
| M1 | Claim with many line items, receipt upload, draft → submit | M | file upload + hashing, mobile form |
| M2 | Policy engine, 3 outcomes per line, rules as config | M | rule semantics (see gaps), must be test-first |
| M3 | Approval chain: manager → auditor (>25,000) → head (>1,00,000); comment, send back, delegate | L | state machine, delegation, self-approval |
| M4 | Auditor queue: filters, bulk approve, 10% random sample audit of auto-approved | M | dense table + bulk action, reproducible sampling |
| M5 | Payout batch → mock bank CSV → Paid | S | never pay a claim twice |
| M6 | Dashboard: spend by category / dept / month, violations, avg approval time | M | aggregates over 3,000 claims |
| M7 | Append-only audit trail; employee sees only own claims | S | enforce in DB + API, not just UI |
| D | Synthetic data: 150 employees, 8 depts, hierarchy, 3,000 claims with planted duplicates and breaches | M | seed must reuse the real policy engine |

**Card-specific expectations on top of the generic 10 artifacts:** claim state machine,
policy-as-configuration design, ADR on approval-chain modelling, Claude review "as a skeptical
finance auditor listing ways to bypass approvals", approver flow timed with a stopwatch, unit
test per policy rule, threshold + delegation tests, 10 written E2E cases, security checklist,
CI with a dependency check, metrics for queue size / approval age / page latency, alert on
oldest pending approval.

---

## 2. Gaps in the card – decide these in the first 10 minutes

Claude listed these; **the team decides every answer** (deck slide 18). Proposed defaults below
– the Lead signs off, then they go into `CLAUDE.md` as business rules and into ADR-001.

| # | Gap | Proposed decision |
|---|---|---|
| G1 | How do per-line outcomes roll up to the claim? | Claim outcome = worst line outcome: any `reject` → claim auto-rejected with all reasons; any `route` → approval chain; all `auto_approve` → auto-approved. |
| G2 | What qualifies for **auto-approve**? Card never says. | All lines within limits, no flags, receipts present, **claim total ≤ 5,000**. Otherwise route. |
| G3 | Over a limit → reject or route? | **Route** with a violation flag (manager decides). Auto-reject only for: missing mandatory receipt, exact duplicate (same receipt hash), future date, amount ≤ 0. |
| G4 | 25,000 / 1,00,000 – claim total or line? `>` or `≥`? | Claim total, strictly greater. 25,000 exactly → manager only. Test both sides of each boundary. |
| G5 | Meals 1,500 "per day" – across lines/claims? | Sum of meal lines per employee per calendar date, across all non-rejected claims. |
| G6 | Hotel per night – how are nights and city tier known? | Line carries `city` and `nights`; tier-1 list in config: Mumbai, Delhi, Bengaluru, Chennai, Hyderabad, Kolkata, Pune, Ahmedabad. Limit × nights. |
| G7 | Duplicate scope | Same employee + vendor + amount + date as an earlier line, **or** same receipt SHA-256 across **all** employees. Vendor/amount/date match → flag + route; hash match → auto-reject. |
| G8 | Categories without a rule (airfare, other) | No limit, always route. |
| G9 | Weekend spend | Flag "manager attention" → never auto-approve. |
| G10 | **Reject** by approver isn't listed (only comment / send back / delegate) | Approve, reject (reason required), send back, comment, delegate. |
| G11 | Send back → resubmit: restart chain or resume? | Back to `SENT_BACK` (editable); resubmit re-runs the policy engine and **restarts the chain from manager**. |
| G12 | Delegation rules | Date-bounded; same or higher role only; can't delegate to the claimant; no chains of delegation; audit records "approved by X on behalf of Y". |
| G13 | Self-approval / conflict of interest | Approver can never act on own claim. Manager's claim goes to *their* manager; finance head's own claim goes to an auditor + a second finance-head-role user (seed one). |
| G14 | 10% sample audit – when, and does it block payout? | Flag at auto-approve time with a seeded RNG (reproducible); flagged claims enter the auditor queue and are **excluded from payout until cleared**. |
| G15 | Mock bank-file format undefined | `batch_id, value_date, employee_code, beneficiary_name, account_no (synthetic), ifsc (synthetic), amount, narration`. Header + trailer row with count and total. |
| G16 | When does a claim become Paid? | On batch export. A claim can be in only one batch (unique constraint). |
| G17 | Authentication not specified | Mock login: pick a seeded user → signed JWT with role. All access checks server-side. |
| G18 | Receipt files | PDF/JPG/PNG, ≤ 5 MB, stored on a Docker volume, served only via an authorised endpoint. |
| G19 | "Average approval time" definition | Submitted → final approval, business hours ignored, per month. |
| G20 | Claim splitting to dodge the 25,000 threshold | Flag ≥2 claims by the same employee within 7 days whose combined total crosses a threshold. (Stretch – name it in the skeptical-auditor review even if not built.) |

---

## 3. Risks

| Risk | Likelihood / impact | Mitigation | Owner |
|---|---|---|---|
| **Scope is large for 4 people** – 7 must-haves + every lifecycle artifact | High / High | Build in slices (section 5). Never start slice N+1 while slice N is red. | Lead |
| **Clock ambiguity** – drill at 15:30 or T+3:30 | High / High | Confirm with a mentor immediately. | Lead |
| **Repo layout diverges from standard** – code is in `backend/app`, standard says `src/api`; `CLAUDE.md` is outside the repo | Certain / Med (judges compare) | **Decided:** keep `backend/`, web app goes in `frontend/`; `CLAUDE.md` + README updated, `CLAUDE.md` in the repo root. | Lead + Backend |
| **CI won't run** – workflow is at `backend/.github/workflows/`; GitHub only reads the repo-root `.github/workflows/` | Certain / Med | Move to root `.github/workflows/ci.yml`, add `pip-audit` / `npm audit` as the dependency check. | Backend-2 |
| No root `docker-compose.yml` – one-command start fails from a fresh clone | Certain / High | `deploy/docker-compose.yml` (or root) with db, api, web, prometheus, grafana, seed job. | Backend-2 |
| Policy semantics argued mid-build | High / High | Section 2 decisions frozen by T+0:40, written into `CLAUDE.md`. | Lead |
| Seed data inconsistent with the engine (planted duplicates not flagged) | Med / Med | Seed script calls the real policy engine; test counts the planted cases. | Backend-2 |
| Frontend blocked on API | High / Med | API contract (OpenAPI) by T+1:00; Frontend codes against fixtures/MSW until endpoints land. | Backend-1 |
| Access-control holes (IDOR on claims/receipts, self-approval, double payout) | Med / High (security + auditor review) | Server-side checks + tests for each; DB unique constraints. | Backend-1 |
| Audit trail not actually append-only | Med / Med | DB trigger rejecting UPDATE/DELETE on `audit_events`; one test proves it. | Backend-1 |
| Merge collisions at T+2:00 | High / Med | Path ownership (section 4); `git pull --rebase` before push; small commits. | All |
| Working on `pre-main`, not `feature/*` | Certain / Low | Branch per lane: `feature/policy-engine`, `feature/web-claims`, etc. | All |
| SRE + demo squeezed | High / High | T+3:10 freeze is non-negotiable. | Lead |

---

## 4. Team split – 4 people

Roles are owners, not silos: everyone prompts Claude and everyone reviews one teammate's
Claude output before merge.

| | Member | Role | Owns (paths) | Never touches |
|---|---|---|---|---|
| **A** | `<name>` | **Backend-1 + Lead/Architect** – domain core | `backend/` domain (claims, policy, approvals, audit), `backend/alembic/`, `backend/tests/`, `docs/adr/`, `CLAUDE.md` | `frontend/` |
| **B** | `<name>` | **Backend-2 + DevOps/SRE** – data, finance, platform | `backend/` (auditor, payout, dashboard, seed), `deploy/`, `.github/workflows/`, `tests/unit/` perf | domain core files owned by A |
| **C** | `<name>` | **UI/UX + QA** – design and verification | `docs/design/`, wireframes, design tokens, `tests/e2e/`, test plan, test cases + defect log (Excel), stories backlog | `backend/` |
| **D** | `<name>` | **Frontend** – React app | `frontend/` | `backend/` |

Shared docs (ideation, LLD, presentation, runbook, RCA, journal) are split in section 7.

### A – Backend-1 + Lead (domain core)

1. Freeze section 2 decisions; put business rules in `CLAUDE.md`.
2. Data model + Alembic migration: `departments, employees (manager_id, role), policy_rules (JSON config), claims, claim_lines, receipts (sha256), approval_steps, delegations, comments, audit_events, payout_batches, payout_items`.
3. Claim state machine (doc + code):
   `DRAFT → SUBMITTED → {AUTO_REJECTED | AUTO_APPROVED | PENDING_MANAGER}`;
   `PENDING_MANAGER → PENDING_AUDITOR (>25k) → PENDING_HEAD (>1L) → APPROVED`;
   any `PENDING_* → SENT_BACK → SUBMITTED` or `→ REJECTED`;
   `AUTO_APPROVED (sample-flagged) → PENDING_AUDITOR`; `APPROVED → IN_BATCH → PAID`.
4. **Policy engine, tests first** – one pytest per rule and per boundary (G1–G9).
5. Claims API: CRUD draft, lines, receipt upload (hash), submit; ownership enforced.
6. Approvals API: approve / reject / send back / comment / delegate; self-approval blocked; threshold routing.
7. Audit trail: written in the same transaction as every state change; DB trigger blocks UPDATE/DELETE.
8. ADR-001 approval-chain modelling; ADR-002 policy as configuration. Run the **skeptical finance auditor** prompt against the design.

### B – Backend-2 + DevOps/SRE

1. **First 30 min:** fix the platform – root compose (db, api, web, prometheus, grafana), root CI workflow, `.env.example`, move/align repo layout with A.
2. Seed script: 150 employees, 8 departments, hierarchy, 4 finance users, policy config, 3,000 historical claims over 12 months with planted duplicates and breaches – generated through A's policy engine. Runs as a compose one-shot.
3. Auditor queue API: filters (status, dept, category, amount range, flag, date), bulk approve, sample-audit flag (seeded RNG, 10%).
4. Payout API: create batch from APPROVED + cleared claims, export CSV (G15), mark PAID, unique constraint against double payment.
5. Dashboard API: spend by category / dept / month, violation counts, average approval time.
6. Metrics: `pending_approvals_total{level}`, `oldest_pending_approval_age_seconds`, HTTP latency histogram (already started in `observability.py`); Grafana dashboard JSON; Prometheus alert on oldest pending > threshold.
7. CI: ruff + black + pytest + `pip-audit` / `npm audit`; prove it fails on a deliberately broken test.
8. Locust run on claim list + dashboard; state targets (e.g. p95 < 500 ms at 50 users).
9. Runbook draft; lead the SRE drill hands-on.

### C – UI/UX + QA

1. Screen inventory + wireframes for 4 roles (`artifact-design`): claim capture (mobile-first), my claims, approver inbox with **side-by-side receipt viewer**, auditor queue (dense table + bulk bar), payout batch, dashboard, delegation, audit timeline.
2. Design tokens (colour, type, spacing, status badge colours for every state), empty / loading / error states for each table, accessibility basics (labels, focus order, contrast, keyboard).
3. Stories backlog in Excel with acceptance criteria – one story per must-have.
4. Test plan (scope, risks, entry/exit criteria) + Excel test cases generated rule-by-rule (`test-case-author`).
5. Playwright: **10 E2E cases** (list below) against the running stack.
6. **Stopwatch test** of the approver flow (target: approve a routine claim in < 30 s) – record times before/after a UI fix.
7. Keyboard pass + phone-width (375 px) pass; defect log kept live all afternoon.
8. Security checklist run with `security-review`; mark each finding real / false alarm.

Proposed E2E cases: (1) employee drafts, saves, reopens claim; (2) submit within limits → auto-approved; (3) missing receipt > 500 → auto-rejected with reason; (4) meal over 1,500 → routed, manager approves; (5) 30,000 claim → manager → auditor; (6) 1,20,000 claim → three levels; (7) manager sends back, employee edits, resubmits; (8) delegate approves while manager on leave; (9) auditor filters + bulk approves; (10) finance head creates payout batch, downloads CSV, claims show Paid. Plus negative: employee URL-hacks another claim id → 404.

### D – Frontend

1. Vite + React 19 app in `frontend/`, router, API client, mock-login (pick a seeded user → role).
2. Apply C's tokens; shared components: `DataTable` (sort, filter, select-all, bulk bar), `StatusBadge`, `EmptyState`, `ErrorState`, `Skeleton`, `ReceiptViewer`.
3. Employee: claim form with dynamic line items, receipt upload, draft/submit, policy result per line with reasons, my claims list + detail with audit timeline.
4. Approver: inbox, claim detail with side-by-side receipt viewer, approve / reject / send back / comment, delegation form.
5. Auditor: queue with filters, bulk approve, sample-audit badge.
6. Finance head: payout batch create + CSV download; dashboard (category, dept, month charts; violations; avg approval time).
7. Every screen: loading, empty and error states; works at 375 px; keyboard reachable.
8. Until B/A endpoints land, code against fixtures matching the API contract.

---

## 5. Build slices – the order of work

| Slice | Done when | Target |
|---|---|---|
| **S1 – thin end-to-end** | Employee submits a 2-line claim → policy engine runs → manager approves → `APPROVED`; audit row written; employee can't see others' claims. Running in compose. | **T+2:00** |
| **S2 – full chain + finance** | Thresholds to auditor/head, send back, delegation, auditor queue + bulk + sample audit, payout CSV → `PAID`. | **T+2:50** |
| **S3 – insight + ops** | Dashboard, metrics, Grafana, alert firing. | **T+3:10** |

**Cut order if behind** (cut features, never tests or artifacts): G20 claim-splitting → dashboard
charts become tables → delegation UI (keep API + test) → side-by-side viewer becomes a link →
auditor filters reduced to status + dept.

---

## 6. Time checkpoints per person

Clock assumes **T0 = 14:00**. Each row ends with a check: if it is not true at that time, the
person says so in chat and the Lead cuts scope.

| Slot | Clock | **A – Backend-1 + Lead** | **B – Backend-2 + DevOps/SRE** | **C – UI/UX + QA** | **D – Frontend** |
|---|---|---|---|---|---|
| T+0:25–0:45 | 14:25–14:45 | Gap decisions signed off; rules into `CLAUDE.md`; mentor clock confirmed | Root compose + root CI + layout fix; env green on all 4 laptops | Screen inventory; stories backlog skeleton | Vite app scaffolded in `frontend/`, runs in compose |
| **✔ 14:45** | | *Section 2 frozen* | *`docker compose up` brings db + api* | *Screens listed* | *Blank app served* |
| T+0:45–1:00 | 14:45–15:00 | Schema + migration; API contract (OpenAPI) published; C4 diagram + state machine | Seed script skeleton (employees, depts, hierarchy) | Wireframes (4 roles) + design tokens | Router, mock login, API client, shared components |
| **✔ 15:00** | | *Contract + schema merged* | *150 employees seeded* | *Wireframes + tokens reviewed by D* | *Login → role landing page* |
| T+1:00–1:30 | 15:00–15:30 | Policy-engine tests written (red), then engine (green) | 3,000 historical claims seeded via engine; metrics gauges | Test plan; Excel test cases per rule; ADR review | Claim form + line items + upload against fixtures |
| **✔ 15:30** | | *All rule tests green* | *Planted dup/breach counts verified* | *Test plan + cases done* | *Claim form renders all states* |
| T+1:30–2:00 | 15:30–16:00 | Claims API (draft, submit, upload, ownership) + manager approve; audit trail | Auditor queue API + bulk approve + sample audit | Playwright harness; E2E 1–4 | My claims, claim detail, approver inbox wired to real API |
| **✔ 16:00 – S1 gate** | | *S1 works end to end in compose* | *Queue API tested* | *E2E 1–4 run* | *S1 clickable in browser* |
| T+2:00–2:30 | 16:00–16:30 | Thresholds, send back, reject, delegation, self-approval block + tests | Payout batch + CSV + PAID; dashboard API | E2E 5–8; stopwatch test #1; phone/keyboard pass | Approver actions + receipt viewer; auditor queue table + bulk bar |
| T+2:30–2:50 | 16:30–16:50 | ADR-001/002 final; skeptical-auditor review → fixes | Grafana dashboard + alert on oldest pending; Locust run | E2E 9–10; defect log; `security-review` checklist | Payout screen; dashboard; delegation form |
| **✔ 16:50 – S2 gate** | | *Chain + delegation tests green* | *Alert fires; perf numbers recorded* | *10 E2E executed, defects logged* | *All role views working* |
| T+2:50–3:10 | 16:50–17:10 | LLD; journal entries; merge reviews | Fresh-clone test on a clean laptop; CI green; runbook draft | Final screens screenshots; stopwatch #2 | Empty/loading/error states polish; a11y fixes from C |
| **✔ 17:10 – FREEZE** | | *Everything except the drill is done* | | | |
| T+3:10–3:30 | 17:10–17:30 | Presentation (business alignment, security, perf) | Rehearse runbook commands | Demo rehearsal #1 (5 min, on the clock) | Demo data reset script check |
| T+3:30–4:15 | 17:30–18:15 | **Drill lead:** timeline file opened first; decides hypotheses | **Hands-on:** detect in Grafana, trimmed logs to Claude, fix + regression test | Verifies fix against the metric; writes RCA with `rca-runbook` | Keeps demo env clean; checks UI after fix |
| T+4:15–4:45 | 18:15–18:45 | Demo: problem + architecture + key decision | Demo: metrics, drill, RCA | Demo: failure handled well | Demo: live happy path (drives) |

**Emergency cut (if the drill really is at 15:30):** S1 only by 15:25 (A + D), B gets compose +
metrics + alert up by 15:25, C writes test plan + 4 E2E + backlog; everything else after the drill.

---

## 7. Artifact deliverables – owner and due time

Deck slide 10 ("ten artifacts"), the evaluation guidelines checklist, and the card's phase
expectations, merged.

| # | Artifact | Source | Owner | Reviewer | Due | Location |
|---|---|---|---|---|---|---|
| 1 | Code base, README, **one-command start** | Deck #10, guidelines | B | A | 17:10 | repo root, `deploy/` |
| 2 | Architecture: C4 context + container diagram | Guidelines, card | A | B | 15:00 | `docs/architecture.md` |
| 3 | **Two ADRs** (approval-chain model; policy as config) | Guidelines, card | A | C | 16:50 | `docs/adr/` |
| 4 | API contract (OpenAPI) | Guidelines | A | D | 15:00 | `docs/api-contract.md` + `/docs` |
| 5 | Claim state machine | Card | A | C | 15:00 | `docs/architecture.md` |
| 6 | Policy-as-configuration design | Card | A | B | 15:30 | `docs/adr/` + seed config |
| 7 | Skeptical-auditor bypass review (Claude output + team verdicts) | Card | A | C | 16:50 | `docs/security/approval-bypass-review.md` |
| 8 | **UI designs**: wireframes, design tokens, final screens | Deck #10, guidelines | C | D | 15:00 / 17:10 | `docs/design/` |
| 9 | Clickable UI with empty/loading/error states, a11y, phone width | Guidelines (heavily scored) | D | C | 16:50 | `frontend/` |
| 10 | Approver stopwatch test results | Card | C | D | 17:10 | `docs/design/stopwatch.md` |
| 11 | **Stories backlog with acceptance criteria (Excel)** | Deck #10 | C | A | 15:00 | `docs/backlog.xlsx` |
| 12 | **Test plan** (scope, risks, entry/exit) | Deck #10 | C | B | 15:30 | `docs/test-plan.md` |
| 13 | Unit tests per policy rule; threshold + delegation tests | Card | A | C | 16:50 | `tests/` |
| 14 | 10 written E2E cases + Playwright | Card, guidelines | C | D | 16:50 | `tests/e2e/`, Excel |
| 15 | **Test results + defect log** | Deck #10, guidelines | C | B | 17:10 | `docs/test-results/` |
| 16 | Security checklist run (findings real / rejected) | Card, deck (IT security 5 pts) | C | A | 16:50 | `docs/security/checklist.md` |
| 17 | Performance test: targets, Locust run, bottleneck | Deck (perf 5 pts) | B | A | 16:50 | `docs/perf/` |
| 18 | CI: lint + tests + dependency check, proven failing on a broken test | Card, guidelines | B | A | 16:00 | `.github/workflows/` |
| 19 | Metrics (queue size, approval age, latency), Grafana dashboard, alert | Card, guidelines | B | A | 16:50 | `deploy/prometheus/`, `deploy/grafana/` |
| 20 | **Runbook** | Deck #10, guidelines | B | C | 17:10 | `docs/runbook.md` |
| 21 | RCA + drill timeline | Guidelines | C (writes) / B (fix) | A | 18:15 | `docs/rca-<date>.md` |
| 22 | **Ideation document** (problem, options, chosen approach) | Deck #10 | A | D | 16:00 | `docs/ideation.md` |
| 23 | **LLD** (components, data model, interfaces) | Deck #10 | A | B | 17:10 | `docs/lld.md` |
| 24 | `CLAUDE.md` with business rules | Guidelines | A | all | 14:45, kept current | repo root |
| 25 | Claude usage journal, 5–8 entries, ≥1 correction | Guidelines | everyone adds, A curates | – | rolling, checked 17:10 | `docs/claude-journal.md` |
| 26 | Reusable asset (e.g. a `policy-rule-test-generator` skill) | Guidelines | C | A | 17:10 | `.claude/skills/` |
| 27 | **Presentation** incl. business alignment, IT security, performance | Deck #10 | A | all | 17:30 | `docs/presentation.pptx` |
| 28 | **Five-minute demo**, rehearsed | Deck #10, guidelines | all (D drives) | – | rehearsal 17:10, live 18:15 | – |

**Journal moments to capture** (one each, so the 5–8 entries span every phase): gap analysis
(arch), skeptical-auditor review (arch), wireframes/table states (UI), policy tests first
(dev), a **correction** where Claude got a rule boundary wrong (dev/test), security review
false alarm rejected (test), CI + secrets check (deploy), drill triage (SRE).

---

## 8. Demo script (fixed beats, deck slide 22)

| Beat | Time | Content | Who |
|---|---|---|---|
| Problem | 0:20 | "Breaches and duplicate receipts get paid and approvals take days." | A |
| Architecture + key decision | 0:40 | C4 container + approval chain as data (ADR-001) | A |
| Live happy path | 1:30 | Employee submits 30,000 claim → policy flags weekend line → manager approves → auditor bulk-approves → payout CSV → Paid | D |
| Failure handled well | 1:00 | Duplicate receipt auto-rejected with reason; employee can't open another's claim | C |
| Metrics, drill, RCA | 1:30 | Grafana: oldest pending alert; drill timeline and RCA | B |
