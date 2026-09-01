"""Slack OAuth 2.0 (popup flow) + per-website credential storage.

Flow:
1. GET /api/connectors/slack/oauth/start?website_id=... -> redirect to Slack
   authorize URL with a cryptographically random state stored in Redis (10 min TTL,
   in-memory fallback when Redis is absent).
2. User authorizes; Slack redirects to /api/connectors/slack/oauth/callback.
3. State is verified, code exchanged via oauth.v2.access, token Fernet-encrypted
   and stored on websites.slack_credentials. The 4 channels are auto-created and a
   welcome message posts to #rankforge-daily.
4. An HTML response closes the popup via postMessage + window.close().
"""

import logging
import os
import secrets
import time
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from config import SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, BACKEND_URL
from database import get_supabase
from security import encrypt_secret

logger = logging.getLogger("backend.routers.connectors_slack")
router = APIRouter(tags=["slack-oauth"])

SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_SCOPES = "chat:write,chat:write.public,channels:manage,channels:read,incoming-webhook"

# In-memory fallback for OAuth states when Redis isn't reachable.
_oauth_states_memory: dict = {}

STATE_TTL_SECONDS = 600


def _redis_client():
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        return None
    try:
        import redis
        return redis.from_url(redis_url, socket_connect_timeout=2)
    except Exception:
        return None


def _store_state(token: str, website_id: str) -> None:
    r = _redis_client()
    value = f"{website_id}|{int(time.time())}"
    if r:
        try:
            r.setex(f"slack_oauth_state:{token}", STATE_TTL_SECONDS, value)
            return
        except Exception as e:
            logger.warning(f"Redis state store failed ({e}); using memory")
    _oauth_states_memory[token] = {"value": value, "expires": time.time() + STATE_TTL_SECONDS}


def _consume_state(token: str) -> Optional[str]:
    """Return website_id if the state is valid, else None (one-time use)."""
    r = _redis_client()
    key = f"slack_oauth_state:{token}"
    if r:
        try:
            raw = r.get(key)
            if not raw:
                return None
            r.delete(key)
            return raw.decode().split("|")[0]
        except Exception:
            pass
    entry = _oauth_states_memory.pop(token, None)
    if entry and entry["expires"] > time.time():
        return entry["value"].split("|")[0]
    return None


