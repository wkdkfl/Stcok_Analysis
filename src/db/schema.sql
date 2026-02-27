-- ═══════════════════════════════════════════════════════════
-- Stock Analyzer — Supabase PostgreSQL Schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor)
-- ═══════════════════════════════════════════════════════════

-- ── Enable pgcrypto for UUID generation ──────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ══════════════════════════════════════════════════════════
-- 1. USERS
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT,                          -- bcrypt hash (NULL for OAuth-only users)
    name          TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'free'   -- 'admin', 'premium', 'free'
                  CHECK (role IN ('admin', 'premium', 'free')),
    oauth_provider TEXT DEFAULT NULL,            -- 'google', NULL for email/password
    oauth_id      TEXT DEFAULT NULL,             -- OAuth provider user ID
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

-- ══════════════════════════════════════════════════════════
-- 2. SESSIONS
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address  TEXT,
    user_agent  TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_token   ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- ══════════════════════════════════════════════════════════
-- 3. SAVED ANALYSES
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS saved_analyses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    company_name TEXT DEFAULT '',
    results_json JSONB NOT NULL,                 -- serialized analysis results
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_analyses_user ON saved_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_analyses_ticker ON saved_analyses(ticker);

-- ══════════════════════════════════════════════════════════
-- 4. SAVED AI REPORTS
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS saved_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker          TEXT NOT NULL,
    company_name    TEXT DEFAULT '',
    report_markdown TEXT NOT NULL,
    llm_provider    TEXT,
    llm_model       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_reports_user ON saved_reports(user_id);

-- ══════════════════════════════════════════════════════════
-- 5. PORTFOLIOS
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS portfolios (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL DEFAULT 'My Portfolio',
    tickers     JSONB NOT NULL DEFAULT '[]'::JSONB,       -- ["AAPL","MSFT",...]
    weights     JSONB DEFAULT NULL,                        -- {"AAPL":0.3,"MSFT":0.7}
    settings    JSONB DEFAULT '{}'::JSONB,                 -- weight_scheme, benchmark, etc.
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id);

-- ══════════════════════════════════════════════════════════
-- 6. WATCHLISTS
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS watchlists (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL DEFAULT 'Watchlist',
    tickers     JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists(user_id);

-- ══════════════════════════════════════════════════════════
-- 7. USER API KEYS (encrypted)
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS user_api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,                -- 'openai', 'anthropic'
    encrypted_key   TEXT NOT NULL,                -- AES-256 encrypted
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_user_api_keys_user ON user_api_keys(user_id);

-- ══════════════════════════════════════════════════════════
-- 8. AUDIT LOGS
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,                   -- 'login', 'logout', 'analysis', 'report', 'admin_action'
    detail      TEXT DEFAULT '',
    ip_address  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user   ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_time   ON audit_logs(created_at DESC);

-- ══════════════════════════════════════════════════════════
-- 9. RATE LIMITS (per-user request tracking)
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS rate_limits (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,                   -- 'analysis', 'screener', 'ai_report'
    window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_count INT NOT NULL DEFAULT 1,
    UNIQUE(user_id, action_type, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_user_action ON rate_limits(user_id, action_type);

-- ══════════════════════════════════════════════════════════
-- 10. FAILED LOGIN ATTEMPTS (brute-force protection)
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS failed_logins (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT NOT NULL,
    ip_address  TEXT,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_failed_logins_email ON failed_logins(email);
CREATE INDEX IF NOT EXISTS idx_failed_logins_time  ON failed_logins(attempted_at);

-- ══════════════════════════════════════════════════════════
-- Row-Level Security (RLS)
-- Users can only access their own data
-- ══════════════════════════════════════════════════════════

-- Enable RLS on user-data tables
ALTER TABLE saved_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_reports  ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios     ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists     ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_api_keys  ENABLE ROW LEVEL SECURITY;

-- Note: RLS policies are managed via Supabase service_role key in the app.
-- The app authenticates as service_role and handles authorization in Python.
-- This provides defense-in-depth if direct DB access is ever exposed.

-- ══════════════════════════════════════════════════════════
-- Cleanup helper: auto-expire old sessions
-- ══════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM sessions WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Cleanup old failed login attempts (older than 24h)
CREATE OR REPLACE FUNCTION cleanup_old_failed_logins()
RETURNS void AS $$
BEGIN
    DELETE FROM failed_logins WHERE attempted_at < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;
