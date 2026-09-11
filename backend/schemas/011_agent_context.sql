-- RankForge migration: agent context provenance.
-- Idempotent: safe to run multiple times via Supabase SQL Editor.

-- What data each draft was built from (counts + provenance per source).
ALTER TABLE IF EXISTS public.content_log
    ADD COLUMN IF NOT EXISTS grounding_summary JSONB;
