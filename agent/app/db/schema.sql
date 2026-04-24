-- =============================================================================
-- OpsTron Database Schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Table 1: User Profiles (extends Supabase Auth)
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name TEXT,
  phone_number TEXT,
  role TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  github_username TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Users can read/update their own profile
CREATE POLICY "Users can view own profile" ON user_profiles
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON user_profiles
  FOR UPDATE USING (auth.uid() = id);


-- =============================================================================
-- Table 2: Deployments
-- =============================================================================
CREATE TABLE IF NOT EXISTS deployments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  commit_sha TEXT NOT NULL,
  repository TEXT NOT NULL,
  author TEXT NOT NULL,
  branch TEXT DEFAULT 'main',
  message TEXT,
  status TEXT DEFAULT 'watching' CHECK (status IN ('watching', 'success', 'failed')),
  watch_started_at TIMESTAMPTZ DEFAULT NOW(),
  watch_ended_at TIMESTAMPTZ,
  errors_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_deployments_commit ON deployments(commit_sha);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployments_created ON deployments(created_at DESC);

-- Enable RLS (service key bypasses, anon key respects)
ALTER TABLE deployments ENABLE ROW LEVEL SECURITY;

-- Allow public read (for dashboard)
CREATE POLICY "Deployments are publicly readable" ON deployments
  FOR SELECT USING (true);


-- =============================================================================
-- Table 3: RCA Logs
-- =============================================================================
CREATE TABLE IF NOT EXISTS rca_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  deployment_id UUID REFERENCES deployments(id) ON DELETE SET NULL,
  service TEXT NOT NULL,
  error TEXT NOT NULL,
  stacktrace TEXT,
  rca_report JSONB,
  is_deployment_error BOOLEAN DEFAULT FALSE,
  severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  endpoint TEXT,
  request_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_rca_logs_deployment ON rca_logs(deployment_id);
CREATE INDEX IF NOT EXISTS idx_rca_logs_severity ON rca_logs(severity);
CREATE INDEX IF NOT EXISTS idx_rca_logs_created ON rca_logs(created_at DESC);

-- Enable RLS
ALTER TABLE rca_logs ENABLE ROW LEVEL SECURITY;

-- Allow public read
CREATE POLICY "RCA logs are publicly readable" ON rca_logs
  FOR SELECT USING (true);


