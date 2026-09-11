import os
import glob
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("backend.scripts.migrate")


def get_db_url() -> str | None:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("DIRECT_URL")
    )


def run_migrations() -> dict:
    """Execute SQL migrations in backend/schemas or inform user to run master script."""
    print("----------------------------------------------------------------")
    print("           RANKFORGE DATABASE MIGRATION RUNNER                  ")
    print("----------------------------------------------------------------")

    schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
    if not schemas_dir.exists():
        logger.warning(f"Schemas directory not found at {schemas_dir}")
        return {"success": False, "applied": []}

    sql_files = sorted(glob.glob(str(schemas_dir / "*.sql")))
    applied = []

    db_url = get_db_url()

    if db_url:
        import psycopg2

        print("  [INFO] Direct Postgres connection detected. Executing DDL migrations...")
        try:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cur = conn.cursor()

            # Ensure schema_migrations table exists
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMPTZ DEFAULT now()
                );
            """
            )

            cur.execute("SELECT migration_name FROM public.schema_migrations;")
            already_applied = {row[0] for row in cur.fetchall()}

            for sql_file_path in sql_files:
                file_name = Path(sql_file_path).name
                if file_name in already_applied:
                    print(f"  [MIGRATED]  {file_name.ljust(35)} (Already Applied)")
                    continue

                print(f"  [APPLYING]  {file_name.ljust(35)} ...")
                with open(sql_file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                try:
                    cur.execute(content)
                    cur.execute(
                        "INSERT INTO public.schema_migrations (migration_name, applied_at) VALUES (%s, %s);",
                        (file_name, datetime.utcnow().isoformat()),
                    )
                    applied.append(file_name)
                    print(f"  [SUCCESS]   {file_name.ljust(35)} (Applied)")
                except Exception as e:
                    print(f"  [ERROR]     {file_name.ljust(35)}: {e}")
                    logger.error(f"Failed to execute {file_name}: {e}")

            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            print(f"  [ERROR] Database connection failed: {e}")
            return {"success": False, "error": str(e), "applied": applied}

    else:
        # Only PostgREST / Supabase REST client available
        from database import get_supabase

        supabase = get_supabase()
        print("  [NOTICE] Direct Postgres URL (DATABASE_URL) is not set in backend/.env.")
        print("  PostgREST does not support arbitrary DDL (CREATE/ALTER TABLE).")
        print("  To apply migrations, run these in your Supabase SQL Editor (repo root, in order):")
        print("    1. supabase_master_complete.sql")
        print("    2. supabase_migration_missing.sql")
        print("    3. supabase_migration_aeo.sql")
        print("    4. supabase_migration_vectors.sql  (creates match_knowledge / match_brain_memory RPCs)")
        print("    5. supabase_migration_rls.sql")
        print("    6. supabase_migration_indexation_runs.sql  (indexation_checks, runs, brand_voice_guides, fact_verifications)")
        print("  Plus backend/schemas/009_autonomous_settings_missing.sql for auto_refresh + keyword_research.intent.")

        # Check existing tables via REST probe
        test_tables = ["accounts", "websites", "content_log", "realtime_alerts", "autonomous_settings", "daily_costs",
                       "indexation_checks", "runs", "brand_voice_guides"]
        print("\n  Probing Supabase PostgREST tables status:")
        for tbl in test_tables:
            try:
                res = supabase.table(tbl).select("id").limit(1).execute()
                status = "EXISTS" if res is not None else "UNKNOWN"
            except Exception as ex:
                status = f"MISSING ({ex.code if hasattr(ex, 'code') else '404'})"
            print(f"    - {tbl.ljust(25)}: {status}")

    print("================================================================")
    print(f"Migrations check complete. {len(applied)} new migration(s) applied directly.")
    print("================================================================")
    return {"success": True, "applied": applied}


if __name__ == "__main__":
    run_migrations()
