-- REAL-DATA INTEGRATION SCHEMA UPDATES
-- Run these in Supabase SQL Editor

-- Enhanced content_log table for pipeline
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS pipeline_status TEXT DEFAULT 'not_started';
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS eeat_data JSONB;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS ai_search_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS information_gain_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS wordpress_draft_id INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS business_potential_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS winning_patterns JSONB;

-- Serp Landscape table - real SERP analysis
CREATE TABLE IF NOT EXISTS serp_landscape (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  keyword TEXT NOT NULL,
  top_pages JSONB,
  winning_patterns JSONB,
  extracted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_serp_keyword ON serp_landscape(website_id, keyword);

-- Content Pipeline Logs - FULL AUDIT TRAIL (100+ steps)
CREATE TABLE IF NOT EXISTS content_pipeline_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID,
  website_id UUID REFERENCES websites(id),
  phase TEXT CHECK (phase IN ('audience_demand','serp_competitor','positioning_outline','multi_step_writing','multi_expert_review','humanizer_gate','wordpress_export')),
  step_number INT,
  step_name TEXT,
  status TEXT CHECK (status IN ('pending','running','completed','failed','needs_human')),
  input_data JSONB,
  output_data JSONB,
  thought TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_content ON content_pipeline_logs(content_id, step_number);
CREATE INDEX IF NOT EXISTS idx_pipeline_phase ON content_pipeline_logs(website_id, phase, step_number);

-- Expert Reviews - 11 expert scores
CREATE TABLE IF NOT EXISTS content_expert_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES content_log(id),
  expert_name TEXT,
  score INT CHECK (score >= 0 AND score <= 100),
  issues JSONB,
  passed BOOLEAN,
  reviewed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_content ON content_expert_reviews(content_id);

-- Internal link suggestions
CREATE TABLE IF NOT EXISTS internal_link_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES content_log(id),
  source_url TEXT,
  target_url TEXT,
  anchor_text TEXT,
  context JSONB,
  proposed_at TIMESTAMPTZ DEFAULT NOW(),
  approved_at TIMESTAMPTZ,
  approved_by TEXT,
  applied BOOLEAN DEFAULT false
);

-- Create views for easier querying
CREATE VIEW IF NOT EXISTS vw_content_pipeline_status AS
SELECT 
  content_id,
  website_id,
  MAX(CASE WHEN phase = 'audience_demand' THEN 'completed' ELSE 'pending' END) as audience_demand,
  MAX(CASE WHEN phase = 'serp_competitor' THEN 'completed' ELSE 'pending' END) as serp_competitor,
  MAX(CASE WHEN phase = 'positioning_outline' THEN 'completed' ELSE 'pending' END) as positioning_outline,
  MAX(CASE WHEN phase = 'multi_step_writing' THEN 'completed' ELSE 'pending' END) as multi_step_writing,
  MAX(CASE WHEN phase = 'multi_expert_review' THEN 'completed' ELSE 'pending' END) as multi_expert_review,
  MAX(CASE WHEN phase = 'humanizer_gate' THEN 'completed' ELSE 'pending' END) as humanizer_gate,
  COUNT(*) as total_steps_completed
FROM content_pipeline_logs
WHERE status = 'completed'
GROUP BY content_id, website_id;

-- Add real-time data source tracking to alerts
ALTER TABLE realtime_alerts ADD COLUMN IF NOT EXISTS data_source TEXT;
ALTER TABLE realtime_alerts ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT true;

-- Alert for when data sources are missing
CREATE TABLE IF NOT EXISTS data_source_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  missing_service TEXT CHECK (missing_service IN ('gsc','ga4','crawlee','pagespeed')),
  action_required TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge Sources for Grounded Mode
CREATE TABLE IF NOT EXISTS knowledge_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  source_type TEXT CHECK (source_type IN ('google_drive','notion','pdf','docx','url','brand_brief','founder_insights','customer_research')),
  title TEXT,
  file_path TEXT,
  content_extracted TEXT,
  embedding vector(1536),
  is_verified BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_website ON knowledge_sources(website_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_verified ON knowledge_sources(website_id, is_verified);

-- Deep research cache for Deep Web mode
CREATE TABLE IF NOT EXISTS deep_research_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword TEXT,
  serp_data JSONB,
  competitor_gaps JSONB,
  keyword_planner_data JSONB,
  prompt_questions JSONB,
  cached_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deep_keyword ON deep_research_cache(keyword);