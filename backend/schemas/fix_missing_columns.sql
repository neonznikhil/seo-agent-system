-- Fix missing columns in websites table
ALTER TABLE websites ADD COLUMN IF NOT EXISTS oauth_enabled BOOLEAN DEFAULT false;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS slack_webhook_url TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS alert_email TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS local_target TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wordpress_url TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wordpress_user TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wordpress_password TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- Fix content_log
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS quality_checked BOOLEAN DEFAULT false;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS wp_post_id INTEGER;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS wp_draft_url TEXT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS approved_by TEXT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP;

-- Fix technical_audits
ALTER TABLE technical_audits ADD COLUMN IF NOT EXISTS audit_type TEXT;
ALTER TABLE technical_audits ADD COLUMN IF NOT EXISTS metrics JSONB;

-- Create website_pages if missing
CREATE TABLE IF NOT EXISTS website_pages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    content TEXT,
    word_count INTEGER,
    last_crawled TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create keyword_opportunities if missing
CREATE TABLE IF NOT EXISTS keyword_opportunities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    search_volume INTEGER DEFAULT 0,
    current_position INTEGER,
    opportunity_score FLOAT DEFAULT 0,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Phase 3 Column Alterations
ALTER TABLE websites ADD COLUMN IF NOT EXISTS slack_channels JSONB DEFAULT '{"daily": "#rankforge-daily", "backlinks": "#rankforge-backlinks", "weekly": "#rankforge-weekly", "alerts": "#rankforge-alerts"}'::jsonb;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS acquired_backlinks_count INTEGER DEFAULT 0;
ALTER TABLE brain_memory ADD COLUMN IF NOT EXISTS outcome_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE brain_memory ADD COLUMN IF NOT EXISTS actual_outcome_score FLOAT DEFAULT NULL;

