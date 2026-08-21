-- Content Decay & Auto-Refresh + Topic Authority Schema
-- Run in Supabase SQL Editor

-- Content Decay Logs - track pages losing rank/clicks
CREATE TABLE IF NOT EXISTS content_decay_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
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
  refreshed_content_id UUID REFERENCES content_log(id),
  wordpress_post_id INT,
  last_refresh_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_decay_website_status ON content_decay_logs(website_id, status);
CREATE INDEX IF NOT EXISTS idx_decay_detected ON content_decay_logs(detected_at DESC);

-- Topic Authority Clusters - organize content into pillar topics
CREATE TABLE IF NOT EXISTS topic_clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  cluster_name TEXT,
  pillar_keyword TEXT,
  pillar_page_url TEXT,
  keywords JSONB,
  coverage INT DEFAULT 0,
  authority_score FLOAT DEFAULT 0,
  avg_position FLOAT DEFAULT 0,
  internal_links_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clusters_website ON topic_clusters(website_id);
CREATE INDEX IF NOT EXISTS idx_clusters_authority ON topic_clusters(website_id, authority_score DESC);

-- Cluster Articles - individual articles in a cluster
CREATE TABLE IF NOT EXISTS cluster_articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id UUID REFERENCES topic_clusters(id),
  website_id UUID REFERENCES websites(id),
  keyword TEXT,
  intent TEXT,
  business_potential INT CHECK (business_potential BETWEEN 0 AND 3),
  search_volume INT,
  current_position FLOAT,
  status TEXT CHECK (status IN ('opportunity','queued','writing','draft_ready','published','decayed','published_refresh')) DEFAULT 'opportunity',
  content_id UUID REFERENCES content_log(id),
  priority_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  queued_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cluster_articles_priority ON cluster_articles(cluster_id, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_cluster_articles_status ON cluster_articles(website_id, status);

-- GEO Visibility Logs - track AI search citation
CREATE TABLE IF NOT EXISTS geo_visibility_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  prompt TEXT,
  ai_engine TEXT CHECK (ai_engine IN ('chatgpt','perplexity','google_ai_overview')),
  was_cited BOOLEAN,
  citation_text TEXT,
  citation_url TEXT,
  checked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_geo_visibility ON geo_visibility_logs(website_id, was_cited DESC);

-- Add columns to existing content_log
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS is_refresh BOOLEAN DEFAULT false;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS original_page_url TEXT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS decay_log_id UUID REFERENCES content_decay_logs(id);
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS mode TEXT; -- grounded, deep_web, combined, refresh