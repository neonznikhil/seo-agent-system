-- ==========================================================
-- RankForge migration 3: real pgvector search
-- Run in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Safe to re-run: every statement is guarded (IF NOT EXISTS /
-- per-row exception handling). Verified live 2026-09-07 that
-- knowledge_base.embedding and brain_memory.embedding are TEXT
-- holding 1024-dim vectors, so this converts them in place.
--
-- What it does:
--  1. Enables pgvector.
--  2. Adds embedding_vec vector(1024) to knowledge_base +
--     brain_memory, backfills from the TEXT column row-by-row
--     (one malformed row cannot abort the migration).
--  3. Keeps embedding_vec in sync on future INSERT/UPDATE.
--  4. Creates match_knowledge / match_brain_memory RPCs with the
--     EXACT parameter names the backend calls, returning the
--     columns the backend reads. p_website_id is optional so the
--     existing website-unfiltered calls keep working.
-- ==========================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------- knowledge_base ----------
ALTER TABLE public.knowledge_base
    ADD COLUMN IF NOT EXISTS embedding_vec vector(1024);

DO $$
DECLARE
    r RECORD;
    converted int := 0;
    skipped int := 0;
BEGIN
    FOR r IN SELECT id, embedding FROM public.knowledge_base
             WHERE embedding_vec IS NULL AND embedding IS NOT NULL
    LOOP
        BEGIN
            UPDATE public.knowledge_base
               SET embedding_vec = r.embedding::vector
             WHERE id = r.id;
            converted := converted + 1;
        EXCEPTION WHEN OTHERS THEN
            skipped := skipped + 1;
        END;
    END LOOP;
    RAISE NOTICE 'knowledge_base backfill: % converted, % skipped (malformed)', converted, skipped;
END $$;

CREATE INDEX IF NOT EXISTS idx_knowledge_base_vec
    ON public.knowledge_base USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100);

-- ---------- brain_memory ----------
ALTER TABLE public.brain_memory
    ADD COLUMN IF NOT EXISTS embedding_vec vector(1024);

DO $$
DECLARE
    r RECORD;
    converted int := 0;
    skipped int := 0;
BEGIN
    FOR r IN SELECT id, embedding FROM public.brain_memory
             WHERE embedding_vec IS NULL AND embedding IS NOT NULL
    LOOP
        BEGIN
            UPDATE public.brain_memory
               SET embedding_vec = r.embedding::vector
             WHERE id = r.id;
            converted := converted + 1;
        EXCEPTION WHEN OTHERS THEN
            skipped := skipped + 1;
        END;
    END LOOP;
    RAISE NOTICE 'brain_memory backfill: % converted, % skipped (malformed)', converted, skipped;
END $$;

CREATE INDEX IF NOT EXISTS idx_brain_memory_vec
    ON public.brain_memory USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100);

-- ---------- sync triggers (future writes stay searchable) ----------
CREATE OR REPLACE FUNCTION public.sync_embedding_vec() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.embedding IS NOT NULL THEN
        BEGIN
            NEW.embedding_vec := NEW.embedding::vector;
        EXCEPTION WHEN OTHERS THEN
            NEW.embedding_vec := NULL;
        END;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_kb_vec ON public.knowledge_base;
CREATE TRIGGER trg_kb_vec BEFORE INSERT OR UPDATE OF embedding
    ON public.knowledge_base FOR EACH ROW EXECUTE FUNCTION public.sync_embedding_vec();

DROP TRIGGER IF EXISTS trg_brain_vec ON public.brain_memory;
CREATE TRIGGER trg_brain_vec BEFORE INSERT OR UPDATE OF embedding
    ON public.brain_memory FOR EACH ROW EXECUTE FUNCTION public.sync_embedding_vec();

-- ---------- RPCs (parameter names match backend calls) ----------
CREATE OR REPLACE FUNCTION public.match_knowledge(
    query_embedding vector(1024),
    match_threshold float DEFAULT 0.60,
    match_count int DEFAULT 15,
    p_website_id uuid DEFAULT NULL
) RETURNS TABLE (
    id uuid,
    fact text,
    content text,
    source_url text,
    freshness_score float,
    credibility_score float,
    similarity float
) LANGUAGE sql STABLE AS $$
    SELECT kb.id,
           kb.fact,
           kb.content,
           kb.source_url,
           COALESCE(kb.freshness_score, 1.0)::float,
           COALESCE(kb.credibility_score, 1.0)::float,
           (1 - (kb.embedding_vec <=> query_embedding))::float AS similarity
      FROM public.knowledge_base kb
     WHERE kb.embedding_vec IS NOT NULL
       AND (p_website_id IS NULL OR kb.website_id = p_website_id)
       AND 1 - (kb.embedding_vec <=> query_embedding) > match_threshold
     ORDER BY kb.embedding_vec <=> query_embedding
     LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION public.match_brain_memory(
    query_embedding vector(1024),
    match_threshold float DEFAULT 0.70,
    p_website_id uuid DEFAULT NULL
) RETURNS TABLE (
    id uuid,
    similarity float
) LANGUAGE sql STABLE AS $$
    SELECT bm.id,
           (1 - (bm.embedding_vec <=> query_embedding))::float AS similarity
      FROM public.brain_memory bm
     WHERE bm.embedding_vec IS NOT NULL
       AND (p_website_id IS NULL OR bm.website_id = p_website_id)
       AND 1 - (bm.embedding_vec <=> query_embedding) > match_threshold
     ORDER BY bm.embedding_vec <=> query_embedding
     LIMIT 20;
$$;
