-- ============================================================================
-- HackBridge Database Schema — Supabase (PostgreSQL + pgvector)
-- Run this in the Supabase SQL Editor to bootstrap the entire schema.
-- ============================================================================

-- Enable pgvector for semantic embedding storage (384-dim for MiniLM-L6-v2)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- USERS TABLE
-- Stores all platform participants. The `id` column references Supabase's
-- built-in auth.users so GoTrue handles password hashing & JWTs, while this
-- table holds application-level profile data.
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('organizer', 'judge', 'participant', 'admin')),
    skills        JSONB DEFAULT '[]'::jsonb,
    bio           TEXT DEFAULT '',
    expertise_embedding VECTOR(384),     -- sentence-transformers/all-MiniLM-L6-v2 output dim
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Index for fast nearest-neighbor searches on judge expertise
CREATE INDEX IF NOT EXISTS idx_users_expertise_embedding
    ON users USING ivfflat (expertise_embedding vector_cosine_ops)
    WITH (lists = 10);

-- ============================================================================
-- HACKATHONS TABLE
-- Each hackathon event. Status drives frontend routing and API gating.
-- ============================================================================
CREATE TABLE IF NOT EXISTS hackathons (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    description   TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'judging', 'completed')),
    start_time    TIMESTAMPTZ DEFAULT now(),
    end_time      TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- ============================================================================
-- PROJECTS TABLE
-- Submitted hackathon projects. tech_stack_embedding enables semantic matching
-- against judge expertise vectors. similarity_flag is set by the dedupe engine.
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hackathon_id        UUID NOT NULL REFERENCES hackathons(id) ON DELETE CASCADE,
    team_name           TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    github_url          TEXT DEFAULT '',
    tech_stack          JSONB DEFAULT '[]'::jsonb,
    tech_stack_embedding VECTOR(384),
    similarity_flag     BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_hackathon
    ON projects(hackathon_id);

CREATE INDEX IF NOT EXISTS idx_projects_tech_embedding
    ON projects USING ivfflat (tech_stack_embedding vector_cosine_ops)
    WITH (lists = 10);

-- ============================================================================
-- EVALUATIONS TABLE
-- Judge scoring rubric: innovation, technical, business, presentation.
-- bias_flag is toggled by the statistical anomaly detector (Z-score > 2σ).
-- ============================================================================
CREATE TABLE IF NOT EXISTS evaluations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    judge_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hackathon_id        UUID NOT NULL REFERENCES hackathons(id) ON DELETE CASCADE,
    score_innovation    REAL NOT NULL CHECK (score_innovation >= 0 AND score_innovation <= 100),
    score_technical     REAL NOT NULL CHECK (score_technical >= 0 AND score_technical <= 100),
    score_business      REAL NOT NULL CHECK (score_business >= 0 AND score_business <= 100),
    score_presentation  REAL NOT NULL CHECK (score_presentation >= 0 AND score_presentation <= 100),
    total_score         REAL GENERATED ALWAYS AS (
                            score_innovation * 0.30 +
                            score_technical  * 0.30 +
                            score_business   * 0.20 +
                            score_presentation * 0.20
                        ) STORED,
    feedback            TEXT DEFAULT '',
    bias_flag           BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, judge_id)    -- one evaluation per judge per project
);

CREATE INDEX IF NOT EXISTS idx_evaluations_hackathon
    ON evaluations(hackathon_id);

CREATE INDEX IF NOT EXISTS idx_evaluations_judge
    ON evaluations(judge_id);

-- ============================================================================
-- PROJECT ASSIGNMENTS TABLE
-- Maps judges → projects. Created by the AI reviewer assignment engine.
-- max_projects constraint enforced at application level (≤5 per judge).
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_assignments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    judge_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hackathon_id  UUID NOT NULL REFERENCES hackathons(id) ON DELETE CASCADE,
    assigned_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, judge_id)
);

-- ============================================================================
-- AUDIT LOG TABLE
-- Immutable ledger for all AI decisions — dedupe flags, bias detections,
-- reviewer assignments. Critical for the "transparency" judging criterion.
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action        TEXT NOT NULL,
    reference_id  TEXT,
    details       TEXT DEFAULT '',
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON audit_log(action);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
    ON audit_log(created_at DESC);

-- ============================================================================
-- Row Level Security (RLS) — Disabled for hackathon demo speed.
-- In production, enable RLS and add policies per role.
-- ============================================================================
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE hackathons DISABLE ROW LEVEL SECURITY;
ALTER TABLE projects DISABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations DISABLE ROW LEVEL SECURITY;
ALTER TABLE project_assignments DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY;
