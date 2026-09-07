"""Nightly Supabase backup to timestamped local JSON.

Covers every table the backend reads/writes. Uses the service_role key
(bypasses RLS). Run via Task Scheduler / cron:

    python backend/scripts/backup_supabase.py

Output: backups/supabase_YYYYMMDD_HHMMSS/*.json + manifest.json
Retention: keeps the newest 14 backups, deletes older ones.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

TABLES = [
    "websites", "content_log", "blog_approvals", "blogs",
    "content_pipeline_logs", "knowledge_base", "brain_memory",
    "brain_daily_jobs", "brain_auto_pages_queue", "tasks",
    "autonomous_settings", "autonomous_decisions", "daily_costs",
    "daily_searches", "analytics_data", "research", "keyword_research",
    "aeo_citations", "ai_visibility", "article_markdown_cache",
    "reddit_opportunities", "geo_visibility_logs", "backlinks",
    "backlink_opportunities", "backlink_prospects", "backlink_monitor",
    "technical_audits", "realtime_alerts", "pending_fixes",
    "agent_memory", "tone_profiles", "knowledge_sources",
    "users", "wordpress_connections",
]

RETENTION = int(os.getenv("BACKUP_RETENTION_COUNT", "14"))


def main() -> int:
    from backend.database import get_supabase

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "backups" / f"supabase_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    supabase = get_supabase()
    manifest = {"taken_at": datetime.now().isoformat(), "tables": {}}
    for table in TABLES:
        try:
            rows = supabase.table(table).select("*").execute().data or []
            (out_dir / f"{table}.json").write_text(
                json.dumps(rows, ensure_ascii=False, default=str), encoding="utf-8"
            )
            manifest["tables"][table] = len(rows)
            print(f"  {table}: {len(rows)} rows")
        except Exception as e:
            manifest["tables"][table] = f"ERROR: {str(e)[:150]}"
            print(f"  {table}: ERROR {str(e)[:120]}")

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Retention: keep newest N backups
    backups = sorted((PROJECT_ROOT / "backups").glob("supabase_*"))
    for old in backups[:-RETENTION]:
        for f in old.glob("*.json"):
            f.unlink()
        old.rmdir()
        print(f"  pruned {old.name}")

    print(f"Backup complete: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
