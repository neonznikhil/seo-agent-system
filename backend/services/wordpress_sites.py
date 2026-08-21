"""Storage for self-hosted WordPress site credentials (Application Passwords).

Supabase is used when configured; otherwise credentials are kept in a local
JSON file so the integration works without any external service.
"""
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..config import (
    SUPABASE_KEY,
    SUPABASE_URL,
    WORDPRESS_APP_PASSWORD,
    WORDPRESS_URL,
    WORDPRESS_USERNAME,
    WP_SITES_FILE,
)

logger = logging.getLogger("backend.services.wordpress_sites")

TABLE = "wordpress_sites"
_lock = threading.Lock()

ENV_SITE_ID = "env-default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _supabase():
    from ..database import get_supabase

    return get_supabase()


def _read_file() -> List[Dict]:
    if not os.path.exists(WP_SITES_FILE):
        return []
    try:
        with open(WP_SITES_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Failed to read %s: %s", WP_SITES_FILE, e)
        return []


def _write_file(sites: List[Dict]) -> None:
    directory = os.path.dirname(os.path.abspath(WP_SITES_FILE))
    os.makedirs(directory, exist_ok=True)
    with open(WP_SITES_FILE, "w", encoding="utf-8") as fh:
        json.dump(sites, fh, indent=2)


def _env_site() -> Optional[Dict]:
    if not (WORDPRESS_URL and WORDPRESS_USERNAME and WORDPRESS_APP_PASSWORD):
        return None
    return {
        "id": ENV_SITE_ID,
        "name": _normalize_url(WORDPRESS_URL),
        "site_url": _normalize_url(WORDPRESS_URL),
        "username": WORDPRESS_USERNAME,
        "app_password": WORDPRESS_APP_PASSWORD,
        "source": "env",
        "created_at": None,
        "updated_at": None,
    }


def save_site(site_url: str, username: str, app_password: str, name: str = "") -> Dict:
    """Create or update a site by URL. Returns the stored record."""
    site_url = _normalize_url(site_url)
    record = {
        "site_url": site_url,
        "username": username,
        "app_password": app_password,
        "name": name or site_url,
        "updated_at": _now(),
    }

    if supabase_enabled():
        try:
            existing = _supabase().table(TABLE).select("id").eq("site_url", site_url).execute().data
            if existing:
                site_id = existing[0]["id"]
                _supabase().table(TABLE).update(record).eq("id", site_id).execute()
            else:
                record["created_at"] = _now()
                inserted = _supabase().table(TABLE).insert(record).execute().data
                site_id = inserted[0]["id"] if inserted else str(uuid.uuid4())
            return {**record, "id": str(site_id), "source": "supabase"}
        except Exception as e:
            logger.warning("Supabase save failed, falling back to local store: %s", e)

    with _lock:
        sites = _read_file()
        for site in sites:
            if site.get("site_url") == site_url:
                site.update(record)
                _write_file(sites)
                return {**site, "source": "file"}
        record["id"] = str(uuid.uuid4())
        record["created_at"] = _now()
        sites.append(record)
        _write_file(sites)
    return {**record, "source": "file"}


def list_sites(include_secrets: bool = False) -> List[Dict]:
    sites: List[Dict] = []
    if supabase_enabled():
        try:
            rows = _supabase().table(TABLE).select("*").execute().data or []
            sites = [{**row, "id": str(row["id"]), "source": "supabase"} for row in rows]
        except Exception as e:
            logger.warning("Supabase list failed, falling back to local store: %s", e)
    if not sites:
        sites = [{**site, "source": "file"} for site in _read_file()]

    env_site = _env_site()
    if env_site and not any(s.get("site_url") == env_site["site_url"] for s in sites):
        sites.append(env_site)

    if include_secrets:
        return sites
    return [{k: v for k, v in site.items() if k != "app_password"} for site in sites]


def get_site(site_id: Optional[str] = None) -> Optional[Dict]:
    """Return a site with credentials. Falls back to the only/env site."""
    sites = list_sites(include_secrets=True)
    if site_id:
        for site in sites:
            if str(site.get("id")) == str(site_id) or site.get("site_url") == _normalize_url(site_id):
                return site
        return None
    if not sites:
        return None
    stored = [s for s in sites if s.get("source") != "env"]
    return stored[0] if stored else sites[0]


def delete_site(site_id: str) -> bool:
    if supabase_enabled():
        try:
            _supabase().table(TABLE).delete().eq("id", site_id).execute()
            return True
        except Exception as e:
            logger.warning("Supabase delete failed, falling back to local store: %s", e)

    with _lock:
        sites = _read_file()
        remaining = [s for s in sites if str(s.get("id")) != str(site_id)]
        if len(remaining) == len(sites):
            return False
        _write_file(remaining)
    return True
