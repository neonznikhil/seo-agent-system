import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.knowledge")
router = APIRouter()


class KnowledgeIn(BaseModel):
    website_id: str
    title: str
    content: str
    source: Optional[str] = None
    tags: Optional[List[str]] = None


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None


class KnowledgeOut(BaseModel):
    id: str
    website_id: str
    title: str
    content: str
    source: Optional[str] = None
    tags: Optional[List[str]] = None


@router.get("/knowledge")
async def list_knowledge(website_id: Optional[str] = None, q: Optional[str] = None):
    query = get_supabase().table("knowledge_base").select("*")
    if website_id:
        query = query.eq("website_id", website_id)
    if q:
        query = query.ilike("title", f"%{q}%")
    res = query.order("created_at", desc=True).execute()
    return res.data or []


@router.post("/knowledge")
async def create_knowledge(body: KnowledgeIn):
    res = get_supabase().table("knowledge_base").insert(body.model_dump()).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create knowledge")
    return row


@router.get("/knowledge/search")
async def search_knowledge(q: str, website_id: Optional[str] = None):
    query = get_supabase().table("knowledge_base").select("*").ilike("title", f"%{q}%")
    if website_id:
        query = query.eq("website_id", website_id)
    res = query.execute()
    return res.data or []
