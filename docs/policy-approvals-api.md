# Policy Engine and Approval Chain API

27 Nov 2026 · Diksha Mandal · describes `main`

Submitting a claim now runs a configurable policy engine over every line and either auto-approves it, auto-rejects it with reasons, marks it `DUPLICATE` when it repeats another claim's receipt, or routes it through a manager → finance auditor → finance head chain. Base URL, login token, error format and money format are the same as in [claims-api.md](claims-api.md). The full contract is [openapi.json](openapi.json).

## Claim states

```
DRAFT ─submit─► SUBMITTED ─policy─┬─► AUTO_APPROVED
                                 ├─► AUTO_REJECTED                       (final)
                                 ├─► DUPLICATE                           (final)
                                 └─► PENDING_APPROVAL ─approve last step─► APPROVED
                                        ├─reject──────► REJECTED          (final)
                                        └─send back───► CLARIFICATION_REQUESTED ─edit + resubmit─► SUBMITTED
```

- `SUBMITTED` is transient: the policy runs in the same request, so a claim never rests there.
- `DUPLICATE` is set when a line has the same vendor, amount and receipt number as a line on another claim (see `DUPLICATE_RECEIPT_NUMBER` below). It is final: no approval chain, and the claim cannot be edited.
- The owner can edit (PUT, upload receipts) only in `DRAFT` and `CLARIFICATION_REQUESTED`; anything else, including `DUPLICATE`, returns `409 claim_not_editable`.
- Resubmitting after a send-back re-runs the policy and builds a **new chain from step 1** (`submission_round` goes up by 1; earlier rounds stay in the history).
- `PAID`, payout batches and the 10% sample audit are not built yet; the states leave room for them.

## Policy engine

Rules are rows in the `policy_rules` table. The default rules and settings live in `backend/app/policy/defaults.py`; at startup the API inserts any rule (by `code`) or setting (by `key`) that is missing and **never overwrites an existing row**, so changes made with `PUT /policy-rules/{code}` survive restarts. `backend/db/seed.sql` no longer inserts them. Changing a limit is a data change (`PUT /policy-rules/{code}`), never a code change.

Rule changes take effect on the next submit. The API has no versions, drafts, "publish" or "effective from" date: a `PUT` changes the live rule at once (the F3 Policy rules design shows those, but no endpoint exists for them).

Expense categories are `meal`, `hotel`, `local` (local conveyance, one line = one trip), `cab`, `airfare` and `other`. `cab`, `airfare` and `other` have no limit.

| Code | What it checks | Outcome when broken |
| --- | --- | --- |
| `MEAL_DAILY_LIMIT` | Meals ≤ 1,500 INR per day, summed across this claim and the employee's other claims (not draft, rejected, auto-rejected or duplicate) | Route |
| `HOTEL_NIGHTLY_LIMIT_T1` | Hotel ≤ 6,000 INR per night in tier-1 cities | Route |
| `HOTEL_NIGHTLY_LIMIT_OTHER` | Hotel ≤ 4,000 INR per night in other cities | Route |
| `LOCAL_TRIP_LIMIT` | Local conveyance (`local`) ≤ 2,000 INR per line (one line = one trip) | Route |
| `RECEIPT_MANDATORY` | Receipt file + receipt number above 500 INR | Auto-reject (backstop: submit already blocks this with 422) |
| `DUPLICATE_RECEIPT_NUMBER` | Same vendor + amount + receipt number as a line on any other counted claim of any employee, or as an earlier line of this claim (vendor and receipt number compared ignoring case and spaces) | Mark duplicate: the whole claim becomes `DUPLICATE` |
| `WEEKEND_SPEND` | Expense date on Saturday or Sunday | Route (manager attention) |
| `SPLIT_CLAIM` | This claim ≤ 25,000 but, with the employee's other ≤ 25,000 claims from the last 7 days, above 25,000 | Route |

Switched off by default (rows kept, `active` = false):

| Code | What it checked | Why it is off |
| --- | --- | --- |
| `CAB_TRIP_LIMIT` | Cab ≤ 2,000 INR per line | Replaced by `LOCAL_TRIP_LIMIT`; `cab` now has no limit |
| `DUPLICATE_LINE` | Same vendor + amount + date as an earlier line | Replaced by `DUPLICATE_RECEIPT_NUMBER` |
| `DUPLICATE_RECEIPT_HASH` | Same receipt file (SHA-256) as another claim's receipt | Replaced by `DUPLICATE_RECEIPT_NUMBER`. `PUT /policy-rules/DUPLICATE_RECEIPT_HASH` with `{"active": true}` switches it back on, which also catches the same file under a different receipt number (outcome auto-reject) |

A `DUPLICATE` claim is never counted towards meal totals or split detection, and is never the "original" another claim is compared with.

How the outcome is worked out:

