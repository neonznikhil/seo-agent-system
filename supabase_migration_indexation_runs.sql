-- ============================================================================
-- RankForge Complete Migration: Outcomes, Runs, Indexation & Missing Tables
-- Run this in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run)
-- Safe to re-run: 100% idempotent.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. Ensure Missing Core Tables Exist (rank_tracking, internal_link_index, content_refresh_queue)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.rank_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    blog_id UUID,
    wp_post_id TEXT,
    wp_url TEXT,
    target_keyword TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'tracking' CHECK (status IN ('tracking', 'paused', 'completed')),
    published_at TIMESTAMPTZ DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    current_position INT,
    best_position INT,
    position_history JSONB DEFAULT '[]'::JSONB,
    provenance TEXT DEFAULT 'measured',
    source TEXT DEFAULT 'serper_search',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rank_tracking_website ON public.rank_tracking(website_id);
CREATE INDEX IF NOT EXISTS idx_rank_tracking_status ON public.rank_tracking(status);
CREATE INDEX IF NOT EXISTS idx_rank_tracking_keyword ON public.rank_tracking(target_keyword);

CREATE TABLE IF NOT EXISTS public.internal_link_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    blog_id UUID,
    url TEXT,
    title TEXT,
    target_keyword TEXT,
    linkable_topics JSONB DEFAULT '[]'::JSONB,
    summary TEXT,
    published_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_internal_link_website ON public.internal_link_index(website_id);
CREATE INDEX IF NOT EXISTS idx_internal_link_url ON public.internal_link_index(url);

CREATE TABLE IF NOT EXISTS public.content_refresh_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    blog_id UUID,
    wp_post_id TEXT,
    target_keyword TEXT,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_content_refresh_website ON public.content_refresh_queue(website_id);
CREATE INDEX IF NOT EXISTS idx_content_refresh_status ON public.content_refresh_queue(status);

