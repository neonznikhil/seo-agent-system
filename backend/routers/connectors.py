import os
import json
import logging
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, Field

try:
    from database import get_supabase, execute_db
except (ImportError, ValueError):
    try:
        from database import get_supabase, execute_db
    except (ImportError, ValueError):
        from backend.database import get_supabase, execute_db

try:
    from security import encrypt_secret, decrypt_secret
except (ImportError, ValueError):
    try:
        from security import encrypt_secret, decrypt_secret
    except (ImportError, ValueError):
        from backend.security import encrypt_secret, decrypt_secret
from auto_supabase import (
    connect_and_setup,
    write_env_file,
    extract_project_ref,
    build_db_url,
)
from services.website_service import get_default_website_id, get_default_website_id_async
from services.connector_credentials import resolve_wp_username, is_placeholder_wp_username

logger = logging.getLogger("backend.routers.connectors")
router = APIRouter(tags=["connectors"])


def _apply_env_credentials(updates: Dict[str, str]) -> bool:
    """Promote already-verified credentials into the running process.

    `write_env_file` intentionally only touches disk, so without this a saved
    credential has no effect until the next restart. Callers must verify the
    value against the live provider first (an unverified key would otherwise
    poison the process). Changing any SUPABASE_* var also invalidates the
    cached singleton, otherwise `get_supabase()` keeps using the old client.
    """
    applied = {k: v for k, v in updates.items() if v}
    if not applied:
        return False
    os.environ.update(applied)
    if any(k.startswith("SUPABASE") for k in applied):
        try:
            from database import reset_supabase_client, reset_nim_availability
            reset_supabase_client()
            reset_nim_availability()
        except Exception as e:
            logger.debug(f"[Connectors] Supabase client reset note: {e}")
        return True
    return False


async def _probe_supabase(url: str, key: str) -> tuple[bool, str]:
    """Live-check Supabase credentials before adopting them into the process."""
    import asyncio

    def _run() -> tuple[bool, str]:
        try:
            from supabase import create_client
            create_client(url, key).table("websites").select("id").limit(1).execute()
            return True, "ok"
        except Exception as e:
            return False, str(e)[:200]

    return await asyncio.to_thread(_run)


async def verify_nvidia_key(api_key: str, model: Optional[str] = None) -> tuple[bool, str, int]:
    """Return (connected, message, models_count) for an NVIDIA NIM key.

    GET /v1/models is a *public* catalog endpoint: it answers 200 even for an
    invalid or missing key, so using it as the connectivity check reported every
    key as "Connected". Only the authenticated chat-completions endpoint proves
    a key works (401 = no key, 403 = rejected key, 200 = valid).
    """
    key = (api_key or "").strip()
    if not key:
        return False, "NVIDIA API key is required", 0

    # A single hardcoded model id made a *valid* key look invalid whenever that
    # one id was deprecated/renamed (404) — the key works, the model doesn't.
    # Try the configured model first, then the documented fallbacks, and only
    # treat 401/403 as "bad key".
    candidates: list[str] = []
    for candidate in (
        model,
        os.getenv("NIM_LLM_MODEL"),
        os.getenv("NIM_LLM_FALLBACK"),
        "meta/llama-3.2-11b-vision-instruct",
        "google/gemma-4-31b-it",
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    last_error = "NVIDIA API request failed"
    try:
        # NVIDIA's first (cold) completion can take 20-30s; a short budget
        # produced spurious "timed out" results for perfectly valid keys.
        async with httpx.AsyncClient(timeout=45.0) as client:
            for model_id in candidates:
                resp = await client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 8,
                    },
                )
                if resp.status_code in (401, 403):
                    return False, "Invalid NVIDIA API key or unauthorized access", 0
                if resp.status_code == 429:
                    # Rate limited but the key authenticated — it is valid.
                    return True, "NVIDIA NIM key verified (rate limited; backing off)", 0
                if resp.status_code == 404:
                    # Model id not found — the key may still be fine; try the next.
                    last_error = f"NVIDIA model '{model_id}' not found (HTTP 404)"
                    continue
                if resp.status_code != 200:
                    # Anything else (5xx, 400, ...) is not fixed by another model;
                    # stop instead of burning the whole timeout on retries.
                    return False, f"NVIDIA API request failed (HTTP {resp.status_code})", 0

                models_count = 0
                try:
                    models_resp = await client.get(
                        "https://integrate.api.nvidia.com/v1/models",
                        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                    )
                    if models_resp.status_code == 200:
                        models_count = len(models_resp.json().get("data", []) or [])
                except Exception:
                    pass
                return True, "NVIDIA NIM key verified", models_count

            return False, last_error, 0
    except httpx.TimeoutException:
        return False, "Connection to NVIDIA NIM timed out", 0
    except Exception as e:
        logger.error(f"Error verifying NVIDIA API key: {e}")
        return False, "Failed to reach NVIDIA. Please try again.", 0


# Serper results are cached briefly so /connectors/status (polled by the UI) does
# not fire a live search on every render, while still reflecting a revoked or
# credit-exhausted key within the TTL instead of reporting a permanent green.
_SERPER_STATUS_CACHE: dict = {"key": None, "ok": None, "message": None, "at": 0.0}
_SERPER_CACHE_TTL_SECONDS = 120


async def verify_serper_key(api_key: str, *, use_cache: bool = True) -> tuple[bool, str]:
    """Return (connected, message) for a Serper.dev key via a live query.

    A present-but-invalid key used to report connected=true because the status
    endpoint only checked that the env var was non-empty. Only a 200 from the
    search endpoint proves the key works; 401/403 means it is rejected and 402/400
    with a credits message means the account is out of credits.
    """
    import time as _time

    key = (api_key or "").strip()
    if not key:
        return False, "Serper API key is required"

    if use_cache:
        cached = _SERPER_STATUS_CACHE
        if (
            cached["key"] == key
            and cached["ok"] is not None
            and (_time.monotonic() - cached["at"]) < _SERPER_CACHE_TTL_SECONDS
        ):
            return cached["ok"], cached["message"]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                json={"q": "RankForge SEO test", "num": 3},
            )
        if resp.status_code == 200:
            result = (True, "Serper key verified")
        elif resp.status_code in (401, 403):
            result = (False, "Serper rejected this API key (401/403 Unauthorized)")
        elif "credit" in resp.text.lower() or "not enough" in resp.text.lower():
            result = (False, "Serper account has no credits left")
        else:
            result = (False, f"Serper request failed (HTTP {resp.status_code})")
    except httpx.TimeoutException:
        result = (False, "Connection to Serper timed out")
    except Exception as e:
        logger.error(f"Error verifying Serper API key: {e}")
        result = (False, "Failed to reach Serper. Please try again.")

    _SERPER_STATUS_CACHE.update({"key": key, "ok": result[0], "message": result[1], "at": _time.monotonic()})
    return result


# GSC/GA4 live verification is cached like Serper: /connectors/status is polled
# by the UI, so we must not hit the Google APIs on every render, yet a revoked
# credential must stop reading "Connected" within the TTL.
_GOOGLE_STATUS_CACHE: dict = {}
_GOOGLE_CACHE_TTL_SECONDS = 300


async def _cached_google_check(cache_key: str, signature: str, check) -> tuple[bool, str]:
    """Return a cached (connected, message) for a Google connector live check."""
    import time as _time

    entry = _GOOGLE_STATUS_CACHE.get(cache_key)
    if (
        entry
        and entry.get("signature") == signature
        and (_time.monotonic() - entry["at"]) < _GOOGLE_CACHE_TTL_SECONDS
    ):
        return entry["ok"], entry["message"]

    try:
        ok, message = await check()
    except Exception as e:
        ok, message = False, str(e)[:200]
    _GOOGLE_STATUS_CACHE[cache_key] = {
        "signature": signature, "ok": ok, "message": message, "at": _time.monotonic()
    }
    return ok, message


