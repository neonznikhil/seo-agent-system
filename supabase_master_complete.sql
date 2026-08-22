-- ====================================================================
-- RANKFORGE COMPLETE CONSOLIDATED SUPABASE SCHEMA
-- Run this in Supabase SQL Editor in ONE single run
-- ====================================================================

-- 1. Enable Vector Extension for Embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Websites Table
CREATE TABLE IF NOT EXISTS websites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain TEXT NOT NULL UNIQUE,
  url TEXT,
  cms_url TEXT,
  cms_user TEXT,
  app_password TEXT,
  gsc_property TEXT,
  status TEXT DEFAULT 'active',
  oauth_enabled BOOLEAN DEFAULT false,
  wp_oauth_connected BOOLEAN DEFAULT false,
  slack_webhook_url TEXT,
  alert_email TEXT,
  local_target TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Pages Table
CREATE TABLE IF NOT EXISTS pages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  title TEXT,
  content_text TEXT,
  embedding vector(1024),
  last_audited TIMESTAMPTZ,
  impressions INT DEFAULT 0,
  ctr FLOAT DEFAULT 0.0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Website Knowledge & Tone
CREATE TABLE IF NOT EXISTS website_knowledge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  url TEXT,
  title TEXT,
  content_text TEXT,
  embedding vector(1024),
  content_type TEXT CHECK (content_type IN ('homepage','about','product','blog')),
  tone_sample TEXT,
  extracted_facts JSONB DEFAULT '[]'::JSONB,
  crawled_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tone_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE UNIQUE,
  tone_description TEXT NOT NULL,
  writing_style TEXT NOT NULL,
  vocabulary JSONB DEFAULT '[]'::JSONB,
  forbidden_words JSONB DEFAULT '[]'::JSONB,
  sample_embeddings vector(1024)[],
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_base (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  fact TEXT NOT NULL,
  fact_type TEXT NOT NULL CHECK (fact_type IN ('product_name','pricing','feature','company_info','tone_rule')),
  source_url TEXT,
  embedding vector(1024),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  source_type TEXT CHECK (source_type IN ('google_drive','notion','pdf','docx','url','brand_brief','founder_insights','customer_research')),
  title TEXT,
  file_path TEXT,
  content_extracted TEXT,
  embedding vector(1536),
  is_verified BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Content Log (Articles & Drafts)
CREATE TABLE IF NOT EXISTS content_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','draft_planned','pending_approval','needs_revision','published','failed')),
  keyword TEXT,
  use_case TEXT,
  embedding vector(1024),
  faq_schema JSONB DEFAULT '{}'::JSONB,
  internal_links JSONB DEFAULT '[]'::JSONB,
  similarity_score FLOAT,
  published_url TEXT,
  quality_checked BOOLEAN DEFAULT false,
  pipeline_status TEXT DEFAULT 'not_started',
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
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. GSC Keywords & SERP Landscape
CREATE TABLE IF NOT EXISTS gsc_keywords (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  keyword TEXT,
  query TEXT,
  impressions INT DEFAULT 0,
  clicks INT DEFAULT 0,
  ctr FLOAT DEFAULT 0.0,
  position FLOAT DEFAULT 0.0,
  url TEXT,
  is_active BOOLEAN DEFAULT true,
  crawled_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS serp_landscape (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  top_pages JSONB,
  top_urls JSONB,
  paa_questions JSONB,
  featured_snippet JSONB,
  gaps JSONB,
  winning_patterns JSONB,
  extracted_at TIMESTAMPTZ DEFAULT NOW(),
  crawled_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deep_research_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword TEXT,
  serp_data JSONB,
  competitor_gaps JSONB,
  keyword_planner_data JSONB,
  prompt_questions JSONB,
  cached_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Topic Clusters & Cluster Articles
CREATE TABLE IF NOT EXISTS topic_clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  cluster_name TEXT,
  pillar_topic TEXT,
  pillar_keyword TEXT,
  pillar_page_url TEXT,
  keywords JSONB,
  clusters JSONB,
  coverage INT DEFAULT 0,
  authority_score FLOAT DEFAULT 0,
  avg_position FLOAT DEFAULT 0,
  internal_links_count INT DEFAULT 0,
  created_from_alert_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cluster_articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id UUID REFERENCES topic_clusters(id) ON DELETE CASCADE,
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  keyword TEXT,
  intent TEXT,
  business_potential INT CHECK (business_potential BETWEEN 0 AND 3),
  search_volume INT,
  current_position FLOAT,
  status TEXT CHECK (status IN ('opportunity','queued','writing','draft_ready','published','decayed','published_refresh')) DEFAULT 'opportunity',
  content_id UUID REFERENCES content_log(id) ON DELETE SET NULL,
  priority_score FLOAT,
  gsc_impressions INT,
  gsc_position FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  queued_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ
);

-- 8. Content Decay & GEO Visibility
CREATE TABLE IF NOT EXISTS content_decay_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  page_url TEXT,
  page_title TEXT,
  primary_keyword TEXT,
  previous_position FLOAT,
  current_position FLOAT,
  previous_clicks INT,
  current_clicks INT,
  decay_percent FLOAT,
  decay_reason JSONB,
  diagnosis JSONB,
  status TEXT CHECK (status IN ('detected','diagnosing','refresh_queued','refreshing','draft_ready','approved','published','ignored')) DEFAULT 'detected',
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  diagnosed_at TIMESTAMPTZ,
  refreshed_content_id UUID REFERENCES content_log(id) ON DELETE SET NULL,
  wordpress_post_id INT,
  last_refresh_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS geo_visibility_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  prompt TEXT,
  ai_engine TEXT CHECK (ai_engine IN ('chatgpt','perplexity','google_ai_overview')),
  was_cited BOOLEAN,
  citation_text TEXT,
  citation_url TEXT,
  checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Audits & Quality Checks
CREATE TABLE IF NOT EXISTS audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  page_url TEXT,
  issue_type TEXT NOT NULL CHECK (issue_type IN ('missing_meta','duplicate_title','low_ctr_title','missing_h1','no_alt','no_internal','missing_canonical','broken_link','redirect_chain','schema_error','noindex_wrong')),
  old_value TEXT,
  new_value TEXT,
  impact_score FLOAT,
  status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval','fixed','rejected')),
  human_user_id TEXT,
  approval_timestamp TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS technical_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  audit_type TEXT,
  issue_type TEXT NOT NULL CHECK (issue_type IN ('sitemap','robots','canonical','broken_link','redirect_chain','schema','noindex','ssl','performance')),
  severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('high','medium','low')),
  metrics JSONB DEFAULT '{}'::JSONB,
  details JSONB DEFAULT '{}'::JSONB,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','fixed','ignored')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quality_checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_log_id UUID REFERENCES content_log(id) ON DELETE CASCADE,
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  spell_check_pass BOOLEAN DEFAULT true,
  spell_errors JSONB DEFAULT '[]'::JSONB,
  tone_match_score FLOAT DEFAULT 0.0 CHECK (tone_match_score >= 0 AND tone_match_score <= 1),
  knowledge_match_pass BOOLEAN DEFAULT true,
  knowledge_errors JSONB DEFAULT '[]'::JSONB,
  factual_accuracy_pass BOOLEAN DEFAULT true,
  overall_pass BOOLEAN DEFAULT true,
  checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. Agent Thoughts, Feedback, Tasks & Pipeline Logs
CREATE TABLE IF NOT EXISTS agent_thoughts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  thought TEXT NOT NULL,
  decision TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  rejected_type TEXT NOT NULL,
  rejected_value TEXT,
  human_feedback TEXT NOT NULL,
  learning TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  action TEXT NOT NULL,
  payload JSONB DEFAULT '{}'::JSONB,
  result JSONB DEFAULT '{}'::JSONB,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','success','failed','skipped')),
  real_api_called TEXT,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_pipeline_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID,
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  phase TEXT CHECK (phase IN ('audience_demand','serp_competitor','positioning_outline','multi_step_writing','multi_expert_review','humanizer_gate','wordpress_export')),
  step_number INT,
  step_name TEXT,
  status TEXT CHECK (status IN ('pending','running','completed','failed','needs_human')),
  input_data JSONB,
  output_data JSONB,
  thought TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_expert_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES content_log(id) ON DELETE CASCADE,
  expert_name TEXT,
  score INT CHECK (score >= 0 AND score <= 100),
  issues JSONB,
  passed BOOLEAN,
  reviewed_at TIMESTAMPTZ DEFAULT NOW()
);

