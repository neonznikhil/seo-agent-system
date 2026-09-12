-- ==========================================================
-- RankForge migration 2: AEO/GEO + backlink queue tables
-- Run in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Safe to re-run: every statement is IF NOT EXISTS guarded.
-- (Probed 2026-09-07: these 5 tables 404; geo_visibility_logs OK.)
-- ==========================================================

-- 1. aeo_citations: AEOAgent.track_buyer_intent_queries writes one row
--    per checked buyer-intent query (engine that ACTUALLY ran).
CREATE TABLE IF NOT EXISTS public.aeo_citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID,
    query TEXT,
    llm_name TEXT,
    cited BOOLEAN DEFAULT FALSE,
    competitor_cited BOOLEAN DEFAULT FALSE,
    citation_snippet TEXT,
    schema_markup JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_aeo_citations_website ON public.aeo_citations(website_id, created_at DESC);

-- 2. ai_visibility: periodic AI-overview visibility snapshots.
CREATE TABLE IF NOT EXISTS public.ai_visibility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID,
    domain TEXT,
    checked_at TIMESTAMPTZ,
    keywords_checked INTEGER DEFAULT 0,
    ai_overview_appearances INTEGER DEFAULT 0,
    cited_count INTEGER DEFAULT 0,
    keyword_results JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_visibility_website ON public.ai_visibility(website_id, checked_at DESC);

-- 3. article_markdown_cache: markdown copies served to AI scrapers.
CREATE TABLE IF NOT EXISTS public.article_markdown_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wp_url TEXT UNIQUE,
    slug TEXT,
    markdown_content TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_article_markdown_slug ON public.article_markdown_cache(slug);

-- 4. reddit_opportunities: Reddit threads worth a helpful comment.
CREATE TABLE IF NOT EXISTS public.reddit_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID,
    thread_title TEXT,
    thread_url TEXT,
    subreddit TEXT,
    keyword TEXT,
    opportunity_type TEXT,
    status TEXT DEFAULT 'pending',
    generated_comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reddit_opportunities_website ON public.reddit_opportunities(website_id, created_at DESC);

-- 5. backlink_opportunities: BacklinkAgent stages qualified leads here.
--    NOTE: superset of the repo's master schema — includes the columns
--    the agent actually writes (domain_authority, type, email_draft,
--    gap_analysis) and allows status 'pending' used by the queue.
CREATE TABLE IF NOT EXISTS public.backlink_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID,
    source_url TEXT,
    target_url TEXT,
    anchor_text TEXT,
    domain_authority INT DEFAULT 0,
    domain_rating INT DEFAULT 0,
    category TEXT DEFAULT 'resource_page',
    type TEXT DEFAULT 'competitor_replication',
    opportunity_type TEXT DEFAULT 'competitor_gap',
    status TEXT NOT NULL DEFAULT 'pending',
    email_draft TEXT,
    gap_analysis TEXT,
    priority FLOAT DEFAULT 0.8,
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_backlink_opps_website ON public.backlink_opportunities(website_id, status);

-- 6. AEO pipeline flags on content_log (read by /api/aeo/status).
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS citations_injected BOOLEAN DEFAULT FALSE;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS definitions_injected BOOLEAN DEFAULT FALSE;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS quick_facts_injected BOOLEAN DEFAULT FALSE;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS schema_injected BOOLEAN DEFAULT FALSE;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS markdown_generated BOOLEAN DEFAULT FALSE;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS semantic_score FLOAT DEFAULT 0.0;

-- 7. RLS: same convention as the rest of this project
--    (backend operates with the service_role key).
ALTER TABLE IF EXISTS public.aeo_citations DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.ai_visibility DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.article_markdown_cache DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.reddit_opportunities DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.backlink_opportunities DISABLE ROW LEVEL SECURITY;