-- ----------------------------------------------------------------------------
-- 1. Runs Envelope (Supports both run_service.py and workflow_service.py)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID NOT NULL REFERENCES public.websites(id) ON DELETE CASCADE,
    job_name TEXT,
    workflow_type TEXT,
    previous_run_id UUID REFERENCES public.runs(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    snapshot JSONB,
    summary TEXT,
    changes JSONB,
    rationale TEXT,
    unresolved JSONB,
    fixed_count INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    still_open_count INTEGER DEFAULT 0,
    regressed_count INTEGER DEFAULT 0,
    next_actions JSONB,
    provenance TEXT DEFAULT 'measured',
    source TEXT,
    error TEXT,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runs_website_job_time ON public.runs(website_id, job_name, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_website_workflow ON public.runs(website_id, workflow_type, started_at DESC);

-- ----------------------------------------------------------------------------
-- 2. Indexation Checks (Supports indexation_service.py insert & history)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.indexation_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID NOT NULL REFERENCES public.websites(id) ON DELETE CASCADE,
    run_id UUID REFERENCES public.runs(id),
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_pages INTEGER DEFAULT 0,
    indexed_pages INTEGER DEFAULT 0,
    submitted_total INTEGER DEFAULT 0,
    valid_indexed INTEGER DEFAULT 0,
    indexation_rate DECIMAL(5,4) DEFAULT 0.0000,
    not_indexed_urls TEXT[],
    sitemap_url TEXT,
    gsc_connected BOOLEAN DEFAULT false,
    method TEXT DEFAULT 'sitemap_count',
    threshold DECIMAL(5,4) DEFAULT 0.80,
    gate_passed BOOLEAN,
    action_taken TEXT,
    source TEXT DEFAULT 'gsc_sitemaps',
    raw_payload JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_indexation_checks_site_time ON public.indexation_checks(website_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_indexation_website ON public.indexation_checks(website_id, fetched_at DESC);

-- ----------------------------------------------------------------------------
-- 3. Keyword Positions (Supports keyword_agent.py & canonical SERP truth)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.keyword_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID NOT NULL REFERENCES public.websites(id) ON DELETE CASCADE,
    run_id UUID REFERENCES public.runs(id),
    keyword TEXT NOT NULL,
    page_url TEXT,
    position FLOAT,
    impressions INT DEFAULT 0,
    clicks INT DEFAULT 0,
    ctr FLOAT DEFAULT 0,
    search_volume INT,
    volume INT,
    cpc FLOAT,
    difficulty INT,
    intent TEXT,
    provenance TEXT NOT NULL DEFAULT 'observed' CHECK (provenance IN ('measured','observed','estimated')),
    source TEXT,
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(website_id, keyword, page_url, fetched_at)
);
CREATE INDEX IF NOT EXISTS idx_kw_pos_website ON public.keyword_positions(website_id, keyword);

-- ----------------------------------------------------------------------------
-- 4. Fact Verifications (Supports writer_agent.py QA gate audit trail)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fact_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID NOT NULL REFERENCES public.websites(id) ON DELETE CASCADE,
    content_id UUID,
    run_id UUID REFERENCES public.runs(id),
    claim TEXT,
    claim_text TEXT,
    claim_type TEXT DEFAULT 'general',
    verified BOOLEAN,
    verification_status TEXT DEFAULT 'pending',
    evidence_url TEXT,
    source_url TEXT,
    evidence_snippet TEXT,
    confidence FLOAT DEFAULT 0,
    verified_by TEXT,
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fact_verifications_content ON public.fact_verifications(content_id);

-- ----------------------------------------------------------------------------
-- 5. Brand Voice Guides (Used by brand_voice_service.py for closed-loop training)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.brand_voice_guides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    version INTEGER DEFAULT 1,
    tone TEXT,
    structure_rules TEXT[],
    formatting_rules TEXT[],
    banned_phrases TEXT[],
    required_phrases TEXT[],
    good_examples TEXT[],
    bad_examples TEXT[],
    verified_facts TEXT[],
    approved_articles TEXT[],
    rejected_articles TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_brand_voice_site_version ON public.brand_voice_guides(website_id, version DESC);

-- ----------------------------------------------------------------------------
-- 6. Example Library (Approved / Rejected articles with reviewer feedback)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.example_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID NOT NULL REFERENCES public.websites(id) ON DELETE CASCADE,
    verdict TEXT,
    type TEXT,
    reason TEXT,
    excerpt TEXT,
    content TEXT,
    prompt_version_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_example_library_site ON public.example_library(website_id);

-- ----------------------------------------------------------------------------
-- 7. Prompt Versions (Tracking prompt evolution)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.prompt_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    pipeline TEXT,
    workflow TEXT,
    version TEXT NOT NULL,
    prompt_text TEXT,
    prompt_hash TEXT,
    notes TEXT,
    changelog TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 8. Search Performance Snapshots & Data Source Alerts
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.search_performance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID NOT NULL REFERENCES public.websites(id) ON DELETE CASCADE,
    run_id UUID REFERENCES public.runs(id),
    impressions INT DEFAULT 0,
    clicks INT DEFAULT 0,
    ctr FLOAT DEFAULT 0,
    avg_position FLOAT DEFAULT 0,
    top_pages JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.data_source_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    reason TEXT NOT NULL,
    cost_cents INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 9. Add Provenance Columns to Existing Tables (Safely with IF EXISTS)
-- ----------------------------------------------------------------------------
ALTER TABLE IF EXISTS public.technical_audits ADD COLUMN IF NOT EXISTS provenance TEXT DEFAULT 'measured';
ALTER TABLE IF EXISTS public.technical_audits ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'live_http_crawl';
ALTER TABLE IF EXISTS public.technical_audits ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE IF EXISTS public.content_decay_logs ADD COLUMN IF NOT EXISTS provenance TEXT DEFAULT 'measured';
ALTER TABLE IF EXISTS public.content_decay_logs ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'gsc_impressions';
ALTER TABLE IF EXISTS public.content_decay_logs ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE IF EXISTS public.rank_tracking ADD COLUMN IF NOT EXISTS provenance TEXT DEFAULT 'measured';
ALTER TABLE IF EXISTS public.rank_tracking ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'serper_search';
ALTER TABLE IF EXISTS public.rank_tracking ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE IF EXISTS public.ai_visibility ADD COLUMN IF NOT EXISTS provenance TEXT DEFAULT 'observed';
ALTER TABLE IF EXISTS public.ai_visibility ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'ai_citation_check';
ALTER TABLE IF EXISTS public.ai_visibility ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE IF EXISTS public.keyword_opportunities ADD COLUMN IF NOT EXISTS provenance TEXT DEFAULT 'observed';
ALTER TABLE IF EXISTS public.content_pipeline_logs ADD COLUMN IF NOT EXISTS prompt_version TEXT;

-- ----------------------------------------------------------------------------
-- 10. Autonomous Settings Thresholds (Safely with IF EXISTS)
-- ----------------------------------------------------------------------------
ALTER TABLE IF EXISTS public.autonomous_settings ADD COLUMN IF NOT EXISTS indexation_min_rate FLOAT DEFAULT 0.80;
ALTER TABLE IF EXISTS public.autonomous_settings ADD COLUMN IF NOT EXISTS striking_min INT DEFAULT 11;
ALTER TABLE IF EXISTS public.autonomous_settings ADD COLUMN IF NOT EXISTS striking_max INT DEFAULT 20;

-- ----------------------------------------------------------------------------
-- 11. Enable RLS (Service Role key automatically bypasses RLS)
-- ----------------------------------------------------------------------------
ALTER TABLE IF EXISTS public.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.indexation_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.keyword_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.fact_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.brand_voice_guides ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.example_library ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.prompt_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.search_performance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.data_source_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.rank_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.internal_link_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.content_refresh_queue ENABLE ROW LEVEL SECURITY;