def _popup_html(success: bool, workspace: str = "", error: str = "") -> HTMLResponse:
    payload = (
        '{"success": true, "integration": "slack", "workspace": '
        + ('"' + workspace.replace('"', "'") + '"')
        + "}" if success else
        '{"success": false, "integration": "slack", "error": '
        + ('"' + error.replace('"', "'") + '"')
        + "}"
    )
    color = "#2eb67d" if success else "#e01e5a"
    heading = "Slack Connected" if success else "Slack Connection Failed"
    detail = workspace or error or ""
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{heading}</title>
<style>
body {{ font-family: 'IBM Plex Mono', monospace; background:#1a1a1a; color:#eee;
       display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
.card {{ border:1px solid {color}; padding:32px 40px; text-align:center; }}
h1 {{ font-size:16px; letter-spacing:.08em; text-transform:uppercase; }}
p {{ font-size:11px; color:#aaa; }}
</style></head>
<body>
<div class="card">
  <h1 style="color:{color}">{heading}</h1>
  <p>{detail}</p>
  <p>You can close this window.</p>
</div>
<script>
  window.opener && window.opener.postMessage({payload}, '*');
  setTimeout(function() {{ window.close(); }}, 800);
</script>
</body>
</html>"""
    return HTMLResponse(html)


@router.get("/api/connectors/slack/oauth/start")
@router.get("/connectors/slack/oauth/start")
async def slack_oauth_start(website_id: Optional[str] = None):
    """Begin the OAuth flow: generate state, persist it, redirect to Slack."""
    client_id = SLACK_CLIENT_ID or os.getenv("SLACK_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="SLACK_CLIENT_ID is not configured. Set SLACK_CLIENT_ID and "
                   "SLACK_CLIENT_SECRET in the backend environment first.",
        )

    state_token = secrets.token_urlsafe(32)
    wid = website_id or "default"
    _store_state(state_token, wid)

    redirect_uri = f"{BACKEND_URL}/api/connectors/slack/oauth/callback"
    url = (
        f"{SLACK_AUTHORIZE_URL}?client_id={client_id}"
        f"&scope={SLACK_SCOPES}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state_token}"
    )
    return RedirectResponse(url, status_code=302)


@router.get("/api/connectors/slack/oauth/callback")
@router.get("/connectors/slack/oauth/callback")
async def slack_oauth_callback(code: Optional[str] = None, state: Optional[str] = None):
    """Exchange the OAuth code, encrypt the bot token, store credentials."""
    if not state:
        return _popup_html(False, error="OAuth state missing.")
    website_id = _consume_state(state)
    if not website_id:
        return _popup_html(False, error="OAuth state expired or invalid.")

    if not code:
        return _popup_html(False, error="Slack did not return an authorization code.")

    client_id = SLACK_CLIENT_ID or os.getenv("SLACK_CLIENT_ID", "")
    client_secret = SLACK_CLIENT_SECRET or os.getenv("SLACK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return _popup_html(False, error="Server missing SLACK_CLIENT_ID/SECRET configuration.")

    redirect_uri = f"{BACKEND_URL}/api/connectors/slack/oauth/callback"

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                SLACK_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            data = resp.json()
    except Exception as e:
        logger.error(f"[SlackOAuth] Token exchange failed: {e}")
        return _popup_html(False, error=f"Token exchange failed: {str(e)[:120]}")

    if not data.get("ok"):
        error = data.get("error") or "unknown_error"
        logger.error(f"[SlackOAuth] oauth.v2.access error: {error}")
        return _popup_html(False, error=f"Slack rejected the authorization: {error}")

    access_token = data.get("access_token") or ""
    team = data.get("team") or {}
    bot_user_id = data.get("bot_user_id") or ""
    webhook = data.get("incoming_webhook") or {}
    workspace_name = team.get("name") or "your workspace"

    if not access_token:
        return _popup_html(False, error="Slack returned no access token.")

    encrypted_token = encrypt_secret(access_token)

    credentials = {
        "workspace_name": workspace_name,
        "workspace_id": team.get("id"),
        "bot_user_id": bot_user_id,
        "token_encrypted": encrypted_token,
        "connected_at": datetime.utcnow().isoformat(),
        "webhook_url": webhook.get("url"),
    }

    supabase = get_supabase()
    try:
        if website_id != "default":
            supabase.table("websites").update({
                "slack_credentials": credentials,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", website_id).execute()
        else:
            # Attach to the single active website
            sites = supabase.table("websites").select("id").order("created_at").limit(1).execute().data or []
            if sites:
                supabase.table("websites").update({
                    "slack_credentials": credentials,
                }).eq("id", sites[0]["id"]).execute()
                website_id = sites[0]["id"]
    except Exception as e:
        # Raw token never logged — only metadata
        logger.error(f"[SlackOAuth] Failed to store credentials: {e}")
        return _popup_html(False, error="Connected to Slack but failed to persist credentials.")

    # Auto-create the 4 channels using the fresh bot token
    try:
        from ..services.slack_app_service import slack_app_service
        result = await slack_app_service.initialize_channels(website_id)
        logger.info(f"[SlackOAuth] Channels initialized: {result}")
    except Exception as e:
        logger.warning(f"[SlackOAuth] Channel creation note: {e}")

    # Welcome message to #rankforge-daily
    try:
        from ..services.slack_app_service import slack_app_service, SLACK_CHANNELS
        blocks = [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (f":wave: RankForge is now connected to *{workspace_name}*.\n"
                         "Autonomous daily briefs, backlink discoveries, weekly intelligence and "
                         "crisis alerts will be posted automatically.")
            }
        }]
        await slack_app_service.post_block_message(
            SLACK_CHANNELS["daily"], blocks,
            f"RankForge connected to {workspace_name}", "oauth_welcome", website_id,
        )
    except Exception as e:
        logger.warning(f"[SlackOAuth] Welcome message note: {e}")

    return _popup_html(True, workspace=workspace_name)


@router.post("/api/connectors/slack/disconnect")
@router.post("/connectors/slack/disconnect")
async def slack_disconnect(payload: dict = None):
    payload = payload or {}
    website_id = payload.get("website_id")
    if not website_id or website_id == "default":
        raise HTTPException(status_code=400, detail="website_id required")

    try:
        get_supabase().table("websites").update({
            "slack_credentials": None,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", website_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "message": "Slack disconnected"}
