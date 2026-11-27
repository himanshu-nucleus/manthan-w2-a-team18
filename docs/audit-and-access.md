# Audit Trail and Claim Visibility

27 Nov 2026 · Diksha Mandal · branch `feature/backend/audit-trail`

Every state change, every receipt or file download, every failed login and every refused access writes one append-only audit row, and every claim endpoint goes through one visibility rule: an employee sees only their own claims, and a probe for someone else's claim looks exactly like a claim that does not exist.

## Who sees which claim

One rule (`app/services/access.py`) used by every claim endpoint; lists apply it inside the SQL query.

| Role | Sees |
| --- | --- |
| `employee` | Own claims only |
| `line_manager` | Own claims, direct reports' claims, and claims whose approval chain names them (assigned, acted, on behalf of) or names someone who delegated to them today |
| `finance_auditor`, `finance_head` | Every claim |

- A claim the caller may not see returns **404 `claim_not_found`**, the same body as a claim that does not exist. Checked on all 13 claim endpoints for another employee and for an unrelated manager.
- Only the owner can change, submit or upload to a claim; `employee_id` is never read from a request body.
- Receipts download only through their claim, with a server-generated file name confined to the upload folder (no `../`).
- **Change from before:** line managers no longer see every claim in the company.

## What is audited

| Action | Entity | Actor |
| --- | --- | --- |
| `CREATED`, `UPDATED`, `SUBMITTED`, `RESUBMITTED` | `claim` | Claimant |
| `POLICY_EVALUATED`, `CHAIN_BUILT` | `claim` | **SYSTEM** |
| `ATTACHMENT_UPLOADED`, `ATTACHMENT_DOWNLOADED` | `claim_attachment` (metadata only: name, size, SHA-256) | User |
| `STEP_APPROVED` | `approval_step` | Approver, with `on_behalf_of_id` for a delegate |
| `APPROVED`, `REJECTED`, `SENT_BACK` | `claim` | Approver; reason in `comment` |
| `COMMENTED` | `claim_comment` | User; text in `comment` |
| `DELEGATED`, `DELEGATION_REVOKED` | `delegation` | Delegator |
| `RULE_CREATED`, `SETTING_CREATED` | `policy_rule`, `policy_setting` | **SYSTEM** (defaults at startup) |
| `RULE_UPDATED` | `policy_rule` | Finance head |
| `BATCH_CREATED`, `CSV_EXPORTED` | `payout_batch` | Finance user |
| `MARKED_PAID` | `claim` | Finance user |
| `USER_CREATED` | `user` (never the password) | Finance head |
| `LOGIN_FAILED` | `user` (the username typed, never the password) | **SYSTEM** |
| `ACCESS_DENIED` | `claim`, `approval_step`, `delegation`, `user`, `endpoint` | The refused user; `changes` holds the request (`GET /api/v1/claims/5`) and the reason |

Rows written before migration `0006` may carry older names: `POLICY_RULE_UPDATED`, `BATCH_EXPORTED`, `PAID`, `DELEGATION_CREATED`, `DELEGATION_CANCELLED`, and `UPDATED` for an upload. They are never rewritten.

Every row stores: `entity_type`, `entity_id`, `claim_id` (whenever a claim is involved), `action`, `changes` (`{"field": {"old", "new"}}`), `actor_id` (null for SYSTEM) and `actor_role`, `on_behalf_of_id`, `comment`, `ip_address`, `request_id`, `created_at` (server UTC), and `prev_hash` / `hash`.

**Request id:** send `X-Request-ID` (letters, digits, `.` `_` `-`, up to 64) or one is generated; it is returned in the response header and stored on every row the request writes.

## Same transaction, no gaps

- `audit.record(...)` (`app/services/audit.py`) is the only writer, called from the service layer in the same database session as the action: if either fails, both roll back, and a rolled-back action leaves no row (checked: a refused submit wrote nothing).
- Chosen over a decorator or an ORM hook because only the service knows the old and new values, the reason, and who acted on whose behalf; FastAPI has no service-level interception point.
- `ACCESS_DENIED` and `LOGIN_FAILED` are the exception: written in their **own** transaction (`record_detached`) so they survive the request failing.