1. Each line gets every reason it triggered; its outcome is the most severe one (`MARK_DUPLICATE` > `AUTO_REJECT` > `ROUTE_FOR_APPROVAL` > `AUTO_APPROVE`).
2. The claim outcome is the most severe of its lines and claim-level findings.
   `MARK_DUPLICATE` sets the claim status to `DUPLICATE` and builds no approval chain.
3. A claim with no findings is auto-approved only if its total is **≤ 500 INR** (setting `auto_approve_max_total`); otherwise it is routed with reason code `AUTO_APPROVE_LIMIT`.

The hotel city tier is worked out by the server from the `tier1_cities` setting (case-insensitive), never sent by the client. The receipt hash is computed on upload. Vendors are compared ignoring case and extra spaces.

Each submission stores one result row per line (and one claim-level row when needed) with the rule codes, reasons and the **rule values used at that moment**, so a later limit change does not rewrite history. The audit trail gets a `POLICY_EVALUATED` event.

**Adding a rule type:** subclass `RuleType` in `backend/app/policy/rules.py`, decorate it with `@register`, add a default row for it in `backend/app/policy/defaults.py` (or insert a `policy_rules` row) that uses it. The engine core does not change.

## Approval chain

| Step | Approver | When |
| --- | --- | --- |
| 1 | The claimant's manager (from `users.manager_id`) | Always |
| 2 | Any finance auditor | Claim total > 25,000 INR |
| 3 | Any finance head | Claim total > 1,00,000 INR |

Thresholds come from the `approval_thresholds` setting. The chain is built at submit and saved as `approval_steps` rows, so each claim keeps its own chain even if settings change. Only one step is `PENDING` at a time; later steps wait as `WAITING`.

Guard rails:

- The claimant can never act on their own claim, directly or as a delegate.
- One person acts on at most one step of a claim per round (so `admin` cannot be both manager and finance head of the same claim).
- No usable manager (none, inactive, or the claimant is a finance head without one) → step 1 goes to **any finance head except the claimant**.
- If any step has nobody eligible, submit fails with `409 no_eligible_approver`; a step is never skipped.
- Only the current step's approver, or their active delegate, can act; anyone else gets `403 not_current_approver`.
- Every action locks the claim row; claim and step rows carry a `version` column. Send `step_id` with an action: if that step is no longer current, `409 step_already_decided`. Tested: two auditors approving at the same instant → one `200`, one `409`.

Delegation: an approver on leave delegates to someone of the **same or higher role** for a date range starting today or later. No self-delegation, no overlapping delegations from one person, and no delegating to someone who is away themselves. Delegation is followed one hop only. The audit trail records `"acted_by": "manager on behalf of manager1"`.

## Endpoints

All under `/api/v1`; every one returns 401 without a valid token.

| Method | Path | Who | Purpose | Errors |
| --- | --- | --- | --- | --- |
| POST | `/claims/{id}/submit` | Owner | Submit or resubmit; runs policy, builds chain | 403, 404, 409, 422, 503 |
| GET | `/claims/{id}/policy-results` | Anyone who can see the claim | Latest per-line and claim-level outcomes and reasons | 404 |
| GET | `/policy-rules` | Any logged-in user (`?include_inactive=true` for finance head) | List rules | — |
| PUT | `/policy-rules/{code}` | Finance head | Change params, outcome, template or active flag; audited | 403, 404, 422 |
| GET | `/approvals/pending?limit=&offset=` | Anyone | My queue: steps assigned to me, open to my role, or delegated to me today | — |
| POST | `/claims/{id}/approve` | Current approver or delegate | Approve current step; last step approves the claim | 403, 404, 409 |
| POST | `/claims/{id}/reject` | Current approver or delegate | Reject; comment required; final | 403, 404, 409, 422 |
| POST | `/claims/{id}/send-back` | Current approver or delegate | Back to claimant; comment required | 403, 404, 409, 422 |
| GET | `/claims/{id}/approval-steps` | Anyone who can see the claim | Every round's steps, latest round first | 404 |
| POST | `/claims/{id}/comments` | Anyone who can see the claim | Add a comment; status unchanged | 404, 422 |
| GET | `/claims/{id}/comments` | Anyone who can see the claim | Comments, oldest first | 404 |
| POST | `/delegations` | Line manager, auditor, head | Delegate for a date range | 403, 422 |
| GET | `/delegations/me` | Anyone | Delegations I gave or received | — |
| DELETE | `/delegations/{id}` | The delegator | Cancel (204) | 404 |

`PUT /claims/{id}` with `"action": "submit"` still works and runs the same flow.

## Examples

### Submit

```
POST /api/v1/claims/{id}/submit        (no body: submits the claim as saved)
```

Returns `200` with the full claim (same shape as `GET /claims/{id}`), now also carrying `policy_outcome`, `policy_evaluated_at`, `submission_round` and `version`.

