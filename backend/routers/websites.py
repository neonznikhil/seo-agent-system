import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from backend.database import get_supabase, set_account_context
from middleware.auth import get_current_account_id
from security import encrypt_secret, decrypt_secret, sanitize_website_row
from agents.knowledge_agent import run_knowledge_agent
from services.local_store import (
    save_local_website,
    list_local_websites,
    get_local_website,
    delete_local_website,
)

logger = logging.getLogger("backend.routers.websites")
router = APIRouter()

# Columns that hold secrets. They are encrypted at rest and NEVER returned.
_SECRET_COLUMNS = {"app_password", "wordpress_password", "serper_api_key"}

# Public column list used for every SELECT on the websites table.
_WEBSITE_SAFE_COLUMNS = (
    "id, domain, url, cms_url, cms_user, wordpress_url, wordpress_user, "
    "gsc_property, niche, name, status, created_at, updated_at, "
    "last_audit_score, last_audit_date, account_id"
)


class WebsiteIn(BaseModel):
    id: Optional[str] = None
    domain: Optional[str] = None
    url: Optional[str] = None
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    wordpress_url: Optional[str] = None
    wordpress_user: Optional[str] = None
    wordpress_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = "active"


class WebsiteUpdate(BaseModel):
    domain: Optional[str] = None
    url: Optional[str] = None
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    wordpress_url: Optional[str] = None
    wordpress_user: Optional[str] = None
    wordpress_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = None


def extract_domain(raw_url: Optional[str], default_domain: Optional[str] = None) -> str:
    if default_domain and default_domain.strip():
        return default_domain.strip().replace("https://", "").replace("http://", "").split("/")[0]
    if raw_url and raw_url.strip():
        clean = raw_url.strip().replace("https://", "").replace("http://", "").split("/")[0]
        if clean:
            return clean
    return ""


def _resolve_app_password(row: dict) -> str:
    """Decrypt the stored application password for outbound API calls only."""
    raw = (
        row.get("wordpress_password_encrypted")
        or row.get("app_password")
        or row.get("wordpress_password")
        or ""
    )
    if not raw:
        return ""
    decrypted = decrypt_secret(raw)
    return decrypted