# ---------------------------------------------------------
# Pydantic Request / Response Models
# ---------------------------------------------------------
class TestNvidiaRequest(BaseModel):
    # Optional so "Test" can verify the key already persisted in the backend env
    # instead of 422-ing when the form field is empty.
    api_key: Optional[str] = Field(None, description="NVIDIA NIM API Key starting with nvapi-")


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
    wp_username: Optional[str] = Field(None, description="WordPress username / application user")
    username: Optional[str] = Field(None, description="Alias for wp_username")
    wp_app_password: Optional[str] = Field(None, description="WordPress Application Password")
    app_password: Optional[str] = Field(None, description="Alias for wp_app_password")


class WordPressSaveRequest(BaseModel):
    site_url: str = Field(..., description="WordPress website URL")
    wp_username: Optional[str] = Field(None, description="WordPress username")
    username: Optional[str] = Field(None, description="Alias for wp_username")
    wp_app_password: Optional[str] = Field(None, description="WordPress Application Password")
    app_password: Optional[str] = Field(None, description="Alias for wp_app_password")
    website_id: Optional[str] = Field(None, description="Website ID to attach credentials to")


class TestSerperRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="Serper API Key")


class TestGscRequest(BaseModel):
    credentials_json: Optional[str] = Field(None, description="Google Service Account JSON")
    property_url: Optional[str] = Field(None, description="Property URL")


class TestGa4Request(BaseModel):
    property_id: Optional[str] = Field(None, description="GA4 Property ID")
    credentials_json: Optional[str] = Field(None, description="Google Credentials JSON")


class GenericConnectorSave(BaseModel):
    key: Optional[str] = None
    api_key: Optional[str] = None
    url: Optional[str] = None
    token: Optional[str] = None
    secret: Optional[str] = None
    email: Optional[str] = None
    property_id: Optional[str] = None


class SaveAllRequest(BaseModel):
    nvidia_api_key: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_db_password: Optional[str] = None
    wordpress_site_url: Optional[str] = None
    wordpress_username: Optional[str] = None
    wordpress_app_password: Optional[str] = None
    serper_api_key: Optional[str] = None
    gsc_property_url: Optional[str] = None
    gsc_credentials_json: Optional[str] = None
    ga4_property_id: Optional[str] = None
    ga4_credentials_json: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    auto_publish: Optional[bool] = True


# ---------------------------------------------------------
# 1. NVIDIA Connectors Endpoints
# ---------------------------------------------------------

@router.post("/api/connectors/test-nvidia")
@router.post("/connectors/test-nvidia")
async def test_nvidia(payload: TestNvidiaRequest):
    """Test NVIDIA NIM API key via the authenticated chat endpoint."""
    api_key = (payload.api_key or os.getenv("NVIDIA_API_KEY", "")).strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="NVIDIA API key is required")

    connected, message, models_count = await verify_nvidia_key(api_key)
    if not connected:
        status = 401 if "Invalid" in message or "unauthorized" in message.lower() else 502
        raise HTTPException(status_code=status, detail=message)

    models_list: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
        if resp.status_code == 200:
            models_list = [
                m.get("id") for m in resp.json().get("data", []) if isinstance(m, dict) and "id" in m
            ]
    except Exception:
        pass

    return {
        "connected": True,
        "status": "success",
        "message": f"Successfully connected to NVIDIA NIM ({models_count} models available)",
        "models_count": models_count,
        "models": models_list[:25],
    }


@router.get("/api/connectors/nvidia/test")
@router.get("/connectors/nvidia/test")
@router.post("/api/connectors/nvidia/test")
@router.post("/connectors/nvidia/test")
async def test_nvidia_live():
    """Live diagnostic test executing both real NIM LLM completion and 1536-dim embedding."""
    from services.nim_client import generate, embed
    try:
        completion = await generate("Explain autonomous SEO in one sentence.", max_tokens=60)
        vector = await embed("autonomous search engine optimization")
        return {
            "success": True,
            "connected": True,
            "llm_completion": completion,
            "embedding_dimensions": len(vector),
            "vector_sample": vector[:5] if vector else [],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "connected": False,
            "error": "NVIDIA connection failed. Please check your API key."
        }


@router.post("/api/connectors/save-nvidia")
@router.post("/connectors/save-nvidia")
async def save_nvidia(payload: SaveNvidiaRequest):
    """Persist NVIDIA NIM API key and report live verification honestly."""
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    res = write_env_file(custom_keys={"NVIDIA_API_KEY": api_key})
    try:
        from database import reset_nim_availability
        reset_nim_availability()
    except Exception:
        pass
    persisted = bool(res and (res.get("backend_env") or res.get("keys_set")))

    # A write to .env only proves the string was stored, not that the key works.
    # Probe the authenticated NIM endpoint so the UI never shows "Connected"
    # for an invalid key.
    connected, verify_message, _ = await verify_nvidia_key(api_key)

    # Only adopt the key into the live process once it has been proven valid.
    # Blindly assigning os.environ here used to poison the whole running app
    # with an unverified key, turning every NIM call into a 403 until restart.
    if connected:
        os.environ["NVIDIA_API_KEY"] = api_key

    if persisted and connected:
        message = "NVIDIA API Key saved and verified."
    elif persisted:
        message = (
            f"NVIDIA API Key saved, but live verification failed. {verify_message}".strip()
        )
    else:
        message = "NVIDIA API Key received but could not be written to the durable store"

    return {
        "success": persisted,
        "connected": connected,
        "persisted": persisted,
        "message": message,
        "env_updated": res,
    }


@router.get("/api/connectors/supabase/test")
@router.get("/connectors/supabase/test")
async def test_supabase_live_diagnostic():
    """Live diagnostic test querying real Supabase tables and returning table record counts."""
    supabase = get_supabase()
    tables = ["websites", "users", "content_log", "tasks", "daily_costs", "keyword_proposals"]
    counts = {}
    connected = False
    try:
        w = await execute_db(supabase.table("websites").select("id", count="exact").limit(1))
        connected = True
        counts["websites"] = getattr(w, "count", len(w.data or []))
        
        for t in tables[1:]:
            try:
                res = await execute_db(supabase.table(t).select("id", count="exact").limit(1))
                counts[t] = getattr(res, "count", len(res.data or []))
            except Exception:
                counts[t] = 0

        return {
            "success": True,
            "connected": connected,
            "table_counts": counts,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "connected": False,
            "error": "NVIDIA connection failed. Please check your API key.",
            "table_counts": counts,
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/api/connectors/test-supabase")
@router.post("/connectors/test-supabase")
async def test_supabase(payload: TestSupabaseRequest):
    """Test Supabase connection using REST endpoint and optional direct Postgres connection."""
    supabase_url = (payload.supabase_url or os.getenv("SUPABASE_URL", "")).strip()
    anon_key = (payload.anon_key or os.getenv("SUPABASE_KEY", "")).strip()

    if not supabase_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Supabase URL must start with http:// or https://")

    rest_connected = False
    rest_detail = ""
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}"}
            base = supabase_url.rstrip("/")
            # Probe the REST endpoint first: /auth/v1/health is frequently
            # unreachable or slow on a healthy project, and the old ordering
            # burned the full 8s timeout before falling through to a REST check
            # that answers in ~200ms. That delay pushed the whole test past the
            # client timeout, so a working Supabase reported "timed out".
            for probe in (f"{base}/rest/v1/", f"{base}/auth/v1/health"):
                try:
                    resp = await client.get(probe, headers=headers)
                except Exception as exc:
                    rest_detail = str(exc)[:200]
                    continue
                if resp.status_code in (200, 204, 401, 403):
                    # 401/403 still proves the project answers; the key scope is
                    # a separate concern reported elsewhere.
                    rest_connected = resp.status_code in (200, 204)
                    rest_detail = f"{probe} -> HTTP {resp.status_code}"
                    if rest_connected:
                        break
                else:
                    rest_detail = f"{probe} -> HTTP {resp.status_code}"
    except Exception as e:
        logger.warning(f"REST health check warning: {e}")
        rest_detail = str(e)[:200]

    db_connected = False
    if payload.db_password:
        try:
            import psycopg2
            project_ref = extract_project_ref(supabase_url)
            db_url = build_db_url(project_ref, payload.db_password)
            conn = psycopg2.connect(db_url, connect_timeout=5)
            conn.close()
            db_connected = True
        except Exception as e:
            logger.warning(f"Direct DB URL connection check failed: {e}")

    # A non-empty anon key is NOT proof of a working connection. Only report
    # connected when a real REST/DB probe succeeded, otherwise the UI shows a
    # green "Connected" badge for a bogus URL and every later query fails.
    connected = rest_connected or db_connected
    response = {
        "connected": connected,
        "rest_connected": rest_connected,
        "db_connected": db_connected,
        "status": "success" if connected else "failed",
        "message": (
            f"Supabase connection verified (REST: {'OK' if rest_connected else 'Failed'}, "
            f"Direct DB: {'OK' if db_connected else 'N/A'})"
            if connected
            else "Could not reach Supabase. Verify the project URL and anon key."
        ),
    }
    if rest_detail:
        response["rest_detail"] = rest_detail
    return response


