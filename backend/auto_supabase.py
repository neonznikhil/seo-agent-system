import os
import re
import logging
from pathlib import Path
from typing import Optional

import httpx
from dotenv import dotenv_values
from supabase import create_client, Client
logger = logging.getLogger("backend.auto_supabase")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
FRONTEND_ENV_FILE = PROJECT_ROOT / "frontend-next" / ".env.local"

TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "websites": """
        CREATE TABLE IF NOT EXISTS websites (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            domain text,
            url text,
            cms_url text,
            cms_user text,
            app_password text,
            niche text,
            gsc_property text,
            status text DEFAULT 'active',
            created_at timestamptz DEFAULT now()
        )
    """,
    "settings": """
        CREATE TABLE IF NOT EXISTS settings (
            key text NOT NULL,
            value text,
            website_id uuid,
            created_at timestamptz DEFAULT now(),
            PRIMARY KEY (key, website_id)
        )
    """,
    "agent_memory": """
        CREATE TABLE IF NOT EXISTS agent_memory (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            agent_name text,
            memory_type text,
            content text,
            embedding vector(1536),
            metadata jsonb DEFAULT '{}'::jsonb,
            confidence float DEFAULT 1.0,
            times_used int DEFAULT 0,
            times_successful int DEFAULT 0,
            last_used timestamptz DEFAULT now(),
            created_at timestamptz DEFAULT now()
        )
    """,
    "conversations": """
        CREATE TABLE IF NOT EXISTS conversations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            agent_name text,
            role text,
            message text,
            metadata jsonb DEFAULT '{}'::jsonb,
            created_at timestamptz DEFAULT now()
        )
    """,
    "knowledge_base": """
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            website_id uuid,
            type text DEFAULT 'business_info',
            title text,
            content text,
            embedding vector(1536),
            source text,
            url text,
            chunk_index int DEFAULT 0,
            total_chunks int DEFAULT 1,
            freshness_score float DEFAULT 1.0,
            credibility_score float DEFAULT 1.0,
            source_type text DEFAULT 'file',
            validated boolean DEFAULT false,
            validation_score float DEFAULT 0.0,
            entities jsonb DEFAULT '{"people":[],"orgs":[],"locations":[],"laws":[],"services":[],"keywords":[]}'::jsonb,
            related_ids uuid[] DEFAULT '{}',
            content_hash text,
            usage_count int DEFAULT 0,
            metadata jsonb DEFAULT '{}'::jsonb,
            last_used timestamptz DEFAULT now(),
            created_at timestamptz DEFAULT now()
        )
    """,
    "knowledge_relations": """
        CREATE TABLE IF NOT EXISTS knowledge_relations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            from_id uuid,
            to_id uuid,
            source_id uuid,
            target_id uuid,
            relation_type text DEFAULT 'mentions',
            strength float DEFAULT 0.8,
            created_at timestamptz DEFAULT now()
        )
    """,
    "daily_costs": """
        CREATE TABLE IF NOT EXISTS daily_costs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            date date DEFAULT CURRENT_DATE,
            agent_name text,
            tokens int DEFAULT 0,
            cost_usd float DEFAULT 0.0,
            created_at timestamptz DEFAULT now()
        )
    """,
    "blogs": """
        CREATE TABLE IF NOT EXISTS blogs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            title text,
            slug text,
            content text,
            html_content text,
            meta_description text,
            primary_keyword text,
            status text DEFAULT 'draft_pending_approval',
            seo_score float DEFAULT 0,
            word_count int DEFAULT 0,
            wp_post_id int,
            wp_url text,
            published_at timestamptz,
            created_at timestamptz DEFAULT now()
        )
    """,
    "blog_approvals": """
        CREATE TABLE IF NOT EXISTS blog_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            user_id text,
            blog_id uuid,
            title text,
            html_content text,
            seo_title text,
            meta_description text,
            slug text,
            keyword text,
            seo_score float,
            type text DEFAULT 'new_post',
            status text DEFAULT 'pending',
            auto_generated boolean DEFAULT true,
            wordpress_action text DEFAULT 'create',
            wordpress_post_id int,
            gate_issues jsonb,
            rejection_reason text,
            created_at timestamptz DEFAULT now(),
            approved_at timestamptz,
            wordpress_url text
        )
    """,
    "content_log": """
        CREATE TABLE IF NOT EXISTS content_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            title text,
            keyword text,
            content text,
            status text DEFAULT 'draft',
            pipeline_status text,
            seo_score float,
            wp_post_id int,
            created_at timestamptz DEFAULT now()
        )
    """,
    "keyword_opportunities": """
        CREATE TABLE IF NOT EXISTS keyword_opportunities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            keyword text,
            volume int,
            difficulty int,
            opportunity_score float,
            source text,
            status text DEFAULT 'new',
            discovered_at timestamptz DEFAULT now()
        )
    """,
    "serp_landscape": """
        CREATE TABLE IF NOT EXISTS serp_landscape (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            keyword text,
            top_urls jsonb,
            captured_at timestamptz DEFAULT now()
        )
    """,
    "brain_daily_jobs": """
        CREATE TABLE IF NOT EXISTS brain_daily_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            job_type text,
            status text,
            result jsonb,
            error text,
            run_at timestamptz DEFAULT now()
        )
    """,
    "brain_auto_pages_queue": """
        CREATE TABLE IF NOT EXISTS brain_auto_pages_queue (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            primary_keyword text,
            suggested_topic text,
            reason text,
            priority_score float DEFAULT 50,
            auto_approve boolean DEFAULT false,
            status text DEFAULT 'suggested',
            source text DEFAULT 'daily_search',
            queue_id uuid,
            created_at timestamptz DEFAULT now()
        )
    """,
    "wordpress_connections": """
        CREATE TABLE IF NOT EXISTS wordpress_connections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            site_url text,
            wp_username text,
            wp_app_password text,
            encrypted_password text,
            status text DEFAULT 'connected',
            last_synced timestamptz,
            created_at timestamptz DEFAULT now()
        )
    """,
    "wordpress_oauth_tokens": """
        CREATE TABLE IF NOT EXISTS wordpress_oauth_tokens (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            user_id text,
            access_token text,
            refresh_token text,
            token_type text,
            expires_at timestamptz,
            wp_site_url text,
            wp_user_login text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "seo_meta": """
        CREATE TABLE IF NOT EXISTS seo_meta (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            keyword text,
            seo_title text,
            meta_description text,
            slug text,
            keyword_density float,
            created_at timestamptz DEFAULT now()
        )
    """,
    "tasks": """
        CREATE TABLE IF NOT EXISTS tasks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            agent_name text,
            action text,
            payload jsonb,
            result jsonb,
            status text,
            real_api_called text,
            error text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "backlinks": """
        CREATE TABLE IF NOT EXISTS backlinks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            source_url text,
            target_url text,
            domain_authority float DEFAULT 0,
            type text DEFAULT 'outreach',
            status text DEFAULT 'active',
            anchor_text text,
            email_draft text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "backlink_opportunities": """
        CREATE TABLE IF NOT EXISTS backlink_opportunities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            target_url text,
            domain_authority float DEFAULT 0,
            type text DEFAULT 'competitor_replication',
            status text DEFAULT 'pending',
            anchor_text text,
            email_draft text,
            gap_analysis text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "seo_reports": """
        CREATE TABLE IF NOT EXISTS seo_reports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            report_data jsonb,
            created_at timestamptz DEFAULT now()
        )
    """,
    "daily_searches": """
        CREATE TABLE IF NOT EXISTS daily_searches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            keyword text,
            trends jsonb DEFAULT '{}'::jsonb,
            competitor_data jsonb DEFAULT '{}'::jsonb,
            created_at timestamptz DEFAULT now()
        )
    """,
    "analytics_data": """
        CREATE TABLE IF NOT EXISTS analytics_data (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            blog_id uuid,
            wordpress_post_id int,
            views int DEFAULT 0,
            clicks int DEFAULT 0,
            avg_time float DEFAULT 0,
            bounce_rate float DEFAULT 0,
            source text DEFAULT 'wordpress',
            date date DEFAULT CURRENT_DATE,
            created_at timestamptz DEFAULT now()
        )
    """,
    "autonomous_settings": """
        CREATE TABLE IF NOT EXISTS autonomous_settings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id text,
            auto_publish boolean DEFAULT true,
            auto_generate boolean DEFAULT true,
            auto_refresh boolean DEFAULT true,
            goals jsonb DEFAULT '{"target_articles_per_week": 5, "target_traffic_growth": 15.0, "focus_keywords": ["Houston car accident lawyer", "Texas commercial truck claims"]}'::jsonb,
            success_rate float DEFAULT 1.0,
            daily_costs jsonb DEFAULT '{}'::jsonb,
            updated_at timestamptz DEFAULT now()
        )
    """,
    "aeo_citations": """
        CREATE TABLE IF NOT EXISTS aeo_citations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            query text,
            llm_name text,
            cited boolean DEFAULT false,
            competitor_cited boolean DEFAULT false,
            citation_snippet text,
            schema_markup jsonb DEFAULT '{}'::jsonb,
            created_at timestamptz DEFAULT now()
        )
    """,
    "monitoring_alerts": """
        CREATE TABLE IF NOT EXISTS monitoring_alerts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            alert_type text,
            severity text,
            title text,
            description text,
            data jsonb,
            status text DEFAULT 'unread',
            source_monitor text,
            created_at timestamptz DEFAULT now()
        )
    """,
    "backlink_monitor": """
        CREATE TABLE IF NOT EXISTS backlink_monitor (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            website_id uuid,
            source_url text,
            target_url text,
            anchor_text text,
            target_keyword text,
            status text DEFAULT 'active',
            last_checked_at timestamptz,
            created_at timestamptz DEFAULT now()
        )
    """,
}