@router.get("/websites")
@router.get("/websites/list")
@router.get("/api/websites/list")
async def list_websites(request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    rows = []
    try:
        res = supabase.table("websites").select("*").order("created_at", desc=False).execute()
        rows = res.data or []
    except Exception as e:
        logger.debug(f"[Websites] Supabase query note: {e}")

    local_rows = list_local_websites(account_id)
    known_ids = {str(r.get("id")) for r in rows if r.get("id")}
    for lr in local_rows:
        if str(lr.get("id")) not in known_ids:
            rows.append(lr)
            known_ids.add(str(lr.get("id")))

    if not rows:
        wp_site = os.getenv("WORDPRESS_SITE_URL", "") or os.getenv("WP_SITE_URL", "")
        if wp_site:
            clean_dom = wp_site.replace("https://", "").replace("http://", "").split("/")[0]
            site_obj = {
                "id": str(uuid.uuid4()),
                "domain": clean_dom,
                "url": wp_site,
                "cms_url": wp_site,
                "wordpress_url": wp_site,
                "status": "active",
                "account_id": account_id,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            save_local_website(site_obj)
            rows.append(site_obj)

    return [sanitize_website_row(r) for r in rows]


@router.get("/api/websites/active")
@router.get("/websites/active")
@router.get("/websites/active/")
async def get_active_website(request: Request):
    """P2 FIX STEP2 — return most recent active website for user."""
    account_id = get_current_account_id(request)
    user_id = request.headers.get("X-User-Id") or account_id
    supabase = get_supabase()
    # Try supabase first
    result = None
    try:
        # Use account_id filter if column exists, else fallback
        try:
            result = supabase.table("websites").select("id, domain, url, cms_url, status, updated_at").eq("account_id", account_id).eq("status", "active").order("updated_at", desc=True).limit(1).execute()
        except Exception:
            result = supabase.table("websites").select("id, domain, url, status, updated_at").eq("status", "active").order("updated_at", desc=True).limit(1).execute()
        if result and result.data:
            site = result.data[0]
            return {"website_id": site["id"], "domain": site.get("domain"), "url": site.get("url") or site.get("cms_url"), "status": site.get("status")}
    except Exception:
        pass
    # Local fallback
    try:
        from ..services.local_store import list_local_websites
        local = list_local_websites(account_id)
        # also try user_id store
        if not local and user_id != account_id:
            try:
                local = list_local_websites(user_id)
            except Exception:
                pass
        actives = [w for w in local if w.get("status") == "active"]
        if actives:
            actives.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
            site = actives[0]
            return {"website_id": site["id"], "domain": site.get("domain"), "url": site.get("url") or site.get("cms_url"), "status": site.get("status", "active")}
        if local:
            site = sorted(local, key=lambda x: x.get("updated_at") or "", reverse=True)[0]
            return {"website_id": site["id"], "domain": site.get("domain"), "url": site.get("url"), "status": site.get("status")}
    except Exception:
        pass
    return {"website_id": None, "domain": None, "url": None, "status": None}


async def trigger_auto_crawl(website_id: str, account_id: str):
    """Background task triggered on website registration."""
    supabase = get_supabase()
    set_account_context(supabase, account_id)
    try:
        # Get website URL
        site_data = supabase.table("websites").select("url, domain, cms_url, wordpress_url").eq("id", website_id).single().execute().data
        site_url = ""
        if site_data:
            site_url = site_data.get("url") or site_data.get("cms_url") or site_data.get("wordpress_url") or f"https://{site_data.get('domain', '')}"
        
        if not site_url or site_url in ("https://", "http://"):
            logger.error(f"[AutoCrawl] No URL for website {website_id}")
            return

        # Use the new robust crawl function
        from ..services.knowledge_service import crawl_and_index_website
        res = await crawl_and_index_website(website_id, site_url)

        count = res.get("chunks_saved", 0)
        try:
            supabase.table("content_log").insert({
                "website_id": website_id,
                "account_id": account_id,
                "title": f"Knowledge Crawl: {res.get('pages_found', 0)} pages found, {count} chunks indexed",
                "status": "completed",
                "pipeline_status": "knowledge_indexed",
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception:
            pass

        logger.info(f"[AutoCrawl] Completed for site {website_id}: {count} chunks indexed.")
    except Exception as e:
        logger.error(f"[AutoCrawl] Failed for website {website_id}: {e}")
        try:
            supabase.table("websites").update({
                "status": "active",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", website_id).execute()
        except Exception:
            pass


@router.post("/websites")
@router.post("/websites/create")
@router.post("/api/websites/create")
async def create_or_update_website(website: WebsiteIn, request: Request, background_tasks: BackgroundTasks):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    cms_url = website.cms_url or website.url or website.wordpress_url
    resolved_domain = extract_domain(cms_url, website.domain)
    if not resolved_domain:
        raise HTTPException(status_code=400, detail="A valid domain or CMS URL is required")

    site_id = website.id or str(uuid.uuid4())
    payload: dict = {
        "id": site_id,
        "account_id": account_id,
        "domain": resolved_domain,
        "status": website.status or "crawling",
        "updated_at": datetime.utcnow().isoformat(),
    }
    if cms_url:
        payload["cms_url"] = cms_url
        payload["url"] = cms_url
        payload["wordpress_url"] = cms_url
    if website.cms_user or website.wordpress_user:
        user_val = website.cms_user or website.wordpress_user
        payload["cms_user"] = user_val
        payload["wordpress_user"] = user_val
    if website.gsc_property:
        payload["gsc_property"] = website.gsc_property
    
    app_pwd = website.app_password or website.wordpress_password
    if app_pwd:
        try:
            encrypted_pwd = encrypt_secret(app_pwd)
            payload["app_password"] = encrypted_pwd
            payload["wordpress_password"] = encrypted_pwd
            payload["wordpress_password_encrypted"] = encrypted_pwd
        except Exception as e:
            logger.error(f"Failed to encrypt WordPress credentials: {e}")
            raise HTTPException(status_code=500, detail="Failed to secure credentials")

    created_website_id = site_id
    res_obj = None

    # 1. Try Supabase
    try:
        existing = supabase.table("websites").select("id").eq("domain", resolved_domain).execute().data
        if existing and len(existing) > 0:
            target_id = existing[0]["id"]
            res = supabase.table("websites").update(payload).eq("id", target_id).execute()
            created_website_id = target_id
            if res.data:
                res_obj = sanitize_website_row(res.data[0])
        else:
            payload["created_at"] = datetime.utcnow().isoformat()
            res = supabase.table("websites").insert(payload).execute()
            if res.data:
                created_website_id = res.data[0]["id"]
                res_obj = sanitize_website_row(res.data[0])
    except Exception as e:
        logger.debug(f"[Websites] Supabase write note (falling back to persistent store): {e}")

    # 2. Always persist locally
    local_saved = save_local_website(payload)
    if not res_obj:
        created_website_id = local_saved["id"]
        res_obj = sanitize_website_row(local_saved)

    if created_website_id:
        background_tasks.add_task(trigger_auto_crawl, created_website_id, account_id)

    return res_obj


@router.get("/websites/{website_id}")
async def get_website(website_id: str, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    try:
        res = supabase.table("websites").select("*").eq("id", website_id).execute()
        if res.data and len(res.data) > 0:
            return sanitize_website_row(res.data[0])
    except Exception as e:
        logger.debug(f"[Websites] Supabase get note: {e}")

    local = get_local_website(website_id)
    if local:
        return sanitize_website_row(local)
    raise HTTPException(status_code=404, detail="Website not found")


@router.put("/websites/{website_id}")
async def update_website(website_id: str, update: WebsiteUpdate, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    payload = {k: v for k, v in update.model_dump().items() if v is not None}
    if not payload:
        return {"detail": "no changes"}

    app_pwd = payload.pop("app_password", None) or payload.pop("wordpress_password", None)
    if app_pwd:
        payload["app_password"] = encrypt_secret(app_pwd)
        payload["wordpress_password"] = payload["app_password"]
        payload["wordpress_password_encrypted"] = payload["app_password"]

    payload["updated_at"] = datetime.utcnow().isoformat()
    payload["id"] = website_id

    try:
        supabase.table("websites").update(payload).eq("id", website_id).execute()
    except Exception:
        pass

    saved = save_local_website(payload)
    return sanitize_website_row(saved)


@router.post("/websites/{website_id}/crawl")
@router.post("/api/websites/{website_id}/crawl")
async def crawl_website_on_demand(website_id: str, request: Request, background_tasks: BackgroundTasks):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    # Support sync full-site crawl via query ?sync=true or JSON body {sync:true, max_pages:50, site_url:"..."}
    sync = False
    max_pages = 50
    site_url_override: Optional[str] = None
    try:
        # Query params
        qp = dict(request.query_params)
        if qp.get("sync", "").lower() in ("1", "true", "yes"):
            sync = True
        if qp.get("max_pages") and str(qp.get("max_pages")).isdigit():
            max_pages = max(5, min(100, int(qp.get("max_pages"))))
        if qp.get("site_url"):
            site_url_override = qp.get("site_url")
        if qp.get("url"):
            site_url_override = qp.get("url")
        # Body params (if any)
        try:
            body = await request.json()
            if isinstance(body, dict):
                if body.get("sync") is True or str(body.get("sync")).lower() == "true":
                    sync = True
                if body.get("max_pages"):
                    max_pages = max(5, min(100, int(body.get("max_pages"))))
                if body.get("site_url"):
                    site_url_override = body.get("site_url")
                if body.get("url"):
                    site_url_override = body.get("url")
        except Exception:
            pass
    except Exception:
        pass

    if sync:
        # Synchronous full-site crawl — wait for result and return detailed stats
        try:
            supabase.table("websites").update({
                "status": "crawling",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", website_id).execute()
        except Exception:
            pass
        try:
            from ..services.knowledge_service import KnowledgeService
            ks = KnowledgeService(website_id=website_id, account_id=account_id)
            res = await ks.watch_business_website(target_site=site_url_override, max_pages=max_pages)
            # Mark active after crawl
            try:
                supabase.table("websites").update({
                    "status": "active",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", website_id).execute()
            except Exception:
                pass
            return {
                "success": True,
                "status": "completed",
                "mode": "full-site BFS + recursive sitemap",
                "website_id": website_id,
                **res,
            }
        except Exception as e:
            logger.error(f"[Crawl] Sync crawl failed for {website_id}: {e}")
            try:
                supabase.table("websites").update({
                    "status": "active",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", website_id).execute()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=str(e))

    # Default: background async crawl (legacy)
    try:
        supabase.table("websites").update({
            "status": "crawling",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", website_id).execute()
    except Exception:
        pass

    background_tasks.add_task(trigger_auto_crawl, website_id, account_id)
    return {"success": True, "status": "crawling", "message": "Full-site crawl initiated in background (BFS sitemap + internal links, up to 50 pages). Poll /api/knowledge?website_id=... for results."}


@router.delete("/websites/{website_id}")
@router.delete("/api/websites/{website_id}")
async def delete_website(website_id: str, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    try:
        supabase.table("websites").delete().eq("id", website_id).execute()
    except Exception:
        pass

    delete_local_website(website_id)
    return {"success": True, "id": website_id, "detail": "Website removed."}

