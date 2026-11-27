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

COMMIT;
