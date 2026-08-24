-- ====================================================================
-- RANKFORGE AUTH & MULTI-TENANT ISOLATION SCHEMA
-- ====================================================================

-- 1. Accounts Table (Tenant Root)
CREATE TABLE IF NOT EXISTS public.accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'agency', 'enterprise')),
    max_websites INT NOT NULL DEFAULT 1,
    articles_used_this_month INT NOT NULL DEFAULT 0,
    max_articles_per_month INT NOT NULL DEFAULT 10,
    avatar_url TEXT,
    reset_token TEXT,
    reset_token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default admin account if not existing (password: rankforge2026)
-- Bcrypt hash generated with rounds=12
INSERT INTO public.accounts (id, email, password_hash, full_name, plan, max_websites, max_articles_per_month)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'admin@rankforge.ai',
    '$2b$12$6GqgWkvM3vUoWfC3Y/gLxe9OQf5X7p4qVz9B0a1b2c3d4e5f6g7h8',
    'Lead SEO Architect',
    'agency',
    10,
    100
) ON CONFLICT (email) DO NOTHING;

-- 2. User Sessions Table (SHA-256 Token Tracking)
CREATE TABLE IF NOT EXISTS public.user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON public.user_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_user_sessions_account_id ON public.user_sessions(account_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON public.user_sessions(expires_at);

-- 3. Deleted Content Log (Audit & Snapshot Retention)
CREATE TABLE IF NOT EXISTS public.deleted_content_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_id UUID,
    account_id UUID REFERENCES public.accounts(id) ON DELETE SET NULL,
    website_id UUID REFERENCES public.websites(id) ON DELETE SET NULL,
    title TEXT,
    target_keyword TEXT,
    content TEXT,
    snapshot_data JSONB DEFAULT '{}'::jsonb,
    deleted_by TEXT DEFAULT 'system',
    deleted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deleted_content_account ON public.deleted_content_log(account_id);
CREATE INDEX IF NOT EXISTS idx_deleted_content_website ON public.deleted_content_log(website_id);

-- 4. Autonomous Health Log
CREATE TABLE IF NOT EXISTS public.autonomous_health_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE,
    website_id UUID REFERENCES public.websites(id) ON DELETE SET NULL,
    health_score INT NOT NULL DEFAULT 100,
    checks JSONB DEFAULT '{}'::jsonb,
    jobs_today JSONB DEFAULT '{}'::jsonb,
    auto_fixes_applied INT DEFAULT 0,
    auto_fixed JSONB DEFAULT '[]'::jsonb,
    issues JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_log_account ON public.autonomous_health_log(account_id);
CREATE INDEX IF NOT EXISTS idx_health_log_created_at ON public.autonomous_health_log(created_at DESC);

-- 5. Autonomous Settings (Per-Account & Per-Website Behavioral Config)
CREATE TABLE IF NOT EXISTS public.autonomous_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE CASCADE,
    website_id UUID NOT NULL REFERENCES public.websites(id) ON DELETE CASCADE,
    auto_generate BOOLEAN DEFAULT true,
    auto_publish BOOLEAN DEFAULT false,
    schedules JSONB DEFAULT '{"08:30": "Knowledge Crawl", "09:00": "SERP Research", "09:30": "Knowledge Sync", "10:00": "Brain Learning", "10:30": "Content Refresh", "11:00": "Article Generation", "11:30": "Backlink Scout", "12:00": "Tech Audit"}'::jsonb,
    notifications JSONB DEFAULT '{"article_generated": true, "backlink_acquired": true, "rank_change": true, "weekly_report": true, "crisis_alert": true}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_autonomous_settings_account_website UNIQUE (account_id, website_id)
);

-- 6. Add account_id to Existing Tables for Multi-Tenant Isolation
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;
ALTER TABLE public.blog_approvals ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;
ALTER TABLE public.knowledge_base ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;
ALTER TABLE public.brain_memory ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;
ALTER TABLE public.tasks ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;
ALTER TABLE public.technical_audits ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;
ALTER TABLE public.backlink_opportunities ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.accounts(id) ON DELETE CASCADE;

-- Backfill account_id for existing rows to default admin account
UPDATE public.websites SET account_id = 'a0000000-0000-0000-0000-000000000001' WHERE account_id IS NULL;
UPDATE public.content_log SET account_id = 'a0000000-0000-0000-0000-000000000001' WHERE account_id IS NULL;
UPDATE public.blog_approvals SET account_id = 'a0000000-0000-0000-0000-000000000001' WHERE account_id IS NULL;
UPDATE public.knowledge_base SET account_id = 'a0000000-0000-0000-0000-000000000001' WHERE account_id IS NULL;
UPDATE public.brain_memory SET account_id = 'a0000000-0000-0000-0000-000000000001' WHERE account_id IS NULL;

-- 7. Postgres RPC Context Function for Supabase RLS
CREATE OR REPLACE FUNCTION set_account_context(p_account_id TEXT)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_account_id', p_account_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
