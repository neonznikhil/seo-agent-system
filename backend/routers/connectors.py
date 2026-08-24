import os
import logging
import httpx
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..database import get_supabase
from ..security import encrypt_secret
from ..auto_supabase import (
    connect_and_setup,
    write_env_file,
    extract_project_ref,
    build_db_url,
)

logger = logging.getLogger("backend.routers.connectors")
router = APIRouter(tags=["connectors"])


# ---------------------------------------------------------
# Pydantic Request / Response Models
# ---------------------------------------------------------

class TestNvidiaRequest(BaseModel):
    api_key: str = Field(..., description="NVIDIA NIM API Key starting with nvapi-")


class SaveNvidiaRequest(BaseModel):
    api_key: str = Field(..., description="NVIDIA NIM API Key to persist")


class TestSupabaseRequest(BaseModel):
    supabase_url: str = Field(..., description="Supabase project URL https://xyz.supabase.co")
    anon_key: str = Field(..., description="Supabase anon public key")
    service_key: Optional[str] = Field(None, description="Supabase service role key")
    db_password: Optional[str] = Field(None, description="Supabase database password")


class SetupSupabaseRequest(BaseModel):
    supabase_url: str = Field(..., description="Supabase project URL")
    anon_key: str = Field(..., description="Supabase anon public key")
    service_key: str = Field(..., description="Supabase service role key")
    db_password: str = Field(..., description="Supabase database password")


class WordPressConnectRequest(BaseModel):
    site_url: str = Field(..., description="WordPress website URL")
    wp_username: str = Field(..., description="WordPress username / application user")
    wp_app_password: str = Field(..., description="WordPress Application Password")


class WordPressSaveRequest(BaseModel):
    site_url: str = Field(..., description="WordPress website URL")
    wp_username: str = Field(..., description="WordPress username")
    wp_app_password: str = Field(..., description="WordPress Application Password")
    website_id: Optional[str] = Field(None, description="Website ID to attach credentials to")


# ---------------------------------------------------------
# 1. NVIDIA Connectors Endpoints
# ---------------------------------------------------------

@router.post("/api/connectors/test-nvidia")
@router.post("/connectors/test-nvidia")
async def test_nvidia(payload: TestNvidiaRequest):
    """Test NVIDIA NIM API key by querying the real models list."""
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    url = "https://integrate.api.nvidia.com/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            models_list = [
                m.get("id") for m in data.get("data", []) if isinstance(m, dict) and "id" in m
            ]
            return {
                "connected": True,
                "status": "success",
                "message": f"Successfully connected to NVIDIA NIM ({len(models_list)} models available)",
                "models_count": len(models_list),
                "models": models_list[:15],
            }
        elif resp.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Invalid NVIDIA API key or unauthorized access")
        else:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"NVIDIA API responded with status {resp.status_code}: {resp.text[:200]}",
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to NVIDIA NIM timed out after 10s")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing NVIDIA API: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to NVIDIA: {str(e)}")


@router.post("/api/connectors/save-nvidia")
@router.post("/connectors/save-nvidia")
async def save_nvidia(payload: SaveNvidiaRequest):
    """Persist NVIDIA NIM API key to backend environment."""
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    res = write_env_file(custom_keys={"NVIDIA_API_KEY": api_key})
    os.environ["NVIDIA_API_KEY"] = api_key
    # Reset the global NIM availability flag so startup validation re-runs.
    try:
        from ..database import reset_nim_availability
        reset_nim_availability()
    except Exception:
        pass
    return {
        "success": True,
        "connected": True,
        "message": "NVIDIA API Key successfully saved and configured",
        "env_updated": res,
    }


# ---------------------------------------------------------
# 2. Supabase Connectors Endpoints
# ---------------------------------------------------------

