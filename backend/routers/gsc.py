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
    """Get keywords — from Supabase opportunities first, then live GSC.

    Always reports WHY the result looks the way it does via the
    `connected` flag. Never returns [] without indicating why.
    """
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
            return {"success": True, "connected": True, "source": "keyword_opportunities", "keywords": result.data, "data": result.data}
    except Exception:
        pass

    # 2. Try live GSC via the real GSCService API.
    # NOTE: GSCService has no `fetch_keywords` method — the real entry
    # point is get_keyword_performance(). Do not reintroduce the old call.
    try:
        from services.gsc_service import GSCService
        site_url = None
        try:
            site_row = supabase.table("websites").select("url, domain").eq("id", website_id).limit(1).execute().data or []
            if site_row:
                site_url = site_row[0].get("url") or site_row[0].get("domain")
        except Exception:
            site_url = None
        gsc = GSCService(website_url=site_url)
        if not gsc.is_connected():
            return {"success": True, "connected": False, "keywords": [], "data": [],
                    "message": "GSC not connected. Add credentials in /connectors."}
        perf = await gsc.get_keyword_performance()
        if perf.get("error") and not perf.get("keywords"):
            return {"success": True, "connected": False, "keywords": [], "data": [],
                    "message": f"GSC query failed: {perf.get('error')}"}
        keywords = perf.get("keywords", [])
        if keywords:
            return {"success": True, "connected": True, "source": "gsc", "keywords": keywords, "data": keywords}
        return {"success": True, "connected": True, "source": "gsc", "keywords": [], "data": [],
                "message": "GSC connected but returned no keyword rows for this date range."}
    except Exception as e:
        logger.warning(f"[GSC] keywords lookup note: {e}")

    # 3. Honest empty: nothing in DB and GSC unavailable/misconfigured.
    return {"success": True, "connected": False, "keywords": [], "data": [],
            "message": "No keyword data. Connect GSC credentials in /connectors or run keyword mining first."}


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
    connected = bool(data.get("connected")) if isinstance(data, dict) else False

    if not keywords:
        # HONEST: no averages over an empty list. Say why there is no data.
        return {
            "success": True,
            "connected": connected,
            "website_id": website_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_clicks": None,
            "total_impressions": None,
            "average_ctr": None,
            "average_position": None,
            "keywords": [],
            "opportunities": [],
            "top_pages": [],
            "message": data.get("message", "No performance data available.") if isinstance(data, dict) else "No performance data available.",
        }

    total_clicks = sum(k.get("clicks", 0) for k in keywords)
    total_impressions = sum(k.get("impressions", k.get("search_volume", 0)) for k in keywords)
    avg_ctr = round((total_clicks / max(1, total_impressions)) * 100, 2) if total_impressions > 0 else 0.0
    avg_position = round(sum(k.get("position", 0.0) for k in keywords) / max(1, len(keywords)), 1) if keywords else 0.0

    # Keyword opportunities (high impressions, CTR < 3%)
    opportunities = [
        k for k in keywords
        if float(k.get("ctr", 0.0)) < 0.030 and int(k.get("impressions", k.get("search_volume", 0))) > 1000
    ]

    # Real top pages only: pages that actually have measured GSC data.
    # Never zero-fill clicks/impressions — a page without measurements
    # is absent from this list, not present with invented zeros.
    top_pages = []
    try:
        supabase = get_supabase()
        pages = supabase.table("site_pages").select("url, title, clicks, impressions, ctr").eq("website_id", website_id).limit(5).execute().data or []
        for p in pages:
            if p.get("clicks") is None and p.get("impressions") is None:
                continue
            top_pages.append({
                "page": p.get("url"),
                "title": p.get("title"),
                "clicks": p.get("clicks"),
                "impressions": p.get("impressions"),
                "ctr": p.get("ctr"),
            })
    except Exception:
        pass

    return {
        "success": True,
        "connected": connected,
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
