import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Body, Header
from pydantic import BaseModel

from database import get_supabase
from services.serper_service import serper_service

logger = logging.getLogger("backend.routers.keywords")

router = APIRouter(prefix="/keywords", tags=["Keyword Intelligence"])


class KeywordResearchRequest(BaseModel):
    seed_keyword: str
    website_id: Optional[str] = None
    location: Optional[str] = "United States"


class ClusterKeywordsRequest(BaseModel):
    keywords: List[str]
    website_id: Optional[str] = None


@router.get("")
@router.get("/")
async def list_keywords(
    website_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None)
):
    """List tracked keywords and ranking opportunities from Supabase."""
    supabase = get_supabase()
    try:
        q = supabase.table("keyword_proposals").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        if status:
            q = q.eq("status", status)
        res = q.order("created_at", desc=True).limit(limit).execute()
        return {"success": True, "data": res.data or []}
    except Exception as e:
        logger.warning(f"Error listing keywords: {e}")
        return {"success": True, "data": []}


@router.get("/list")
async def list_keywords_table(
    website_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Real DB query: keywords table WHERE website_id ORDER BY created_at DESC."""
    supabase = get_supabase()
    try:
        q = supabase.table("keywords").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(limit).execute()
        return {"success": True, "data": res.data or []}
    except Exception as e:
        # Fallback to keyword_proposals if keywords table not yet migrated
        logger.warning(f"keywords.list fallback: {e}")
        try:
            q = supabase.table("keyword_proposals").select("*")
            if website_id:
                q = q.eq("website_id", website_id)
            res = q.order("created_at", desc=True).limit(limit).execute()
            return {"success": True, "data": res.data or []}
        except Exception:
            return {"success": True, "data": []}


@router.post("/research")
async def research_keywords(payload: KeywordResearchRequest):
    """Perform real SERP keyword research and volume estimation via Serper.dev."""
    if not payload.seed_keyword.strip():
        raise HTTPException(status_code=400, detail="seed_keyword cannot be empty")

    results = await serper_service.get_keyword_suggestions(payload.seed_keyword)
    return {
        "success": True,
        "seed_keyword": payload.seed_keyword,
        "suggestions": results.get("suggestions", []),
        "related_searches": results.get("related", []),
        "people_also_ask": results.get("people_also_ask", []),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/cluster")
async def cluster_keywords(payload: ClusterKeywordsRequest):
    """Semantic clustering of keyword list into topic clusters."""
    if not payload.keywords:
        raise HTTPException(status_code=400, detail="keywords list cannot be empty")

    from ..services.cluster_engine import ClusterEngine
    engine = ClusterEngine(website_id=payload.website_id or "default")
    clusters = await engine.cluster_keywords_list(payload.keywords)
    return {"success": True, "clusters": clusters}


@router.get("/opportunities")
async def get_keyword_opportunities(website_id: Optional[str] = Query(None)):
    """Retrieve high-potential commercial and informational keyword gaps."""
    supabase = get_supabase()
    try:
        q = supabase.table("keyword_opportunities").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("priority_score", desc=True).limit(50).execute()
        return {"success": True, "data": res.data or []}
    except Exception:
        return {"success": True, "data": []}
