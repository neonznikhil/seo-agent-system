-- ====================================================================
-- RANKFORGE MASTER CONSOLIDATED SUPABASE SCHEMA (MULTI-TENANT & AUTONOMOUS)
-- Run this in your Supabase SQL Editor in ONE single execution.
-- ====================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- --------------------------------------------------------------------
-- 2. Users & Multi-Tenant Accounts Table
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT,
  role TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
  avatar_url TEXT,
  preferences JSONB DEFAULT '{"theme": "dark", "default_tone": "authoritative", "auto_publish": false, "target_word_count": 1500}'::JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default demo user (password: rankforge2026)
INSERT INTO public.users (id, email, password_hash, full_name, role)
VALUES (
  'a0000000-0000-0000-0000-000000000001',
  'admin@rankforge.ai',
  '3a2902fb345a557b420eeae7de1e155bc8cb7b090f488667c40d21397b97394c', -- sha256 of 'rankforge2026'
  'Lead SEO Architect',
  'owner'
) ON CONFLICT (email) DO NOTHING;

-- --------------------------------------------------------------------
-- 3. Websites & Connected Domains
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.websites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
  domain TEXT NOT NULL UNIQUE,
  url TEXT,
  cms_url TEXT,
  cms_user TEXT,
  app_password TEXT,
  wordpress_url TEXT,
  wordpress_user TEXT,
  wordpress_password TEXT,
  gsc_property TEXT,
  ga4_property_id TEXT,
  niche TEXT,
  name TEXT,
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'setup_pending', 'error')),
  oauth_enabled BOOLEAN DEFAULT false,
  wp_oauth_connected BOOLEAN DEFAULT false,
  slack_webhook_url TEXT,
  slack_credentials JSONB,
  alert_email TEXT,
  local_target TEXT,
  last_audit_score INT,
  last_audit_date TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure user_id column exists if table was already created
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS wordpress_url TEXT;
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS wordpress_user TEXT;
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS wordpress_password TEXT;
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS slack_credentials JSONB;
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS last_audit_score INT;
ALTER TABLE public.websites ADD COLUMN IF NOT EXISTS last_audit_date TIMESTAMPTZ;

-- --------------------------------------------------------------------
-- 4. Content Log (All Articles, Drafts & Generations)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.content_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  content TEXT,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'pending_approval', 'approved', 'published', 'rejected', 'refresh_queued', 'generating')),
  keyword TEXT,
  use_case TEXT,
  embedding vector(1024),
  faq_schema JSONB DEFAULT '{}'::JSONB,
  internal_links JSONB DEFAULT '[]'::JSONB,
  similarity_score FLOAT,
  published_url TEXT,
  quality_checked BOOLEAN DEFAULT false,
  pipeline_status TEXT DEFAULT 'not_started',
  phase_results JSONB DEFAULT '{}'::JSONB,
  final_scores JSONB DEFAULT '{}'::JSONB,
  eeat_data JSONB,
  ai_search_score INT,
  information_gain_score INT,
  info_gain_score INT,
  wordpress_draft_id INT,
  business_potential INT,
  business_potential_score INT,
  winning_patterns JSONB,
  is_refresh BOOLEAN DEFAULT false,
  original_page_url TEXT,
  decay_log_id UUID,
  mode TEXT,
  human_score INT,
  seo_score INT,
  eeat_score INT,
  human_user_id TEXT,
  approval_timestamp TIMESTAMPTZ,
  wp_post_id INT,
  wp_draft_url TEXT,
  word_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS wp_post_id INT;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS wp_draft_url TEXT;
ALTER TABLE public.content_log ADD COLUMN IF NOT EXISTS word_count INT DEFAULT 0;

-- --------------------------------------------------------------------
-- 5. Blog Approvals Queue (1-Click Publish Pipeline)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.blog_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  blog_id UUID REFERENCES public.content_log(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  html_content TEXT,
  content TEXT,
  keyword TEXT,
  seo_title TEXT,
  meta_description TEXT,
  slug TEXT,
  seo_score FLOAT DEFAULT 0,
  type TEXT DEFAULT 'blog',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'published')),
  auto_generated BOOLEAN DEFAULT true,
  wordpress_action TEXT DEFAULT 'publish',
  wordpress_post_id INT,
  wordpress_url TEXT,
  rejection_reason TEXT,
  approved_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 6. Knowledge Base & Ground Truth RAG Chunks
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.knowledge_base (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  fact TEXT NOT NULL,
  fact_type TEXT NOT NULL DEFAULT 'company_info',
  source_url TEXT,
  embedding vector(1024),
  freshness_score FLOAT DEFAULT 1.0,
  credibility_score FLOAT DEFAULT 1.0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 7. Autonomous Brain Memory (Self-Learning Patterns)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.brain_memory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  memory_type TEXT CHECK (memory_type IN ('fact','experience','failure','preference','entity','relationship','outcome')),
  title TEXT,
  content TEXT NOT NULL,
  embedding vector(1024),
  source_type TEXT,
  source_id UUID,
  confidence FLOAT DEFAULT 0.8,
  times_used INT DEFAULT 0,
  times_successful INT DEFAULT 0,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 8. Autonomous Cadence & Daily Scheduled Jobs
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.brain_daily_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  job_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  result JSONB DEFAULT '{}'::JSONB,
  error TEXT,
  run_at TIMESTAMPTZ DEFAULT NOW(),
  next_run_at TIMESTAMPTZ
);

