# Payout Batch and CSV Export API

27 Nov 2026 Â· Diksha Mandal Â· branch `feature/backend/approved-claims`

A finance head or finance auditor picks an approval-date range (or TODAY); every eligible approved claim in it goes into one payout batch, is marked `PAID`, and the batch downloads as a mock bank CSV. Base URL, login token, error format and money format are as in [claims-api.md](claims-api.md); full contract in [openapi.json](openapi.json).

## Rules

**Who:** `finance_head` and `finance_auditor` only; everyone else gets `403`. Employees see their claim's `PAID` status, `paid_at` and `payout_batch_reference` through the existing claim APIs.

**Date range** (business time zone `TIMEZONE`, default `Asia/Kolkata`):

- `range=TODAY` means from = to = today's IST date.
- Otherwise `fromDate` and `toDate` are both required, as `YYYY-MM-DD`; neither may be in the future; `fromDate` â‰¤ `toDate`; no maximum length.
- The range filters the claim's **approval date** (new column `claims.approved_at`), both days included.
- Breaking a rule returns `400 invalid_date_range` with the reason. A wrongly formatted date returns `422`.

**Eligible claim** â€” all of:

1. Status `APPROVED` or `AUTO_APPROVED`.
2. `approved_at` within the range.
3. Not in a batch and not `PAID`.
4. Not held for sample audit (hook `held_for_sample_audit()`; always false until the 10% sample audit is built).
5. For `APPROVED`: every approval step of its latest round is `APPROVED`.

Every eligible claim in the range goes into the batch; none can be left out. The amount is the sum of the claim's approved lines (today every line of an approved claim; line-level rejection does not exist). If any eligible claim's stored total differs from the sum of its lines, nothing is created and the response is `409 claim_amount_mismatch` naming the claims.

**Approval date:** set when the last approval step approves (`APPROVED`) or when the policy auto-approves (`AUTO_APPROVED`). Migration `0005_payouts` back-fills it for claims approved before this change.

## What creating a batch does

All in one database transaction; any failure undoes everything:

1. Batch creation is serialised (PostgreSQL advisory lock) and the eligible claims are locked (`SELECT â€¦ FOR UPDATE`).
2. A `payout_batches` row: `PB-<IST date>-<NNN>`, numbering restarting at 001 each day.
3. One `payout_batch_items` row per claim, with `transaction_reference` `<batch>-0001`, `-0002`, â€¦ and a copy of every value printed in the file.
4. Each claim: status `PAID`, `paid_at`, `payout_batch_id`; audit event `PAID`.
5. Audit event `BATCH_CREATED` on the batch.

No eligible claims â†’ `422 no_eligible_claims` and no batch. The database refuses a second payment of the same claim (`UNIQUE(payout_batch_items.claim_id)`).

## CSV file

- Name `payout_<batchReference>.csv`, UTF-8 without BOM, CRLF line endings, standard CSV quoting.
- Header, one row per claim in approval-date order, then `TRAILER,<claimCount>,<totalAmount>`.
- `ValueDate` is the batch's creation date (IST) as `dd-mm-yyyy`; `EmployeeId` is `EMP` + 4-digit user id; `ClaimId` is `CLM-` + 6-digit claim id; `Amount` has 2 decimals, no separators.
- Any value starting with `=`, `+`, `-`, `@`, tab or carriage return is prefixed with `'` (formula injection).
- Built only from the saved batch and items, so every download is byte-identical. Each download writes a `BATCH_EXPORTED` audit event, increments `export_count` and sets the batch to `EXPORTED`.

```
BatchReference,TransactionReference,ValueDate,EmployeeId,BeneficiaryName,Department,ClaimId,Amount,Currency,Narration
PB-20261127-001,PB-20261127-001-0001,27-11-2026,EMP0004,Employee One,Engineering,CLM-000007,400.00,INR,Expense reimbursement CLM-000007
PB-20261127-001,PB-20261127-001-0002,27-11-2026,EMP0004,Employee One,Engineering,CLM-000008,30000.00,INR,Expense reimbursement CLM-000008
PB-20261127-001,PB-20261127-001-0010,27-11-2026,EMP0005,Employee Two,Engineering,CLM-000023,1234.50,INR,Expense reimbursement CLM-000023
PB-20261127-001,PB-20261127-001-0011,27-11-2026,EMP0012,"'=HYPERLINK(""http://x"",""click"")",Engineering,CLM-000025,250.00,INR,Expense reimbursement CLM-000025
TRAILER,11,186184.50
```

(Rows 0003â€“0009 left out here; the last row shows a formula-like name neutralised.)

## Endpoints

All under `/api/v1/payouts`; 401 without a token, 403 for other roles.

| Method | Path | Purpose | Success | Errors |
| --- | --- | --- | --- | --- |
| GET | `/eligible-claims?range=TODAY` or `?fromDate=&toDate=` | Preview claims, count and total; changes nothing | 200 | 400, 409, 422 |
| POST | `/batches` | Body `{"range": "TODAY"}` or `{"fromDate": "...", "toDate": "..."}`; creates the batch, claims become `PAID` | 201 | 400, 409, 422 |
| GET | `/batches?limit=&offset=` | Batches, newest first | 200 | 422 |
| GET | `/batches/{id}` | Batch with its items | 200 | 404 |
| GET | `/batches/{id}/export` | The CSV (`text/csv`, `Content-Disposition: attachment`) | 200 | 404 |

