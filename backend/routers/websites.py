import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..database import get_supabase
from ..agents.knowledge_agent import run_knowledge_agent

logger = logging.getLogger("backend.routers.websites")
router = APIRouter()


class WebsiteIn(BaseModel):
    domain: str
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = "active"


class WebsiteUpdate(BaseModel):
    domain: Optional[str] = None
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = None


@router.get("/websites")
async def list_websites():
    res = get_supabase().table("websites").select("*").execute()
    return res.data or []


@router.post("/websites")
async def create_website(website: WebsiteIn, background_tasks: BackgroundTasks):
    res = get_supabase().table("websites").insert(website.model_dump()).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create website")
    background_tasks.add_task(run_knowledge_agent, row["id"], row.get("cms_url") or f"https://{row['domain']}")
    return row


@router.get("/websites/{website_id}")
async def get_website(website_id: str):
    res = get_supabase().table("websites").select("*").eq("id", website_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Not found")
    return res.data


@router.put("/websites/{website_id}")
async def update_website(website_id: str, website: WebsiteUpdate):
    updates = {k: v for k, v in website.model_dump().items() if v is not None}
    if not updates:
        return {"detail": "no changes"}
    res = get_supabase().table("websites").update(updates).eq("id", website_id).execute()
    return res.data[0] if res.data else {"detail": "updated"}