-- --------------------------------------------------------------------
-- 9. Agent Telemetry, Tasks & Live Thoughts
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  action TEXT NOT NULL,
  payload JSONB DEFAULT '{}'::JSONB,
  result JSONB DEFAULT '{}'::JSONB,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'success', 'failed', 'skipped')),
  duration FLOAT,
  real_api_called TEXT,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.agent_thoughts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  thought TEXT NOT NULL,
  decision TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 10. Technical SEO Audits & Pending Fixes
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.technical_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  audit_type TEXT DEFAULT 'full_crawl',
  issue_type TEXT NOT NULL DEFAULT 'health_check',
  severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('high', 'medium', 'low', 'critical')),
  health_score INT DEFAULT 85,
  score INT DEFAULT 85,
  metrics JSONB DEFAULT '{}'::JSONB,
  details JSONB DEFAULT '{}'::JSONB,
  issues JSONB DEFAULT '[]'::JSONB,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'fixed', 'ignored')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.pending_fixes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  audit_id UUID REFERENCES public.technical_audits(id) ON DELETE SET NULL,
  fix_type TEXT NOT NULL,
  description TEXT,
  fix_payload JSONB DEFAULT '{}'::JSONB,
  status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval', 'approved', 'applied', 'rejected')),
  proposed_by TEXT,
  applied_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 11. Backlink Opportunities, Prospects & Monitor
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.backlink_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  target_url TEXT,
  anchor_text TEXT,
  domain_rating INT DEFAULT 0,
  category TEXT DEFAULT 'resource_page',
  opportunity_type TEXT DEFAULT 'competitor_gap',
  status TEXT NOT NULL DEFAULT 'opportunity' CHECK (status IN ('opportunity', 'approved', 'contacted', 'acquired', 'lost', 'rejected')),
  priority FLOAT DEFAULT 0.8,
  checked_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.backlink_prospects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  prospect_url TEXT NOT NULL,
  domain_rating FLOAT DEFAULT 0,
  contact_email TEXT,
  strategy TEXT DEFAULT 'resource_page',
  reason TEXT,
  broken_link_url TEXT,
  anchor_suggestion TEXT,
  target_page_url TEXT,
  target_keyword TEXT,
  relevance_score FLOAT DEFAULT 1.0,
  status TEXT DEFAULT 'opportunity' CHECK (status IN ('opportunity', 'approved', 'contacted', 'acquired', 'lost', 'rejected')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 12. Content Calendar & Scheduling
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.content_calendar (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  keywords JSONB DEFAULT '[]'::JSONB,
  scheduled_date DATE NOT NULL DEFAULT CURRENT_DATE,
  status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'in_progress', 'draft_ready', 'published', 'cancelled')),
  priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
  content_log_id UUID REFERENCES public.content_log(id) ON DELETE SET NULL,
  target_table TEXT DEFAULT 'content_log',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 13. Realtime Alerts & Monitoring
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
  title TEXT NOT NULL,
  description TEXT,
  data JSONB DEFAULT '{}'::JSONB,
  status TEXT DEFAULT 'unread' CHECK (status IN ('unread', 'read', 'actioned', 'dismissed')),
  is_read BOOLEAN DEFAULT false,
  is_actioned BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.realtime_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium',
  title TEXT NOT NULL,
  description TEXT,
  data JSONB DEFAULT '{}'::JSONB,
  is_read BOOLEAN DEFAULT false,
  is_actioned BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 14. AEO / GEO Visibility & Citation Tracking
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.geo_visibility_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  platform TEXT DEFAULT 'google_ai_overview',
  query TEXT,
  prompt TEXT,
  ai_engine TEXT DEFAULT 'google_ai_overview',
  cited BOOLEAN DEFAULT false,
  was_cited BOOLEAN DEFAULT false,
  citation_position INT,
  response_snippet TEXT,
  citation_text TEXT,
  citation_url TEXT,
  checked_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 15. Settings Key-Value Store
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.settings (
  key TEXT NOT NULL,
  value TEXT,
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (key, website_id)
);

