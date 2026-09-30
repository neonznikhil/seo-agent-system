"""RankForge Website Service.
Central authority for resolving active and default website entities.
Strictly returns real website UUIDs or None. Never returns the string 'default'.
"""

import logging
import threading
import time
from typing import Optional, Dict, Any, List
from database import get_supabase
from services.local_store import list_local_websites, get_local_website

logger = logging.getLogger("backend.services.website_service")

# Resolving the default website is a synchronous Supabase round-trip that several
# polled endpoints used to run inline on the API event loop, blocking every other
# request for seconds. The answer is also stable for a whole session, so cache it
# briefly. A negative result is cached too: when no site exists yet the query is
# the slow path (it falls through to the local store) and would otherwise run on
# every poll.
_DEFAULT_ID_TTL_SEC = 10.0
_default_id_lock = threading.Lock()
_default_id_cache: Optional[str] = None
_default_id_cached_at = 0.0


def _fetch_default_website_id() -> Optional[str]:
    """Uncached resolution. Call from a worker thread, never the event loop."""
    try:
        supabase = get_supabase()
        res = (
            supabase.table("websites")
            .select("id, domain, created_at")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0 and res.data[0].get("id"):
            return str(res.data[0]["id"])
    except Exception as e:
        logger.debug(f"[WebsiteService] Supabase default website query note: {e}")

    local = list_local_websites()
    if local and len(local) > 0 and local[0].get("id"):
        return str(local[0]["id"])
    return None


def get_default_website_id() -> Optional[str]:
    """Retrieve the primary active website ID from Supabase websites table or local store.

    Synchronous and TTL-cached. Async callers on the event loop must use
    ``get_default_website_id_async`` so the blocking query does not stall the loop.
    """
    global _default_id_cache, _default_id_cached_at
    now = time.monotonic()
    with _default_id_lock:
        if _default_id_cached_at and (now - _default_id_cached_at) < _DEFAULT_ID_TTL_SEC:
            return _default_id_cache
    resolved = _fetch_default_website_id()
    with _default_id_lock:
        _default_id_cache = resolved
        _default_id_cached_at = time.monotonic()
    return resolved


async def get_default_website_id_async() -> Optional[str]:
    """Async wrapper: resolve on a worker thread and never block the event loop."""
    import asyncio
    global _default_id_cache, _default_id_cached_at
    now = time.monotonic()
    with _default_id_lock:
        if _default_id_cached_at and (now - _default_id_cached_at) < _DEFAULT_ID_TTL_SEC:
            return _default_id_cache
    resolved = await asyncio.to_thread(_fetch_default_website_id)
    with _default_id_lock:
        _default_id_cache = resolved
        _default_id_cached_at = time.monotonic()
    return resolved


def invalidate_default_website_cache() -> None:
    """Drop the cached default id so the next lookup reflects a create/delete."""
    global _default_id_cache, _default_id_cached_at
    with _default_id_lock:
        _default_id_cache = None
        _default_id_cached_at = 0.0



def get_website_domain(website_id: Optional[str] = None) -> str:
    """Retrieve domain for a given website_id or default website."""
    target_id = website_id or get_default_website_id()
    if not target_id:
        return ""
    try:
        supabase = get_supabase()
        res = (
            supabase.table("websites")
            .select("domain, url, cms_url")
            .eq("id", target_id)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            row = res.data[0]
            domain = row.get("domain") or row.get("url") or row.get("cms_url") or ""
            return domain.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
    except Exception as e:
        logger.debug(f"[WebsiteService] Supabase domain query note: {e}")

    local = get_local_website(target_id)
    if local:
        domain = local.get("domain") or local.get("url") or local.get("cms_url") or ""
        return domain.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
    return ""


def get_website_details(website_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full details of website by ID or default website."""
    target_id = website_id or get_default_website_id()
    if not target_id:
        return None
    try:
        supabase = get_supabase()
        res = (
            supabase.table("websites")
            .select("*")
            .eq("id", target_id)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception as e:
        logger.debug(f"[WebsiteService] Supabase website details query note: {e}")
    return get_local_website(target_id)


def list_active_website_ids() -> List[str]:
    """Retrieve all active website IDs from Supabase or local store."""
    ids = []
    try:
        supabase = get_supabase()
        res = supabase.table("websites").select("id").execute()
        if res.data:
            ids = [str(r["id"]) for r in res.data if r.get("id")]
    except Exception as e:
        logger.debug(f"[WebsiteService] Supabase active websites query note: {e}")
    
    local = list_local_websites()
    for l in local:
        lid = str(l.get("id"))
        if lid and lid not in ids:
            ids.append(lid)
    return ids


def get_website_id_from_request(request: Optional[Any] = None) -> Optional[str]:
    """Resolve website_id from Request header X-Website-Id, state, query param, or fallback to default website."""
    if request:
        headers = getattr(request, "headers", {})
        wid = headers.get("X-Website-Id") or headers.get("x-website-id")
        if wid and wid not in ("default", "default-website-id", "all", "", "null", "undefined"):
            return str(wid)
        query_params = getattr(request, "query_params", {})
        q_wid = query_params.get("website_id")
        if q_wid and q_wid not in ("default", "default-website-id", "all", "", "null", "undefined"):
            return str(q_wid)
    return get_default_website_id()