RPCS = {
    "enable_vector_ext": "CREATE EXTENSION IF NOT EXISTS vector",
    "match_knowledge": """
        CREATE OR REPLACE FUNCTION match_knowledge (
            query_embedding vector(1536),
            match_threshold float DEFAULT 0.65,
            match_count int DEFAULT 10
        ) RETURNS TABLE (
            id uuid,
            title text,
            content text,
            type text,
            source text,
            credibility_score float,
            freshness_score float,
            validated boolean,
            validation_score float,
            entities jsonb,
            similarity float
        ) LANGUAGE plpgsql STABLE AS $$
        BEGIN
            RETURN QUERY
            SELECT kb.id, kb.title, kb.content, kb.type, kb.source,
                   COALESCE(kb.credibility_score, 1.0)::float,
                   COALESCE(kb.freshness_score, 1.0)::float,
                   COALESCE(kb.validated, false)::boolean,
                   COALESCE(kb.validation_score, 0.0)::float,
                   COALESCE(kb.entities, '{}'::jsonb)::jsonb,
                   (1 - (kb.embedding <=> query_embedding))::float AS similarity
            FROM knowledge_base kb
            WHERE kb.embedding IS NOT NULL
              AND 1 - (kb.embedding <=> query_embedding) > match_threshold
            ORDER BY kb.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$;
    """,
    "match_brain_memory": """
        CREATE OR REPLACE FUNCTION match_brain_memory (
            query_embedding vector(1536),
            match_threshold float DEFAULT 0.70,
            match_count int DEFAULT 5
        ) RETURNS TABLE (
            id uuid,
            title text,
            content text,
            memory_type text,
            similarity float
        ) LANGUAGE plpgsql STABLE AS $$
        BEGIN
            RETURN QUERY
            SELECT bm.id, bm.agent_name AS title, bm.content, bm.memory_type,
                   (1 - (bm.embedding <=> query_embedding))::float AS similarity
            FROM agent_memory bm
            WHERE bm.embedding IS NOT NULL
              AND 1 - (bm.embedding <=> query_embedding) > match_threshold
            ORDER BY bm.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$;
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


def update_env_keys(keys_dict: dict) -> dict:
    """Merge arbitrary keys into root .env, backend/.env and frontend-next/.env.local."""
    backend_env_file = PROJECT_ROOT / "backend" / ".env"
    
    # 1. Update root .env
    backend_env = _load_existing_env(ENV_FILE)
    backend_env.update(keys_dict)
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        for key, value in backend_env.items():
            f.write(f"{key}={value}\n")
            
    # 2. Update backend/.env
    backend_env_file.parent.mkdir(parents=True, exist_ok=True)
    with open(backend_env_file, "w", encoding="utf-8") as f:
        for key, value in backend_env.items():
            f.write(f"{key}={value}\n")
            
    # 3. Update frontend-next/.env.local with NEXT_PUBLIC_* variables
    frontend_env = _load_existing_env(FRONTEND_ENV_FILE)
    for k, v in keys_dict.items():
        if k.startswith("NEXT_PUBLIC_") or k in ["SUPABASE_URL", "SUPABASE_ANON_KEY"]:
            if k == "SUPABASE_URL":
                frontend_env["NEXT_PUBLIC_SUPABASE_URL"] = v
            elif k == "SUPABASE_ANON_KEY":
                frontend_env["NEXT_PUBLIC_SUPABASE_ANON_KEY"] = v
            else:
                frontend_env[k] = v
        if k == "NVIDIA_API_KEY":
            frontend_env["NEXT_PUBLIC_NVIDIA_CONFIGURED"] = "true"
        if k == "WORDPRESS_SITE_URL":
            frontend_env["NEXT_PUBLIC_WORDPRESS_CONFIGURED"] = "true"

    FRONTEND_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FRONTEND_ENV_FILE, "w", encoding="utf-8") as f:
        for key, value in frontend_env.items():
            f.write(f"{key}={value}\n")
            
    # Also update current process os.environ
    for k, v in keys_dict.items():
        os.environ[k] = str(v)
        
    return {
        "backend_env": str(ENV_FILE),
        "frontend_env": str(FRONTEND_ENV_FILE),
        "keys_set": list(keys_dict.keys()),
    }


def write_env_file(
    supabase_url: Optional[str] = None,
    anon_key: Optional[str] = None,
    service_key: Optional[str] = None,
    db_password: Optional[str] = None,
    custom_keys: Optional[dict] = None,
) -> dict:
    """Write .env and frontend-next/.env.local with Supabase or custom credentials."""
    keys_to_update = {}
    if custom_keys and isinstance(custom_keys, dict):
        keys_to_update.update(custom_keys)

    if supabase_url:
        keys_to_update["SUPABASE_URL"] = supabase_url
        keys_to_update["NEXT_PUBLIC_SUPABASE_URL"] = supabase_url
    if anon_key:
        keys_to_update["SUPABASE_ANON_KEY"] = anon_key
        keys_to_update["NEXT_PUBLIC_SUPABASE_ANON_KEY"] = anon_key
    if service_key:
        keys_to_update["SUPABASE_SERVICE_ROLE_KEY"] = service_key
        keys_to_update["SUPABASE_KEY"] = service_key
    if supabase_url and db_password:
        try:
            project_ref = extract_project_ref(supabase_url)
            db_url = build_db_url(project_ref, db_password)
            keys_to_update["SUPABASE_DB_URL"] = db_url
            keys_to_update["DATABASE_URL"] = db_url
        except Exception as e:
            logger.warning(f"Could not build DB URL: {e}")

    return update_env_keys(keys_to_update)



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
    """Create tables using psycopg2 as fallback (also creates pgvector RPCs)."""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    created = []
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            for name, sql in RPCS.items():
                try:
                    cur.execute(sql)
                    logger.info(f"Executed SQL setup step: {name}")
                except Exception as e:
                    logger.warning(f"Setup step {name} failed: {e}")

            for table_name, sql in TABLES.items():
                try:
                    cur.execute(sql)
                    created.append(table_name)
                    logger.info(f"Created/verified table: {table_name}")
                except Exception as e:
                    if "already exists" in str(e):
                        created.append(table_name)
                    else:
                        logger.error(f"Failed to create table {table_name}: {e}")
        _seed_defaults(conn)
    except Exception as e:
        logger.error(f"psycopg2 connection or execution failed: {e}")
    finally:
        if conn:
            conn.close()
    return created


def _seed_defaults(conn) -> None:
    """Seed default automation settings so the system is ON after setup."""
    defaults = [
        ("automate_seo", "on"),
        ("auto_publish_new_pages", "off"),
        ("daily_refresh", "on"),
    ]
    try:
        with conn.cursor() as cur:
            for key, value in defaults:
                cur.execute(
                    """
                    INSERT INTO settings (key, value, website_id)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (key, website_id) DO NOTHING
                    """,
                    (key, value),
                )
            logger.info("Seeded default automation settings")
    except Exception as e:
        logger.warning(f"Seed defaults failed: {e}")


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
        if not db_password:
            logger.info("No DB password provided, relying on SQL API only")
        else:
            logger.info("Using psycopg2 for full table + RPC creation")
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
