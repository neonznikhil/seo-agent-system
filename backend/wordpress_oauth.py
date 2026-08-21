import os
import base64
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone

import httpx
import requests
from cryptography.fernet import Fernet, InvalidToken
from supabase import create_client

from .config import SUPABASE_URL, SUPABASE_KEY, ENCRYPTION_SECRET, FRONTEND_URL, WORDPRESS_URL

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
    encoded_success = base64.urlsafe_b64encode(success_url.encode()).decode().rstrip("=")
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


def test_wp_connection(site_url: str, username: str, app_password: str) -> dict:
    url = site_url.rstrip("/") + "/wp-json/wp/v2/users/me"
    credentials = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    headers = {"Authorization": f"Basic {credentials}"}

    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code != 200:
        raise RuntimeError(f"WordPress connection test failed: {resp.status_code} - {resp.text}")

    return resp.json()


def save_connection(user_id: str, site_url: str, username: str, app_password: str) -> dict:
    wp_user_info = test_wp_connection(site_url, username, app_password)

    encrypted_password = encrypt(app_password)

    supabase = _get_supabase()
    supabase.table("wordpress_connections").upsert({
        "user_id": user_id,
        "site_url": site_url,
        "wp_username": username,
        "encrypted_password": encrypted_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="user_id").execute()

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


def publish_post(user_id: str, title: str, content: str, status: str = "draft") -> dict:
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

    resp = requests.post(url, json=body, headers=headers, timeout=30)

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