### 1. Auto-approve: 400 INR weekday meal

```json
200 OK  (POST /claims/7/submit)
{"id": 7, "status": "AUTO_APPROVED", "policy_outcome": "AUTO_APPROVE", "total_amount": "400.00",
 "submission_round": 1, "lines": [{"position": 1, "category": "meal", "amount": "400.00",
 "expense_date": "2024-02-14", "vendor": "Cafe A", "...": "..."}], "...": "..."}
```

```json
GET /api/v1/claims/7/policy-results
200 OK
{"claim_id": 7, "round": 1, "outcome": "AUTO_APPROVE", "evaluated_at": "2026-11-27T11:03:07Z",
 "lines": [{"line_position": 1, "outcome": "AUTO_APPROVE", "rule_codes": [], "reasons": [],
            "rule_snapshot": {}, "evaluated_at": "2026-11-27T11:03:07Z"}],
 "claim_level": []}
```

### 2. Route: 30,000 INR, hotel in Mumbai at 7,000 per night

```json
GET /api/v1/claims/8/policy-results
200 OK
{"claim_id": 8, "round": 1, "outcome": "ROUTE_FOR_APPROVAL",
 "lines": [
   {"line_position": 1, "outcome": "ROUTE_FOR_APPROVAL", "rule_codes": ["HOTEL_NIGHTLY_LIMIT_T1"],
    "reasons": ["Hotel 7,000.00 INR per night in Mumbai exceeds tier-1 limit of 6,000.00 INR"],
    "rule_snapshot": {"HOTEL_NIGHTLY_LIMIT_T1": {"params": {"limit": "6000", "city_tier": "tier1"},
                                                 "outcome_on_breach": "ROUTE_FOR_APPROVAL"}}},
   {"line_position": 2, "outcome": "AUTO_APPROVE", "rule_codes": [], "reasons": []}],
 "claim_level": []}
```

```json
GET /api/v1/claims/8/approval-steps
200 OK
[{"id": 1, "claim_id": 8, "round": 1, "step_order": 1, "approver_role": "line_manager",
  "assigned_approver_id": 2, "status": "PENDING", "acted_by_id": null, "on_behalf_of_id": null,
  "acted_at": null, "comment": null, "created_at": "..."},
 {"id": 2, "claim_id": 8, "round": 1, "step_order": 2, "approver_role": "finance_auditor",
  "assigned_approver_id": null, "status": "WAITING", "...": "..."}]
```

`assigned_approver_id: null` means any active finance auditor other than the claimant may act.

### 3. Duplicate: same vendor, amount and receipt number on another claim

Two employees each submit a `local` line of 400 INR. Claim #1 has vendor "Metro Cabs" and receipt number "RCPT-77". Claim #2 has vendor " metro  CABS " and receipt number "rcpt-77" (case and extra spaces are ignored).

```json
GET /api/v1/claims/2/policy-results
200 OK
{"claim_id": 2, "round": 1, "outcome": "MARK_DUPLICATE",
 "lines": [{"line_position": 1, "outcome": "MARK_DUPLICATE", "rule_codes": ["DUPLICATE_RECEIPT_NUMBER"],
            "reasons": ["Duplicate: same vendor, amount and receipt number as line 1 of claim #1"]}],
 "claim_level": []}
```

Claim #2 has status `DUPLICATE` and no approval steps (`GET /claims/2/approval-steps` returns `[]`). It cannot be edited:

```json
PUT /api/v1/claims/2
409 Conflict
{"error": {"code": "claim_not_editable", "...": "..."}}
```

Other reasons seen in testing:

- `Expense on Saturday 17-Feb-2024 is weekend spend; flagged for manager attention`
- `Meal spend 1,800.00 INR on 15-Feb-2024 exceeds daily limit of 1,500.00 INR`
- `Local conveyance 2,500.00 INR on 15-Feb-2024 exceeds per-trip limit of 2,000.00 INR`
- `Claims submitted in the last 7 days total 32,400.00 INR, above 25,000.00 INR: possible claim splitting`
- `Claim total 1,000.00 INR is above the auto-approve limit of 500.00 INR`

### Approver actions

```json
POST /api/v1/claims/8/approve
{"step_id": 1, "comment": "Client visit confirmed"}
```

Returns `200` with the claim. It stays `PENDING_APPROVAL` while later steps remain, and becomes `APPROVED` after the last one. Sending the same `step_id` again returns:

```json
409 Conflict
{"error": {"code": "step_already_decided", "message": "That approval step has already been decided.",
           "details": {"current_step_id": 2}}}
```

```json
POST /api/v1/claims/10/send-back
{"comment": "Why a Saturday?"}
```

