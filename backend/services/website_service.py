"""RankForge Website Service.
Central authority for resolving active and default website entities.
Strictly returns real website UUIDs or None. Never returns the string 'default'.
"""

import logging
from typing import Optional, Dict, Any, List
from database import get_supabase
from .local_store import list_local_websites, get_local_website

logger = logging.getLogger("backend.services.website_service")


def get_default_website_id() -> Optional[str]:
    """Retrieve the primary active website ID from Supabase websites table or local store."""
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
