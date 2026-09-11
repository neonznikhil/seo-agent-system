-- ====================================================================
-- 009: Autonomous settings schema drift fix (production blocker)
-- Run via Supabase SQL Editor or `run_migrations()` with DATABASE_URL.
-- Idempotent: safe to re-run.
-- ====================================================================

ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS auto_publish BOOLEAN DEFAULT true;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS auto_generate BOOLEAN DEFAULT true;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS auto_refresh BOOLEAN DEFAULT true;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS auto_topic_selection BOOLEAN DEFAULT true;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS auto_generate_enabled BOOLEAN DEFAULT true;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS daily_blog_target INTEGER DEFAULT 5;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS blogs_generated_today INTEGER DEFAULT 0;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS generation_interval_minutes INTEGER DEFAULT 288;
ALTER TABLE public.autonomous_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Backfill auto_refresh from goals JSONB where the code fallback stored it
UPDATE public.autonomous_settings
SET auto_refresh = COALESCE((goals->>'auto_refresh')::boolean, true)
WHERE auto_refresh IS NULL;

-- Writer suggestions resilience (non-fatal 42703 seen live 2026-09-08)
ALTER TABLE public.keyword_research ADD COLUMN IF NOT EXISTS intent TEXT;
ALTER TABLE public.keyword_research ADD COLUMN IF NOT EXISTS search_volume INTEGER DEFAULT 0;
ALTER TABLE public.keyword_research ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'queued';
