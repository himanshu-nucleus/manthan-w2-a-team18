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

COMMIT;
