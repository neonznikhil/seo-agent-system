import logging
import re
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..database import get_supabase
from ..agents.knowledge_agent import run_knowledge_agent

logger = logging.getLogger("backend.routers.websites")
router = APIRouter()


class WebsiteIn(BaseModel):
    id: Optional[str] = None
    domain: Optional[str] = None
    url: Optional[str] = None
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = "active"


class WebsiteUpdate(BaseModel):
    domain: Optional[str] = None
    url: Optional[str] = None
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = None


def extract_domain(raw_url: Optional[str], default_domain: Optional[str] = None) -> str:
    if default_domain and default_domain.strip():
        return default_domain.strip().replace("https://", "").replace("http://", "").split("/")[0]
    if raw_url and raw_url.strip():
        clean = raw_url.strip().replace("https://", "").replace("http://", "").split("/")[0]
        if clean:
            return clean
    return "example.com"


@router.get("/")
@router.get("/websites")
async def list_websites():
    try:
        supabase = get_supabase()
        res = supabase.table("websites").select("*").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error fetching websites: {e}")
        return []


@router.post("/websites")
async def create_or_update_website(website: WebsiteIn, background_tasks: BackgroundTasks):
    supabase = get_supabase()
    
    # Extract domain if missing
    cms_url = website.cms_url or website.url
    resolved_domain = extract_domain(cms_url, website.domain)
    
    payload = {
        "domain": resolved_domain,
        "status": website.status or "active",
        "updated_at": datetime.utcnow().isoformat(),
    }
    if cms_url:
        payload["cms_url"] = cms_url
        payload["url"] = cms_url
    if website.cms_user:
        payload["cms_user"] = website.cms_user
    if website.app_password:
        payload["app_password"] = website.app_password
    if website.gsc_property:
        payload["gsc_property"] = website.gsc_property

    # 1. If an explicit ID is provided, update that website
    if website.id:
        try:
            res = supabase.table("websites").update(payload).eq("id", website.id).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            logger.warning(f"Failed to update website by id {website.id}: {e}")

    # 2. Check if a website with this domain exists
    existing = None
    try:
        existing = supabase.table("websites").select("*").eq("domain", resolved_domain).limit(1).execute().data
    except Exception:
        pass

    if existing and len(existing) > 0:
        wid = existing[0]["id"]
        res = supabase.table("websites").update(payload).eq("id", wid).execute()
        return res.data[0] if res.data else existing[0]

    # 3. Create new website
    payload["created_at"] = datetime.utcnow().isoformat()
    res = supabase.table("websites").insert(payload).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create website")
    
    background_tasks.add_task(run_knowledge_agent, row["id"], row.get("cms_url") or f"https://{row['domain']}")
    return row


@router.get("/websites/{website_id}")
async def get_website(website_id: str):
    supabase = get_supabase()
    res = supabase.table("websites").select("*").eq("id", website_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Website not found")
    return res.data


@router.put("/{website_id}")
@router.put("/websites/{website_id}")
@router.patch("/{website_id}")
@router.patch("/websites/{website_id}")
async def update_website(website_id: str, website: WebsiteUpdate):
    supabase = get_supabase()
    updates = {k: v for k, v in website.model_dump().items() if v is not None}
    if not updates:
        return {"detail": "no changes"}
    
    if "cms_url" in updates and "url" not in updates:
        updates["url"] = updates["cms_url"]
    updates["updated_at"] = datetime.utcnow().isoformat()

    try:
        res = supabase.table("websites").update(updates).eq("id", website_id).execute()
        return res.data[0] if res.data else {"detail": "updated"}
    except Exception as e:
        logger.error(f"Failed to update website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/websites/{website_id}")
async def delete_website(website_id: str):
    supabase = get_supabase()
    res = supabase.table("websites").delete().eq("id", website_id).execute()
    return {"detail": "deleted", "rows_affected": len(res.data or [])}