@router.post("/api/connectors/setup-supabase")
@router.post("/api/setup/supabase")
@router.post("/setup/supabase")
async def setup_supabase_endpoint(payload: SetupSupabaseRequest):
    """Full Supabase bootstrap: write .env, create tables, pgvector extension, and match RPCs."""
    logger.info("Setting up Supabase project tables and RPCs")
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

    # Bootstrap verified the project — adopt the creds now so the running app
    # uses them immediately instead of after a restart.
    _apply_env_credentials({
        "SUPABASE_URL": payload.supabase_url.strip(),
        "SUPABASE_ANON_KEY": payload.anon_key.strip(),
        "SUPABASE_KEY": payload.anon_key.strip(),
        "SUPABASE_SERVICE_ROLE_KEY": payload.service_key.strip(),
        "SUPABASE_SERVICE_KEY": payload.service_key.strip(),
    })

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
@router.post("/api/connectors/wordpress/test")
@router.post("/connectors/wordpress/test")
@router.post("/wordpress/connect")
async def wordpress_connect(payload: WordPressConnectRequest):
    """Backend proxy to test WordPress credentials without CORS issues, verifying user role & capability."""
    site_url = payload.site_url.strip().rstrip("/")
    username = resolve_wp_username(payload.wp_username, payload.username)
    if not username:
        raise HTTPException(
            status_code=400,
            detail="A real WordPress username is required. Leave it blank or as a placeholder "
                   "value and the connection cannot be verified — enter your actual WP user name.",
        )
    password = (payload.wp_app_password or payload.app_password or "").strip()

    if not password or "•" in password:
        try:
            from services.local_store import list_local_websites
            for s in list_local_websites():
                if (s.get("wordpress_url") or s.get("url") or "").rstrip("/") == site_url:
                    stored = s.get("app_password") or s.get("wordpress_password") or s.get("wordpress_password_encrypted") or ""
                    if stored:
                        password = decrypt_secret(stored) if stored.startswith("gAAAA") else stored
                    break
        except Exception:
            pass
        if not password or "•" in password:
            password = os.getenv("WORDPRESS_APP_PASSWORD", "")

    return await _verify_wordpress_credentials(site_url, username, password)


async def _verify_wordpress_credentials(site_url: str, username: str, password: str) -> Dict[str, Any]:
    """Live-test WordPress credentials. Raises HTTPException on auth/API failure.

    Shared by the Test button and the Save button so "saved" never implies
    "connected" unless the credentials actually authenticated.
    """
    if not site_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Site URL must start with http:// or https://")

    user_url = f"{site_url}/wp-json/wp/v2/users/me?context=edit"
    fallback_user_url = f"{site_url}/?rest_route=/wp/v2/users/me"
    posts_url = f"{site_url}/wp-json/wp/v2/posts?per_page=3&status=publish,draft"

    wp_headers = {
        "User-Agent": "Mozilla/5.0 RankForge/1.0",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=6.0), headers=wp_headers, follow_redirects=True) as client:
            user_resp = await client.get(user_url, auth=(username, password))
            if user_resp.status_code == 401 and " " in password:
                user_resp = await client.get(user_url, auth=(username, password.replace(" ", "")))
            elif user_resp.status_code == 401 and " " not in password and len(password) == 24:
                spaced = " ".join([password[i:i+4] for i in range(0, len(password), 4)])
                user_resp = await client.get(user_url, auth=(username, spaced))

            if user_resp.status_code != 200:
                user_resp = await client.get(fallback_user_url, auth=(username, password))
                if user_resp.status_code == 401 and " " in password:
                    user_resp = await client.get(fallback_user_url, auth=(username, password.replace(" ", "")))

            if user_resp.status_code in (401, 403):
                raise HTTPException(
                    status_code=401,
                    detail="WordPress Authentication failed (401). Verify username and Application Password in WP Admin -> Users -> Profile.",
                )
            elif user_resp.status_code != 200:
                raise HTTPException(
                    status_code=user_resp.status_code,
                     detail="WordPress REST API error. Please check your WordPress credentials.",
                )

            user_data = user_resp.json()
            roles = user_data.get("roles", []) or []
            can_publish = bool("editor" in roles or "administrator" in roles or "author" in roles)

            if roles and not can_publish and any(r in ["subscriber", "contributor"] for r in roles):
                raise HTTPException(
                    status_code=403,
                    detail=f"WordPress User Role '{roles}' has insufficient permissions. Needs Editor or Administrator role. Go to WP Admin > Users > Edit User > Role = Editor.",
                )

            posts = []
            try:
                posts_resp = await client.get(posts_url, auth=(username, password))
                if posts_resp.status_code == 200:
                    for p in posts_resp.json()[:3]:
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
                "can_publish": can_publish,
                "message": (
                    f"Successfully connected to WordPress as {user_data.get('name', username)} "
                    f"(Role: {', '.join(roles) if roles else 'unknown'})"
                    + ("" if can_publish else ". Warning: this role may not be able to publish posts.")
                ),
                "user": {
                    "id": user_data.get("id"),
                    "name": user_data.get("name"),
                    "slug": user_data.get("slug"),
                    "roles": roles,
                },
                "site_url": site_url,
                "recent_posts": posts,
            }
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Connection to WordPress site {site_url} timed out after 12s")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Could not connect to {site_url}. Verify domain and SSL certificate.")
    except HTTPException:
        raise
    except Exception as e:
        # Surface what actually broke instead of a blind "check your credentials"
        # that hides bugs (JSON decode errors, DNS, unexpected shapes).
        logger.error(f"Error in WordPress connection test for {site_url}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"WordPress connection test failed ({type(e).__name__}): {str(e)[:180]}",
        )



