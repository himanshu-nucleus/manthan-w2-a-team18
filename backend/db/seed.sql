-- ExpenseFlow dummy data. SYNTHETIC ONLY - never put real people or credentials here.
--
-- Schema comes from Alembic; this file only inserts rows. Run it after migrating,
-- from the repository root:
--
--   cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head; cd ..
--   Get-Content backend\db\seed.sql | docker compose exec -T db psql -U manthan -d manthan -v ON_ERROR_STOP=1
--
-- Idempotent: safe to run again; existing rows are left alone.
-- Append new seed sections at the end of this file as tables are added.

BEGIN;

-- ---------------------------------------------------------------------------
-- Users
-- ---------------------------------------------------------------------------
-- Default finance head (also the admin). Login: admin / admin.
-- password_hash = PBKDF2-SHA256 of 'admin', made with app.security.hash_password.
INSERT INTO users (username, full_name, email, role, password_hash)
VALUES (
    'admin',
    'Finance Head',
    'finance.head@expenseflow.example',
    'finance_head',
    'pbkdf2_sha256$600000$EKUho/c5kSWXSQCFDqJ90w==$CcKUtfK8eCnLuD0RJaQ3gvVQSjcUcbCU3DHw7brHppw='
)
ON CONFLICT (username) DO NOTHING;

-- One demo login per remaining persona. Hashes made with app.security.hash_password.
-- Line manager. Login: manager / manager.
INSERT INTO users (username, full_name, email, role, password_hash)
VALUES (
    'manager',
    'Demo Line Manager',
    'line.manager@expenseflow.example',
    'line_manager',
    'pbkdf2_sha256$600000$6kSE967UH4XiR24CkPdilQ==$pdI3Z75nwtGrS9Zi4I5Ot3/QLOnG3CxeKcLSmV1JAyA='
)
ON CONFLICT (username) DO NOTHING;

-- Finance auditor. Login: auditor / auditor.
INSERT INTO users (username, full_name, email, role, password_hash)
VALUES (
    'auditor',
    'Demo Finance Auditor',
    'finance.auditor@expenseflow.example',
    'finance_auditor',
    'pbkdf2_sha256$600000$TAIWwy1OIYQMBnq88N00Mg==$SKa6Z2JFWPXX7NIBh/Y6ES896q2CRF1vGhNXI7yWLVI='
)
ON CONFLICT (username) DO NOTHING;

-- Employee reporting to 'manager'. Login: employee / employee.
INSERT INTO users (username, full_name, email, role, manager_id, password_hash)
VALUES (
    'employee',
    'Demo Employee',
    'employee@expenseflow.example',
    'employee',
    (SELECT id FROM users WHERE username = 'manager'),
    'pbkdf2_sha256$600000$X/4hrVaVGyXL+VaoQAP9cA==$7cdqhWWBFOq9uLUmpvKVajuWK6esHZKQKEpQNpExHeA='
)
ON CONFLICT (username) DO NOTHING;

-- Extra users for trying the claims API. Password = username.
-- employee1 and employee2 report to manager1; manager1 reports to admin.
INSERT INTO users (username, full_name, email, role, password_hash, manager_id)
VALUES
    ('manager1', 'Line Manager One', 'manager1@expenseflow.example', 'line_manager',
     'pbkdf2_sha256$600000$ao5QzXwAz8UlmtFMhD1Wlg==$2hjtmqu9cSB+eR39gEZxt+ujzxb41mz8OHDhONKbYMY=',
     (SELECT id FROM users WHERE username = 'admin')),
    ('auditor1', 'Finance Auditor One', 'auditor1@expenseflow.example', 'finance_auditor',
     'pbkdf2_sha256$600000$nWtvAo9nJ9j1vb+Ul1LFvw==$rJj1D5Dtu2HvGT/16t64NGesAQsJWQJN+7Agu/TAhyE=',
     (SELECT id FROM users WHERE username = 'admin'))
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, full_name, email, role, password_hash, manager_id)
VALUES
    ('employee1', 'Employee One', 'employee1@expenseflow.example', 'employee',
     'pbkdf2_sha256$600000$cPugPb0SWCFdpgEvav4aGA==$vh+jOu9M44i7KTHVbDpajTVkv5HBESuZKE6WRtatbT8=',
     (SELECT id FROM users WHERE username = 'manager1')),
    ('employee2', 'Employee Two', 'employee2@expenseflow.example', 'employee',
     'pbkdf2_sha256$600000$4+SYFjg+DiKLwmu5bzZIGQ==$2KWErRCaUN7FabEm4wAn3AHgRTKMrSKw13uJeN/i63I=',
     (SELECT id FROM users WHERE username = 'manager1'))
