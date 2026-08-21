-- SEO Agent System - Complete Database Schema
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS topic_clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  cluster_name TEXT,
  pillar_keyword TEXT,
  pillar_page_url TEXT,
  keywords JSONB,
  coverage INT DEFAULT 0,
  authority_score FLOAT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cluster_articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id UUID REFERENCES topic_clusters(id),
  website_id UUID REFERENCES websites(id),
  keyword TEXT,
  intent TEXT,
  business_potential INT CHECK (business_potential BETWEEN 0 AND 3),
  status TEXT CHECK (status IN ('opportunity','queued','writing','draft_ready','published','decayed')) DEFAULT 'opportunity',
  content_id UUID REFERENCES content_log(id),
  priority_score FLOAT,
  gsc_impressions INT,
  gsc_position FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS serp_landscape (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  keyword TEXT,
  top_urls JSONB, -- [{url, title, h1, h2s, word_count, has_table, has_faq, schema_types, last_updated}]
  paa_questions JSONB,
  featured_snippet JSONB,
  gaps JSONB, -- {missing_h2s: [], word_count_gap: {ours, avg}, missing_table: bool, missing_faq: bool, new_competitors: []}
  crawled_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backlink_prospects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  prospect_url TEXT,
  domain_rating FLOAT,
  contact_email TEXT,
  strategy TEXT CHECK (strategy IN ('broken_link','resource_page','competitor_gap','guest_post')),
  reason TEXT,
  anchor_suggestion TEXT,
  status TEXT CHECK (status IN ('opportunity','contacted','acquired','lost','rejected')) DEFAULT 'opportunity',
  broken_link_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backlink_monitor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  backlink_url TEXT,
  source_url TEXT,
  anchor_text TEXT,
  domain_rating FLOAT,
  status_code INT,
  status TEXT CHECK (status IN ('active','broken','redirected','lost')),
  checked_at TIMESTAMPTZ DEFAULT NOW()
);

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
  status TEXT CHECK (status IN ('detected','diagnosing','refresh_queued','refreshing','draft_ready','approved','published','ignored')) DEFAULT 'detected',
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  refreshed_content_id UUID REFERENCES content_log(id)
);

-- Add new columns to content_log if they don't exist
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS is_refresh BOOLEAN DEFAULT false;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS original_page_url TEXT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS mode TEXT CHECK (mode IN ('grounded','deep','combined')) DEFAULT 'combined';
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS human_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS seo_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS eeat_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS ai_search_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS info_gain_score INT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS business_potential INT;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_topic_clusters_website_id ON topic_clusters(website_id);
CREATE INDEX IF NOT EXISTS idx_cluster_articles_website_id ON cluster_articles(website_id);
CREATE INDEX IF NOT EXISTS idx_cluster_articles_cluster_id ON cluster_articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_serp_landscape_website_id ON serp_landscape(website_id);
CREATE INDEX IF NOT EXISTS idx_backlink_prospects_website_id ON backlink_prospects(website_id);
CREATE INDEX IF NOT EXISTS idx_backlink_monitor_website_id ON backlink_monitor(website_id);
CREATE INDEX IF NOT EXISTS idx_geo_visibility_website_id ON geo_visibility_logs(website_id);
CREATE INDEX IF NOT EXISTS idx_content_decay_website_id ON content_decay_logs(website_id);
