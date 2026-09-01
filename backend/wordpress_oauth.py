import os
import base64
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet, InvalidToken
from supabase import create_client

from config import SUPABASE_URL, SUPABASE_KEY, ENCRYPTION_SECRET, FRONTEND_URL, WORDPRESS_URL

logger = logging.getLogger("backend.wordpress_oauth")


def _get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _get_fernet() -> Fernet:
    if not ENCRYPTION_SECRET:
        raise RuntimeError("ENCRYPTION_SECRET not configured")
    secret = ENCRYPTION_SECRET.encode() if isinstance(ENCRYPTION_SECRET, str) else ENCRYPTION_SECRET
    return Fernet(secret)


def encrypt(data: str) -> str:
    return _get_fernet().encrypt(data.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise RuntimeError("Failed to decrypt token - key mismatch or corrupted data")


def generate_authorize_url(state: str, success_url: str) -> str:
    base = WORDPRESS_URL.rstrip("/") + "/wp-admin/authorize-application.php"
    from urllib.parse import quote
    encoded_success = quote(success_url, safe="")
    return f"{base}?app_name=Rankforge&success_url={encoded_success}&state={state}"


def store_state(state: str, user_id: str, site_url: str) -> None:
    supabase = _get_supabase()
    supabase.table("wp_oauth_states").upsert({
        "state": state,
        "user_id": user_id,
        "site_url": site_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def validate_and_consume_state(state: str, user_id: str) -> Optional[str]:
    supabase = _get_supabase()
    result = (
        supabase.table("wp_oauth_states")
        .select("*")
        .eq("state", state)
        .eq("user_id", user_id)
        .execute()
        .data
    )

    if not result:
        return None

    row = result[0]
    site_url = row.get("site_url")

    supabase.table("wp_oauth_states").delete().eq("state", state).execute()

    return site_url


async def test_wordpress_connection(site_url: str, username: str, app_password: str) -> dict:
    """
    Tests WordPress connection with explicit error diagnostics:
    - 200: Connected (role, name, user_id)
    - 401: Wrong username or app password
    - 403: Security plugin / Cloudflare blocking REST API
    - 404: Pretty permalinks / REST API disabled
    - Timeout: Connection timed out
    - Other: Specific error message
    """
    clean_url = site_url.rstrip("/")
    if clean_url and not clean_url.startswith("http"):
        clean_url = f"https://{clean_url}"

    headers = {
        "User-Agent": "Mozilla/5.0 RankForge/1.0",
        "Accept": "application/json",
    }
    endpoints = [
        f"{clean_url}/wp-json/wp/v2/users/me?context=edit",
        f"{clean_url}/?rest_route=/wp/v2/users/me&context=edit",
        f"{clean_url}/wp-json/wp/v2/users/me",
    ]

    last_error_res = None
    for ep in endpoints:
        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
                r = await client.get(ep, auth=(username, app_password))

            if r.status_code == 200:
                user_data = r.json()
                roles = user_data.get("roles", ["unknown"]) or ["unknown"]
                can_pub = bool(user_data.get("capabilities", {}).get("publish_posts") or any(role in ["author", "editor", "administrator"] for role in roles))
                return {
                    "status": "connected",
                    "connected": True,
                    "role": roles[0] if roles else "unknown",
                    "roles": roles,
                    "display_name": user_data.get("name", username),
                    "user_id": user_data.get("id"),
                    "can_publish": can_pub,
                    "message": f"Connected as {user_data.get('name', username)} (Role: {roles[0] if roles else 'unknown'})",
                }
            elif r.status_code == 401:
                last_error_res = {
                    "status": "error",
                    "connected": False,
                    "message": "Wrong username or app password. Generate a new app password in WordPress under Users > Profile > Application Passwords."
                }
            elif r.status_code == 403:
                last_error_res = {
                    "status": "error",
                    "connected": False,
                    "message": "Access blocked. Your security plugin (Wordfence, Cloudflare, etc.) is blocking the REST API. Whitelist this IP or disable REST API blocking in your security plugin settings."
                }
            elif r.status_code == 404:
                last_error_res = {
                    "status": "error",
                    "connected": False,
                    "message": "WordPress REST API not found. Make sure your site is using pretty permalinks (Settings > Permalinks > Post name) and the REST API is enabled."
                }
            else:
                last_error_res = {
                    "status": "error",
                    "connected": False,
                    "message": f"Unexpected response: HTTP {r.status_code}. Check that the site URL is correct and accessible."
                }
        except httpx.TimeoutException:
            last_error_res = {
                "status": "error",
                "connected": False,
                "message": "Connection timed out. Check that the site URL is correct and the server is responding."
            }
        except Exception as e:
            last_error_res = {
                "status": "error",
                "connected": False,
                "message": f"Could not connect: {str(e)}"
            }

    return last_error_res or {
        "status": "error",
        "connected": False,
        "message": "Could not establish connection to WordPress site."
    }


async def test_wp_connection(site_url: str, username: str, app_password: str) -> dict:
    res = await test_wordpress_connection(site_url, username, app_password)
    if not res.get("connected") and res.get("status") != "connected":
        raise RuntimeError(res.get("message", "WordPress connection test failed"))
    return {
        "id": res.get("user_id"),
        "name": res.get("display_name", username),
        "roles": res.get("roles", ["editor"]),
    }


async def save_connection(user_id: str, site_url: str, username: str, app_password: str) -> dict:
    wp_user_info = await test_wp_connection(site_url, username, app_password)

    encrypted_password = encrypt(app_password)

    try:
        supabase = _get_supabase()
        supabase.table("wordpress_connections").upsert({
            "user_id": user_id,
            "site_url": site_url,
            "wp_username": username,
            "encrypted_password": encrypted_password,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="user_id").execute()
    except Exception as e:
        logger.warning(f"Could not persist to wordpress_connections in Supabase: {e}")

    try:
        from .services.local_store import save_local_wp_connection
        save_local_wp_connection({
            "user_id": user_id,
            "site_url": site_url,
            "wp_username": username,
            "encrypted_password": encrypted_password,
            "wp_app_password_encrypted": encrypted_password,
            "is_active": True,
        })
    except Exception as local_e:
        logger.debug(f"Local store WP connection note: {local_e}")

    return {
        "connected": True,
        "site_url": site_url,
        "username": username,
        "wp_user_id": wp_user_info.get("id"),
        "wp_name": wp_user_info.get("name") or wp_user_info.get("slug"),
    }


def get_connection(user_id: str) -> Optional[dict]:
    supabase = _get_supabase()
    result = (
        supabase.table("wordpress_connections")
        .select("*")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    if not result:
        return None
    return result[0]


def get_decrypted_connection(user_id: str) -> Optional[dict]:
    row = get_connection(user_id)
    if not row:
        return None
    return {
        "site_url": row.get("site_url"),
        "username": row.get("wp_username"),
        "password": decrypt(row.get("encrypted_password", "")),
    }


def disconnect(user_id: str) -> None:
    supabase = _get_supabase()
    supabase.table("wordpress_connections").delete().eq("user_id", user_id).execute()


async def publish_post(user_id: str, title: str, content: str, status: str = "draft") -> dict:
    conn = get_decrypted_connection(user_id)
    if not conn:
        raise RuntimeError("WordPress not connected")

    site_url = conn["site_url"].rstrip("/")
    username = conn["username"]
    password = conn["password"]

    url = f"{site_url}/wp-json/wp/v2/posts"
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }
    body = {"title": title, "content": content, "status": status}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=body, headers=headers)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"WordPress publish failed: {resp.status_code} - {resp.text}")

    post_data = resp.json()
    wp_post_id = post_data.get("id")
    wp_url = post_data.get("link", f"{site_url}/?p={wp_post_id}")
    edit_url = f"{site_url}/wp-admin/post.php?post={wp_post_id}&action=edit"

    return {
        "wp_post_id": wp_post_id,
        "wp_url": wp_url,
        "edit_url": edit_url,
        "status": post_data.get("status"),
    }