-- 11. Alerts, Monitoring & Fixes
CREATE TABLE IF NOT EXISTS realtime_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  alert_type TEXT CHECK (alert_type IN ('rank_drop','rank_opportunity','competitor_price','competitor_content','tech_broken_link','tech_speed','tech_mobile','tech_crawl','tech_index','keyword_opportunity','content_gap','monitor_error','wp_error')),
  severity TEXT CHECK (severity IN ('critical','high','medium','low','info')),
  title TEXT NOT NULL,
  description TEXT,
  data JSONB,
  data_source TEXT,
  verified BOOLEAN DEFAULT true,
  source_monitor TEXT,
  is_read BOOLEAN DEFAULT false,
  is_actioned BOOLEAN DEFAULT false,
  action_taken TEXT,
  requires_human_approval BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS monitoring_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  monitor_type TEXT,
  status TEXT,
  checked_urls INT,
  issues_found INT,
  execution_ms INT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pending_fixes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  audit_id UUID,
  fix_type TEXT,
  fix_payload JSONB,
  fix_method TEXT,
  status TEXT DEFAULT 'pending_approval',
  proposed_by TEXT,
  approved_by TEXT,
  applied_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_source_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  missing_service TEXT CHECK (missing_service IN ('gsc','ga4','crawlee','pagespeed')),
  action_required TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 12. Backlinks & Outreach
