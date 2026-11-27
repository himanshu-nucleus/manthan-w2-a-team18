# Claims API Guide

27 Nov 2026 · Diksha Mandal

The Claims API is on branch `feature/Claims` (PR to `main` pending review): 7 endpoints to create, submit, read and audit expense claims with receipt uploads.

## Basics

Every claims endpoint needs a login token, returns JSON, and reports errors in one shared format.

| Item | Value |
| --- | --- |
| Base URL (local) | `http://localhost:8000/api/v1` |
| Swagger UI | http://localhost:8000/docs |
| Contract file | `docs/openapi.json` (regenerate with `python -m scripts.export_openapi` in `backend/`) |
| Auth | `POST /auth/login` with `{"username", "password"}`, then send `Authorization: Bearer <access_token>` |
| Token lifetime | 8 hours |
| Field names | `snake_case` (`employee_id`, `expense_date`), same as `/users` |
| Money | Strings with 2 decimals (`"850.00"`), INR only |
| Dates | `YYYY-MM-DD`; timestamps are ISO 8601 with time zone |

Every error has this shape:

```json
{"error": {"code": "claim_not_found", "message": "Claim not found.", "details": {}}}
```

`employee_id`, `status` and all timestamps are never read from a request body. The server sets them from the logged-in user.

## Claim flow

A claim is saved as `DRAFT` (any fields may be blank), receipts are uploaded to it, then it is submitted once and becomes `SUBMITTED` and read-only.

1. **Create a draft:** `POST /claims` with `"action": "draft"`. Returns the claim `id`.
2. **Upload receipts:** `POST /claims/{id}/attachments`, one file per call. Each returns an attachment `id`.
3. **Link receipts to lines:** `PUT /claims/{id}` with each line's `receipt_id` set to an attachment id, still `"action": "draft"`.
4. **Submit:** `PUT /claims/{id}` with `"action": "submit"`. Full validation runs; on success the status is `SUBMITTED`.
5. **After submit:** the claim can be read and audited, but any `PUT` returns `409 claim_not_editable`.

A claim with no receipts can skip steps 2 and 3 and be created and submitted in one call: `POST /claims` with `"action": "submit"`. Approval states (manager, auditor, finance head) arrive with the approval-chain work.

## Who can do what

An employee sees only their own claims; every other role sees all claims; only the owner can change a claim, and only while it is a draft.

| Action | `employee` | `line_manager`, `finance_auditor`, `finance_head` |
| --- | --- | --- |
| Create a claim | Own claim | Own claim |
| List claims | Own only | All claims |
| Read a claim, its audit trail, its receipts | Own only; others return **404** | Any claim |
| Edit or submit a claim | Own `DRAFT` only | Own `DRAFT` only; someone else's returns **403** |
| Upload a receipt | Own `DRAFT` only | Own `DRAFT` only |

An employee asking for another employee's claim gets 404, not 403, so claim ids cannot be probed.

## Endpoints at a glance

All paths are under `/api/v1`; every one returns 401 `not_authenticated` without a valid token.

| Method | Path | Purpose | Success | Other errors |
| --- | --- | --- | --- | --- |
| POST | `/claims` | Create a claim as draft or submit it | 201 | 422 |
| PUT | `/claims/{claim_id}` | Replace a draft's content; save as draft or submit | 200 | 403, 404, 409, 422 |
| GET | `/claims` | Paged list (`status`, `limit`, `offset`) | 200 | 422 |
| GET | `/claims/{claim_id}` | One claim with lines and attachments | 200 | 404 |
| GET | `/claims/{claim_id}/audit` | Change history, newest first | 200 | 404 |
| POST | `/claims/{claim_id}/attachments` | Upload one receipt (multipart field `file`) | 201 | 403, 404, 409, 413, 415, 422 |
| GET | `/claims/{claim_id}/attachments/{attachment_id}` | Download a receipt file | 200 | 404 |

## Create and update a claim

`POST /claims` and `PUT /claims/{claim_id}` take the same body. `PUT` replaces the whole claim: send every line each time, because lines left out are removed.

| Field | Type | Draft | Submit |
| --- | --- | --- | --- |
| `action` | `"draft"` or `"submit"` | Default `"draft"` | `"submit"` |
| `title` | text, up to 200 | Optional | Optional |
| `currency` | `"INR"` | Default `"INR"`; anything else is 422 | Same |
| `lines` | array, up to 50 | May be empty | At least 1 |
| `lines[].category` | `meal`, `hotel`, `cab`, `airfare`, `other` | Optional | Required |
| `lines[].amount` | decimal string, > 0, 2 places | Optional | Required |
| `lines[].expense_date` | `YYYY-MM-DD`, not in the future | Optional | Required |
| `lines[].vendor` | text, up to 200 | Optional | Required |
| `lines[].description` | text, up to 1000 | Optional | Optional |
| `lines[].city` | text, up to 100 | Optional | Required for `hotel` |
| `lines[].nights` | integer 1–365 | Optional | Required for `hotel` |
| `lines[].receipt_number` | text, up to 100 | Optional | Required when amount > 500 |
| `lines[].receipt_id` | attachment id on this claim | Optional | Required when amount > 500 |

