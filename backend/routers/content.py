import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.content")
router = APIRouter()


class ContentIn(BaseModel):
    website_id: str
    title: str
    content: str
    status: Optional[str] = "draft"
    content_type: Optional[str] = "blog"


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    content_type: Optional[str] = None


class ContentOut(BaseModel):
    id: str
    website_id: str
    title: str
    content: str
    status: str
    content_type: str


@router.get("/content")
async def list_content(website_id: Optional[str] = None, status: Optional[str] = None):
    query = get_supabase().table("content_log").select("*")
    if website_id:
        query = query.eq("website_id", website_id)
    if status:
        query = query.eq("status", status)
    res = query.order("created_at", desc=True).execute()
    return res.data or []


@router.post("/content")
async def create_content(body: ContentIn):
    res = get_supabase().table("content_log").insert(body.model_dump()).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create content")
    return row


@router.get("/content/{content_id}")
async def get_content(content_id: str):
    res = get_supabase().table("content_log").select("*").eq("id", content_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Not found")
    return res.data


@router.put("/content/{content_id}")
async def update_content(content_id: str, body: ContentUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"detail": "no changes"}
    res = get_supabase().table("content_log").update(updates).eq("id", content_id).execute()
    return res.data[0] if res.data else {"detail": "updated"}
