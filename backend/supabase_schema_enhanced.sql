-- realtime_alerts - All issues, drops, bugs, opportunities appear here
CREATE TABLE IF NOT EXISTS realtime_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  alert_type TEXT CHECK (alert_type IN ('rank_drop','rank_opportunity','competitor_price','competitor_content','tech_broken_link','tech_speed','tech_mobile','tech_crawl','tech_index','keyword_opportunity','content_gap','monitor_error','wp_error')),
  severity TEXT CHECK (severity IN ('critical','high','medium','low','info')),
  title TEXT NOT NULL,
  description TEXT,
  data JSONB,
  source_monitor TEXT,
  is_read BOOLEAN DEFAULT false,
  is_actioned BOOLEAN DEFAULT false,
  action_taken TEXT,
  requires_human_approval BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_unread ON realtime_alerts(website_id, is_read) WHERE is_read=false;
CREATE INDEX IF NOT EXISTS idx_alerts_created ON realtime_alerts(website_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON realtime_alerts(website_id, severity);

-- monitoring_logs - Track monitor execution
CREATE TABLE IF NOT EXISTS monitoring_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID,
  monitor_type TEXT,
  status TEXT,
  checked_urls INT,
  issues_found INT,
  execution_ms INT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_monitoring_recent ON monitoring_logs(website_id, created_at DESC);

-- topic_clusters - Auto-generated content strategy
CREATE TABLE IF NOT EXISTS topic_clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  pillar_topic TEXT,
  pillar_keyword TEXT,
  clusters JSONB,
  created_from_alert_id UUID REFERENCES realtime_alerts(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clusters_website ON topic_clusters(website_id, created_at DESC);

-- pending_fixes - Manual fixes awaiting human approval
CREATE TABLE IF NOT EXISTS pending_fixes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
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

CREATE INDEX IF NOT EXISTS idx_fixes_pending ON pending_fixes(website_id, status) WHERE status='pending_approval';

-- content_pipeline_logs - Full pipeline audit trail
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

-- content_expert_reviews - Multi-expert review results
CREATE TABLE IF NOT EXISTS content_expert_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES content_log(id),
  expert_name TEXT,
  score INT,
  issues JSONB,
  passed BOOLEAN,
  reviewed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_content ON content_expert_reviews(content_id);

-- content_log - Main content tracking (added columns)
-- ALTER TABLE content_log ADD COLUMN IF NOT EXISTS pipeline_status TEXT DEFAULT 'not_started';
-- ALTER TABLE content_log ADD COLUMN IF NOT EXISTS eeat_data JSONB;
-- ALTER TABLE content_log ADD COLUMN IF NOT EXISTS ai_search_score INT;
-- ALTER TABLE content_log ADD COLUMN IF NOT EXISTS information_gain_score INT;
-- ALTER TABLE content_log ADD COLUMN IF NOT EXISTS wordpress_draft_id INT;