CREATE TABLE IF NOT EXISTS backlinks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  target_url TEXT NOT NULL,
  anchor_text TEXT,
  domain_rating INT DEFAULT 0,
  first_seen TIMESTAMPTZ DEFAULT NOW(),
  last_seen TIMESTAMPTZ DEFAULT NOW(),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','lost','toxic')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backlink_prospects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  prospect_url TEXT NOT NULL,
  domain_rating FLOAT,
  contact_email TEXT,
  strategy TEXT CHECK (strategy IN ('broken_link','resource_page','competitor_gap','guest_post')) NOT NULL,
  reason TEXT NOT NULL,
  broken_link_url TEXT,
  anchor_suggestion TEXT,
  target_page_url TEXT,
  target_keyword TEXT,
  relevance_score FLOAT,
  status TEXT CHECK (status IN ('opportunity','approved','contacted','acquired','lost','rejected')) DEFAULT 'opportunity',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backlink_monitor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  backlink_url TEXT NOT NULL,
  source_url TEXT NOT NULL,
  anchor_text TEXT,
  domain_rating FLOAT,
  status_code INT,
  status TEXT CHECK (status IN ('active','broken','redirected','lost')) DEFAULT 'active',
  first_seen_at TIMESTAMPTZ DEFAULT NOW(),
  checked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS internal_link_graph (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  from_url TEXT NOT NULL,
  to_url TEXT NOT NULL,
  anchor_text TEXT,
  pagerank_from FLOAT,
  pagerank_to FLOAT,
  sessions_from INT DEFAULT 0,
  is_orphan_target BOOLEAN DEFAULT false,
  crawled_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS internal_link_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES content_log(id) ON DELETE CASCADE,
  source_url TEXT,
  target_url TEXT,
  anchor_text TEXT,
  context JSONB,
  proposed_at TIMESTAMPTZ DEFAULT NOW(),
  approved_at TIMESTAMPTZ,
  approved_by TEXT,
  applied BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS outreach_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  prospect_id UUID REFERENCES backlink_prospects(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT CHECK (status IN ('draft_ready','approved','sent','replied','rejected')) DEFAULT 'draft_ready',
  approved_by TEXT,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 13. System Logs & Integrations
CREATE TABLE IF NOT EXISTS llms_txt_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  last_updated TIMESTAMPTZ DEFAULT NOW(),
  next_due TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days')
);

CREATE TABLE IF NOT EXISTS critical_action_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  agent_name TEXT,
  action_type TEXT,
  attempted_at TIMESTAMPTZ,
  blocked BOOLEAN,
  block_reason TEXT,
  status_before TEXT,
  approved_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wordpress_oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  user_id TEXT,
  wp_site_url TEXT,
  client_id TEXT,
  access_token TEXT,
  access_token_encrypted TEXT,
  refresh_token TEXT,
  refresh_token_encrypted TEXT,
  token_type TEXT DEFAULT 'Bearer',
  expires_at TIMESTAMPTZ,
  scope TEXT,
  provider TEXT DEFAULT 'wordpress',
  wp_user_id INT,
  wp_user_login TEXT,
  is_connected BOOLEAN DEFAULT true,
  connected_at TIMESTAMPTZ DEFAULT NOW(),
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 14. Brain Memory & Autopilot
CREATE TABLE IF NOT EXISTS brain_memory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  memory_type TEXT CHECK (memory_type IN ('fact','experience','failure','preference','entity','relationship','outcome')),
  title TEXT,
  content TEXT,
  embedding vector(1024),
  source_type TEXT,
  source_id UUID,
  confidence FLOAT DEFAULT 0.8,
  times_used INT DEFAULT 0,
  times_successful INT DEFAULT 0,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brain_daily_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  job_type TEXT CHECK (job_type IN ('daily_search','daily_refresh_check','daily_cluster_build','daily_geo_check','daily_backlink_check','daily_new_page_suggestion')),
  status TEXT CHECK (status IN ('pending','running','completed','failed')) DEFAULT 'pending',
  result JSONB,
  error TEXT,
  run_at TIMESTAMPTZ DEFAULT NOW(),
  next_run_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS brain_content_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES content_log(id) ON DELETE CASCADE,
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  keyword TEXT,
  position_history JSONB,
  what_worked JSONB,
  what_failed JSONB,
  learned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brain_auto_pages_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  suggested_topic TEXT,
  primary_keyword TEXT,
  reason TEXT,
  priority_score FLOAT,
  source TEXT,
  status TEXT CHECK (status IN ('suggested','approved_auto','queued_for_writing','writing','draft_ready','published','rejected')) DEFAULT 'suggested',
  auto_approve BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 15. Vector Matching Functions (RPC)
CREATE OR REPLACE FUNCTION match_content (
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
  FROM content_log
  WHERE website_id = p_website_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT 10;
$$;

CREATE OR REPLACE FUNCTION match_pages (
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) RETURNS TABLE (
  id uuid,
  url text,
  similarity float
) LANGUAGE sql STABLE AS $$
  SELECT
    id,
    url,
    1 - (embedding <=> query_embedding) AS similarity
  FROM pages
  WHERE website_id = p_website_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT 20;
$$;

CREATE OR REPLACE FUNCTION match_knowledge (
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) RETURNS TABLE (
  id uuid,
  fact text,
  similarity float
) LANGUAGE sql STABLE AS $$
  SELECT
    id,
    fact,
    1 - (embedding <=> query_embedding) AS similarity
  FROM knowledge_base
  WHERE website_id = p_website_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT 10;
$$;

CREATE OR REPLACE FUNCTION match_brain_memory (
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
  FROM brain_memory
  WHERE website_id = p_website_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT 20;
$$;

-- 16. Performance Indexes
CREATE INDEX IF NOT EXISTS idx_websites_domain ON websites(domain);
CREATE INDEX IF NOT EXISTS idx_pages_website ON pages(website_id);
CREATE INDEX IF NOT EXISTS idx_content_log_website ON content_log(website_id);
CREATE INDEX IF NOT EXISTS idx_content_log_status ON content_log(status);
CREATE INDEX IF NOT EXISTS idx_quality_checks_content ON quality_checks(content_log_id);
CREATE INDEX IF NOT EXISTS idx_agent_thoughts_website ON agent_thoughts(website_id);
CREATE INDEX IF NOT EXISTS idx_tasks_website ON tasks(website_id);
CREATE INDEX IF NOT EXISTS idx_alerts_unread ON realtime_alerts(website_id, is_read) WHERE is_read=false;
CREATE INDEX IF NOT EXISTS idx_alerts_created ON realtime_alerts(website_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON realtime_alerts(website_id, severity);
CREATE INDEX IF NOT EXISTS idx_topic_clusters_website ON topic_clusters(website_id);
CREATE INDEX IF NOT EXISTS idx_cluster_articles_priority ON cluster_articles(cluster_id, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_cluster_articles_status ON cluster_articles(website_id, status);
CREATE INDEX IF NOT EXISTS idx_decay_website_status ON content_decay_logs(website_id, status);
CREATE INDEX IF NOT EXISTS idx_geo_visibility ON geo_visibility_logs(website_id, was_cited DESC);
CREATE INDEX IF NOT EXISTS idx_serp_keyword ON serp_landscape(website_id, keyword);
CREATE INDEX IF NOT EXISTS idx_pipeline_content ON content_pipeline_logs(content_id, step_number);
CREATE INDEX IF NOT EXISTS idx_pipeline_phase ON content_pipeline_logs(website_id, phase, step_number);
CREATE INDEX IF NOT EXISTS idx_reviews_content ON content_expert_reviews(content_id);
CREATE INDEX IF NOT EXISTS idx_fixes_pending ON pending_fixes(website_id, status) WHERE status='pending_approval';
CREATE INDEX IF NOT EXISTS idx_backlink_prospects_website ON backlink_prospects(website_id, status, strategy);
CREATE INDEX IF NOT EXISTS idx_backlink_monitor_website ON backlink_monitor(website_id, status);
CREATE INDEX IF NOT EXISTS idx_internal_graph_website ON internal_link_graph(website_id, is_orphan_target);
CREATE INDEX IF NOT EXISTS idx_brain_memory_website_type ON brain_memory(website_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_brain_daily_jobs_website ON brain_daily_jobs(website_id);
CREATE INDEX IF NOT EXISTS idx_brain_auto_queue_website ON brain_auto_pages_queue(website_id, status);
