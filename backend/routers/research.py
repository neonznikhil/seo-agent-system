import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.research")
router = APIRouter()


class ResearchIn(BaseModel):
    website_id: str
    topic: str
    query: Optional[str] = None


class ResearchOut(BaseModel):
    id: str
    website_id: str
    topic: str
    query: Optional[str] = None
    status: str
    result: Optional[dict] = None


class CompetitorIn(BaseModel):
    website_id: str
    domain: str
    notes: Optional[str] = None


class CompetitorOut(BaseModel):
    id: str
    website_id: str
    domain: str
    notes: Optional[str] = None


@router.get("/research")
async def list_research(website_id: Optional[str] = None):
    query = get_supabase().table("research").select("*")
    if website_id:
        query = query.eq("website_id", website_id)
    res = query.order("created_at", desc=True).execute()
    return res.data or []


@router.post("/research")
async def create_research(body: ResearchIn):
    res = get_supabase().table("research").insert(body.dict()).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create research")
    return row


@router.get("/research/competitors")
async def list_competitors(website_id: Optional[str] = None):
    query = get_supabase().table("competitors").select("*")
    if website_id:
        query = query.eq("website_id", website_id)
    res = query.execute()
    return res.data or []


@router.post("/research/competitors")
async def create_competitor(body: CompetitorIn):
    res = get_supabase().table("competitors").insert(body.dict()).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create competitor")
    return row
