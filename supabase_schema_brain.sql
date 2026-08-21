-- Brain Memory Schema
-- Knowledge base that remembers, learns, and runs daily autopilot
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS brain_memory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  memory_type TEXT CHECK (memory_type IN ('fact','experience','failure','preference','entity','relationship','outcome')),
  title TEXT,
  content TEXT,
  embedding vector(1024),
  source_type TEXT,
  source_id UUID,
  confidence FLOAT DEFAULT 0.8,
  times_used INT DEFAULT 0,
  times_successful INT DEFAULT 0,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brain_daily_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  job_type TEXT CHECK (job_type IN ('daily_search','daily_refresh_check','daily_cluster_build','daily_geo_check','daily_backlink_check','daily_new_page_suggestion')),
  status TEXT CHECK (status IN ('pending','running','completed','failed')) DEFAULT 'pending',
  result JSONB,
  error TEXT,
  run_at TIMESTAMPTZ DEFAULT NOW(),
  next_run_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS brain_content_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES content_log(id) ON DELETE CASCADE,
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  keyword TEXT,
  position_history JSONB,
  what_worked JSONB,
  what_failed JSONB,
  learned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brain_auto_pages_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  suggested_topic TEXT,
  primary_keyword TEXT,
  reason TEXT,
  priority_score FLOAT,
  source TEXT,
  status TEXT CHECK (status IN ('suggested','approved_auto','queued_for_writing','writing','draft_ready','published','rejected')) DEFAULT 'suggested',
  auto_approve BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brain_memory_embedding ON brain_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_brain_memory_website_type ON brain_memory(website_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_brain_daily_jobs_website ON brain_daily_jobs(website_id);
CREATE INDEX IF NOT EXISTS idx_brain_daily_jobs_status ON brain_daily_jobs(status);
CREATE INDEX IF NOT EXISTS idx_brain_content_perf_website ON brain_content_performance(website_id);
CREATE INDEX IF NOT EXISTS idx_brain_auto_queue_website ON brain_auto_pages_queue(website_id);
CREATE INDEX IF NOT EXISTS idx_brain_auto_queue_status ON brain_auto_pages_queue(website_id, status);

CREATE OR REPLACE FUNCTION match_brain_memory (
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) RETURNS TABLE (
  id uuid,
  similarity float
) LANGUAGE sql STABLE AS $$
  SELECT
    id,
    1 - (embedding <=> query_embedding) AS similarity
  FROM brain_memory
  WHERE website_id = p_website_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT 20;
$$;
