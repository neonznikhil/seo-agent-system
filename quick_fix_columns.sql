-- ==========================================================
-- FINAL DATABASE COLUMN & CONSTRAINT PATCH
-- Run this in Supabase SQL Editor:
-- ==========================================================

ALTER TABLE content_pipeline_logs ADD COLUMN IF NOT EXISTS step_in_phase INT;
ALTER TABLE content_pipeline_logs DROP CONSTRAINT IF EXISTS content_pipeline_logs_phase_check;
ALTER TABLE content_pipeline_logs DROP CONSTRAINT IF EXISTS content_pipeline_logs_status_check;

ALTER TABLE content_log ADD COLUMN IF NOT EXISTS final_scores JSONB DEFAULT '{}'::jsonb;
ALTER TABLE content_log ADD COLUMN IF NOT EXISTS phase_results JSONB DEFAULT '{}'::jsonb;
ALTER TABLE content_log ALTER COLUMN content DROP NOT NULL;
ALTER TABLE content_log DROP CONSTRAINT IF EXISTS content_log_status_check;

ALTER TABLE realtime_alerts ADD COLUMN IF NOT EXISTS actioned_at TIMESTAMPTZ;
ALTER TABLE realtime_alerts DROP CONSTRAINT IF EXISTS realtime_alerts_alert_type_check;
ALTER TABLE realtime_alerts DROP CONSTRAINT IF EXISTS realtime_alerts_severity_check;

ALTER TABLE backlink_monitor ADD COLUMN IF NOT EXISTS target_keyword TEXT;
ALTER TABLE backlink_monitor ADD COLUMN IF NOT EXISTS target_page_url TEXT;
ALTER TABLE brain_daily_jobs DROP CONSTRAINT IF EXISTS brain_daily_jobs_job_type_check;
ALTER TABLE backlink_prospects DROP CONSTRAINT IF EXISTS backlink_prospects_strategy_check;
ALTER TABLE backlink_prospects DROP CONSTRAINT IF EXISTS backlink_prospects_status_check;
