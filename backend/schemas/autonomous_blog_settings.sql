-- RankForge Autonomous Blog Generation Settings — Problem 4.1 + P1 persistent schedule
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS daily_blog_target INTEGER DEFAULT 5;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS blogs_generated_today INTEGER DEFAULT 0;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS last_reset_date DATE DEFAULT CURRENT_DATE;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS generation_interval_minutes INTEGER DEFAULT 288;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS auto_topic_selection BOOLEAN DEFAULT true;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS auto_generate_enabled BOOLEAN DEFAULT true;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS schedule_label TEXT DEFAULT 'every 4.8 hours';

-- Ensure daily_blog_target is clamped 1-10
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_daily_blog_target') THEN
    ALTER TABLE public.autonomous_settings ADD CONSTRAINT chk_daily_blog_target CHECK (daily_blog_target >= 1 AND daily_blog_target <= 10);
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_autonomous_settings_website ON public.autonomous_settings(website_id);
