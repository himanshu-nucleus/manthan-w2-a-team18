# ADR-001: How approval chains are modelled

- **Status:** Accepted
- **Date:** 2026-11-27
- **Deciders:** Himanshu (backend lead), Diksha (backend 2, DevOps/SRE), Rahul (UI/UX, QA), Abhayraj (frontend)
- **Code:** `backend/app/services/chain.py`, `backend/app/models/approval.py`, `backend/app/services/approvals.py`, `backend/app/api/approvals.py`, `backend/app/policy/defaults.py`
- **Detail:** [policy-approvals-api.md](../policy-approvals-api.md)

## Context

A claim the policy engine routes for approval must pass a chain: the claimant's line manager always; a finance auditor when the total is above 25,000 INR; a finance head when it is above 1,00,000 INR. Approvers go on leave and delegate. Claims get sent back and resubmitted. Two approvers can click at the same moment. Finance auditors need to see, for any claim, who approved which step, when, and on whose behalf. The thresholds must be configuration, not code.

## Decision

The chain is **materialised as rows at submit time**, one `approval_steps` row per step, per submission round.

1. **Built at submit.** `build_chain()` runs inside the submit transaction, after the policy engine returns `ROUTE_FOR_APPROVAL`:
   - step 1: `line_manager`, `assigned_approver_id` = the claimant's `users.manager_id`, if that manager exists, is active and is not the claimant; otherwise a `finance_head` pool step;
   - step 2: `finance_auditor` pool step if `total_amount > approval_thresholds.finance_auditor` (25000);
   - step 3: `finance_head` pool step if `total_amount > approval_thresholds.finance_head` (100000).
   Thresholds are read from the `approval_thresholds` row in `policy_settings`, seeded from `defaults.py`. A claim of exactly 25,000 INR does not get the auditor step (strict `>`).
2. **Assigned or pool.** `assigned_approver_id` set means only that person (or their delegate) may act; `NULL` means any active user with `approver_role`, other than the claimant.
3. **No silent skips.** If any step has nobody eligible, submit fails with `409 no_eligible_approver`. A step is never dropped.
4. **One step open at a time.** Step 1 is `PENDING`, later steps `WAITING`. Approving opens the next step; approving the last sets the claim `APPROVED` and `approved_at`. Reject or send-back closes the remaining steps as `CANCELLED`. Step statuses: `WAITING`, `PENDING`, `APPROVED`, `REJECTED`, `SENT_BACK`, `CANCELLED`.
5. **Rounds.** `claims.submission_round` goes up on every submit; the new round gets a fresh chain from step 1. Earlier rounds stay as history (`GET /claims/{id}/approval-steps` returns every round, latest first).
6. **Actions name the step.** Approve, reject and send-back accept `step_id`. The claim row is locked and both claims and steps carry a `version` column (SQLAlchemy `version_id_col`). If `step_id` is no longer current: `409 step_already_decided`. Tested: two auditors approving at the same instant get one `200` and one `409`.
7. **Who acted.** Each step stores `acted_by_id`, `on_behalf_of_id`, `acted_at` and `comment`; the audit trail gets `STEP_APPROVED` (and `APPROVED` / `REJECTED` / `SENT_BACK` on the claim) with `on_behalf_of_id`.
8. **Delegation** is a `delegations` row (delegator, delegate, from/to date, active). It is followed **one hop only**. A delegate may act on a step assigned to the delegator, or on a pool step of the delegator's role. Creating one requires a delegate of the same or higher role, a start date of today or later, no self-delegation (also a DB check constraint), no overlap, and a delegate who is not away themselves.

## Alternatives considered

| Option | Why not |
| --- | --- |
| **Compute the chain on the fly** from the claim total and current settings each time someone opens the queue | A settings change or a manager change would silently re-route claims already in flight; there would be nothing to hang "who approved step 2" on except audit rows; concurrency control would have no row to lock or version. |
| **Workflow engine** (e.g. Temporal, Camunda, a BPMN library) | A three-step linear chain does not need one. It adds a service to run and learn in a hackathon, and the chain state would live outside PostgreSQL, away from the claim, the audit trail and the transaction that changes both. |
| **Single status field** on the claim (e.g. `PENDING_MANAGER`, `PENDING_AUDITOR`, `PENDING_HEAD`) | Fewer tables, but no record of who acted on each step or on whose behalf, no per-round history after a send-back, and every new step type means new statuses. The claim keeps one `PENDING_APPROVAL` status; the step rows hold the detail. |
| **Assign every step to a named person at submit** | Auditors and heads work as a pool; naming one person makes a single absence block the claim. Only step 1 (the manager) is named. |

