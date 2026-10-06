-- Tables for Supabase / Postgres. Money is stored as integer cents (BIGINT).
CREATE TABLE IF NOT EXISTS users (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS expenses (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  amount_cents BIGINT NOT NULL CHECK (amount_cents > 0),
  expense_date TEXT NOT NULL,            -- stored as YYYY-MM-DD text
  crop TEXT NOT NULL DEFAULT '',
  payment_method TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS expenses_user_date ON expenses (user_id, expense_date);
CREATE TABLE IF NOT EXISTS settings (
  user_id BIGINT PRIMARY KEY REFERENCES users(id),
  budget_cents BIGINT NOT NULL DEFAULT 0 CHECK (budget_cents >= 0),
  revenue_cents BIGINT NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0)
);
-- Security: Supabase exposes public tables through its own web API.
-- Turning on Row Level Security (with no policies) blocks that API completely.
-- Our Flask app connects directly with the database connection string, so it still works.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
