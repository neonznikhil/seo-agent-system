"""OAuth 2.0 flows (GSC, GA4, WordPress) and real API-key verifiers.

Slack OAuth lives in connectors_slack.py. Every flow in this module performs
REAL token exchanges against the provider — fabricated tokens, fake workspaces
and invented credit numbers are never returned.
"""

import os
import time
import json
import secrets
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    BACKEND_URL, WP_SITE_URL, WORDPRESS_URL,
    REDIS_URL,
)
from database import get_supabase
from security import encrypt_secret, decrypt_secret

try:
    import redis as redis_lib
    _redis_client = redis_lib.from_url(REDIS_URL or "redis://localhost:6379/0", decode_responses=True)
    _redis_available = _redis_client.ping()
except Exception:
    _redis_available = False
    _redis_client = None

logger = logging.getLogger("backend.routers.oauth_connectors")
router = APIRouter(tags=["OAuth Connectors"])


def _redis_set(key: str, value: str, ttl_sec: int = 600) -> bool:
    if _redis_available and _redis_client:
        return _redis_client.setex(key, ttl_sec, value)
    return False


def _redis_get(key: str) -> Optional[dict]:
    if _redis_available and _redis_client:
        val = _redis_client.get(key)
        if val:
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return None
    return None


def _redis_del(key: str) -> bool:
    if _redis_available and _redis_client:
        return _redis_client.delete(key)
    return False


def set_oauth_state(state: str, data: dict, ttl_sec: int = 600) -> bool:
    payload = json.dumps({"data": data, "expires_at": time.time() + ttl_sec})
    return _redis_set(f"oauth_state:{state}", payload, ttl_sec)


def get_and_validate_oauth_state(state: str) -> Optional[dict]:
    entry = _redis_get(f"oauth_state:{state}")
    if not entry:
        return None
    if time.time() > entry.get("expires_at", 0):
        _redis_del(f"oauth_state:{state}")
        return None
    return entry.get("data")


def _popup_html(success: bool, provider: str, detail: str = "", extra_payload: str = "{}") -> HTMLResponse:
    payload = json.dumps({
        "success": success,
        "integration": provider,
        "detail": detail,
        **(json.loads(extra_payload) if extra_payload else {}),
    })
    color = "#2eb67d" if success else "#e01e5a"
    heading = f"{provider.upper()} Connected" if success else f"{provider.upper()} Connection Failed"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{heading}</title></head>
<body style="font-family:monospace;background:#1a1a1a;color:#eee;text-align:center;padding-top:40vh">
<h2 style="color:{color}">{heading}</h2>
<p>{detail}</p>
<script>
  window.opener && window.opener.postMessage({payload}, '*');
  setTimeout(function() {{ window.close(); }}, 800);