@router.post("/api/wordpress/save")
@router.post("/api/connectors/save-wordpress")
@router.post("/wordpress/save")
async def wordpress_save(payload: WordPressSaveRequest):
    """Save WordPress credentials Fernet-encrypted into Supabase + environment."""
    site_url = payload.site_url.strip().rstrip("/")
    username = resolve_wp_username(payload.wp_username, payload.username)
    if not username:
        raise HTTPException(
            status_code=400,
            detail="A real WordPress username is required. Placeholder values are not "
                   "accepted — enter your actual WP user name.",
        )
    password = (payload.wp_app_password or payload.app_password or "").strip().replace(" ", "")
    if not password:
        raise HTTPException(status_code=400, detail="WordPress application password is required")

    # Verify BEFORE persisting: a "saved" response must never imply "connected"
    # unless the credentials actually authenticated (R4 — no fabricated success).
    verification = await _verify_wordpress_credentials(site_url, username, password)

    write_env_file(custom_keys={
        "WORDPRESS_SITE_URL": site_url,
        "WORDPRESS_USERNAME": username,
    })
    # Adopt into the live process so publish/draft calls stop using stale creds.
    _apply_env_credentials({"WORDPRESS_USERNAME": username})

    encrypted = encrypt_secret(password)
    supabase = get_supabase()
    domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
    wid = payload.website_id

    try:
        if wid and wid not in ("default", "all", ""):
            await execute_db(supabase.table("websites").update({
                "cms_url": site_url,
                "url": site_url,
                "cms_user": username,
                "wordpress_user": username,
                "wordpress_url": site_url,
                "app_password": encrypted,
                "wordpress_password": encrypted,
                "status": "active",
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", wid))
        else:
            existing_site = (await execute_db(supabase.table("websites").select("id").eq("domain", domain).limit(1))).data
            if existing_site:
                wid = existing_site[0]["id"]
                await execute_db(supabase.table("websites").update({
                    "cms_url": site_url,
                    "url": site_url,
                    "cms_user": username,
                    "wordpress_user": username,
                    "wordpress_url": site_url,
                    "app_password": encrypted,
                    "wordpress_password": encrypted,
                    "status": "active",
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", wid))
            else:
                new_site_res = (await execute_db(supabase.table("websites").insert({
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
                }))).data
                if new_site_res:
                    wid = new_site_res[0]["id"]
    except Exception as e:
        logger.warning(f"Could not attach credentials to websites row: {e}")

    try:
        from services.local_store import save_local_wp_connection, save_local_website
        save_local_wp_connection({
            "website_id": wid or "default",
            "site_url": site_url,
            "wp_username": username,
            "wp_app_password_encrypted": encrypted,
            "is_active": True,
        })
        save_local_website({
            "id": wid or "default",
            "domain": domain,
            "url": site_url,
            "wordpress_url": site_url,
            "wordpress_user": username,
            "app_password": encrypted,
            "status": "active",
        })
    except Exception as local_e:
        logger.debug(f"Local store WP save note: {local_e}")

    return {
        "success": True,
        "connected": bool(verification.get("connected")),
        "can_publish": verification.get("can_publish"),
        "role": (verification.get("user") or {}).get("roles") or [],
        "site_url": site_url,
        "website_id": wid,
        "message": "WordPress credentials verified and saved securely (Fernet-encrypted)",
    }


# ---------------------------------------------------------
# 4. Search APIs (Serper & Tavily)
# ---------------------------------------------------------

@router.post("/api/connectors/test-serper")
@router.post("/connectors/test-serper")
async def test_serper(payload: Optional[TestSerperRequest] = None):
    """Test Serper.dev API by executing a live Google Search query."""
    key = (payload.api_key if payload and payload.api_key else os.getenv("SERPER_API_KEY", "")).strip()
    if not key:
        raise HTTPException(status_code=400, detail="Serper API Key is required")

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": key,
        "Content-Type": "application/json",
    }
    body = {"q": "RankForge SEO test", "num": 10}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=body)

        if resp.status_code == 200:
            data = resp.json()
            organic = data.get("organic", [])
            os.environ["SERPER_API_KEY"] = key
            try:
                write_env_file(custom_keys={"SERPER_API_KEY": key})
            except Exception as e:
                logger.debug(f"Could not persist SERPER_API_KEY to .env: {e}")

            return {
                "connected": True,
                "status": "success",
                "message": f"Successfully connected to Serper ({len(organic)} live results returned)",
                "results_count": len(organic),
                "organic": organic[:3],
            }
        elif resp.status_code == 400 and ("credits" in resp.text.lower() or "not enough" in resp.text.lower()):
            os.environ["SERPER_API_KEY"] = key
            try:
                write_env_file(custom_keys={"SERPER_API_KEY": key})
            except Exception:
                pass
            return {
                "connected": False,
                "status": "warning",
                "message": "Serper API key saved. Note: Serper reported 'Not enough credits'. Please refill credits on serper.dev.",
                "results_count": 0,
            }
        elif resp.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Invalid Serper API key")
        else:
            raise HTTPException(status_code=resp.status_code, detail=f"External Serper API request failed ({resp.status_code}): {resp.text[:120]}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to Serper timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Serper connection error: {str(e)}")


@router.post("/api/connectors/save-serper")
@router.post("/connectors/save-serper")
async def save_serper(payload: TestSerperRequest):
    """Persist the Serper API key durably, then verify it with a live query.

    The key is written to the durable .env store independently of the live test,
    so a network hiccup on the verification call never loses the user's key.
    """
    key = (payload.api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Serper API Key is required")

    persisted = False
    try:
        res = write_env_file(custom_keys={"SERPER_API_KEY": key})
        persisted = bool(res and (res.get("backend_env") or res.get("keys_set")))
    except Exception as e:
        logger.error(f"Failed to persist Serper key: {e}")

    try:
        result = await test_serper(TestSerperRequest(api_key=key))
    except HTTPException as e:
        return {
            "success": persisted,
            "connected": False,
            "persisted": persisted,
            "message": f"Serper key saved, but live verification failed: {e.detail}",
            "results_count": 0,
            "organic": [],
        }
    # test_serper already promoted the key into the live process on success only,
    # so an unverifiable key never overrides the working environment.
    result["persisted"] = persisted
    result["saved"] = persisted
    return result


# ---------------------------------------------------------
# 5. Analytics (GSC & GA4)
# ---------------------------------------------------------

def _persist_google_credentials(env_updates: Dict[str, str], settings: Dict[str, Any]) -> Dict[str, Any]:
    """Persist verified Google credentials to .env, the process, and the local store.

    Returns an honest per-sink report; the caller only claims a save when at
    least one durable sink actually succeeded.
    """
    sinks: Dict[str, bool] = {"env_file": False, "process": False, "local_store": False}
    try:
        write_env_file(custom_keys=env_updates)
        sinks["env_file"] = True
    except Exception as e:
        logger.error(f"[Connectors] Google credentials .env write failed: {e}")
    try:
        _apply_env_credentials(env_updates)
        sinks["process"] = True
    except Exception as e:
        logger.error(f"[Connectors] Google credentials process apply failed: {e}")
    try:
        from services.local_store import set_local_connector_settings
        set_local_connector_settings(settings)
        sinks["local_store"] = True
    except Exception as e:
        logger.error(f"[Connectors] Google credentials local store failed: {e}")
    return sinks


async def _verify_gsc_live(credentials_json: Optional[str], property_url: Optional[str]) -> Dict[str, Any]:
    """Run a live Search Console call with the supplied or stored credentials.

    The Google client is synchronous, so it runs in a worker thread with a
    timeout — otherwise a slow/hung API call would block the event loop and the
    status endpoint (polled by the UI) would hang with it.
    """
    import asyncio

    from services.gsc_service import GSCService
    svc = GSCService(website_url=property_url or os.getenv("GSC_SITE_URL") or None,
                     credentials_path=credentials_json)
    if not svc.is_connected():
        return {"connected": False, "status": "not_configured", "properties": [],
                "message": "GSC not connected. Paste the service-account JSON in Connectors."}

    def _call() -> List[str]:
        service = svc._get_service()
        sites = service.sites().list().execute()
        return [
            s.get("siteUrl")
            for s in (sites.get("siteEntry") or [])
            if s.get("permissionLevel") in ("siteOwner", "siteFullUser", "siteRestrictedUser") and s.get("siteUrl")
        ]

    verified = await asyncio.wait_for(asyncio.to_thread(_call), timeout=20.0)
    if not verified:
        return {"connected": False, "status": "no_properties", "properties": [],
                "message": "GSC credentials valid but no verified properties. Verify the site in Search Console."}
    return {"connected": True, "status": "success", "properties": verified,
            "message": f"GSC credentials active ({len(verified)} properties accessible)"}


@router.get("/api/connectors/gsc/test")
@router.get("/connectors/gsc/test")
@router.post("/api/connectors/gsc/test")
@router.post("/connectors/gsc/test")
@router.post("/api/connectors/test-gsc")
@router.post("/connectors/test-gsc")
async def test_gsc(payload: Optional[TestGscRequest] = None):
    """Verify Google Search Console credentials live, then persist them durably.

    The pasted service-account JSON is written as GSC_SERVICE_ACCOUNT_JSON; the
    services previously only read GSC_CREDENTIALS_PATH, so a successful save was
    silently ignored. Persistence is reported per sink instead of a blanket
    "saved" that could hide a lost write.
    """
    cred_json = (payload.credentials_json if payload else None) or os.getenv("GSC_SERVICE_ACCOUNT_JSON")
    property_url = (payload.property_url if payload else None) or os.getenv("GSC_SITE_URL")

    if cred_json:
        try:
            json.loads(cred_json)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Service Account JSON format")

    try:
        result = await _verify_gsc_live(cred_json, property_url)
    except Exception as e:
        logger.warning(f"GSC test failed: {e}")
        return {
            "connected": False,
            "status": "error",
            "properties": [],
            "message": f"GSC connection failed: {str(e)[:180]}",
            "saved": False,
        }

    if not result.get("connected"):
        return {**result, "saved": False}

    # Credentials are proven live — persist them.
    env_updates: Dict[str, str] = {}
    if cred_json:
        env_updates["GSC_SERVICE_ACCOUNT_JSON"] = cred_json.strip()
    if property_url:
        env_updates["GSC_SITE_URL"] = property_url.strip()
    settings: Dict[str, Any] = {}
    if property_url:
        settings["gsc_property_url"] = property_url.strip()
    sinks = _persist_google_credentials(env_updates, settings) if (env_updates or settings) else {}
    return {**result, "saved": any(sinks.values()) if sinks else False, "persisted_to": sinks}


@router.post("/api/connectors/sync-gsc")
@router.post("/connectors/sync-gsc")
async def sync_gsc(payload: Optional[dict] = None):
    """Pull live search impressions, clicks, and queries from Google Search Console."""
    target_id = None
    if isinstance(payload, dict):
        target_id = payload.get("website_id")
    target_id = target_id or await get_default_website_id_async()
    try:
        from services.analytics_service import AnalyticsService
        result = await AnalyticsService.sync_gsc_data(website_id=target_id)
        if isinstance(result, dict) and result.get("success"):
            return {"success": True, "synced": True, "data": result}
        message = (result or {}).get("message") if isinstance(result, dict) else None
        return {
            "success": False,
            "synced": False,
            "message": message or "GSC sync failed. Check credentials in Connectors.",
            "records_synced": (result or {}).get("records_synced", 0) if isinstance(result, dict) else 0,
        }
    except Exception as e:
        logger.warning(f"GSC sync failed: {e}")
        return {"success": False, "synced": False, "message": "GSC sync failed. Please try again later.", "records_synced": 0}


async def _verify_ga4_live(property_id: Optional[str], credentials_json: Optional[str]) -> Dict[str, Any]:
    """Run a live GA4 Data API call with the supplied or stored credentials."""
    import asyncio

    from services.ga4_service import GA4Service
    svc = GA4Service(property_id=property_id, credentials_path=credentials_json)
    if not svc.is_connected():
        return {"connected": False, "status": "not_configured", "sessions_last_7_days": None,
                "message": "GA4 not connected. Set the Property ID and paste service-account JSON in Connectors."}
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    def _call() -> int:
        svc._ensure_initialized()
        response = svc._service.properties().runReport(
            property=f"properties/{svc.property_id}",
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "metrics": [{"name": "sessions"}],
            },
        ).execute()
        metrics = response.get("rows", [{}])[0].get("metricValues", [])
        return int(metrics[0].get("value", 0)) if metrics else 0

    sessions = await asyncio.wait_for(asyncio.to_thread(_call), timeout=20.0)
    return {
        "connected": True,
        "status": "success",
        "sessions_last_7_days": sessions,
        "message": f"Successfully connected to Google Analytics 4 ({sessions} sessions in the last 7 days)",
    }


@router.post("/api/connectors/test-ga4")
@router.post("/connectors/test-ga4")
async def test_ga4(payload: Optional[TestGa4Request] = None):
    """Verify GA4 Data API connection live, then persist credentials durably."""
    prop_id = ((payload.property_id if payload else None) or "").strip() or os.getenv("GA4_PROPERTY_ID", "")
    cred_json = ((payload.credentials_json if payload else None) or "").strip() or os.getenv("GA4_CREDENTIALS_JSON", "")

    if cred_json:
        try:
            json.loads(cred_json)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Service Account JSON format")

    try:
        result = await _verify_ga4_live(prop_id, cred_json or None)
    except Exception as e:
        logger.warning(f"GA4 test failed: {e}")
        return {
            "connected": False,
            "status": "error",
            "sessions_last_7_days": None,
            "message": f"GA4 connection failed: {str(e)[:180]}",
            "saved": False,
        }

    if not result.get("connected"):
        return {**result, "saved": False}

    env_updates: Dict[str, str] = {}
    if prop_id:
        env_updates["GA4_PROPERTY_ID"] = prop_id
    if cred_json:
        env_updates["GA4_CREDENTIALS_JSON"] = cred_json
    settings: Dict[str, Any] = {}
    if prop_id:
        settings["ga4_property_id"] = prop_id
    sinks = _persist_google_credentials(env_updates, settings) if (env_updates or settings) else {}
    return {**result, "saved": any(sinks.values()) if sinks else False, "persisted_to": sinks}


@router.post("/api/connectors/test-ga4-stream")
@router.post("/connectors/test-ga4-stream")
async def test_ga4_stream(payload: Optional[TestGa4Request] = None, website_id: Optional[str] = Query(None)):
    """Live GA4 realtime stream status for the selected website."""
    prop_id = ((payload.property_id if payload else None) or "").strip() or os.getenv("GA4_PROPERTY_ID", "")
    cred_json = ((payload.credentials_json if payload else None) or "").strip() or os.getenv("GA4_CREDENTIALS_JSON", "")
    if not prop_id:
        return {
            "connected": False,
            "stream_status": "not_configured",
            "message": "GA4 property not configured. Connect GA4 in Connectors to enable real-time analytics.",
        }

    try:
        from services.ga4_service import GA4Service
        svc = GA4Service(property_id=prop_id, credentials_path=cred_json or None)
        data = await svc.get_page_traffic(
            start_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
            end_date=datetime.utcnow().strftime("%Y-%m-%d"),
            limit=10,
        )
        if data.get("error"):
            return {
                "connected": False,
                "stream_status": "error",
                "active_visitors": None,
                "message": str(data.get("error"))[:200],
            }
        # `get_page_traffic` reports the total under `total_sessions`; reading the
        # nonexistent `sessions` key always produced 0 active visitors.
        sessions = int(data.get("total_sessions", 0) or 0)
        return {
            "connected": True,
            "stream_status": "live",
            "active_visitors": sessions,
            "top_pages": data.get("top_pages", [])[:5],
        }
    except Exception as exc:
        return {
            "connected": False,
            "stream_status": "error",
            "message": str(exc)[:200],
        }

# ---------------------------------------------------------
# 6. Save Generic & Save All
# ---------------------------------------------------------

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
    elif c_name == "slack":
        env_updates["SLACK_WEBHOOK_URL"] = payload.url or payload.key or ""
    elif c_name == "openai":
        env_updates["OPENAI_API_KEY"] = payload.api_key or payload.key or ""
    elif c_name == "perplexity":
        env_updates["PERPLEXITY_API_KEY"] = payload.api_key or payload.key or ""

    if env_updates:
        write_env_file(custom_keys=env_updates)

    return {
        "success": True,
        "connector": c_name,
        "message": f"{connector_name.title()} credentials saved successfully",
        "updated_keys": list(env_updates.keys()),
    }


@router.post("/api/connectors/save-all")
@router.post("/connectors/save-all")
async def save_all_connectors(payload: SaveAllRequest):
    """Save all integrations at once.

    Persistence is considered real only when the credentials are written to the
    database-backed stores (Supabase row + durable local store) or, failing that,
    to the .env file on disk. Ephemeral os.environ writes alone are not durable,
    so the response reports exactly which sink succeeded instead of a blanket
    "saved" that can hide a lost write.
    """
    env_updates = {}
    if payload.nvidia_api_key:
        env_updates["NVIDIA_API_KEY"] = payload.nvidia_api_key.strip()
    if payload.supabase_url:
        env_updates["SUPABASE_URL"] = payload.supabase_url.strip()
    if payload.supabase_anon_key:
        env_updates["SUPABASE_KEY"] = payload.supabase_anon_key.strip()
    if payload.supabase_service_key:
        env_updates["SUPABASE_SERVICE_ROLE_KEY"] = payload.supabase_service_key.strip()
        env_updates["SUPABASE_SERVICE_KEY"] = payload.supabase_service_key.strip()
    if payload.serper_api_key:
        env_updates["SERPER_API_KEY"] = payload.serper_api_key.strip()
    if payload.wordpress_site_url:
        env_updates["WORDPRESS_SITE_URL"] = payload.wordpress_site_url.strip()
        env_updates["WP_SITE_URL"] = payload.wordpress_site_url.strip()
    # Never persist a placeholder username to the durable .env: it would later be
    # picked up as a default identity and authenticate as the wrong account. The
    # real username is stored with the WP credentials below.
    if payload.wordpress_username and not is_placeholder_wp_username(payload.wordpress_username):
        env_updates["WORDPRESS_USERNAME"] = payload.wordpress_username.strip()
    if payload.gsc_property_url:
        env_updates["GSC_SITE_URL"] = payload.gsc_property_url.strip()
    if payload.gsc_credentials_json:
        env_updates["GSC_SERVICE_ACCOUNT_JSON"] = payload.gsc_credentials_json.strip()
    if payload.ga4_property_id:
        env_updates["GA4_PROPERTY_ID"] = payload.ga4_property_id.strip()
    if payload.ga4_credentials_json:
        env_updates["GA4_CREDENTIALS_JSON"] = payload.ga4_credentials_json.strip()
    if payload.slack_webhook_url:
        env_updates["SLACK_WEBHOOK_URL"] = payload.slack_webhook_url.strip()
    if payload.openai_api_key:
        env_updates["OPENAI_API_KEY"] = payload.openai_api_key.strip()
    if payload.perplexity_api_key:
        env_updates["PERPLEXITY_API_KEY"] = payload.perplexity_api_key.strip()

    persisted_keys: List[str] = []
    env_file_written = False
    if env_updates:
        try:
            write_env_file(custom_keys=env_updates)
            env_file_written = True
            persisted_keys = list(env_updates.keys())
        except Exception as e:
            logger.error(f"Failed to persist connector credentials to .env: {e}")

    # Writing to disk is not enough — promote the creds into the running process
    # so the change takes effect without a restart. Supabase is probed live first
    # so a bad URL/key can never replace a working one in the live process.
    if payload.supabase_url and (payload.supabase_anon_key or payload.supabase_service_key):
        probe_url = payload.supabase_url.strip()
        probe_key = (payload.supabase_service_key or payload.supabase_anon_key or "").strip()
        ok, probe_msg = await _probe_supabase(probe_url, probe_key)
        if ok:
            _apply_env_credentials({
                "SUPABASE_URL": probe_url,
                "SUPABASE_ANON_KEY": (payload.supabase_anon_key or "").strip(),
                "SUPABASE_KEY": (payload.supabase_anon_key or "").strip(),
                "SUPABASE_SERVICE_ROLE_KEY": (payload.supabase_service_key or "").strip(),
                "SUPABASE_SERVICE_KEY": (payload.supabase_service_key or "").strip(),
            })
        else:
            logger.warning(f"[Connectors] Supabase creds saved but not adopted: {probe_msg}")

    # Non-secret settings already land in a durable local store.
    try:
        from services import local_store
        local_store.set_local_connector_settings({
            "gsc_property_url": payload.gsc_property_url,
            "ga4_property_id": payload.ga4_property_id,
            "slack_webhook_url": payload.slack_webhook_url,
            "auto_publish": payload.auto_publish,
            "updated_at": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.debug(f"Local connector settings note: {e}")

    # Save WP credentials if password provided. A failure here (e.g. missing
    # username) must be surfaced, not swallowed into a fake success.
    wp_saved = False
    wp_error: Optional[str] = None
    if payload.wordpress_site_url and payload.wordpress_app_password:
        if not resolve_wp_username(payload.wordpress_username):
            wp_error = "WordPress username missing or placeholder — credentials not stored."
        else:
            try:
                result = await wordpress_save(WordPressSaveRequest(
                    site_url=payload.wordpress_site_url,
                    wp_username=payload.wordpress_username,
                    wp_app_password=payload.wordpress_app_password,
                ))
                wp_saved = bool(result.get("success"))
            except HTTPException as e:
                wp_error = str(e.detail)
            except Exception as e:
                wp_error = str(e)
                logger.warning(f"Could not save WP credentials: {e}")

    # Update autonomous settings if toggled
    if payload.auto_publish is not None:
        try:
            supabase = get_supabase()
            target_id = await get_default_website_id_async()
            await execute_db(supabase.table("autonomous_settings").upsert({
                "website_id": target_id,
                "auto_publish": payload.auto_publish,
                "auto_generate": True,
                "auto_refresh": True,
                "target_articles_per_week": 5,
                "updated_at": datetime.utcnow().isoformat(),
            }))
        except Exception as e:
            logger.warning(f"Could not update autonomous settings: {e}")

    if not env_updates and not wp_saved:
        return {
            "success": True,
            "message": "No new credentials were provided — nothing to save.",
            "updated_keys": [],
            "persisted": False,
            "env_file_written": False,
            "wordpress_saved": False,
        }

    success = env_file_written or wp_saved
    if wp_error:
        message = f"Settings saved, but WordPress credentials were NOT stored: {wp_error}"
    elif success:
        message = "All credentials saved to the durable store."
    else:
        message = "Credentials could not be persisted (write failed). Check backend logs."

    return {
        "success": success,
        "message": message,
        "updated_keys": persisted_keys,
        "persisted": success,
        "env_file_written": env_file_written,
        "wordpress_saved": wp_saved,
        "wordpress_error": wp_error,
    }


# ---------------------------------------------------------
# 7. Overall Connectors Status Endpoint (Booleans & Health)
# ---------------------------------------------------------

@router.get("/api/connectors/status")
@router.get("/connectors/status")
async def get_connectors_status(website_id: Optional[str] = None):
    """Get live connection status of all integrations."""
    target_id = website_id or await get_default_website_id_async()

    # 1. Supabase Status
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_KEY", "")
    )
    supabase_connected = False
    supabase_error: Optional[str] = None
    table_count = 0
    if supabase_url:
        try:
            # supabase-py is synchronous; awaiting it off-loop keeps this polled
            # endpoint from freezing every other request while the health probe
            # is in flight.
            await execute_db(get_supabase().table("websites").select("id").limit(1))
            supabase_connected = True
            table_count = 14
        except Exception as e:
            # A key merely being *present* is not a connection. "dummy" and
            # "example.supabase.co" used to report connected=true, so the UI
            # showed a healthy Supabase while every real write silently failed.
            supabase_error = str(e)[:200]
            logger.warning(f"[Connectors] Supabase health check failed: {supabase_error}")

    # Flag placeholder/never-valid values explicitly (no fabricated success).
    _placeholder_url = supabase_url in ("", "https://example.supabase.co") or "example.supabase.co" in supabase_url
    _placeholder_key = supabase_key.strip().lower() in ("", "dummy", "your-supabase-service-role-key", "mock-key")

    supabase_status = {
        "connected": supabase_connected,
        "is_configured": bool(supabase_url and supabase_key and not _placeholder_url and not _placeholder_key),
        "tables_count": table_count,
        "placeholder": _placeholder_url or _placeholder_key,
    }
    if supabase_error:
        supabase_status["error"] = supabase_error

    # 2. NVIDIA Status
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    nim_available = True
    try:
        from database import is_nim_available
        nim_available = await is_nim_available()
    except Exception:
        nim_available = bool(nvidia_key)

    nvidia_status = {
        "connected": bool(nvidia_key) and nim_available,
        "is_configured": bool(nvidia_key),
        "available": nim_available,
        "model": os.getenv("NIM_LLM_MODEL", "google/gemma-4-31b-it"),
        "models_count": None,
    }

    # 3. Serper Status — a non-empty key is not proof it works. Verify live (with
    # a short cache) so an invalid/out-of-credits key is never shown as connected.
    serper_key = os.environ.get("SERPER_API_KEY", "")
    serper_verified = False
    serper_message: Optional[str] = None
    if serper_key:
        try:
            serper_verified, serper_message = await verify_serper_key(serper_key)
        except Exception as e:
            serper_verified, serper_message = False, str(e)[:200]
    serper_status = {
        "connected": serper_verified,
        "is_configured": bool(serper_key),
        "fallback_active": not serper_verified,
    }
    if serper_message:
        serper_status["message"] = serper_message

    # 5. GSC Status — presence of a key is not a connection; only a live test
    # may claim success. The badge stays honest until GSC is actually verified.
    gsc_key = os.environ.get("GSC_SERVICE_ACCOUNT_JSON") or os.environ.get("GSC_SITE_URL", "")
    gsc_configured = bool(gsc_key)
    gsc_connected = False
    gsc_message: Optional[str] = None
    if gsc_configured:
        async def _gsc_live() -> tuple[bool, str]:
            res = await _verify_gsc_live(os.environ.get("GSC_SERVICE_ACCOUNT_JSON"),
                                         os.environ.get("GSC_SITE_URL"))
            return bool(res.get("connected")), res.get("message", "")
        gsc_connected, gsc_message = await _cached_google_check("gsc", gsc_key, _gsc_live)
    gsc_status = {
        "connected": gsc_connected,
        "is_configured": gsc_configured,
        "status_label": "Connected" if gsc_connected else ("Configured (unverified)" if gsc_configured else "Not Configured"),
    }
    if gsc_message:
        gsc_status["message"] = gsc_message

    # 6. GA4 Status — same rule: an unconfigured property must never read "Ready".
    ga4_key = os.environ.get("GA4_PROPERTY_ID") or os.environ.get("GA4_CREDENTIALS_JSON", "")
    ga4_configured = bool(os.environ.get("GA4_PROPERTY_ID") and os.environ.get("GA4_CREDENTIALS_JSON"))
    ga4_connected = False
    ga4_message: Optional[str] = None
    if ga4_configured:
        async def _ga4_live() -> tuple[bool, str]:
            res = await _verify_ga4_live(os.environ.get("GA4_PROPERTY_ID"),
                                         os.environ.get("GA4_CREDENTIALS_JSON"))
            return bool(res.get("connected")), res.get("message", "")
        ga4_connected, ga4_message = await _cached_google_check("ga4", ga4_key, _ga4_live)
    ga4_status = {
        "connected": ga4_connected,
        "is_configured": ga4_configured,
        "status_label": "Connected" if ga4_connected else ("Configured (unverified)" if ga4_configured else "Not Configured"),
    }
    if ga4_message:
        ga4_status["message"] = ga4_message

    # 7. WordPress Status
    #
    # "connected" must mean a live connection test actually succeeded, not that
    # a password string was saved. Previously saving creds (via PUT websites or
    # the connect form) flipped connected=true with zero verification, so an
    # unreachable/placeholder site showed a green "Connected (Role: Editor)"
    # badge while every real publish failed. We now require a recorded verified
    # flag (set only by a successful test_connection) before reporting connected.
    wp_site = os.environ.get("WORDPRESS_SITE_URL", "")
    wp_user = os.environ.get("WORDPRESS_USER", "") or os.environ.get("WORDPRESS_USERNAME", "")
    wp_has_creds = bool(wp_site and os.environ.get("WORDPRESS_APP_PASSWORD"))
    wp_verified = False
    wp_verified_at: Optional[str] = None
    wp_verified_role: Optional[str] = None
    wp_error: Optional[str] = None

    # Gather the persisted record (Supabase primary, local store fallback).
    record: Dict[str, Any] = {}
    supabase_record: Dict[str, Any] = {}
    loc: Optional[Dict[str, Any]] = None
    if target_id:
        # The verification columns (wp_verified*) are not present on every
        # deployment. Selecting a column that does not exist makes PostgREST
        # reject the WHOLE row with HTTP 400, so the Supabase read returned
        # nothing and WP status silently depended on the local store alone.
        # Try the full projection first, then fall back to the columns that are
        # guaranteed to exist.
        base_cols = "app_password, wordpress_password, cms_url, url, cms_user, wordpress_user, wordpress_url"
        verify_cols = "wp_verified, wp_verified_at, wp_verified_role, wp_last_error"
        for projection in (f"{base_cols}, {verify_cols}", base_cols):
            try:
                supabase_record = (
                    await execute_db(
                        get_supabase().table("websites")
                        .select(projection)
                        .eq("id", target_id)
                        .single()
                    )
                ).data or {}
                record.update(supabase_record)
                break
            except Exception as e:
                logger.debug(f"Website connector status lookup note ({projection}): {e}")
    try:
        from services.local_store import get_local_website, list_local_websites
        loc = get_local_website(target_id) if target_id else None
        # Only fall back to "first local website" when no id was requested. If a
        # specific id was requested but is absent, borrowing another site's row
        # would report that site's verified flag as this site's status.
        if not loc and not target_id:
            all_loc = list_local_websites()
            loc = all_loc[0] if all_loc else None
        if loc:
            for k, v in loc.items():
                # Do not let a null from Supabase mask a real value in the local
                # store: the verification write goes to both sinks, and Supabase
                # can silently reject it (RLS) while the local write succeeds.
                # setdefault alone left record[k] = None, and bool(None) is False
                # — so a verified site intermittently reported as disconnected.
                if record.get(k) in (None, "", []) and v not in (None, "", []):
                    record[k] = v
                elif k not in record:
                    record[k] = v
            if loc.get("app_password") or loc.get("wordpress_password") or loc.get("wordpress_password_encrypted"):
                record.setdefault("app_password", loc.get("app_password") or loc.get("wordpress_password_encrypted"))
    except Exception:
        pass

    wp_row_site = record.get("wordpress_url") or record.get("cms_url") or record.get("url") or ""
    wp_row_user = record.get("wordpress_user") or record.get("cms_user") or ""
    wp_has_saved_creds = bool(
        (record.get("app_password") or record.get("wordpress_password") or record.get("wordpress_password_encrypted"))
        and wp_row_site
    )

    # The verification write goes to both sinks, but Supabase can silently reject
    # it (RLS) while the local write succeeds — or vice versa. Resolve the true
    # state by timestamp rather than letting one sink's null (or stale value)
    # mask the other's. This is what made a verified site flip back to
    # "not connected" intermittently.
    def _verified_state(src: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "wp_verified" not in src:
            return None
        return {
            "verified": bool(src.get("wp_verified")),
            "at": src.get("wp_verified_at"),
            "role": src.get("wp_verified_role"),
            "error": src.get("wp_last_error"),
        }

    candidates = [c for c in (_verified_state(supabase_record), _verified_state(loc or {})) if c]

    def _ts(value: Optional[str]) -> float:
        if not value:
            return float("-inf")
        try:
            from datetime import datetime as _dt
            return _dt.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except Exception:
            return float("-inf")

    if candidates:
        chosen = max(candidates, key=lambda c: _ts(c.get("at")))
        wp_verified = chosen["verified"]
        wp_verified_at = chosen["at"]
        wp_verified_role = chosen["role"]
        if chosen.get("error"):
            wp_error = chosen["error"]

    site_for_status = wp_row_site or wp_site
    configured = wp_has_saved_creds or wp_has_creds
    # Verified is the durable truth recorded by a successful live test; it is the
    # only thing that may turn the badge green.
    connected = bool(wp_verified)

    wp_status = {
        "connected": connected,
        "verified": wp_verified,
        "is_configured": configured,
        # Never invent a role: an unrecorded role is reported as null so the UI
        # shows the real state instead of a hardcoded "Editor".
        "role": wp_verified_role or None,
        "site_url": site_for_status,
        "wp_user": wp_row_user or wp_user or None,
        "verified_at": wp_verified_at,
        "status_label": "Connected" if connected else ("Credentials saved — not verified" if configured else "Not Configured"),
    }
    if wp_error and not connected:
        wp_status["error"] = wp_error

    # 8. Slack
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    slack_status = {
        "connected": bool(slack_webhook),
        "is_configured": bool(slack_webhook),
    }

    core_connectors = {
        "nvidia": nvidia_status["connected"],
        "supabase": supabase_status["connected"],
        "wordpress": wp_status["connected"],
        "serper": serper_status["connected"],
    }
    connected_count = sum(1 for is_conn in core_connectors.values() if is_conn)
    total_count = len(core_connectors)
    health_percentage = sum(25 for is_conn in core_connectors.values() if is_conn)

    return {
        "success": True,
        "connected_count": connected_count,
        "total_count": total_count,
        "health_score": health_percentage,
        "supabase": supabase_status,
        "nvidia": nvidia_status,
        "serper": serper_status,
        "gsc": gsc_status,
        "ga4": ga4_status,
        "wordpress": wp_status,
        "slack": slack_status,
        "website_id": target_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


# --- P2 FIX STEP3 — /api/connectors/health per spec ---
@router.get("/api/connectors/health")
@router.get("/connectors/health")
async def get_connector_health(request: Request, website_id: Optional[str] = None):
    """Health check for writer auto-resolve — returns nvidia/supabase/wordpress/serper + missing + domain."""
    # resolve website_id from query, header, or default
    wid = website_id or request.query_params.get("website_id") or request.headers.get("X-Website-Id") or request.headers.get("x-website-id")
    if not wid or wid in ("default", "all", "", "null", "undefined"):
        try:
            wid = await get_default_website_id_async()
        except Exception:
            wid = None
    if not wid:
        try:
            supabase = get_supabase()
            res = await execute_db(supabase.table("websites").select("id").limit(1))
            if res.data:
                wid = res.data[0]["id"]
        except Exception:
            pass
        if not wid:
            try:
                from services.local_store import list_local_websites
                local = list_local_websites()
                if local:
                    wid = local[0].get("id")
            except Exception:
                pass
    health: Dict[str, Any] = {}
    missing: List[str] = []
    # NVIDIA — fast env check (avoid slow NIM generate in health for writer 2s requirement)
    try:
        nkey = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY") or ""
        # quick availability flag from database module without network
        try:
            from database import is_nim_available as _is_avail
            # don't await network, just env
            health["nvidia"] = "connected" if nkey else "error"
        except Exception:
            health["nvidia"] = "connected" if nkey else "error"
        if health["nvidia"] != "connected":
            missing.append("NVIDIA NIM")
    except Exception:
        nkey = os.getenv("NVIDIA_API_KEY") or ""
        health["nvidia"] = "connected" if nkey else "error"
        if health["nvidia"] != "connected":
            missing.append("NVIDIA NIM")
    # Supabase
    try:
        await execute_db(get_supabase().table("websites").select("id").limit(1))
        health["supabase"] = "connected"
    except Exception:
        health["supabase"] = "error"
        missing.append("Supabase")
    # WordPress for specific website
    try:
        supabase = get_supabase()
        site = None
        if wid:
            try:
                res = await execute_db(supabase.table("websites").select("cms_url, url, wordpress_url, cms_user, wordpress_user, app_password, wordpress_password").eq("id", wid).single())
                site = res.data if res.data else None
            except Exception:
                site = None
            if not site:
                try:
                    from services.local_store import get_local_website as _get_local
                    site = _get_local(wid) or {}
                except Exception:
                    site = {}
        wp_url = (site or {}).get("wordpress_url") or (site or {}).get("cms_url") or (site or {}).get("url") or (site or {}).get("wp_url") or ""
        wp_user = (site or {}).get("wordpress_user") or (site or {}).get("cms_user") or (site or {}).get("wp_username") or ""
        wp_pass_enc = (site or {}).get("app_password") or (site or {}).get("wordpress_password") or (site or {}).get("wp_app_password") or ""
        if wp_url:
            # fast check — if url and user/pass exist, consider connected (avoid slow httpx for writer 2s requirement)
            # decrypt check
            wp_pass = wp_pass_enc
            try:
                if wp_pass_enc and wp_pass_enc.startswith("gAAAA"):
                    dec = decrypt_secret(wp_pass_enc)
                    if dec:
                        wp_pass = dec
            except Exception:
                pass
            wp_pass_clean = wp_pass.replace(" ", "") if wp_pass else ""
            if wp_url and wp_user and wp_pass_clean:
                health["wordpress"] = "connected"
                try:
                    from urllib.parse import urlparse
                    health["domain"] = urlparse(wp_url).netloc or wp_url
                except Exception:
                    health["domain"] = wp_url
                if not health.get("domain") and site.get("domain"):
                    health["domain"] = site.get("domain")
            elif wp_url:
                # url exists but no credentials — treat as not_configured but don't block writer
                health["wordpress"] = "not_configured"
                # don't add to missing for writer readiness — spec says wordpress missing is okay? but we keep for display
                # only add to missing if you want strict, but writer Ready requires only nvidia+supabase per initWriterPage
                # so we don't block
            else:
                health["wordpress"] = "not_configured"
                missing.append("WordPress")
        else:
            health["wordpress"] = "not_configured"
            # don't block writer ready — wordpress is optional for writing, only for publishing
        if not health.get("domain") and wid:
            try:
                # fallback domain from websites row
                if site and site.get("domain"):
                    health["domain"] = site.get("domain")
                else:
                    # local store
                    from services.local_store import get_local_website as _gl
                    ls = _gl(wid) or {}
                    if ls.get("domain"):
                        health["domain"] = ls.get("domain")
            except Exception:
                pass
    except Exception:
        health["wordpress"] = "error"
        missing.append("WordPress")
    # Serper — same honesty rule: presence alone is not "connected".
    serper_key = os.getenv("SERPER_API_KEY", "")
    if serper_key:
        serper_ok, _serper_msg = await verify_serper_key(serper_key)
        health["serper"] = "connected" if serper_ok else "unverified"
    else:
        health["serper"] = "not_set"
    if not serper_key:
        missing.append("Serper")
    health["missing"] = missing
    health["overall"] = "ready" if len(missing) == 0 else "partial"
    if wid:
        health["website_id"] = wid
    # also include domain if we resolved
    if "domain" not in health and wid:
        try:
            supabase = get_supabase()
            res = await execute_db(supabase.table("websites").select("domain").eq("id", wid).single())
            if res.data and res.data.get("domain"):
                health["domain"] = res.data.get("domain")
        except Exception:
            pass
    return health
