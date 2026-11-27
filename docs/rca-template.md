# RCA template (SRE drill)

Copy the template section into a new file or the incident thread, fill every field, and link the
fix PR. Blameless: describe what the system and process allowed, not who slipped.
Commands and metric names are in `docs/runbook.md`.

---

## Template

### Summary

| Field | Value |
|---|---|
| Incident ID / title | |
| Severity | High / Medium / Low |
| Status | Open / Mitigated / Resolved |
| Incident lead | |
| Date | |
| Fix PR | |

One paragraph: what broke, for whom, for how long, how it was fixed.

### Timeline (local time, IST)

| Time | Event |
|---|---|
| HH:MM | Change that introduced the problem (commit / deploy / config) |
| HH:MM | First signal (alert fired / user report / test failure) |
| HH:MM | Acknowledged by |
| HH:MM | Root cause identified |
| HH:MM | Mitigation / fix deployed |
| HH:MM | Verified against the metric |
| HH:MM | Closed |

### Detection

- How found: alert name (`ApiDown`, `ApiHighLatencyP95`, `ApiHighErrorRate`), dashboard panel,
  health endpoint, test, or person.
- Metric and query used (PromQL / SQL), with the value seen.
- Time to detect (first bad request -> first signal). If no alert fired, say why and add a follow-up.

### Impact

- Who was affected (roles, number of users/claims), which endpoints or screens.
- Duration. Data loss or corruption: yes/no (check the audit chain: `GET /api/v1/audit-logs/verify`).

### Root cause (5 whys)

1. Why did users see the failure?
2. Why did that happen?
3. Why ...?
4. Why ...?
5. Why did our process not catch it earlier?

Root cause in one sentence:

### Fix

- Immediate mitigation:
- Permanent fix (files, PR):

### Verification

- Metric before and after (same query as in Detection), with timestamps.
- Manual check performed (command / screen / user role).

### Regression test added

- Test file and test names; confirm they **failed before** the fix and **pass after**.

### Follow-ups

| Action | Owner (role/person) | Due | Tracking |
|---|---|---|---|
| | | | |

### Lessons

- What went well:
- What went badly:
- Where we got lucky:

---

## Worked example: D1 - `POST /claims` returns 500 for null optional text

### Summary

| Field | Value |
|---|---|
| Incident ID / title | D1 - POST/PUT `/api/v1/claims` 500 on null or blank optional text |
| Severity | High |
| Status | Resolved |
| Incident lead | Frontend (Abhayraj, with Claude Code) |
| Date | 2026-11-27 |
| Fix PR | #15 (branch `fix/backend-validation`, commit `bde6b80`) |

Saving or editing a claim draft from the real UI failed with HTTP 500 whenever an optional text
field (vendor, description, city, receipt_number, title) was sent as `null` or blank. Employees
could not save drafts that left optional fields empty. Found before release during a real-backend
smoke run; fixed in the API so it validates those fields and returns 422 for bad input instead of 500.

### Timeline (2026-11-27, IST)

Only the fix commit time is recorded in git; other rows are in order but without exact times.

| Time | Event |
|---|---|
| - | Claim form built and tested by a sub-agent against MSW mocks; all frontend tests passed. |
| - | Lead ran a scripted real-browser smoke against the real backend: draft save returned 500. |
| - | Reproduced with the API directly; traced to the claim request schema. |
| - | User instruction: "if you find any bug in backend then you fix it" -> fix on `fix/backend-validation`. |
| 17:48 | Fix committed (`bde6b80`: "fix: return 422, not 500, for null or blank optional claim text"). |
| - | PR #15 merged into `main`; real-backend smoke re-run: draft save succeeds. |

### Detection

- Found by the real-backend smoke (Playwright script via node, not the MSW-backed test suite).
- Signal: HTTP 500 on `POST /api/v1/claims`. In Prometheus this shows as
  `http_requests_total{path="/api/v1/claims",status="500"}` increasing, and would feed
  `ApiHighErrorRate` (5xx > 5% for 5m) under real traffic.
- Not caught earlier because every frontend test ran against mocks, which accepted `null`.

### Impact

- Employees (and anyone creating claims) could not save a draft with empty optional fields.
- Endpoints: `POST /api/v1/claims`, `PUT /api/v1/claims/{claim_id}`.
- Found pre-release, so no production users were affected. No data written on failed requests.

### Root cause (5 whys)

1. Why did the user see an error? `POST /claims` returned 500.
2. Why 500? Request validation raised a `TypeError` that was not turned into a 422.
3. Why a `TypeError`? The fields were declared as `Field(max_length=...)` on `str | None`, so
   pydantic ran the length constraint against `None`.
4. Why was that not caught by backend tests? No test sent `null` or blank values for optional text fields.
5. Why was it not caught before integration? Frontend work was verified only against MSW mocks;
   a real-backend smoke run was not part of the definition of done.

Root cause: the length constraint was attached to the whole `Optional` type instead of to `str`
inside it, and no test exercised null optional text.

### Fix

- Immediate mitigation (frontend): the claim form drops null fields before sending
  (`frontend/src/features/claims/components/claim-form.tsx`).
- Permanent fix (backend): put the constraint on `str` inside the union using `StringConstraints`
  (`backend/app/schemas/claim.py`). Bad input now returns 422 with per-field errors; `null` is accepted.
  Shipped in PR #15 together with D2.

### Verification

- Real-backend smoke re-run: employee creates a draft, uploads a receipt, submits; claim reaches
  `PENDING_APPROVAL`.
- Metric check: no new `status="500"` series for `path="/api/v1/claims"` in
  `http_requests_total` during the re-run.

### Regression test added

- `backend/tests/test_schema_validation.py`: 16 new tests covering null and blank optional text on
  create and update. They failed before the fix and pass after. Backend suite: 142 passing at the time.

### Follow-ups

| Action | Owner | Status |
|---|---|---|
| Add a real-backend smoke run to the definition of done for every screen | Frontend (Abhayraj) + QA (Rahul) | Proposed |
| Keep null-dropping in the form, but do not rely on it; the API must validate | Frontend | Done |
| Add null/blank cases whenever a new optional text field is added to a schema | Backend (Himanshu) | Proposed |

### Lessons

- Went well: the smoke run against the real backend found it before release; the fix came with tests.
- Went badly: green mock-based tests gave false confidence.
- Lucky: found before the drill, not during it.
