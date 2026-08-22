-- COMPETITORS TABLE
CREATE TABLE IF NOT EXISTS public.competitors (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    name TEXT,
    url TEXT,
    last_scraped TIMESTAMP,
    snapshot JSONB DEFAULT '{}',
    changes JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- COMPETITOR SNAPSHOTS
CREATE TABLE IF NOT EXISTS public.competitor_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    competitor_id UUID REFERENCES competitors(id) ON DELETE CASCADE,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    content_hash TEXT,
    snapshot_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- COMPETITOR CHANGES
CREATE TABLE IF NOT EXISTS public.competitor_changes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    competitor_id UUID REFERENCES competitors(id) ON DELETE CASCADE,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    change_type TEXT,
    old_value TEXT,
    new_value TEXT,
    detected_at TIMESTAMP DEFAULT NOW()
);

-- WEBSITE PAGES (missing table)
CREATE TABLE IF NOT EXISTS public.website_pages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    content TEXT,
    word_count INTEGER DEFAULT 0,
    internal_links JSONB DEFAULT '[]',
    external_links JSONB DEFAULT '[]',
    last_crawled TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- KEYWORD OPPORTUNITIES (if missing)
CREATE TABLE IF NOT EXISTS public.keyword_opportunities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    search_volume INTEGER DEFAULT 0,
    current_position INTEGER,
    opportunity_score FLOAT DEFAULT 0,
    status TEXT DEFAULT 'new',
    source TEXT DEFAULT 'ai',
    created_at TIMESTAMP DEFAULT NOW()
);

-- CONTENT CALENDAR TABLE
CREATE TABLE IF NOT EXISTS public.content_calendar (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    keywords TEXT[],
    scheduled_date DATE,
    status TEXT DEFAULT 'planned',
    content_id UUID REFERENCES content_log(id),
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT NOW()
);

-- LLMS TXT TABLE (if missing)
CREATE TABLE IF NOT EXISTS public.llms_txt (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
    content TEXT,
    updated_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(website_id)
);

-- ADD MISSING COLUMNS TO WEBSITES
ALTER TABLE websites ADD COLUMN IF NOT EXISTS oauth_enabled BOOLEAN DEFAULT false;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS slack_webhook_url TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS alert_email TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS local_target TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wordpress_url TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wordpress_user TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wordpress_password TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS niche TEXT;

-- ADD MISSING COLUMNS TO CONTENT_LOG
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS quality_checked BOOLEAN DEFAULT false;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS wp_post_id INTEGER;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS wp_draft_url TEXT;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS word_count INTEGER DEFAULT 0;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS meta_description TEXT;

-- ADD MISSING COLUMNS TO TECHNICAL_AUDITS
ALTER TABLE technical_audits ADD COLUMN IF NOT EXISTS audit_type TEXT;
ALTER TABLE technical_audits ADD COLUMN IF NOT EXISTS metrics JSONB DEFAULT '{}';
ALTER TABLE technical_audits ADD COLUMN IF NOT EXISTS health_score INTEGER DEFAULT 0;
ALTER TABLE technical_audits ADD COLUMN IF NOT EXISTS issues JSONB DEFAULT '[]';

-- BRAIN DAILY JOBS (if missing columns)
ALTER TABLE brain_daily_jobs ADD COLUMN IF NOT EXISTS result JSONB;
ALTER TABLE brain_daily_jobs ADD COLUMN IF NOT EXISTS job_type TEXT;

-- INDEXES FOR PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_competitors_website_id ON competitors(website_id);
CREATE INDEX IF NOT EXISTS idx_competitor_snapshots_competitor_id ON competitor_snapshots(competitor_id);
CREATE INDEX IF NOT EXISTS idx_website_pages_website_id ON website_pages(website_id);
CREATE INDEX IF NOT EXISTS idx_keyword_opportunities_website_id ON keyword_opportunities(website_id);
CREATE INDEX IF NOT EXISTS idx_content_calendar_website_id ON content_calendar(website_id);