-- --------------------------------------------------------------------
-- 16. WordPress Connections Pool
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wordpress_connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
  site_url TEXT NOT NULL,
  username TEXT NOT NULL,
  app_password_encrypted TEXT,
  status TEXT DEFAULT 'connected',
  last_verified_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------
-- 17. Triggers & Synchronization Functions
-- --------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sync_pending_approval_to_blog_approvals()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status = 'pending_approval' THEN
    INSERT INTO public.blog_approvals (
      website_id,
      user_id,
      blog_id,
      title,
      html_content,
      content,
      keyword,
      status,
      created_at
    )
    VALUES (
      NEW.website_id,
      NEW.user_id,
      NEW.id,
      NEW.title,
      NEW.content,
      NEW.content,
      NEW.keyword,
      'pending',
      NOW()
    )
    ON CONFLICT (id) DO NOTHING;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_sync_pending_approval ON public.content_log;
CREATE TRIGGER trigger_sync_pending_approval
AFTER INSERT OR UPDATE OF status ON public.content_log
FOR EACH ROW
EXECUTE FUNCTION sync_pending_approval_to_blog_approvals();

-- --------------------------------------------------------------------
-- 18. Vector Search RPC Functions
-- --------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_content(
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) RETURNS TABLE (
  id uuid,
  similarity float
) LANGUAGE sql STABLE AS $$
  SELECT
    id,
    1 - (embedding <=> query_embedding) AS similarity
  FROM public.content_log
  WHERE website_id = p_website_id
    AND embedding IS NOT NULL
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT 10;
$$;

CREATE OR REPLACE FUNCTION match_brain_memory(
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) RETURNS TABLE (
  id uuid,
  similarity float
) LANGUAGE sql STABLE AS $$
  SELECT
    id,
    1 - (embedding <=> query_embedding) AS similarity
  FROM public.brain_memory
  WHERE website_id = p_website_id
    AND embedding IS NOT NULL
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT 20;
$$;

-- --------------------------------------------------------------------
-- 19. Performance Indexes
-- --------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_websites_user_id ON public.websites(user_id);
CREATE INDEX IF NOT EXISTS idx_websites_domain ON public.websites(domain);
CREATE INDEX IF NOT EXISTS idx_content_log_website ON public.content_log(website_id);
CREATE INDEX IF NOT EXISTS idx_content_log_status ON public.content_log(status);
CREATE INDEX IF NOT EXISTS idx_blog_approvals_website ON public.blog_approvals(website_id);
CREATE INDEX IF NOT EXISTS idx_blog_approvals_status ON public.blog_approvals(status);
CREATE INDEX IF NOT EXISTS idx_brain_memory_website ON public.brain_memory(website_id);
CREATE INDEX IF NOT EXISTS idx_tasks_website ON public.tasks(website_id);
CREATE INDEX IF NOT EXISTS idx_technical_audits_website ON public.technical_audits(website_id);
CREATE INDEX IF NOT EXISTS idx_content_calendar_website ON public.content_calendar(website_id);


-- ====================================================================
-- RANK TRACKING, INTERNAL LINK INDEX & CONTENT REFRESH QUEUE
-- ====================================================================

-- 1. Rank Tracking Table
CREATE TABLE IF NOT EXISTS public.rank_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    blog_id UUID,
    wp_post_id TEXT,
    wp_url TEXT NOT NULL,
    target_keyword TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'tracking' CHECK (status IN ('tracking', 'paused', 'completed')),
    published_at TIMESTAMPTZ DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    current_position INT,
    best_position INT,
    position_history JSONB DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rank_tracking_website ON public.rank_tracking(website_id);
CREATE INDEX IF NOT EXISTS idx_rank_tracking_status ON public.rank_tracking(status);
CREATE INDEX IF NOT EXISTS idx_rank_tracking_keyword ON public.rank_tracking(target_keyword);

-- 2. Internal Link Index Table
CREATE TABLE IF NOT EXISTS public.internal_link_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    blog_id UUID,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    target_keyword TEXT NOT NULL,
    linkable_topics JSONB DEFAULT '[]'::JSONB,
    summary TEXT,
    published_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_internal_link_website ON public.internal_link_index(website_id);
CREATE INDEX IF NOT EXISTS idx_internal_link_url ON public.internal_link_index(url);

-- 3. Content Refresh Queue Table
CREATE TABLE IF NOT EXISTS public.content_refresh_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID REFERENCES public.websites(id) ON DELETE CASCADE,
    blog_id UUID,
    wp_post_id TEXT,
    target_keyword TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_content_refresh_website ON public.content_refresh_queue(website_id);
CREATE INDEX IF NOT EXISTS idx_content_refresh_status ON public.content_refresh_queue(status);