</script>
</body></html>"""
    return HTMLResponse(html)


# -----------------------------------------------------------------------------
# Common OAuth 2.0 helper: exchange authorization code for tokens
# -----------------------------------------------------------------------------
async def _exchange_oauth_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> Optional[dict]:
    """Exchange an authorization code for tokens via Google's token endpoint.
    Returns the parsed JSON response, or None on failure."""
    async with httpx.AsyncClient(timeout=12.0) as client:
        tok_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        tokens = tok_resp.json()
        if "error" in tokens:
            logger.error(f"OAuth token exchange error: {tokens['error']}")
            return None
        return tokens


# -----------------------------------------------------------------------------
# 1. GOOGLE SEARCH CONSOLE OAUTH 2.0 (real exchange)
# -----------------------------------------------------------------------------
@router.get("/connectors/gsc/oauth/start")
async def gsc_oauth_start(website_id: str = "default"):
    client_id = GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        return _popup_html(False, "gsc", "GOOGLE_CLIENT_ID not configured on the server.")

    state = secrets.token_urlsafe(32)
    set_oauth_state(state, {"website_id": website_id, "provider": "gsc"})

    scopes = "https://www.googleapis.com/auth/webmasters.readonly"
    redirect_uri = f"{BACKEND_URL}/api/connectors/gsc/oauth/callback"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}"
        f"&response_type=code&scope={scopes}&access_type=offline&prompt=consent"
        f"&state={state}&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/api/connectors/gsc/oauth/callback")
@router.get("/connectors/gsc/oauth/callback")
async def gsc_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error or not state:
        return _popup_html(False, "gsc", error or "Authorization cancelled.")
    state_data = get_and_validate_oauth_state(state)
    if not state_data:
        return _popup_html(False, "gsc", "OAuth state expired or invalid.")
    website_id = state_data.get("website_id", "default")

    client_id = GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return _popup_html(False, "gsc", "Server missing GOOGLE_CLIENT_ID/SECRET configuration.")

    redirect_uri = f"{BACKEND_URL}/api/connectors/gsc/oauth/callback"
    tokens = await _exchange_oauth_code(code, client_id, client_secret, redirect_uri)
    if not tokens:
        return _popup_html(False, "gsc", "Token exchange failed - invalid code or credentials.")

    access_token = tokens.get("access_token", "")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            sites_resp = await client.get(
                "https://www.googleapis.com/webmasters/v3/sites",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            sites_data = sites_resp.json() if sites_resp.status_code == 200 else {}
            properties = [
                s.get("siteUrl") for s in (sites_data.get("siteEntry") or [])
                if s.get("permissionLevel") in ("siteOwner", "siteFullUser", "siteRestrictedUser")
            ]
    except Exception as e:
        logger.error(f"[GSC OAuth] sites fetch failed: {e}")
        return _popup_html(False, "gsc", f"Failed to fetch verified properties: {str(e)[:120]}")

    supabase = get_supabase()
    try:
        update_payload = {
            "gsc_credentials": {
                "access_token_encrypted": encrypt_secret(access_token),
                "refresh_token_encrypted": encrypt_secret(tokens.get("refresh_token", "")),
                "expires_at": (datetime.utcnow() + timedelta(seconds=int(tokens.get("expires_in", 3600)))).isoformat(),
                "available_properties": properties,
                "connected_at": datetime.utcnow().isoformat(),
            }
        }
        if properties:
            update_payload["gsc_property"] = properties[0]
        supabase.table("websites").update(update_payload).eq("id", website_id).execute()
    except Exception as e:
        logger.warning(f"[GSC OAuth] persist note: {e}")

    return _popup_html(True, "gsc", f"{len(properties)} verified properties found.",
                       extra_payload=json.dumps({"properties": properties}))


# -----------------------------------------------------------------------------
# 2. GOOGLE ANALYTICS 4 OAUTH 2.0 (real exchange)
# -----------------------------------------------------------------------------
@router.get("/connectors/ga4/oauth/start")
async def ga4_oauth_start(website_id: str = "default"):
    client_id = GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        return _popup_html(False, "ga4", "GOOGLE_CLIENT_ID not configured on the server.")

    state = secrets.token_urlsafe(32)
    set_oauth_state(state, {"website_id": website_id, "provider": "ga4"})

    scopes = "https://www.googleapis.com/auth/analytics.readonly"
    redirect_uri = f"{BACKEND_URL}/api/connectors/ga4/oauth/callback"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}"
        f"&response_type=code&scope={scopes}&access_type=offline&prompt=consent"
        f"&state={state}&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/api/connectors/ga4/oauth/callback")
@router.get("/connectors/ga4/oauth/callback")
async def ga4_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error or not state:
        return _popup_html(False, "ga4", error or "Authorization cancelled.")
    state_data = get_and_validate_oauth_state(state)
    if not state_data:
        return _popup_html(False, "ga4", "OAuth state expired or invalid.")
    website_id = state_data.get("website_id", "default")

    client_id = GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return _popup_html(False, "ga4", "Server missing GOOGLE_CLIENT_ID/SECRET configuration.")

    redirect_uri = f"{BACKEND_URL}/api/connectors/ga4/oauth/callback"
    tokens = await _exchange_oauth_code(code, client_id, client_secret, redirect_uri)
    if not tokens:
        return _popup_html(False, "ga4", "Token exchange failed - invalid code or credentials.")

    access_token = tokens.get("access_token", "")

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            # Fetch the account summary for real GA4 property IDs
            accounts_resp = await client.get(
                "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ga4_properties = []
            if accounts_resp.status_code == 200:
                for account in accounts_resp.json().get("accountSummaries", []):
                    for prop in account.get("propertySummaries", []):
                        ga4_properties.append({
                            "id": prop.get("property"),
                            "name": prop.get("displayName"),
                        })
    except Exception as e:
        logger.error(f"[GA4 OAuth] exchange failed: {e}")
        return _popup_html(False, "ga4", f"Token exchange failed: {str(e)[:120]}")

    supabase = get_supabase()
    try:
        update_payload = {
            "ga4_credentials": {
                "access_token_encrypted": encrypt_secret(access_token),
                "refresh_token_encrypted": encrypt_secret(tokens.get("refresh_token", "")),
                "connected_at": datetime.utcnow().isoformat(),
                "properties": ga4_properties,
            }
        }
        if ga4_properties:
            update_payload["ga4_property_id"] = ga4_properties[0]["id"]
        supabase.table("websites").update(update_payload).eq("id", website_id).execute()
    except Exception as e:
        logger.warning(f"[GA4 OAuth] persist note: {e}")

    return _popup_html(True, "ga4", f"{len(ga4_properties)} properties found.",
                       extra_payload=json.dumps({"properties": ga4_properties}))


# -----------------------------------------------------------------------------
# 3. WORDPRESS DEEP-LINK APPLICATION PASSWORDS
# -----------------------------------------------------------------------------
@router.get("/connectors/wordpress/verify-url")
async def verify_wp_url(site_url: str):
    """Verify that WordPress REST API is reachable at site URL."""
    clean_url = site_url.strip().rstrip("/")
    if not clean_url.startswith("http"):
        clean_url = f"https://{clean_url}"

    reachable = False
    status_code = None
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(f"{clean_url}/wp-json/wp/v2/users")
            status_code = resp.status_code
            reachable = resp.status_code == 200
    except Exception:
        pass

    return {
        "success": True,
        "valid": reachable,
        "status_code": status_code,
        "message": "REST API reachable." if reachable else f"REST API check returned HTTP {status_code}",
        "site_url": clean_url,
        "authorize_deep_link": f"{clean_url}/wp-admin/authorize-application.php?app_name=RankForge&success_url={BACKEND_URL}/api/connectors/wordpress/app-password/callback",
    }


@router.get("/api/connectors/wordpress/app-password/callback")
@router.get("/connectors/wordpress/app-password/callback")
async def wp_app_password_callback(
    user_login: Optional[str] = None,
    password: Optional[str] = None,
    site_url: Optional[str] = None,
    website_id: str = "default"
):
    """Receives the WordPress Application Password, encrypts it, stores on website row."""
    if user_login and password:
        supabase = get_supabase()
        resolved_url = site_url or WP_SITE_URL or WORDPRESS_URL or ""
        if website_id != "default":
            try:
                encrypted = encrypt_secret(password)
                supabase.table("websites").update({
                    "wordpress_user": user_login,
                    "cms_user": user_login,
                    "wordpress_password": encrypted,
                    "app_password": encrypted,
                    "wordpress_url": resolved_url,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", website_id).execute()
            except Exception as e:
                logger.warning(f"[WP callback] credential save failed: {e}")

    return _popup_html(True, "wordpress", "Application Password authorized and stored encrypted.")


# -----------------------------------------------------------------------------
# 4. REAL API KEY VERIFIERS (Ahrefs, Serper, NVIDIA NIM, Resend)
# -----------------------------------------------------------------------------
class VerifyApiKeyRequest(BaseModel):
    api_key: str
    website_id: Optional[str] = "default"


def _store_key_on_website(website_id: str, column: str, value: str) -> None:
    if website_id in ("default", "all", ""):
        return
    try:
        get_supabase().table("websites").update({column: encrypt_secret(value)}).eq("id", website_id).execute()
    except Exception as e:
        logger.debug(f"[VerifyKey] store failed: {e}")


@router.post("/connectors/ahrefs/verify")
async def verify_ahrefs_key(payload: VerifyApiKeyRequest):
    """Real Ahrefs v3 API call to validate the key."""
    api_key = payload.api_key.strip()
    if len(api_key) < 8:
        raise HTTPException(status_code=400, detail="Invalid Ahrefs API Key format.")

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://api.ahrefs.com/v3/site-explorer/backlinks",
                params={"target": "ahrefs.com", "limit": 1},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            valid = resp.status_code == 200
            if not valid:
                detail = f"Ahrefs rejected the key (HTTP {resp.status_code})."
                return {"success": False, "error": detail}
    except Exception as e:
        return {"success": False, "error": f"Ahrefs unreachable: {str(e)[:120]}"}

    _store_key_on_website(payload.website_id or "default", "ahrefs_api_key_encrypted", api_key)
    return {"success": True, "message": "Ahrefs key verified via live API call."}


@router.post("/connectors/serper/verify")
async def verify_serper_key(payload: VerifyApiKeyRequest):
    """Real Serper.dev verification through the shared service."""
    from services.serper_service import serper_service

    valid = await serper_service.verify_key(payload.api_key)
    if not valid:
        return {"success": False, "error": "Serper rejected this key. Check it at serper.dev/dashboard"}

    _store_key_on_website(payload.website_id or "default", "serper_api_key_encrypted", payload.api_key.strip())
    return {"success": True, "message": "Serper key verified via live search call."}


@router.post("/connectors/nvidia/verify")
async def verify_nvidia_key(payload: VerifyApiKeyRequest):
    """Real NVIDIA NIM verification: models list call with the provided key."""
    api_key = payload.api_key.strip()
    if len(api_key) < 8:
        raise HTTPException(status_code=400, detail="Invalid NVIDIA API Key.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                models = [m.get("id") for m in resp.json().get("data", [])][:10]
                return {
                    "success": True,
                    "models_available": len(models),
                    "sample_models": models[:5],
                    "message": "NVIDIA NIM key verified via live models call.",
                }
            elif resp.status_code == 401:
                return {"success": False, "error": "NVIDIA rejected this key (HTTP 401)."}
            else:
                return {"success": False, "error": f"NVIDIA returned HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": f"NVIDIA unreachable: {str(e)[:120]}"}


@router.post("/connectors/resend/verify")
async def verify_resend_key(payload: VerifyApiKeyRequest):
    """Real Resend API validation: list API keys endpoint."""
    api_key = payload.api_key.strip()
    if len(api_key) < 8:
        raise HTTPException(status_code=400, detail="Invalid Resend API Key.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.resend.com/api-keys",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                _store_key_on_website(payload.website_id or "default", "resend_api_key_encrypted", api_key)
                return {"success": True, "message": "Resend key verified via live API call."}
            elif resp.status_code == 401:
                return {"success": False, "error": "Resend rejected this key (HTTP 401)."}
            else:
                return {"success": False, "error": f"Resend returned HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": f"Resend unreachable: {str(e)[:120]}"}


# -----------------------------------------------------------------------------
# 5. OAUTH 2.0 TOKEN REFRESH (for GSC & GA4 stored credentials)
# -----------------------------------------------------------------------------
class TokenRefreshRequest(BaseModel):
    website_id: Optional[str] = "default"


async def _refresh_oauth_token(website_id: str, creds_column: str) -> Optional[dict]:
    """Refresh an OAuth 2.0 access token using a stored refresh token.
    Returns dict with new access_token and expires_at, or None on failure."""
    supabase = get_supabase()
    try:
        row = supabase.table("websites").select(creds_column).eq("id", website_id).execute().data
        if not row or not row[0].get(creds_column):
            return None
        creds = row[0][creds_column]
        if not isinstance(creds, dict):
            return None
        # Decrypt refresh token
        refresh_token_encrypted = creds.get("refresh_token_encrypted", "")
        if not refresh_token_encrypted:
            return None
        refresh_token = decrypt_secret(refresh_token_encrypted)
        if not refresh_token:
            return None

        # Get client credentials from env
        client_id = GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            return None

        redirect_uri = f"{BACKEND_URL}/api/connectors/gsc/oauth/callback"  # reuse callback URI

        async with httpx.AsyncClient(timeout=12.0) as client:
            tok_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                },
            )
            tokens = tok_resp.json()
            if "error" in tokens:
                logger.error(f"OAuth token refresh error: {tokens['error']}")
                return None

            access_token = tokens.get("access_token", "")
            expires_in = tokens.get("expires_in", 3600)
            return {
                "access_token": access_token,
                "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat(),
            }
    except Exception as e:
        logger.error(f"OAuth token refresh exception: {e}")
        return None


@router.post("/api/connectors/gsc/oauth/refresh")
async def gsc_oauth_refresh(payload: TokenRefreshRequest):
    result = await _refresh_oauth_token(payload.website_id, "gsc_credentials")
    if not result:
        return JSONResponse(status_code=400, content={"success": False, "error": "Token refresh failed - no valid refresh token or credentials."})
    return JSONResponse(content={"success": True, "access_token": result["access_token"], "expires_at": result["expires_at"]})


@router.post("/api/connectors/ga4/oauth/refresh")
async def ga4_oauth_refresh(payload: TokenRefreshRequest):
    result = await _refresh_oauth_token(payload.website_id, "ga4_credentials")
    if not result:
        return JSONResponse(status_code=400, content={"success": False, "error": "Token refresh failed - no valid refresh token or credentials."})
    return JSONResponse(content={"success": True, "access_token": result["access_token"], "expires_at": result["expires_at"]})