Returns `200`, status `CLARIFICATION_REQUESTED`. `reject` takes the same body and returns status `REJECTED`. Without a comment both return `422`.

Someone who is not the current approver:

```json
403 Forbidden
{"error": {"code": "not_current_approver", "message": "You are not the approver of this claim's current step."}}
```

### Pending queue

```json
GET /api/v1/approvals/pending?limit=20&offset=0
200 OK
{"items": [{
   "step": {"id": 5, "claim_id": 12, "round": 1, "step_order": 1, "approver_role": "line_manager",
            "assigned_approver_id": 2, "status": "PENDING", "...": "..."},
   "claim": {"id": 12, "employee_id": 4, "title": "Local conveyance", "status": "PENDING_APPROVAL",
             "total_amount": "2500.00", "policy_outcome": "ROUTE_FOR_APPROVAL", "...": "..."},
   "on_behalf_of_id": 2}],
 "total": 1, "limit": 20, "offset": 0}
```

`on_behalf_of_id` is set when the item reaches you through a delegation.

### Comments

```json
POST /api/v1/claims/10/comments
{"body": "Moved to the correct date."}
```

```json
201 Created
{"id": 2, "claim_id": 10, "author_id": 4, "body": "Moved to the correct date.", "created_at": "..."}
```

Approve, reject and send-back comments are also added to this list.

### Delegations

```json
POST /api/v1/delegations
{"delegate_id": 6, "from_date": "2026-11-27", "to_date": "2026-11-30", "reason": "On leave"}
```

```json
201 Created
{"id": 1, "delegator_id": 2, "delegate_id": 6, "from_date": "2026-11-27", "to_date": "2026-11-30",
 "reason": "On leave", "active": true, "created_at": "...", "cancelled_at": null}
```

A refused delegation returns `422 delegation_invalid` with a message such as "The delegate must have the same or a higher role than you." `DELETE /delegations/1` returns `204`.

### Policy rules

```json
PUT /api/v1/policy-rules/MEAL_DAILY_LIMIT        (finance head)
{"params": {"limit": "2000"}}
```

```json
200 OK
{"code": "MEAL_DAILY_LIMIT", "name": "Meals up to 1,500 INR per day", "category": "meal",
 "rule_type": "DAILY_CATEGORY_LIMIT", "params": {"limit": "2000"},
 "outcome_on_breach": "ROUTE_FOR_APPROVAL", "active": true,
 "reason_template": "Meal spend {total} INR on {date} exceeds daily limit of {limit} INR",
 "updated_at": "...", "updated_by": 1}
```

`params` are validated against the rule type (`{"limit": "-5"}` → 422), and `reason_template` may only use that rule type's placeholders (`{nope}` → 422). Every change writes a `RULE_UPDATED` audit event (`POLICY_RULE_UPDATED` before migration 0006).

## New error codes

| Status | `error.code` | When |
| --- | --- | --- |
| 403 | `not_current_approver` | Not the current step's approver or their delegate; own claim; already acted on an earlier step |
| 403 | `forbidden` | Employee creating a delegation; non-head changing a rule |
| 404 | `delegation_not_found`, `policy_rule_not_found` | Not found, or not yours to cancel |
| 409 | `claim_not_pending` | Approver action on a claim that is not `PENDING_APPROVAL` |
| 409 | `step_already_decided` | `step_id` is no longer the current step |
| 409 | `no_eligible_approver` | Submit when a step would have nobody but the claimant |
| 422 | `delegation_invalid` | Self, lower role, past date, overlap, or chain |
| 503 | `policy_not_configured` | Rules or settings missing or invalid (missing defaults are re-inserted at startup; restart the API) |

## Setup after pulling

```powershell
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
cd ..; Get-Content backend\db\seed.sql | docker compose exec -T db psql -U manthan -d manthan -v ON_ERROR_STOP=1
```

Migration `0003` adds the tables; migration `0004` adds the `DUPLICATE` status, the `local` category and the `MARK_DUPLICATE` outcome. The API inserts the default rules and settings at startup (see `backend/app/policy/defaults.py`); the seed adds a second finance head `head2` / `head2` and switches off the replaced rules (`DUPLICATE_LINE`, `DUPLICATE_RECEIPT_HASH`, `CAB_TRIP_LIMIT`) in databases seeded earlier. Re-running the seed or restarting the API keeps limits already changed through the API.

## Known gaps

- Two managers approving each other's claims cannot be blocked by rules; it is visible in the audit trail.
- A deliberately misspelt vendor or a changed receipt number escapes the duplicate check; approvers still see the receipt. (A re-saved image only matters if `DUPLICATE_RECEIPT_HASH` is switched on.)
- Changing a rule does not re-evaluate claims already pending; it applies from the next submit.
- No automated tests yet for the policy rules, thresholds or delegation; behaviour was checked with an 87-step manual API run and a concurrency test.