ON CONFLICT (username) DO NOTHING;

-- Second finance head, so a finance head's own claim (or a >1,00,000 claim whose manager
-- step went to 'admin') still has a different finance head to approve it. Login: head2 / head2.
INSERT INTO users (username, full_name, email, role, password_hash)
VALUES (
    'head2',
    'Finance Head Two',
    'head2@expenseflow.example',
    'finance_head',
    'pbkdf2_sha256$600000$u61L5WaZFn7Kq6XKlXWwzw==$QYV1Jk8VD3IwORPhP8N7gisui//1pOtpmkHKdiowt2I='
)
ON CONFLICT (username) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Policy rules (configuration, not code). Amounts are INR strings so they stay exact.
-- Re-running keeps any limit already changed through PUT /policy-rules/{code}.
-- Template placeholders are filled by the rule type; see app/policy/rules.py.
-- ---------------------------------------------------------------------------
INSERT INTO policy_rules (code, name, category, rule_type, params, outcome_on_breach, reason_template)
VALUES
    ('MEAL_DAILY_LIMIT', 'Meals up to 1,500 INR per day', 'meal', 'DAILY_CATEGORY_LIMIT',
     '{"limit": "1500"}', 'ROUTE_FOR_APPROVAL',
     'Meal spend {total} INR on {date} exceeds daily limit of {limit} INR'),
    ('HOTEL_NIGHTLY_LIMIT_T1', 'Hotel up to 6,000 INR per night in tier-1 cities', 'hotel',
     'PER_NIGHT_LIMIT', '{"limit": "6000", "city_tier": "tier1"}', 'ROUTE_FOR_APPROVAL',
     'Hotel {per_night} INR per night in {city} exceeds tier-1 limit of {limit} INR'),
    ('HOTEL_NIGHTLY_LIMIT_OTHER', 'Hotel up to 4,000 INR per night in other cities', 'hotel',
     'PER_NIGHT_LIMIT', '{"limit": "4000", "city_tier": "other"}', 'ROUTE_FOR_APPROVAL',
     'Hotel {per_night} INR per night in {city} exceeds limit of {limit} INR for non-tier-1 cities'),
    ('CAB_TRIP_LIMIT', 'Local cab up to 2,000 INR per trip', 'cab', 'PER_LINE_LIMIT',
     '{"limit": "2000"}', 'ROUTE_FOR_APPROVAL',
     'Cab fare {amount} INR on {date} exceeds per-trip limit of {limit} INR'),
    ('RECEIPT_MANDATORY', 'Receipt mandatory above 500 INR', NULL, 'RECEIPT_REQUIRED',
     '{"above": "500"}', 'AUTO_REJECT',
     'Receipt is mandatory above {above} INR; line {line} ({amount} INR) has none'),
    ('DUPLICATE_LINE', 'Same vendor, amount and date as an earlier line', NULL, 'DUPLICATE_LINE',
     '{}', 'ROUTE_FOR_APPROVAL',
     'Possible duplicate: same vendor, amount and date as {match}'),
    ('DUPLICATE_RECEIPT_HASH', 'Same receipt file as an earlier receipt', NULL,
     'DUPLICATE_RECEIPT_HASH', '{}', 'AUTO_REJECT',
     'Duplicate receipt: the same file was already used on {match}'),
    ('WEEKEND_SPEND', 'Weekend spend flagged for manager attention', NULL, 'WEEKEND',
     '{"days": [5, 6]}', 'ROUTE_FOR_APPROVAL',
     'Expense on {weekday} {date} is weekend spend; flagged for manager attention'),
    ('SPLIT_CLAIM', 'Possible claim splitting to stay under an approval threshold', NULL,
     'SPLIT_CLAIM', '{"window_days": 7, "threshold": "25000"}', 'ROUTE_FOR_APPROVAL',
     'Claims submitted in the last {window_days} days total {combined} INR, above {threshold} INR: possible claim splitting')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Policy settings
-- ---------------------------------------------------------------------------
INSERT INTO policy_settings (key, value, description)
VALUES
    ('tier1_cities',
     '["mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "chennai", "hyderabad", "kolkata", "pune", "ahmedabad"]',
     'Cities that get the tier-1 hotel limit (matched case-insensitively).'),
    ('approval_thresholds',
     '{"finance_auditor": "25000", "finance_head": "100000"}',
     'Claim total (INR) strictly above which the auditor / finance head step is added.'),
    ('auto_approve_max_total',
     '"500"',
     'A claim with no rule breach is auto-approved only if its total (INR) is at most this.')
ON CONFLICT (key) DO NOTHING;

COMMIT;
