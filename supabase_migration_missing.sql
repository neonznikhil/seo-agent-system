-- ==========================================================
-- RankForge migration: create objects PROVEN missing on live DB
-- (probed 2026-09-07 via service_role; all statements additive)
-- Run in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Safe to re-run: every statement is IF NOT EXISTS guarded.
-- ==========================================================

-- 1. blogs: dashboard metrics + scheduler duplicate check read this.
--    Columns are the superset the backend actually writes/reads
--    (crew_blog_writer.blog_row + scheduler target_keyword select).
CREATE TABLE IF NOT EXISTS public.blogs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id uuid,
    title text,
    slug text,
    content text,
    html_content text,
    meta_description text,
    primary_keyword text,
    target_keyword text,
    status text DEFAULT 'draft',
    seo_score float DEFAULT 0,
    validation_score float DEFAULT 0,
    grounding_score float DEFAULT 0,
    word_count int DEFAULT 0,
    citations jsonb DEFAULT '[]'::jsonb,
    rag_hits jsonb DEFAULT '[]'::jsonb,
    wordpress_post_id int,
    wordpress_url text,
    wp_post_id int,
    wp_url text,
    published_at timestamptz,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_blogs_website ON public.blogs(website_id);
CREATE INDEX IF NOT EXISTS idx_blogs_website_keyword ON public.blogs(website_id, target_keyword);

-- 2. agent_memory: agent long-term memory writes (rules.py / cms_tools.py).
CREATE TABLE IF NOT EXISTS public.agent_memory (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text,
    agent_name text,
    memory_type text,
    content text,
    metadata jsonb DEFAULT '{}'::jsonb,
    confidence float DEFAULT 1.0,
    times_used int DEFAULT 0,
    times_successful int DEFAULT 0,
    last_used timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_memory_agent ON public.agent_memory(agent_name);

-- 3. daily_searches: daily SERP/GSC mining jobs write here.
CREATE TABLE IF NOT EXISTS public.daily_searches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id uuid,
    keyword text,
    search_volume int,
    clicks int DEFAULT 0,
    impressions int DEFAULT 0,
    trends jsonb DEFAULT '{}'::jsonb,
    competitor_data jsonb DEFAULT '{}'::jsonb,
    source text DEFAULT 'daily_search',
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_daily_searches_website ON public.daily_searches(website_id);

-- 4. analytics_data: crew_blog_writer reads (keyword, clicks,
--    impressions, position); analytics_service counts rows.
CREATE TABLE IF NOT EXISTS public.analytics_data (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id uuid,
    blog_id uuid,
    wordpress_post_id int,
    keyword text,
    clicks int DEFAULT 0,
    impressions int DEFAULT 0,
    position float,
    views int DEFAULT 0,
    avg_time float DEFAULT 0,
    bounce_rate float DEFAULT 0,
    source text DEFAULT 'wordpress',
    date date DEFAULT CURRENT_DATE,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_analytics_website ON public.analytics_data(website_id);

-- 5. knowledge_base.last_used: knowledge_service updates it on hit.
ALTER TABLE public.knowledge_base ADD COLUMN IF NOT EXISTS last_used timestamptz DEFAULT now();

-- 6. RLS: same convention as the rest of this project
--    (backend operates with the service_role key).
ALTER TABLE IF EXISTS public.blogs DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.agent_memory DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.daily_searches DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.analytics_data DISABLE ROW LEVEL SECURITY;

-- ==========================================================
-- Intentionally NOT included (verified live 2026-09-07):
-- * match_knowledge / match_brain_memory RPCs: live knowledge_base
--   and brain_memory store embeddings as TEXT, not pgvector, so a
--   vector `<=>` function would fail. The app already falls back to
--   text/hybrid retrieval. Convert embeddings to vector(1024) first,
--   then add the RPCs from supabase_schema.sql / brain schema.
-- * set_account_context RPC: never defined in this repo; callers
--   treat it as best-effort. No-op by design.
-- * exec_sql RPC: deliberately not created (arbitrary-SQL RPC is a
--   security risk). Use the SQL Editor for DDL.
-- ==========================================================
