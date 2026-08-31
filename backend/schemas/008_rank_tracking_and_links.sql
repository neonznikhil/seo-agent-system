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
