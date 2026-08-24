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


-- ============================================================
-- APPROVALS SYNC: content_log -> blog_approvals trigger
-- Guarantees every pending_approval article has an approval row.
-- ============================================================

CREATE OR REPLACE FUNCTION sync_pending_approval_to_blog_approvals()
RETURNS TRIGGER AS $$
DECLARE
  existing_id UUID;
BEGIN
  -- Only fire when a row enters the pending_approval state
  IF NEW.status = 'pending_approval' OR NEW.pipeline_status = 'pending_approval' THEN
    SELECT id INTO existing_id FROM blog_approvals WHERE blog_id = NEW.id LIMIT 1;
    IF existing_id IS NULL THEN
      INSERT INTO blog_approvals (
        blog_id, title, html_content, keyword, seo_score, type, status,
        auto_generated, wordpress_action, website_id, created_at
      ) VALUES (
        NEW.id,
        COALESCE(NEW.title, 'Untitled draft'),
        COALESCE(NEW.content, ''),
        NEW.keyword,
        NULL,
        'new_post',
        'pending',
        TRUE,
        'create',
        NEW.website_id,
        COALESCE(NEW.created_at, NOW())
      );
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_pending_approval ON content_log;
CREATE TRIGGER trg_sync_pending_approval
AFTER INSERT OR UPDATE OF status, pipeline_status ON content_log
FOR EACH ROW EXECUTE FUNCTION sync_pending_approval_to_blog_approvals();

-- ============================================================
-- DUPLICATE PREVENTION: one non-failed article per (website, keyword)
-- ============================================================
CREATE UNIQUE INDEX IF NOT EXISTS uq_content_log_website_keyword_active
ON content_log (website_id, keyword)
WHERE pipeline_status IS DISTINCT FROM 'failed'
  AND status IS DISTINCT FROM 'failed'
  AND pipeline_status IS NOT NULL;

-- ============================================================
-- Cleanup support columns
-- ============================================================
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS scheduled_date DATE;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS serper_api_key TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS serper_api_key_encrypted TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS slack_credentials JSONB;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS last_audit_score NUMERIC;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS last_audit_date TIMESTAMP;

-- Hourly cleanup of junk draft rows (invoked by scheduler job)
CREATE OR REPLACE FUNCTION cleanup_junk_drafts()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER := 0;
BEGIN
  WITH junk AS (
    DELETE FROM content_log
    WHERE (title ILIKE '%Draft: a blog%')
       OR title IS NULL
       OR (pipeline_status = 'failed' AND created_at < NOW() - INTERVAL '24 hours')
       OR (COALESCE(LENGTH(content), 0) < 100 AND created_at < NOW() - INTERVAL '1 hour')
    RETURNING id
  ), removed_approvals AS (
    DELETE FROM blog_approvals ba
    USING junk j
    WHERE ba.blog_id = j.id
      AND ba.title ILIKE '%Draft:%'
    RETURNING ba.id
  )
  SELECT COUNT(*) INTO deleted_count FROM junk;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