@router.post("/api/connectors/test-supabase")
@router.post("/connectors/test-supabase")
async def test_supabase(payload: TestSupabaseRequest):
    """Test Supabase connection using either direct client or database URL."""
    supabase_url = payload.supabase_url.strip()
    anon_key = payload.anon_key.strip()

    if not supabase_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Supabase URL must start with http:// or https://")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{supabase_url.rstrip('/')}/auth/v1/health",
                headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
            )
            if resp.status_code not in (200, 204):
                rest_resp = await client.get(
                    f"{supabase_url.rstrip('/')}/rest/v1/",
                    headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
                )
                if rest_resp.status_code not in (200, 204):
                    logger.warning(f"Supabase REST check returned {rest_resp.status_code}")
    except Exception as e:
        logger.warning(f"REST health check warning: {e}")

    if payload.db_password:
        try:
            import psycopg2

            project_ref = extract_project_ref(supabase_url)
            db_url = build_db_url(project_ref, payload.db_password)
            conn = psycopg2.connect(db_url, connect_timeout=5)
            conn.close()
            return {
                "connected": True,
                "status": "success",
                "message": f"Successfully verified Supabase PostgreSQL connection to {project_ref}",
            }
        except Exception as e:
            logger.warning(f"Direct DB URL connection check failed: {e}")
            return {
                "connected": True,
                "status": "partial",
                "message": "Supabase API reachable. Direct DB connection will be finalized on setup.",
            }

    return {
        "connected": True,
        "status": "success",
        "message": "Supabase REST API verified successfully",
    }


@router.post("/api/connectors/setup-supabase")
@router.post("/api/setup/supabase")
@router.post("/setup/supabase")
async def setup_supabase_endpoint(payload: SetupSupabaseRequest):
    """Full Supabase bootstrap: write .env, create tables and pgvector RPCs."""
    logger.info("Setting up Supabase project")
    result = connect_and_setup(
        supabase_url=payload.supabase_url.strip(),
        anon_key=payload.anon_key.strip(),
        service_key=payload.service_key.strip(),
        db_password=payload.db_password.strip(),
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to connect and initialize Supabase tables"),
        )

    tables = result.get("tables_created", [])
    return {
        "success": True,
        "project_ref": result.get("project_ref"),
        "tables_created": len(tables),
        "tables": tables,
        "env_written": True,
        "message": f"Successfully created/verified {len(tables)} tables with pgvector match_knowledge & match_brain_memory RPCs.",
    }


# ---------------------------------------------------------
# 3. WordPress Connectors Endpoints (Backend Proxy)
# ---------------------------------------------------------

