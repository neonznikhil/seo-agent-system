import logging
import json
import os
import secrets
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import httpx
import redis
from cryptography.fernet import Fernet, InvalidToken

from backend.database import get_supabase
from backend.config import (
    WP_OAUTH_CLIENT_ID,
    WP_OAUTH_CLIENT_SECRET,
    WP_OAUTH_AUTHORIZE_URL,
    WP_OAUTH_TOKEN_URL,
    REDIRECT_URI,
    TOKEN_ENCRYPTION_KEY,
    REDIS_URL,
    FRONTEND_URL,
)

logger = logging.getLogger("backend.services.wordpress_oauth_service")

_fernet = Fernet(TOKEN_ENCRYPTION_KEY) if TOKEN_ENCRYPTION_KEY else None


def _get_fernet() -> Fernet:
    if _fernet is None:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY not configured")
    return _fernet


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise RuntimeError("Failed to decrypt token - key mismatch or corrupted data")


def generate_pkce() -> tuple[str, str]:
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    return code_verifier, code_challenge


def _get_redis():
    return redis.from_url(REDIS_URL)


def _state_key(state: str) -> str:
    return f"wp_oauth:state:{state}"


def _validate_wp_url(wp_site_url: str) -> None:
    if not wp_site_url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid WordPress site URL: {wp_site_url}")


