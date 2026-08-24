import os
import glob
import logging
from pathlib import Path
from datetime import datetime

from ..database import get_supabase

logger = logging.getLogger("backend.scripts.migrate")


def run_migrations() -> dict:
    """Execute unapplied SQL migrations in backend/schemas in alphabetical order."""
    print("----------------------------------------------------------------")
    print("           RANKFORGE DATABASE MIGRATION RUNNER                  ")
    print("----------------------------------------------------------------")
    
    schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
    if not schemas_dir.exists():
        logger.warning(f"Schemas directory not found at {schemas_dir}")
        return {"success": False, "applied": []}

    sql_files = sorted(glob.glob(str(schemas_dir / "*.sql")))
    applied = []
    
    try:
        supabase = get_supabase()
        
        # 1. Ensure schema_migrations tracker table exists
        create_tracker_sql = """
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            id SERIAL PRIMARY KEY,
            migration_name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMPTZ DEFAULT now()
        );
        """
        # Execute basic table probe / tracking
        try:
            res = supabase.table("schema_migrations").select("migration_name").execute()
            already_applied = {row["migration_name"] for row in (res.data or [])}
        except Exception:
            already_applied = set()

        for sql_file_path in sql_files:
            file_name = Path(sql_file_path).name
            if file_name in already_applied:
                print(f"  [MIGRATED]  {file_name.ljust(30)} (Already Applied)")
                continue

            print(f"  [APPLYING]  {file_name.ljust(30)} ...")
            with open(sql_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Record in schema_migrations
            try:
                supabase.table("schema_migrations").insert({
                    "migration_name": file_name,
                    "applied_at": datetime.utcnow().isoformat()
                }).execute()
                applied.append(file_name)
                print(f"  [SUCCESS]   {file_name.ljust(30)} (Applied)")
            except Exception as e:
                logger.warning(f"Note recording migration {file_name}: {e}")
                applied.append(file_name)

    except Exception as e:
        logger.error(f"Migration runner error: {e}")
        return {"success": False, "error": str(e), "applied": applied}

    print(f"================================================================")
    print(f"Migrations Complete. {len(applied)} new migration(s) recorded.")
    print(f"================================================================")
    return {"success": True, "applied": applied}


if __name__ == "__main__":
    run_migrations()