## Append-only

| Layer | What stops a change |
| --- | --- |
| API | No create, update or delete audit endpoints (`POST` / `DELETE /audit-logs` → 405) |
| Service | `audit.record` inserts; the module has no update or delete function |
| ORM | Mapper and session guards raise `AuditImmutable` on `session.delete(row)`, attribute changes, and bulk `update()` / `delete()` |
| Database | Triggers refuse `UPDATE`, `DELETE` (migration 0002) and `TRUNCATE` (0006) |
| No cascade | `audit_events` has no foreign key to claims; nothing deletes audit rows when other rows go |
| Tamper evidence | `hash = SHA-256(prev_hash + canonical row content)`; writers take a PostgreSQL advisory lock until commit so the chain stays linear |

**Tested:** a table owner who disables the trigger and edits row 6 is caught by `GET /audit-logs/verify` (`"first_broken_id": 6, "problem": "row content changed"`). Remaining risk: whoever controls the database can drop triggers and rewrite the whole chain; keeping the database credentials separate from application operators is the control for that.

## APIs

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/claims/{id}/audit` | Anyone who can see the claim | The claim's history, newest first, including approval steps, attachments, comments and payment; `ACCESS_DENIED` rows are left out |
| GET | `/api/v1/audit-logs` | Finance head, finance auditor | Search, newest first: `entityType`, `action` (case-insensitive), `actorId`, `claimId`, `fromDate`, `toDate` (IST days, inclusive), `limit` (≤ 200), `offset` |
| GET | `/api/v1/audit-logs/verify` | Finance head | Recompute the hash chain |

```json
GET /api/v1/audit-logs?action=ACCESS_DENIED&claimId=2&limit=1
200 OK
{"items": [{
   "id": 41, "entity_type": "claim", "entity_id": 2, "claim_id": 2, "action": "ACCESS_DENIED",
   "changes": {"request": "POST /api/v1/claims/2/comments",
               "reason": "claim belongs to someone the caller may not see"},
   "actor_id": 3, "actor_role": "line_manager", "on_behalf_of_id": null, "comment": null,
   "ip_address": "127.0.0.1", "request_id": "4f0c1d2e9a7b4c55a1f0e3b2c9d8e7f6",
   "hash": "9e1c…", "created_at": "2026-11-27T12:40:11.204118Z"}],
 "total": 18, "limit": 1, "offset": 0}
```

A delegate's approval in the claim history:

```json
{"entity_type": "approval_step", "entity_id": 1, "claim_id": 2, "action": "STEP_APPROVED",
 "actor_id": 6, "actor_role": "line_manager", "on_behalf_of_id": 2, "comment": "OK on behalf",
 "changes": {"acted_by": {"old": null, "new": "manager on behalf of manager1"}, "...": "..."},
 "request_id": "smoke-1a2b3c4d", "ip_address": "127.0.0.1", "hash": "…"}
```

```json
GET /api/v1/audit-logs/verify
200 OK
{"checked": 60, "valid": true, "unchained_rows": 0, "first_broken_id": null, "problem": null}
```

`unchained_rows` counts rows written before migration `0006`, which have no hash.

## Setup after pulling

```powershell
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
```

Migration `0006_audit_hardening` only adds columns, indexes and the TRUNCATE trigger; no existing row is changed.

## Verification

- Automated suite: 142 tests pass (two updated for the agreed changes: an unrelated manager now gets 404 instead of 403, and the rule-change helper ignores the SYSTEM `RULE_CREATED` rows).
- Manual run against PostgreSQL: 96 checks (IDOR sweep of 13 endpoints × 2 users, audit coverage, SYSTEM actor, request id, denials, failed login, database refusals, tamper detection) and 4 ORM guard checks.
- Gaps: no rate limit on denied attempts (a prober fills the audit table); `LOGIN_FAILED` keeps the typed username, which could be a mistyped password if someone types it in the wrong box.