Blank strings count as empty. `total_amount` is calculated by the server from the line amounts.

**Create a draft**

```json
POST /api/v1/claims
{
  "action": "draft",
  "title": "Client visit Pune",
  "lines": [{"category": "meal", "amount": "600", "expense_date": "2026-11-24"}]
}
```

```json
201 Created
{
  "id": 1, "employee_id": 4, "title": "Client visit Pune", "currency": "INR",
  "status": "DRAFT", "total_amount": "600.00", "submitted_at": null,
  "created_at": "2026-11-27T15:20:11+05:30", "updated_at": "2026-11-27T15:20:11+05:30",
  "created_by": 4, "updated_by": 4,
  "lines": [{
    "id": 1, "position": 1, "category": "meal", "amount": "600.00",
    "expense_date": "2026-11-24", "vendor": null, "description": null, "city": null,
    "nights": null, "receipt_number": null, "receipt_id": null
  }],
  "attachments": []
}
```

**Submit after uploading the receipt (attachment id 1)**

```json
PUT /api/v1/claims/1
{
  "action": "submit",
  "title": "Client visit Pune",
  "lines": [
    {"category": "meal", "amount": "600", "expense_date": "2026-11-24",
     "vendor": "Cafe Synthetic", "receipt_number": "INV-001", "receipt_id": 1},
    {"category": "cab", "amount": "250", "expense_date": "2026-11-24", "vendor": "Synthetic Cabs"}
  ]
}
```

Returns `200` with the full claim, now `"status": "SUBMITTED"`, `"total_amount": "850.00"` and `submitted_at` set.

**Submit with fields missing**

```json
422 Unprocessable Content
{
  "error": {
    "code": "validation_error",
    "message": "The claim cannot be submitted until these fields are fixed.",
    "details": {"fields": [
      {"field": "lines.0.vendor", "message": "is required to submit"},
      {"field": "lines.0.receipt_number", "message": "is required when the amount is above 500 INR"},
      {"field": "lines.0.receipt_id", "message": "is required when the amount is above 500 INR"}
    ]}
  }
}
```

Every problem is listed at once; `field` uses the 0-based line index, so the UI can highlight each input.

## Read claims

**List:** `GET /claims` returns summaries (no lines), most recently updated first.

| Query parameter | Values | Default |
| --- | --- | --- |
| `status` | `DRAFT`, `SUBMITTED` | all |
| `limit` | 1–100 | 20 |
| `offset` | 0 or more | 0 |

```json
GET /api/v1/claims?status=SUBMITTED&limit=20&offset=0
200 OK
{
  "items": [{
    "id": 1, "employee_id": 4, "title": "Client visit Pune", "currency": "INR",
    "status": "SUBMITTED", "total_amount": "850.00",
    "submitted_at": "2026-11-27T15:24:02+05:30",
    "created_at": "2026-11-27T15:20:11+05:30", "updated_at": "2026-11-27T15:24:02+05:30"
  }],
  "total": 1, "limit": 20, "offset": 0
}
```

**One claim:** `GET /claims/{claim_id}` returns the same full shape as create, with `lines` and `attachments`.

**Audit trail:** `GET /claims/{claim_id}/audit` returns every change, newest first. Each event lists only the fields that changed, with old and new values. Actions are `CREATED`, `UPDATED` and `SUBMITTED`; a receipt upload is an `UPDATED` event on `attachments.<id>`. The database rejects any edit or delete of audit rows.

```json
GET /api/v1/claims/1/audit
200 OK
[
  {"id": 4, "entity_type": "claim", "entity_id": 1, "action": "SUBMITTED", "actor_id": 4,
   "created_at": "2026-11-27T15:24:02+05:30",
   "changes": {"status": {"old": "DRAFT", "new": "SUBMITTED"},
               "submitted_at": {"old": null, "new": "2026-11-27T09:54:02+00:00"}}},
  {"id": 3, "action": "UPDATED", "changes": {
     "lines.0.vendor": {"old": null, "new": "Cafe Synthetic"},
     "lines.0.receipt_id": {"old": null, "new": 1},
     "total_amount": {"old": "600.00", "new": "850.00"}}},
  {"id": 2, "action": "UPDATED", "changes": {
     "attachments.1": {"old": null, "new": {"original_name": "receipt.png", "content_type": "image/png",
                                         "size_bytes": 72, "sha256": "8c6806d8…"}}}},
  {"id": 1, "action": "CREATED", "changes": {
     "title": {"old": null, "new": "Client visit Pune"},
     "lines.0.amount": {"old": null, "new": "600.00"}}}
]
```

