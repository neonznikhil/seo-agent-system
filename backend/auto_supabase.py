import os
import re
import logging
from pathlib import Path
from typing import Optional

import httpx
from dotenv import dotenv_values
from supabase import create_client, Client
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logger = logging.getLogger("backend.auto_supabase")

PROJECT_ROOT = Path("/home/nikhiladwaan/seo-agent-system/seo-agent-system")
ENV_FILE = PROJECT_ROOT / ".env"
FRONTEND_ENV_FILE = PROJECT_ROOT / "frontend-next" / ".env.local"

TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id uuid PRIMARY KEY,
            email text,
            created_at timestamptz
        )
    """,
    "agent_memory": """
        CREATE TABLE IF NOT EXISTS agent_memory (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            memory_type text,
            title text,
            content text,
            confidence float DEFAULT 1.0,
            times_used int DEFAULT 0,
            times_successful int DEFAULT 0,
            last_used_at timestamptz,
            created_at timestamptz DEFAULT now()
        )
    """,
    "conversations": """
        CREATE TABLE IF NOT EXISTS conversations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            agent_name text,
            message text,
            role text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "blogs": """
        CREATE TABLE IF NOT EXISTS blogs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            title text,
            content text,
            status text DEFAULT 'draft',
            wp_post_id int,
            wp_url text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "wordpress_connections": """
        CREATE TABLE IF NOT EXISTS wordpress_connections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            site_url text,
            wp_username text,
            encrypted_password text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "backlinks": """
        CREATE TABLE IF NOT EXISTS backlinks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            source_url text,
            target_url text,
            domain_authority float,
            created_at timestamptz DEFAULT now()
        )
    """,
    "seo_reports": """
        CREATE TABLE IF NOT EXISTS seo_reports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            report_type text,
            data jsonb,
            created_at timestamptz DEFAULT now()
        )
    """,
    "memory_embeddings": """
        CREATE TABLE IF NOT EXISTS memory_embeddings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            memory_id uuid REFERENCES agent_memory(id),
            embedding vector(1536),
            created_at timestamptz DEFAULT now()
        )
    """,
}


def extract_project_ref(supabase_url: str) -> str:
    """Extract the project ref from URLs like https://xxxx.supabase.co."""
    pattern = r"https?://([a-zA-Z0-9_-]+)\.supabase\.co"
    match = re.match(pattern, supabase_url.strip())
    if not match:
        raise ValueError(f"Invalid Supabase URL format: {supabase_url}")
    return match.group(1)


def build_db_url(project_ref: str, db_password: str) -> str:
    """Format the PostgreSQL connection URL for Supabase pooler."""
    return (
        f"postgresql://postgres.{project_ref}:{db_password}"
        f"@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?pgbouncer=true"
    )


def _load_existing_env(env_path: Path) -> dict:
    """Load existing .env file preserving all keys."""
    if not env_path.exists():
        return {}
    values = dotenv_values(env_path)
    return {k: v for k, v in values.items() if v is not None}


def write_env_file(
    supabase_url: str,
    anon_key: str,
    service_key: str,
    db_password: str,
) -> dict:
    """Write .env and frontend-next/.env.local with Supabase credentials."""
    project_ref = extract_project_ref(supabase_url)
    db_url = build_db_url(project_ref, db_password)

    backend_env = _load_existing_env(ENV_FILE)
    backend_env.update({
        "SUPABASE_URL": supabase_url,
        "NEXT_PUBLIC_SUPABASE_URL": supabase_url,
        "SUPABASE_ANON_KEY": anon_key,
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": anon_key,
        "SUPABASE_SERVICE_ROLE_KEY": service_key,
        "SUPABASE_DB_URL": db_url,
        "DATABASE_URL": db_url,
    })

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ENV_FILE, "w") as f:
        for key, value in backend_env.items():
            f.write(f"{key}={value}\n")
    logger.info(f"Wrote backend .env to {ENV_FILE}")

    frontend_env = {
        "NEXT_PUBLIC_SUPABASE_URL": supabase_url,
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": anon_key,
    }
    FRONTEND_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FRONTEND_ENV_FILE, "w") as f:
        for key, value in frontend_env.items():
            f.write(f"{key}={value}\n")
    logger.info(f"Wrote frontend .env.local to {FRONTEND_ENV_FILE}")

    return {
        "backend_env": str(ENV_FILE),
        "frontend_env": str(FRONTEND_ENV_FILE),
        "keys_set": list(backend_env.keys()),
    }


def _test_supabase_connection(supabase_url: str, anon_key: str) -> bool:
    """Test Supabase connectivity using the anon key."""
    try:
        client = create_client(supabase_url, anon_key)
        client.auth.get_session()
        return True
    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        return False


def create_tables_via_supabase(supabase_url: str, service_key: str) -> list:
    """Create tables using Supabase client (best effort)."""
    created = []
    try:
        base_url = supabase_url.rstrip("/")
        sql_api_url = f"{base_url}/rest/v1/rpc/exec_sql"

        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=30.0) as http_client:
            for table_name, sql in TABLES.items():
                try:
                    resp = http_client.post(
                        sql_api_url, json={"sql": sql}, headers=headers
                    )
                    if resp.status_code in (200, 201, 204):
                        created.append(table_name)
                    else:
                        logger.warning(
                            f"Supabase SQL API returned {resp.status_code} "
                            f"for {table_name}: {resp.text}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to create {table_name} via Supabase API: {e}"
                    )

        if not created:
            logger.info(
                "Supabase SQL API not available, will fallback to psycopg2"
            )
        return created
    except Exception as e:
        logger.error(f"Supabase table creation failed: {e}")
        return []


def create_tables_via_psycopg2(db_url: str) -> list:
    """Create tables using psycopg2 as fallback."""
    created = []
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                logger.info("Enabled pgvector extension")
            except Exception as e:
                logger.warning(f"Could not enable pgvector extension: {e}")

            for table_name, sql in TABLES.items():
                try:
                    cur.execute(sql)
                    created.append(table_name)
                    logger.info(f"Created table: {table_name}")
                except Exception as e:
                    logger.error(f"Failed to create table {table_name}: {e}")
    except Exception as e:
        logger.error(f"psycopg2 connection or execution failed: {e}")
    finally:
        if conn:
            conn.close()
    return created


def connect_and_setup(
    supabase_url: str,
    anon_key: str,
    service_key: str,
    db_password: str,
) -> dict:
    """Full setup: write env, test connection, create tables."""
    try:
        project_ref = extract_project_ref(supabase_url)
        db_url = build_db_url(project_ref, db_password)

        env_result = write_env_file(supabase_url, anon_key, service_key, db_password)

        if not _test_supabase_connection(supabase_url, anon_key):
            return {
                "success": False,
                "error": "Supabase connection test failed",
            }

        tables = create_tables_via_supabase(supabase_url, service_key)
        if not tables:
            logger.info("Falling back to psycopg2 for table creation")
            tables = create_tables_via_psycopg2(db_url)

        return {
            "success": True,
            "project_ref": project_ref,
            "tables_created": tables,
            "env_written": True,
            "message": (
                f"Connected to project {project_ref}. "
                f"Created {len(tables)} tables."
            ),
        }
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
