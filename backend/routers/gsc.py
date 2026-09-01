import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query, HTTPException

from database import get_supabase, call_nim_llm

logger = logging.getLogger("backend.routers.gsc")
router = APIRouter()


@router.get("/gsc/{website_id}/keywords")
@router.get("/gsc/keywords/{website_id}")
@router.get("/api/gsc/{website_id}/keywords")
@router.get("/api/gsc/keywords/{website_id}")
async def get_keywords(website_id: str):
    """Get keywords — from Supabase opportunities, GSC, or NVIDIA NIM extraction."""
    supabase = get_supabase()
    
    # 1. Try getting from keyword_opportunities table first
    try:
        result = (
            supabase.table("keyword_opportunities")
            .select("*")
            .eq("website_id", website_id)
            .order("opportunity_score", desc=True)
            .limit(20)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return {"success": True, "keywords": result.data, "data": result.data}
    except Exception:
        pass
    
    # 2. Try GSC if configured
    try:
        from ..services.gsc_service import GSCService
        gsc = GSCService()
        keywords = await gsc.fetch_keywords(website_id)
        if keywords:
            return {"success": True, "keywords": keywords, "data": keywords}
    except Exception:
        pass
    
    # 3. Empty return if no keywords found in DB or GSC
    return {"success": True, "keywords": [], "data": []}


@router.get("/gsc/{website_id}/performance")
@router.get("/gsc/roi/{website_id}")
@router.get("/api/gsc/{website_id}/performance")
@router.get("/api/gsc/roi/{website_id}")
async def get_performance(website_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get performance metrics for the website."""
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

    data = await get_keywords(website_id)
    keywords = data.get("keywords", []) if isinstance(data, dict) else data

    total_clicks = sum(k.get("clicks", 0) for k in keywords)
    total_impressions = sum(k.get("impressions", k.get("search_volume", 0)) for k in keywords)
    avg_ctr = round((total_clicks / max(1, total_impressions)) * 100, 2) if total_impressions > 0 else 0.0
    avg_position = round(sum(k.get("position", 0.0) for k in keywords) / max(1, len(keywords)), 1) if keywords else 0.0

    # Keyword opportunities (high impressions, CTR < 3%)
    opportunities = [
        k for k in keywords
        if float(k.get("ctr", 0.0)) < 0.030 and int(k.get("impressions", k.get("search_volume", 0))) > 1000
    ]

    # Query site_pages or content_log for real top pages
    top_pages = []
    try:
        supabase = get_supabase()
        pages = supabase.table("site_pages").select("url, title").eq("website_id", website_id).limit(5).execute().data or []
        for p in pages:
            top_pages.append({
                "page": p.get("url"),
                "title": p.get("title"),
                "clicks": 0,
                "impressions": 0,
                "ctr": "0.0%"
            })
    except Exception:
        pass

    return {
        "success": True,
        "website_id": website_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "average_ctr": avg_ctr,
        "average_position": avg_position,
        "keywords": keywords,
        "opportunities": opportunities,
        "top_pages": top_pages
    }