-- =============================================================================
-- Table 4: Commits (Analyzed)
-- =============================================================================
CREATE TABLE IF NOT EXISTS commits (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  sha TEXT NOT NULL UNIQUE,
  repository TEXT NOT NULL,
  author TEXT NOT NULL,
  message TEXT,
  branch TEXT,
  files_changed JSONB,
  analysis_result JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_commits_sha ON commits(sha);
CREATE INDEX IF NOT EXISTS idx_commits_repo ON commits(repository);
CREATE INDEX IF NOT EXISTS idx_commits_created ON commits(created_at DESC);

-- Enable RLS
ALTER TABLE commits ENABLE ROW LEVEL SECURITY;

-- Allow public read
CREATE POLICY "Commits are publicly readable" ON commits
  FOR SELECT USING (true);


-- =============================================================================
-- Table 5: VAPI Calls
-- =============================================================================
CREATE TABLE IF NOT EXISTS vapi_calls (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  rca_log_id UUID REFERENCES rca_logs(id) ON DELETE SET NULL,
  vapi_call_id TEXT,
  phone_number TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
  transcript TEXT,
  summary TEXT,
  duration_seconds INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_vapi_calls_rca ON vapi_calls(rca_log_id);
CREATE INDEX IF NOT EXISTS idx_vapi_calls_status ON vapi_calls(status);
CREATE INDEX IF NOT EXISTS idx_vapi_calls_created ON vapi_calls(created_at DESC);

-- Enable RLS
ALTER TABLE vapi_calls ENABLE ROW LEVEL SECURITY;

-- Allow public read (transcripts are useful for chatbot)
CREATE POLICY "VAPI calls are publicly readable" ON vapi_calls
  FOR SELECT USING (true);


-- =============================================================================
-- Table 6: Chat Messages
-- =============================================================================
CREATE TABLE IF NOT EXISTS chat_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  session_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  context_type TEXT CHECK (context_type IN ('rca', 'commit', 'vapi', 'deployment', 'general')),
  context_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at DESC);

-- Enable RLS
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Users can only see their own messages
CREATE POLICY "Users can view own messages" ON chat_messages
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own messages" ON chat_messages
  FOR INSERT WITH CHECK (auth.uid() = user_id);


-- =============================================================================
-- Trigger: Auto-update updated_at
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profiles_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();


-- =============================================================================
-- Grant permissions (for service key operations)
-- =============================================================================
-- These grants allow the service key to insert/update without RLS restrictions

GRANT ALL ON deployments TO service_role;
GRANT ALL ON rca_logs TO service_role;
GRANT ALL ON commits TO service_role;
GRANT ALL ON vapi_calls TO service_role;
GRANT ALL ON chat_messages TO service_role;
GRANT ALL ON user_profiles TO service_role;


-- =============================================================================
-- Sample data (optional - for testing)
-- =============================================================================
-- Uncomment to insert test data

-- INSERT INTO deployments (commit_sha, repository, author, branch, message, status)
-- VALUES 
--   ('abc1234', 'hitanshuthegr8/OpsTron', 'hitanshuthegr8', 'main', 'feat: add auth', 'success'),
--   ('def5678', 'hitanshuthegr8/OpsTron', 'hitanshuthegr8', 'main', 'fix: bug fix', 'watching');


-- =============================================================================
-- Table 7: OpsTron Users  (GitHub OAuth — NOT Supabase Auth)
-- =============================================================================
-- We handle GitHub OAuth ourselves (not Supabase Auth), so we need our own
-- user table keyed on GitHub's numeric user ID.
-- This is the source of truth for who owns what agent key and which repos.
-- =============================================================================
CREATE TABLE IF NOT EXISTS opstron_users (
  github_id       TEXT PRIMARY KEY,          -- GitHub numeric ID as text (e.g. "12345678")
  login           TEXT NOT NULL UNIQUE,       -- GitHub username e.g. "hitanshuthegr8"
  name            TEXT,                       -- Display name
  email           TEXT,
  avatar_url      TEXT,
  agent_api_key   TEXT NOT NULL UNIQUE,       -- Per-user agent key (X-API-Key header)
  github_token    TEXT,                       -- Stored OAuth access token (encrypted at app level)
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_opstron_users_login     ON opstron_users(login);
CREATE INDEX IF NOT EXISTS idx_opstron_users_api_key   ON opstron_users(agent_api_key);
CREATE INDEX IF NOT EXISTS idx_opstron_users_last_seen ON opstron_users(last_seen_at DESC);

-- RLS: service key has full access, anon has none
ALTER TABLE opstron_users ENABLE ROW LEVEL SECURITY;
GRANT ALL ON opstron_users TO service_role;


-- =============================================================================
-- Table 8: Connected Repos
-- =============================================================================
-- Tracks which GitHub repos each user has connected to OpsTron.
-- One user can connect many repos. Webhook is installed per repo.
-- =============================================================================
CREATE TABLE IF NOT EXISTS connected_repos (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  github_id       TEXT NOT NULL REFERENCES opstron_users(github_id) ON DELETE CASCADE,
  repo_full_name  TEXT NOT NULL,              -- e.g. "hitanshuthegr8/MyApp"
  owner           TEXT NOT NULL,
  repo_name       TEXT NOT NULL,
  webhook_id      TEXT,                       -- GitHub webhook ID (for deletion later)
  webhook_active  BOOLEAN DEFAULT TRUE,
  connected_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(github_id, repo_full_name)           -- one row per user+repo pair
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_connected_repos_user ON connected_repos(github_id);
CREATE INDEX IF NOT EXISTS idx_connected_repos_repo ON connected_repos(repo_full_name);

-- RLS
ALTER TABLE connected_repos ENABLE ROW LEVEL SECURITY;
GRANT ALL ON connected_repos TO service_role;


-- =============================================================================
-- Migrate existing tables to support multi-tenancy
-- (Safe: uses IF NOT EXISTS / DO NOTHING patterns)
-- =============================================================================

-- Add user_id to rca_logs (links incidents to the user who owns the agent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'rca_logs' AND column_name = 'github_id'
  ) THEN
    ALTER TABLE rca_logs ADD COLUMN github_id TEXT REFERENCES opstron_users(github_id) ON DELETE SET NULL;
    CREATE INDEX idx_rca_logs_user ON rca_logs(github_id);
  END IF;
END $$;

-- Add user_id to deployments
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'deployments' AND column_name = 'github_id'
  ) THEN
    ALTER TABLE deployments ADD COLUMN github_id TEXT REFERENCES opstron_users(github_id) ON DELETE SET NULL;
    CREATE INDEX idx_deployments_user ON deployments(github_id);
  END IF;
END $$;