### Preview

```json
GET /api/v1/payouts/eligible-claims?range=TODAY
200 OK
{"from_date": "2026-11-27", "to_date": "2026-11-27", "claim_count": 11, "total_amount": "186184.50",
 "claims": [
   {"claim_id": 7, "claim_code": "CLM-000007", "employee_id": 4, "employee_code": "EMP0004",
    "beneficiary_name": "Employee One", "department": "Engineering", "status": "AUTO_APPROVED",
    "approved_at": "2026-11-27T11:03:07.098771Z", "amount": "400.00"},
   {"claim_id": 8, "claim_code": "CLM-000008", "employee_id": 4, "employee_code": "EMP0004",
    "beneficiary_name": "Employee One", "department": "Engineering", "status": "APPROVED",
    "approved_at": "2026-11-27T11:03:07.464648Z", "amount": "30000.00"}]}
```

### Create

```json
POST /api/v1/payouts/batches
{"range": "TODAY"}
```

```json
201 Created
{"id": 1, "batch_reference": "PB-20261127-001", "from_date": "2026-11-27", "to_date": "2026-11-27",
 "value_date": "2026-11-27", "claim_count": 11, "total_amount": "186184.50", "currency": "INR",
 "status": "CREATED", "file_name": "payout_PB-20261127-001.csv", "export_count": 0,
 "first_exported_at": null, "created_by": 8, "created_at": "2026-11-27T11:46:34.371539Z"}
```

A claim afterwards (`GET /api/v1/claims/23`, extract):

```json
{"id": 23, "status": "PAID", "total_amount": "1234.50", "approved_at": "2026-11-27T11:46:32.848430Z",
 "paid_at": "2026-11-27T11:46:34.397037Z", "payout_batch_reference": "PB-20261127-001"}
```

### Batch detail

`GET /api/v1/payouts/batches/1` returns the batch summary fields plus `items`:

```json
{"...": "...", "status": "EXPORTED", "export_count": 2,
 "items": [{"transaction_reference": "PB-20261127-001-0001", "claim_id": 7, "claim_code": "CLM-000007",
            "employee_id": 4, "employee_code": "EMP0004", "beneficiary_name": "Employee One",
            "department": "Engineering", "amount": "400.00",
            "narration": "Expense reimbursement CLM-000007"}]}
```

### Errors

```json
400 Bad Request
{"error": {"code": "invalid_date_range", "message": "toDate cannot be in the future (today is 2026-11-27).",
           "details": {"today": "2026-11-27"}}}
```

```json
422 Unprocessable Content
{"error": {"code": "no_eligible_claims", "message": "No approved claims in the selected range.",
           "details": {"from_date": "2026-11-27", "to_date": "2026-11-27"}}}
```

```json
409 Conflict
{"error": {"code": "claim_amount_mismatch",
           "message": "A claim's total does not match the sum of its lines; no batch was created.",
           "details": {"claims": [{"claim_id": 22, "total_amount": "301.00", "sum_of_lines": "300.00"}]}}}
```

Other 400 messages: "fromDate and toDate are both required unless range=TODAY.", "fromDate must be on or before toDate.", "Send either range=TODAY or fromDate and toDate, not both."

## How double, wrong or unapproved payment is prevented

| Risk | Guard |
| --- | --- |
| Two finance users create batches at once | Creation serialised + claims row-locked; tested: one `201` with 3 claims, the other `422`, no claim in two batches |
| Same claim in two batches | `UNIQUE(claim_id)` on items; `PAID` and batched claims are never eligible |
| File downloaded and uploaded twice | Same saved batch every time; each download audited and counted in `export_count` |
| Amount changed after approval | Approved and paid claims cannot be edited; lines re-summed at creation, mismatch â†’ `409` |
| Rounding | Decimal end to end (`NUMERIC`), formatted from saved amounts; trailer total = sum of rows |
| Paid without approval | Only `APPROVED` / `AUTO_APPROVED` with `approved_at`; `APPROVED` also needs every step approved; sample-audit hook |
| Spreadsheet formula injection | `'` prefix on `= + - @`, tab, CR |

## Setup after pulling

```powershell
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
cd ..; Get-Content backend\db\seed.sql | docker compose exec -T db psql -U manthan -d manthan -v ON_ERROR_STOP=1
```

Migration `0005_payouts` (after `0004_policy_decisions`) adds the batch tables, `PAID`, `claims.approved_at` / `paid_at` / `payout_batch_id` and `users.department`; the seed fills departments for the demo users. Optional `.env`: `TIMEZONE=Asia/Kolkata`.

## Known gaps

- No way to void a batch or move claims back from `PAID` if the bank rejects the file.
- The 10% sample audit is a hook only.
- `EmployeeId` and `ClaimId` are derived from database ids until the synthetic data brings real codes.
- No automated tests yet; behaviour checked with a 59-step API run including the concurrency race.