async def get_authorize_url(website_id: str, user_id: str, wp_site_url: str, client_id: str) -> Dict[str, str]:
    _validate_wp_url(wp_site_url)

    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(32)

    state_data = {
        "website_id": website_id,
        "user_id": user_id,
        "wp_site_url": wp_site_url,
        "client_id": client_id,
        "code_verifier": code_verifier,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    r = _get_redis()
    r.setex(_state_key(state), 600, json.dumps(state_data))
    r.close()

    authorize_url = (
        f"{WP_OAUTH_AUTHORIZE_URL}"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&scope=basic"
    )

    return {"authorize_url": authorize_url, "state": state}


async def exchange_code_for_token(code: str, state: str) -> Dict[str, Any]:
    r = _get_redis()
    stored = r.get(_state_key(state))
    r.close()

    if not stored:
        raise ValueError("Invalid or expired OAuth state")

    state_data = json.loads(stored)
    code_verifier = state_data["code_verifier"]
    website_id = state_data["website_id"]
    user_id = state_data["user_id"]
    wp_site_url = state_data["wp_site_url"]
    client_id = state_data["client_id"]

    _validate_wp_url(wp_site_url)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            WP_OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": client_id,
                "client_secret": WP_OAUTH_CLIENT_SECRET,
                "code_verifier": code_verifier,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Token exchange failed: {resp.status_code} - {resp.text}")
        token_data = resp.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    token_type = token_data.get("token_type", "Bearer")
    scope = token_data.get("scope")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    access_token_encrypted = encrypt_token(access_token)
    refresh_token_encrypted = encrypt_token(refresh_token) if refresh_token else None

    wp_user_info = await _get_wp_user_info(wp_site_url, access_token)
    wp_user_id = wp_user_info.get("id")
    wp_user_login = wp_user_info.get("name") or wp_user_info.get("slug")

    supabase = get_supabase()
    token_row = {
        "website_id": website_id,
        "user_id": user_id,
        "wp_site_url": wp_site_url,
        "client_id": client_id,
        "access_token_encrypted": access_token_encrypted,
        "refresh_token_encrypted": refresh_token_encrypted,
        "token_type": token_type,
        "expires_at": expires_at.isoformat(),
        "scope": scope,
        "wp_user_id": wp_user_id,
        "wp_user_login": wp_user_login,
        "is_connected": True,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "last_used_at": datetime.now(timezone.utc).isoformat(),
    }
    supabase.table("wordpress_oauth_tokens").upsert(token_row, on_conflict="website_id,user_id").execute()

    supabase.table("websites").update({"wp_oauth_connected": True, "oauth_enabled": True}).eq("id", website_id).execute()

    supabase.table("critical_action_logs").insert({
        "website_id": website_id,
        "agent_name": "wordpress_oauth",
        "action_type": "wp_oauth_connected",
        "attempted_at": datetime.now(timezone.utc).isoformat(),
        "blocked": False,
        "status_before": "disconnected",
        "approved_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    r = _get_redis()
    r.delete(_state_key(state))
    r.close()

    return {
        "connected": True,
        "wp_user_login": wp_user_login,
        "expires_at": expires_at.isoformat(),
    }


async def _get_wp_user_info(wp_site_url: str, access_token: str) -> Dict[str, Any]:
    url = f"{wp_site_url.rstrip('/')}/wp-json/wp/v2/users/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        logger.error("Failed to get WP user info: %s - %s", resp.status_code, resp.text)
        return {}


async def refresh_access_token(website_id: str, user_id: str) -> str:
    supabase = get_supabase()
    result = (
        supabase.table("wordpress_oauth_tokens")
        .select("*")
        .eq("website_id", website_id)
        .eq("user_id", user_id)
        .eq("is_connected", True)
        .order("connected_at", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if not result:
        raise PermissionError("WordPress OAuth not connected")

    token_row = result[0]
    expires_at_str = token_row.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    else:
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    if expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        return decrypt_token(token_row["access_token_encrypted"])

    refresh_token_encrypted = token_row.get("refresh_token_encrypted")
    if not refresh_token_encrypted:
        supabase.table("wordpress_oauth_tokens").update({"is_connected": False}).eq("id", token_row["id"]).execute()
        supabase.table("websites").update({"wp_oauth_connected": False}).eq("id", website_id).execute()
        raise PermissionError("No refresh token available - reconnect in /settings")

    refresh_token = decrypt_token(refresh_token_encrypted)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            WP_OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": token_row["client_id"],
                "client_secret": WP_OAUTH_CLIENT_SECRET,
            },
        )
        if resp.status_code != 200:
            supabase.table("wordpress_oauth_tokens").update({"is_connected": False}).eq("id", token_row["id"]).execute()
            supabase.table("websites").update({"wp_oauth_connected": False}).eq("id", website_id).execute()
            raise PermissionError("WordPress OAuth disconnected - reconnect in /settings")
        new_token_data = resp.json()

    new_access_token = new_token_data.get("access_token", "")
    new_refresh_token = new_token_data.get("refresh_token", refresh_token)
    new_expires_in = new_token_data.get("expires_in", 3600)
    new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_expires_in)

    updates: Dict[str, Any] = {
        "access_token_encrypted": encrypt_token(new_access_token),
        "expires_at": new_expires_at.isoformat(),
        "last_used_at": datetime.now(timezone.utc).isoformat(),
    }
    if new_refresh_token:
        updates["refresh_token_encrypted"] = encrypt_token(new_refresh_token)

    supabase.table("wordpress_oauth_tokens").update(updates).eq("id", token_row["id"]).execute()

    return new_access_token


async def get_valid_access_token(website_id: str, user_id: str) -> str:
    return await refresh_access_token(website_id, user_id)


async def publish_with_oauth(
    website_id: str,
    user_id: str,
    title: str,
    content_html: str,
    status: str = "draft",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    supabase = get_supabase()
    result = (
        supabase.table("wordpress_oauth_tokens")
        .select("*")
        .eq("website_id", website_id)
        .eq("user_id", user_id)
        .eq("is_connected", True)
        .order("connected_at", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if not result:
        raise PermissionError("WordPress not connected via OAuth - Connect in /settings")

    token_row = result[0]
    wp_site_url = token_row["wp_site_url"].rstrip("/")
    _validate_wp_url(wp_site_url)

    access_token = await get_valid_access_token(website_id, user_id)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    post_body: Dict[str, Any] = {
        "title": title,
        "content": content_html,
        "status": status,
    }
    if meta:
        post_body["meta"] = meta

    url = f"{wp_site_url}/wp-json/wp/v2/posts"

    async def _do_post(token: str) -> httpx.Response:
        h = {**headers, "Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.post(url, json=post_body, headers=h)

    resp = await _do_post(access_token)

    if resp.status_code == 401:
        access_token = await refresh_access_token(website_id, user_id)
        resp = await _do_post(access_token)

    if resp.status_code not in (200, 201):
        error_text = resp.text
        raise RuntimeError(f"WordPress publish failed: {resp.status_code} - {error_text}")

    post_data = resp.json()
    wp_post_id = post_data.get("id")
    wp_url = post_data.get("link", f"{wp_site_url}/?p={wp_post_id}")
    edit_url = f"{wp_site_url}/wp-admin/post.php?post={wp_post_id}&action=edit"

    supabase.table("wordpress_oauth_tokens").update({
        "last_used_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", token_row["id"]).execute()

    supabase.table("content_pipeline_logs").insert({
        "website_id": website_id,
        "phase": "wordpress_export",
        "step_number": 1,
        "step_name": "oauth_publish",
        "status": "completed",
        "input_data": {"title": title, "status": status},
        "output_data": {"wp_post_id": wp_post_id, "wp_url": wp_url},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    supabase.table("critical_action_logs").insert({
        "website_id": website_id,
        "agent_name": "wordpress_oauth",
        "action_type": "publish_post",
        "attempted_at": datetime.now(timezone.utc).isoformat(),
        "blocked": False,
        "approved_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    return {
        "wp_post_id": wp_post_id,
        "wp_url": wp_url,
        "edit_url": edit_url,
        "status": post_data.get("status"),
    }


async def disconnect_oauth(website_id: str, user_id: str) -> None:
    supabase = get_supabase()
    supabase.table("wordpress_oauth_tokens").update({"is_connected": False}).eq("website_id", website_id).eq("user_id", user_id).execute()
    supabase.table("websites").update({"wp_oauth_connected": False}).eq("id", website_id).execute()

    supabase.table("critical_action_logs").insert({
        "website_id": website_id,
        "agent_name": "wordpress_oauth",
        "action_type": "wp_oauth_disconnected",
        "attempted_at": datetime.now(timezone.utc).isoformat(),
        "blocked": False,
        "approved_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


async def get_oauth_status(website_id: str, user_id: str) -> Dict[str, Any]:
    supabase = get_supabase()
    result = (
        supabase.table("wordpress_oauth_tokens")
        .select("*")
        .eq("website_id", website_id)
        .eq("user_id", user_id)
        .eq("is_connected", True)
        .order("connected_at", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if not result:
        return {
            "connected": False,
            "reason": "Not connected - Click Connect WordPress OAuth",
        }

    token_row = result[0]
    try:
        access_token = await get_valid_access_token(website_id, user_id)
        wp_user_info = await _get_wp_user_info(token_row["wp_site_url"], access_token)
        if wp_user_info.get("id"):
            return {
                "connected": True,
                "wp_site_url": token_row["wp_site_url"],
                "wp_user_login": token_row.get("wp_user_login"),
                "expires_at": token_row.get("expires_at"),
                "last_used_at": token_row.get("last_used_at"),
            }
    except Exception as e:
        logger.error("OAuth status check failed: %s", e)

    return {
        "connected": False,
        "reason": "Token expired - reconnect",
        "needs_reconnect": True,
    }
