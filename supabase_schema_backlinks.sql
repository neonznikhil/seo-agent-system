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

CREATE INDEX IF NOT EXISTS idx_backlink_prospects_website ON backlink_prospects(website_id, status, strategy);
CREATE INDEX IF NOT EXISTS idx_backlink_monitor_website ON backlink_monitor(website_id, status);
CREATE INDEX IF NOT EXISTS idx_internal_graph_website ON internal_link_graph(website_id, is_orphan_target);