The example is shortened: each event also carries `entity_type`, `entity_id`, `actor_id` and `created_at`.

## Receipts

Upload one file per call as `multipart/form-data` with the field name `file`; the claim must be your own `DRAFT`.

| Limit | Value | Error when broken |
| --- | --- | --- |
| File types | PDF, PNG, JPEG (declared type and real file content must match) | 415 `unsupported_file_type` |
| Size | 5 MB per file (`MAX_UPLOAD_BYTES`) | 413 `file_too_large` |
| Count | 10 per claim (`MAX_ATTACHMENTS_PER_CLAIM`) | 409 `attachment_limit_reached` |
| Empty file | Not allowed | 422 `empty_file` |

```
POST /api/v1/claims/1/attachments
Content-Type: multipart/form-data   (field: file=receipt.png)
```

```json
201 Created
{"id": 1, "claim_id": 1, "original_name": "receipt.png", "content_type": "image/png",
 "size_bytes": 72, "sha256": "8c6806d8d609…", "uploaded_by": 4,
 "uploaded_at": "2026-11-27T15:22:40+05:30"}
```

Frontend with `fetch`: build a `FormData`, `append("file", fileInput.files[0])`, and do not set `Content-Type` yourself, so the browser adds the boundary.

**Download:** `GET /claims/{claim_id}/attachments/{attachment_id}` streams the file with its real content type and original file name, with the same access rule as the claim. Use it for the approver's side-by-side receipt viewer.

Files are stored at `<UPLOAD_DIR>/claims/<claim_id>/<random name>`: locally `backend/uploads/` (gitignored), in Docker the `receipts` volume. The SHA-256 is stored for the duplicate-receipt rule in the policy engine.

## Errors

The frontend can switch on `error.code`; the HTTP status tells the general kind.

| Status | `error.code` | When |
| --- | --- | --- |
| 401 | `not_authenticated` | No token, bad token or expired token |
| 403 | `forbidden` | Changing or uploading to a claim you do not own |
| 404 | `claim_not_found` | Claim does not exist, or an employee asks for someone else's |
| 404 | `attachment_not_found` | Attachment not on that claim, or its file is missing |
| 409 | `claim_not_editable` | Changing a claim that is not `DRAFT` |
| 409 | `attachment_limit_reached` | 11th receipt on one claim |
| 413 | `file_too_large` | File over 5 MB |
| 415 | `unsupported_file_type` | Not PDF, PNG or JPEG, or content does not match the type |
| 422 | `validation_error` | Bad input (amount ≤ 0, future date, currency not INR, unknown category), a `receipt_id` from another claim, or submit with required fields missing |
| 422 | `empty_file` | Uploaded file has no content |

Invalid input returns **422**, matching the rest of the API, not 400. For `validation_error`, `details.fields` lists each `{field, message}`.

## Setup after pulling

The branch adds one package (`python-multipart`, needed for uploads) and one migration (`0002_claims`), so each backend laptop runs three commands once.

```powershell
cd backend; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..; Get-Content backend\db\seed.sql | docker compose exec -T db psql -U manthan -d manthan -v ON_ERROR_STOP=1
```

In Docker, rebuild the API image (`docker compose up --build`); receipts are kept in the new `receipts` volume.

Synthetic test logins (password = username):

| Username | Role | Reports to |
| --- | --- | --- |
| `admin` | finance_head | — |
| `manager` | line_manager | — |
| `auditor` | finance_auditor | — |
| `employee` | employee | `manager` |
| `manager1` | line_manager | `admin` |
| `auditor1` | finance_auditor | `admin` |
| `employee1` | employee | `manager1` |
| `employee2` | employee | `manager1` |

Use `employee1` and `employee2` to check that one employee cannot see the other's claims.

## Open decisions

- [ ] **Missing receipt above 500 INR:** today submit is blocked with 422. The work plan (G3, test case E2E-3) wants the claim submitted and then auto-rejected by the policy engine. Lead to decide; this changes when the policy engine lands.
- [ ] **Who sees all claims:** every non-employee role sees every claim today. Should a line manager see only their own team?
- [ ] **New package:** `python-multipart==0.0.34` was added to `requirements.txt` for uploads; team to confirm.
- [ ] **Review:** PR from `feature/Claims` into `main` needs one teammate's review.

Next on the backend: policy engine on submit, then approval states (manager, auditor above 25,000 INR, finance head above 1,00,000 INR), send back, and delegation.
