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

-- Email-style finance head logins (login accepts username or email, any case).
-- Password for both: admin. Hashes made in the app.security.hash_password format.
-- Bare ON CONFLICT DO NOTHING also skips a row whose email is already taken.
INSERT INTO users (username, full_name, email, role, password_hash)
VALUES
    ('admin@gmail.com', 'Finance Head (Gmail)', 'admin@gmail.com', 'finance_head',
     'pbkdf2_sha256$600000$ldiiBTWUtoKKxDg1j0fFMg==$GVK7ApGq9ESl5xr3Hl4D0B/awXqSBXxu3tRqZ8jGcsE='),
    ('admin@expenseflow.example', 'Finance Head (ExpenseFlow)', 'admin@expenseflow.example',
     'finance_head',
     'pbkdf2_sha256$600000$ZsdpmnDcFm6Np1QvkG1QdA==$EazTmndykJfH1MBZzQ5bjQs7Tgsqe40ECJqqQcpbTy4=')
ON CONFLICT DO NOTHING;

-- More employees with Gmail addresses, reporting to 'manager'. Password for all: employee.
-- Log in with the username (employee3) or the email (employee3@gmail.com).
INSERT INTO users (username, full_name, email, role, password_hash, manager_id)
VALUES
    ('employee3', 'Employee Three', 'employee3@gmail.com', 'employee',
     'pbkdf2_sha256$600000$Wt19Zj5129rs6gVwmxZFbg==$3PvjyLQMF9S4Dc+T0LvD2y845xgAbGTCSJ2cXEpBt90=',
     (SELECT id FROM users WHERE username = 'manager')),
    ('employee4', 'Employee Four', 'employee4@gmail.com', 'employee',
     'pbkdf2_sha256$600000$OQQl40ZybBmW/SJot49reg==$lE6swDW6ewR8vDpTZsy4qLqXMpPtvscw3N5FS0CPSJM=',
     (SELECT id FROM users WHERE username = 'manager')),
    ('employee5', 'Employee Five', 'employee5@gmail.com', 'employee',
     'pbkdf2_sha256$600000$cHS/NRMchsqBAEqmU020mQ==$BuhK9cCQDaAhRu2yY6c11PqyTcfF5IxYbaFkJPY/icU=',
     (SELECT id FROM users WHERE username = 'manager')),
    ('employee6', 'Employee Six', 'employee6@gmail.com', 'employee',
     'pbkdf2_sha256$600000$VQO+VMU2RiMCMTo886QUsQ==$au9pQ/x7WBoEMWqHgyKJ4t2pn7w4rvE/bRpcmDZwpPQ=',
     (SELECT id FROM users WHERE username = 'manager'))
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Policy rules and settings: the defaults live in backend/app/policy/defaults.py and
-- the API inserts any missing one at startup. These UPDATEs switch off the rules the
-- team replaced (duplicate rule, local category) in databases seeded before that
-- change; they run on every seed, so re-seeding switches them off again.
-- ---------------------------------------------------------------------------
UPDATE policy_rules SET active = false
WHERE code IN ('DUPLICATE_LINE', 'DUPLICATE_RECEIPT_HASH', 'CAB_TRIP_LIMIT');

-- ---------------------------------------------------------------------------
-- Departments for the demo users (printed on payout files). Only fills blanks.
-- ---------------------------------------------------------------------------
UPDATE users SET department = CASE username
        WHEN 'admin' THEN 'Finance'
        WHEN 'head2' THEN 'Finance'
        WHEN 'auditor' THEN 'Finance'
        WHEN 'auditor1' THEN 'Finance'
        WHEN 'manager' THEN 'Consulting'
        WHEN 'employee' THEN 'Consulting'
        WHEN 'manager1' THEN 'Engineering'
        WHEN 'employee1' THEN 'Engineering'
        WHEN 'employee2' THEN 'Engineering'
        WHEN 'admin@gmail.com' THEN 'Finance'
        WHEN 'admin@expenseflow.example' THEN 'Finance'
        WHEN 'employee3' THEN 'Consulting'
        WHEN 'employee4' THEN 'Consulting'
        WHEN 'employee5' THEN 'Consulting'
        WHEN 'employee6' THEN 'Consulting'
    END
WHERE department IS NULL
  AND username IN ('admin', 'head2', 'auditor', 'auditor1', 'manager', 'employee',
                   'manager1', 'employee1', 'employee2', 'admin@gmail.com',
                   'admin@expenseflow.example', 'employee3', 'employee4', 'employee5',
                   'employee6');

COMMIT;
