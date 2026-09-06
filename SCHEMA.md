# RankForge Database Schema

## Canonical Source of Truth

The **single source of truth** for the RankForge database schema is:

**`backend/auto_supabase.py`**

This file contains:
- `TABLES` dict with all 40+ table CREATE statements
- `SCHEMA_PATCHES` list with ALTER TABLE patches for missing columns
- `RPCS` dict with pgvector functions (`match_knowledge`, `match_brain_memory`)
- `setup_supabase()` function that runs at startup to ensure schema is current

### Why auto_supabase.py is canonical
1. It runs automatically at startup via `backend/main.py`
2. It handles both fresh creation and schema migrations via `CREATE IF NOT EXISTS` + `ALTER TABLE IF NOT EXISTS ADD COLUMN`
3. It is tested and verified to work cross-platform (Windows + Linux)
4. It is the only schema path that creates pgvector RPCs

## Migration Order

If you need to run schema manually (e.g., fresh Supabase project):

1. **Run `backend/auto_supabase.py` first:**
   ```python
   python -c "from backend.auto_supabase import setup_supabase; print(setup_supabase())"
   ```

2. **Then run AEO schema if needed:**
   ```sql
   -- Run in Supabase SQL Editor
   \i backend/supabase_schema_aeo.sql
   ```

## Legacy SQL Files (Reference Only)

The following `.sql` files exist for historical reference but are **NOT** automatically executed:

| File | Purpose | Status |
|------|---------|--------|
| `supabase_schema.sql` | Original base schema | Deprecated |
| `supabase_schema_v2.sql` | Updated with new columns | Deprecated |
| `supabase_master_complete.sql` | Master schema with all tables | Deprecated |
| `backend/supabase_schema_enhanced.sql` | Enhanced version | Deprecated |
| `backend/supabase_schema_aeo.sql` | AEO-specific tables | Supplementary |
| `backend/supabase_real_data_schema.sql` | Real data schema | Deprecated |
| `backend/supabase_decay_cluster_schema.sql` | Decay cluster tables | Deprecated |
| `backend/schemas/*.sql` | Phase-based migrations | Deprecated |

**Do NOT run these manually.** `auto_supabase.py` handles all table creation and patching.

## Tables Created by auto_supabase.py

Core tables (25):
- `users`, `websites`, `settings`, `agent_memory`, `conversations`
- `knowledge_base`, `knowledge_relations`
- `daily_costs`, `blogs`, `blog_approvals`
- `rag_conversations`, `rag_evaluations`
- `content_log`, `keyword_opportunities`, `serp_landscape`
- `brain_daily_jobs`, `brain_auto_pages_queue`
- `wordpress_connections`, `wordpress_oauth_tokens`
- `seo_meta`, `tasks`, `backlinks`, `backlink_opportunities`
- `seo_reports`, `daily_searches`, `analytics_data`, `autonomous_settings`

AEO tables (via `supabase_schema_aeo.sql`):
- `ai_visibility`, `article_markdown_cache`, `reddit_opportunities`

Monitoring tables:
- `monitoring_alerts`, `backlink_monitor`, `content_pipeline_logs`
- `brain_memory`, `realtime_alerts`, `critical_action_logs`
- `pending_fixes`, `technical_audits`

## RPC Functions

Created by `auto_supabase.py`:
- `match_knowledge(query_embedding, match_threshold, match_count)` — hybrid vector search for knowledge_base
- `match_brain_memory(query_embedding, match_threshold, match_count)` — vector search for brain_memory
- `enable_vector_ext` — creates pgvector extension

## Schema Patches

`SCHEMA_PATCHES` handles:
- Adding missing columns (`websites.name`, `websites.domain`, `daily_searches.search_volume`, etc.)
- Disabling RLS on tables for local development
- 25+ ALTER TABLE statements executed idempotently
