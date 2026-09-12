-- ==========================================================
-- RankForge migration 4: least-privilege Row Level Security
-- Run in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Safe to re-run. Verified 2026-09-07 that NO frontend page
-- imports the Supabase client (all reads/writes go through the
-- FastAPI backend, which uses the service_role key and bypasses
-- RLS). After this, the anon key exposed in the frontend bundle
-- can read/write NOTHING — fail-closed.
-- ==========================================================

-- Enable RLS on every app table (future tables included).
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename NOT LIKE 'pg\_%'
          AND tablename NOT LIKE 'sql\_%'
          AND tablename NOT IN ('schema_migrations', 'spatial_ref_sys',
                                'geography_columns', 'geometry_columns')
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    END LOOP;
END $$;

-- Explicitly deny the anon + authenticated roles everything.
-- service_role bypasses RLS, so the backend is unaffected.
-- (Default with zero policies is deny-all; these REVOKEs defend
-- in case anyone adds a permissive policy later.)
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename NOT LIKE 'pg\_%'
          AND tablename NOT LIKE 'sql\_%'
          AND tablename NOT IN ('schema_migrations', 'spatial_ref_sys',
                                'geography_columns', 'geometry_columns')
    LOOP
        EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
        EXECUTE format('GRANT ALL ON public.%I TO service_role', t);
    END LOOP;
END $$;

-- If a future feature genuinely needs direct anon reads
-- (e.g. a public page), add a narrow policy THEN, e.g.:
--   CREATE POLICY "public read" ON public.some_table
--   FOR SELECT TO anon USING (true);