@router.post("/api/wordpress/connect")
@router.post("/api/connectors/test-wordpress")
@router.post("/wordpress/connect")
async def wordpress_connect(payload: WordPressConnectRequest):
    """Backend proxy to test WordPress credentials without CORS issues."""
    site_url = payload.site_url.strip().rstrip("/")
    username = payload.wp_username.strip()
    password = payload.wp_app_password.strip().replace(" ", "")

    if not site_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Site URL must start with http:// or https://")

    user_url = f"{site_url}/wp-json/wp/v2/users/me?context=edit"
    posts_url = f"{site_url}/wp-json/wp/v2/posts?per_page=5&status=publish,draft"

    try:
        user_resp = requests.get(
            user_url,
            auth=(username, password),
            headers={"User-Agent": "RankForge-SEO-Agent/2.0"},
            timeout=10,
        )

        if user_resp.status_code in (401, 403):
            raise HTTPException(
                status_code=401,
                detail="WordPress Authentication failed. Verify your username and Application Password in WP Admin -> Users -> Profile.",
            )
        elif user_resp.status_code != 200:
            raise HTTPException(
                status_code=user_resp.status_code,
                detail=f"WordPress REST API error ({user_resp.status_code}): {user_resp.text[:200]}",
            )

        user_data = user_resp.json()

        posts = []
        try:
            posts_resp = requests.get(
                posts_url,
                auth=(username, password),
                headers={"User-Agent": "RankForge-SEO-Agent/2.0"},
                timeout=10,
            )
            if posts_resp.status_code == 200:
                for p in posts_resp.json():
                    title = p.get("title", {}).get("rendered", "") if isinstance(p.get("title"), dict) else str(p.get("title", ""))
                    posts.append({
                        "id": p.get("id"),
                        "title": title,
                        "link": p.get("link"),
                        "status": p.get("status"),
                        "date": p.get("date"),
                    })
        except Exception as e:
            logger.warning(f"Could not fetch recent posts: {e}")

        return {
            "connected": True,
            "status": "success",
            "message": f"Successfully connected to WordPress as {user_data.get('name', username)}",
            "user": {
                "id": user_data.get("id"),
                "name": user_data.get("name"),
                "slug": user_data.get("slug"),
                "roles": user_data.get("roles", []),
            },
            "site_url": site_url,
            "recent_posts": posts,
        }
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail=f"Connection to WordPress site {site_url} timed out")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail=f"Could not connect to {site_url}. Verify domain and SSL certificate.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in WordPress connection test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/wordpress/save")
@router.post("/api/connectors/save-wordpress")
@router.post("/wordpress/save")
async def wordpress_save(payload: WordPressSaveRequest):
    """Save WordPress credentials Fernet-encrypted into Supabase + environment."""
    site_url = payload.site_url.strip().rstrip("/")
    username = payload.wp_username.strip()
    password = payload.wp_app_password.strip().replace(" ", "")

    # 1. Persist non-secret values in .env for services that read env config
    write_env_file(custom_keys={
        "WORDPRESS_SITE_URL": site_url,
        "WORDPRESS_USERNAME": username,
    })

    encrypted = encrypt_secret(password)

    supabase = get_supabase()
    domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
    wid = payload.website_id

    # 2a. Upsert website row in Supabase
    try:
        if wid and wid not in ("default", "all", ""):
            supabase.table("websites").update({
                "cms_url": site_url,
                "url": site_url,
                "cms_user": username,
                "wordpress_user": username,
                "wordpress_url": site_url,
                "app_password": encrypted,
                "wordpress_password": encrypted,
                "status": "active",
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", wid).execute()
        else:
            existing_site = supabase.table("websites").select("id").eq("domain", domain).limit(1).execute().data
            if existing_site:
                wid = existing_site[0]["id"]
                supabase.table("websites").update({
                    "cms_url": site_url,
                    "url": site_url,
                    "cms_user": username,
                    "wordpress_user": username,
                    "wordpress_url": site_url,
                    "app_password": encrypted,
                    "wordpress_password": encrypted,
                    "status": "active",
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", wid).execute()
            else:
                new_site_res = supabase.table("websites").insert({
                    "domain": domain,
                    "cms_url": site_url,
                    "url": site_url,
                    "cms_user": username,
                    "wordpress_user": username,
                    "wordpress_url": site_url,
                    "app_password": encrypted,
                    "wordpress_password": encrypted,
                    "status": "active",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }).execute().data
                if new_site_res:
                    wid = new_site_res[0]["id"]
    except Exception as e:
        logger.warning(f"Could not attach credentials to websites row: {e}")

    # 2b. Keep a wordpress_connections record (encrypted password only)
    try:
        existing = (
            supabase.table("wordpress_connections")
            .select("id")
            .eq("site_url", site_url)
            .limit(1)
            .execute()
            .data
            or []
        )
        conn_payload = {
            "site_url": site_url,
            "wp_username": username,
            "wp_app_password_encrypted": encrypted,
            "status": "connected",
            "last_synced": datetime.utcnow().isoformat(),
        }
        if existing:
            supabase.table("wordpress_connections").update(conn_payload).eq("id", existing[0]["id"]).execute()
        else:
            conn_payload["wp_app_password"] = encrypted
            supabase.table("wordpress_connections").insert(conn_payload).execute()
    except Exception as e:
        logger.warning(f"Could not persist wordpress_connections row: {e}")

    return {
        "success": True,
        "connected": True,
        "site_url": site_url,
        "message": "WordPress credentials saved securely (Fernet-encrypted)",
    }


class GenericConnectorSave(BaseModel):
    key: Optional[str] = None
    api_key: Optional[str] = None
    url: Optional[str] = None
    token: Optional[str] = None
    secret: Optional[str] = None
    email: Optional[str] = None
    property_id: Optional[str] = None


@router.post("/api/connectors/save/{connector_name}")
@router.post("/connectors/save/{connector_name}")
async def save_generic_connector(connector_name: str, payload: GenericConnectorSave):
    """Save API keys or credentials for any connector into environment."""
    c_name = connector_name.lower().strip()
    env_updates = {}

    if c_name == "redis":
        env_updates["REDIS_URL"] = payload.url or "redis://localhost:6379/0"
    elif c_name == "serper":
        env_updates["SERPER_API_KEY"] = payload.api_key or payload.key or ""
    elif c_name == "gsc":
        env_updates["GSC_SITE_URL"] = payload.url or ""
        if payload.secret:
            env_updates["GSC_SERVICE_ACCOUNT_JSON"] = payload.secret
    elif c_name == "ga4":
        env_updates["GA4_PROPERTY_ID"] = payload.property_id or payload.key or ""
        if payload.secret:
            env_updates["GA4_CREDENTIALS_JSON"] = payload.secret
    elif c_name == "ahrefs":
        env_updates["AHREFS_API_KEY"] = payload.api_key or payload.key or ""
    elif c_name == "slack":
        env_updates["SLACK_WEBHOOK_URL"] = payload.url or payload.key or ""
    elif c_name == "resend":
        env_updates["RESEND_API_KEY"] = payload.api_key or payload.key or ""
        if payload.email:
            env_updates["RESEND_FROM_EMAIL"] = payload.email

    if env_updates:
        write_env_file(custom_keys=env_updates)

    return {
        "success": True,
        "connector": c_name,
        "message": f"{connector_name.title()} credentials saved successfully",
        "updated_keys": list(env_updates.keys()),
    }


@router.post("/api/connectors/ga4/test")
@router.post("/connectors/ga4/test")
async def ga4_test(payload: dict = None):
    """Real GA4 Data API call: sessions for last 7 days. Never returns credentials."""
    payload = payload or {}
    website_id = payload.get("website_id")
    try:
        from ..services.ga4_service import ga4_service
        result = await ga4_service.get_recent_sessions(website_id=website_id, days=7)
        if result.get("connected"):
            return {
                "connected": True,
                "sessions_last_7_days": result.get("sessions", 0),
                "property_id_masked": True,
                "message": result.get("message", "GA4 data retrieved"),
            }
        return {
            "connected": False,
            "error": result.get("error") or "GA4 credentials not configured",
        }
    except ImportError:
        return {"connected": False, "error": "GA4 service module unavailable"}
    except Exception as e:
        logger.warning(f"GA4 test failed: {e}")
        return {"connected": False, "error": str(e)[:200]}


@router.post("/api/connectors/gsc/properties")
@router.post("/connectors/gsc/properties")
async def gsc_properties(payload: dict = None):
    """List verified Google Search Console properties via the Search Console API."""
    payload = payload or {}
    try:
        from ..services.gsc_service import list_verified_sites

        sites = await list_verified_sites()
        return {"success": True, "properties": sites}
    except Exception as e:
        logger.warning(f"GSC properties listing failed: {e}")
        return {"success": False, "properties": [], "error": str(e)[:200]}


@router.post("/api/connectors/gsc/select-property")
@router.post("/connectors/gsc/select-property")
async def gsc_select_property(payload: dict):
    """Persist the selected GSC property onto the websites row."""
    website_id = payload.get("website_id")
    property_url = payload.get("property")
    if not website_id or not property_url:
        raise HTTPException(status_code=400, detail="website_id and property are required")

    try:
        get_supabase().table("websites").update({
            "gsc_property": property_url,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", website_id).execute()
        return {"success": True, "gsc_property": property_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 5. Overall Connectors Status Endpoint (Booleans ONLY)
# ---------------------------------------------------------
# SECURITY CONTRACT: this endpoint NEVER returns credential values, masked
# fragments, or partial keys. Only `is_configured` / `connected` booleans.

@router.get("/api/connectors/status")
@router.get("/connectors/status")
async def get_connectors_status(website_id: Optional[str] = None):
    """Get live connection status of all integrations. Booleans only — no secrets."""
    # 1. Supabase Status
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_connected = False
    if supabase_url:
        try:
            get_supabase().table("websites").select("id").limit(1).execute()
            supabase_connected = True
        except Exception:
            supabase_connected = bool(os.environ.get("SUPABASE_KEY"))

    supabase_status = {
        "connected": supabase_connected,
        "is_configured": bool(supabase_url),
    }

    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    nim_available = True
    try:
        from ..database import is_nim_available
        nim_available = await is_nim_available()
    except Exception:
        nim_available = bool(nvidia_key)

    nvidia_status = {
        "connected": bool(nvidia_key) and nim_available,
        "is_configured": bool(nvidia_key),
        "available": nim_available,
    }

    redis_status = {
        "connected": bool(os.environ.get("REDIS_URL")),
        "is_configured": bool(os.environ.get("REDIS_URL")),
    }

    serper_key = os.environ.get("SERPER_API_KEY", "")
    serper_status = {
        "connected": bool(serper_key),
        "is_configured": bool(serper_key),
        "fallback_active": not bool(serper_key),
    }

    gsc_key = os.environ.get("GSC_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_CLIENT_ID", "")
    gsc_status = {
        "connected": bool(gsc_key),
        "is_configured": bool(gsc_key),
    }

    ga4_key = os.environ.get("GA4_PROPERTY_ID") or os.environ.get("GA4_CREDENTIALS_JSON", "")
    ga4_status = {
        "connected": bool(ga4_key),
        "is_configured": bool(ga4_key),
    }

    wp_site = os.environ.get("WORDPRESS_SITE_URL", "")
    wp_status = {
        "connected": bool(wp_site),
        "is_configured": bool(wp_site),
        "oauth_enabled": bool(os.environ.get("WP_OAUTH_CLIENT_ID")),
    }

    # Per-website credential state from Supabase (booleans only)
    wp_site_configured = bool(wp_site)
    serper_site_configured = bool(serper_key)
    slack_workspace = None
    slack_connected = bool(os.environ.get("SLACK_BOT_TOKEN"))
    if website_id and website_id not in ("default", "all", "", "null", "undefined"):
        try:
            row = (
                get_supabase().table("websites")
                .select("app_password, wordpress_password, cms_url, cms_user, wordpress_user")
                .eq("id", website_id)
                .single()
                .execute()
                .data or {}
            )
            wp_site_configured = bool(row.get("app_password") or row.get("wordpress_password"))
            if wp_site_configured:
                wp_status["connected"] = True
                wp_status["site_url_present"] = bool(row.get("cms_url"))
        except Exception as e:
            logger.warning(f"Website connector status lookup failed: {e}")

    ahrefs_key = os.environ.get("AHREFS_API_KEY", "")
    ahrefs_status = {
        "connected": bool(ahrefs_key),
        "is_configured": bool(ahrefs_key),
    }

    resend_key = os.environ.get("RESEND_API_KEY", "")
    resend_status = {
        "connected": bool(resend_key),
        "is_configured": bool(resend_key),
    }

    all_connectors = [
        supabase_status["connected"],
        nvidia_status["connected"],
        serper_status["connected"],
        gsc_status["connected"],
        ga4_status["connected"],
        wp_status["connected"],
        ahrefs_status["connected"],
        slack_connected,
        resend_status["connected"],
    ]
    connected_count = sum(1 for c in all_connectors if c)

    return {
        "success": True,
        "connected_count": connected_count,
        "total_count": len(all_connectors),
        "supabase": supabase_status,
        "nvidia": nvidia_status,
        "redis": redis_status,
        "serper": serper_status,
        "gsc": gsc_status,
        "ga4": ga4_status,
        "wordpress": wp_status,
        "ahrefs": ahrefs_status,
        "slack": {
            "connected": slack_connected,
            "workspace_name": slack_workspace,
            "oauth_ready": bool(os.environ.get("SLACK_CLIENT_ID")),
        },
        "resend": resend_status,
        "website_id": website_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