## Consequences

- Each claim keeps the chain it was submitted with even if thresholds or the manager change later. The flip side: a threshold change does not move claims already pending.
- The pending queue is a query over `approval_steps` (assigned to me, open to my role, or delegated to me today), and claim visibility for managers uses the same rows.
- The auditor's bulk approve is the frontend calling `POST /claims/{id}/approve` with each selected `step_id` in turn; there is no bulk endpoint, so each approval passes the same checks and audit, and one failure does not hide the others.
- Payouts can check that every step of the latest round is `APPROVED` before paying an `APPROVED` claim.
- Approval rules (who may act) are in Python (`chain.py`), while thresholds are data. Changing the shape of the chain (e.g. adding a department head step) is a code change.
- There were no automated tests for thresholds or delegation when this was written; behaviour was checked with an 87-step manual API run and the concurrency test.

## Ways to bypass approvals we considered

Written from a skeptical finance auditor's point of view.

| Attempt | Status | How |
| --- | --- | --- |
| Approve my own claim | Blocked | The claimant can never act on any step of their own claim, directly or as someone's delegate (`403 not_current_approver`, audited as `ACCESS_DENIED`). |
| Be the approver on two steps of the same claim (e.g. `admin` as manager and finance head) | Blocked | One person, or anyone acting on their behalf, acts on at most one step per round. |
| Delegate my approvals to my own report or to myself | Blocked | Delegate must have the same or higher role; self-delegation refused by the service and a DB check constraint. |
| Chain delegations to reach a friendly approver | Blocked | Delegation is followed one hop only; delegating to someone who is away is refused. |
| Approve a step that has already moved on, or race a second approver | Blocked | `step_id` plus row lock and `version` → `409 step_already_decided`. |
| Edit the claim after it is approved, or while it is pending | Blocked | Owner edits only in `DRAFT` and `CLARIFICATION_REQUESTED`; resubmit builds a new chain from step 1 and re-runs the policy. |
| Have no manager so nobody checks step 1 | Blocked | Step 1 falls back to the finance head pool; if nobody is eligible, submit fails with 409 rather than skipping. |
| Keep each claim under 25,000 INR to avoid the auditor (split claims) | Partly blocked | `SPLIT_CLAIM` routes a claim when it and the employee's other ≤ 25,000 claims from the last 7 days total above 25,000. Splits spread over a longer window are outside this rule. Every claim above 500 INR still needs the manager. |
| Submit the same receipt twice | Partly blocked | `DUPLICATE_RECEIPT_NUMBER` marks the claim `DUPLICATE` (vendor and receipt number compared ignoring case and spaces). A misspelt vendor or changed receipt number escapes it; approvers still see the receipt. `DUPLICATE_RECEIPT_HASH` (same file) is off by default and can be switched on. |
| Lower a limit just before submitting | Open, but visible | Only the finance head can change rules (`PUT /policy-rules/{code}`), each change is a `RULE_UPDATED` audit row, and every evaluation stores the rule values it used. |
| Two managers approving each other's claims | Open | No rule can tell collusion from normal work; it shows in the audit trail (`STEP_APPROVED` with actor ids). |
| Get paid without full approval | Blocked | Payout takes only `APPROVED` / `AUTO_APPROVED` claims, and for `APPROVED` every step of the latest round must be `APPROVED`; `UNIQUE(payout_batch_items.claim_id)` stops a second payment. |
| Auto-approve small claims without anyone looking | Open by design | Claims with no findings and total ≤ 500 INR are auto-approved. The 10% sample audit that would catch abuse here is not built yet (the payout hook `held_for_sample_audit()` always returns false). |
| Erase the evidence afterwards | Blocked at app level | Audit rows are append-only (no API, ORM guards, DB triggers on `UPDATE`/`DELETE`/`TRUNCATE`) and hash-chained; `GET /audit-logs/verify` detects edits. Someone who controls the database itself can still rewrite the chain. |
