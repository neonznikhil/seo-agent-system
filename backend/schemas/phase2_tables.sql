-- ============================================================================
-- RankForge Phase 2 Database Schema & Migrations
-- Tables: rank_history, rank_predictions, competitor_profiles, weekly_reports,
--         workspace_members, validation_errors
-- ============================================================================

-- 1. RANK HISTORY TABLE (Time-series telemetry for ranking predictions)
CREATE TABLE IF NOT EXISTS public.rank_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    position NUMERIC DEFAULT 0,
    date DATE DEFAULT CURRENT_DATE,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    ctr NUMERIC DEFAULT 0.0,
    competitor_count_top10 INTEGER DEFAULT 0,
    content_age_days INTEGER DEFAULT 0,
    backlink_count INTEGER DEFAULT 0,
    last_refresh_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rank_history_site_kw ON public.rank_history(website_id, keyword, date);

-- 2. RANK PREDICTIONS TABLE (Preemptive rankings intelligence)
CREATE TABLE IF NOT EXISTS public.rank_predictions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    current_position NUMERIC,
    predicted_position_30d NUMERIC,
    confidence FLOAT DEFAULT 0.85,
    recommended_action TEXT NOT NULL, -- 'refresh_content', 'build_backlinks', 'add_internal_links', 'update_schema'
    reasoning TEXT,
    status TEXT DEFAULT 'pending_action', -- 'pending_action', 'action_taken', 'dismissed'
    action_taken_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. COMPETITOR PROFILES TABLE (Deep competitor tracking)
CREATE TABLE IF NOT EXISTS public.competitor_profiles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    tracked_keywords JSONB DEFAULT '[]',
    estimated_monthly_traffic INTEGER DEFAULT 0,
    publish_frequency NUMERIC DEFAULT 1.0, -- articles per week
    avg_content_length INTEGER DEFAULT 1500,
    backlink_velocity NUMERIC DEFAULT 0.0, -- new backlinks per month
    schema_types JSONB DEFAULT '[]',
    top_pages JSONB DEFAULT '[]',
    last_5_articles JSONB DEFAULT '[]',
    last_surge_detected TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(website_id, domain)
);

-- 4. WEEKLY REPORTS TABLE (Self-audit performance reports)
CREATE TABLE IF NOT EXISTS public.weekly_reports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    report_week DATE DEFAULT CURRENT_DATE,
    agent_stats JSONB DEFAULT '{}', -- success rate & duration per agent
    goals_summary JSONB DEFAULT '{}', -- goals achieved vs goals set
    wins JSONB DEFAULT '[]',
    failures JSONB DEFAULT '[]',
    next_week_plan JSONB DEFAULT '{}',
    overall_health_score NUMERIC DEFAULT 95.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. WORKSPACE MEMBERS TABLE (Role-based access control)
CREATE TABLE IF NOT EXISTS public.workspace_members (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer', -- 'owner', 'editor', 'viewer'
    invited_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(website_id, email)
);

-- 6. VALIDATION ERRORS TABLE (Pydantic data health tracking)
CREATE TABLE IF NOT EXISTS public.validation_errors (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    table_name TEXT NOT NULL,
    failed_data JSONB DEFAULT '{}',
    error_message TEXT NOT NULL,
    severity TEXT DEFAULT 'warning',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. ADD PHASE 2 COLUMNS TO EXISTING TABLES
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'Asia/Kolkata';
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS brand_voice_rules JSONB DEFAULT '{}';

ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS monthly_goals JSONB DEFAULT '{}';
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS budget_threshold NUMERIC DEFAULT 150.0;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS daily_costs JSONB DEFAULT '{}';
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS adaptive_scheduling_enabled BOOLEAN DEFAULT true;

ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS image_suggestions JSONB DEFAULT '[]';
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS semantic_terms_injected JSONB DEFAULT '[]';
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS eeat_signals JSONB DEFAULT '{}';
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS competitive_benchmark JSONB DEFAULT '{}';

ALTER TABLE public.geo_visibility_logs ADD COLUMN IF NOT EXISTS cited BOOLEAN DEFAULT false;
ALTER TABLE public.geo_visibility_logs ADD COLUMN IF NOT EXISTS citation_position INTEGER;
ALTER TABLE public.geo_visibility_logs ADD COLUMN IF NOT EXISTS response_snippet TEXT;
ALTER TABLE public.geo_visibility_logs ADD COLUMN IF NOT EXISTS platform TEXT;
