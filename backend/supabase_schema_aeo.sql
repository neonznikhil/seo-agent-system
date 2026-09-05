-- ============================================================================
-- RankForge AEO/GEO Intelligence Layer — Database Migrations
-- ============================================================================

-- 1. AI Visibility Tracking
CREATE TABLE IF NOT EXISTS public.ai_visibility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    domain TEXT,
    checked_at TIMESTAMPTZ,
    keywords_checked INTEGER DEFAULT 0,
    ai_overview_appearances INTEGER DEFAULT 0,
    cited_count INTEGER DEFAULT 0,
    keyword_results JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_visibility_website ON public.ai_visibility(website_id, checked_at DESC);

-- 2. Article Markdown Cache for AI Scrapers
CREATE TABLE IF NOT EXISTS public.article_markdown_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wp_url TEXT UNIQUE,
    slug TEXT,
    markdown_content TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_article_markdown_slug ON public.article_markdown_cache(slug);

-- 3. Reddit Opportunities
CREATE TABLE IF NOT EXISTS public.reddit_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
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

-- 4. AEO Content Enhancements on content_log
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS citations_injected BOOLEAN DEFAULT false;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS definitions_injected BOOLEAN DEFAULT false;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS quick_facts_injected BOOLEAN DEFAULT false;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS schema_injected BOOLEAN DEFAULT false;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS markdown_generated BOOLEAN DEFAULT false;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS semantic_score FLOAT DEFAULT 0.0;
