import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from ..database import get_supabase, set_account_context
from ..middleware.auth import get_current_account_id
from ..security import encrypt_secret, decrypt_secret, sanitize_website_row
from ..agents.knowledge_agent import run_knowledge_agent

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
async def list_websites(request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)
    try:
        res = supabase.table("websites").select("*").eq("account_id", account_id).execute()
        return [sanitize_website_row(r) for r in (res.data or [])]
    except Exception as e:
        logger.error(f"Error fetching websites for account {account_id}: {e}")
        return []


@router.post("/websites")
async def create_or_update_website(website: WebsiteIn, request: Request, background_tasks: BackgroundTasks):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    cms_url = website.cms_url or website.url or website.wordpress_url
    resolved_domain = extract_domain(cms_url, website.domain)
    if not resolved_domain:
        raise HTTPException(status_code=400, detail="A valid domain or CMS URL is required")

    payload: dict = {
        "account_id": account_id,
        "domain": resolved_domain,
        "status": website.status or "active",
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
        except Exception as e:
            logger.error(f"Failed to encrypt WordPress credentials: {e}")
            raise HTTPException(status_code=500, detail="Failed to secure credentials")

    # 1. If explicit ID provided, update matching row under this account
    if website.id:
        try:
            res = supabase.table("websites").update(payload).eq("id", website.id).eq("account_id", account_id).execute()
            if res.data:
                return sanitize_website_row(res.data[0])
        except Exception as e:
            logger.warning(f"Failed to update website by id {website.id}: {e}")

    # 2. Check if domain already exists for this tenant account
    try:
        existing = supabase.table("websites").select("id").eq("domain", resolved_domain).eq("account_id", account_id).execute().data
        if existing and len(existing) > 0:
            site_id = existing[0]["id"]
            res = supabase.table("websites").update(payload).eq("id", site_id).eq("account_id", account_id).execute()
            return sanitize_website_row(res.data[0] if res.data else payload)
    except Exception as e:
        logger.warning(f"Domain lookup note: {e}")

    # 3. Create new website
    payload["created_at"] = datetime.utcnow().isoformat()
    try:
        res = supabase.table("websites").insert(payload).execute()
        if not res.data:
            raise HTTPException(status_code=400, detail="Could not create website")
        
        row = res.data[0]
        # Trigger background initial knowledge crawl
        try:
            background_tasks.add_task(run_knowledge_agent, website_id=row["id"])
        except Exception:
            pass

        return sanitize_website_row(row)
    except Exception as e:
        logger.error(f"Failed to insert website: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create website: {str(e)}")


@router.get("/websites/{website_id}")
async def get_website(website_id: str, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    try:
        res = supabase.table("websites").select("*").eq("id", website_id).eq("account_id", account_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Website not found")
        return sanitize_website_row(res.data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching website {website_id}: {e}")
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

    payload["updated_at"] = datetime.utcnow().isoformat()

    try:
        res = supabase.table("websites").update(payload).eq("id", website_id).eq("account_id", account_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Website not found or not authorized")
        return sanitize_website_row(res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update website: {str(e)}")


@router.delete("/websites/{website_id}")
async def delete_website(website_id: str, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    try:
        supabase.table("websites").delete().eq("id", website_id).eq("account_id", account_id).execute()
        return {"success": True, "detail": "Website removed."}
    except Exception as e:
        logger.error(f"Error deleting website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete website: {str(e)}")
