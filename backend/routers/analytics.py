import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.analytics")

router = APIRouter(prefix="/analytics", tags=["Analytics & Telemetry"])


@router.get("/overview")
async def get_analytics_overview(website_id: Optional[str] = Query(None), days: int = Query(30, ge=1, le=365)):
    """Retrieve aggregated organic search performance from GSC and GA4 records."""
    supabase = get_supabase()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    total_clicks = 0
    total_impressions = 0
    avg_ctr = 0.0
    avg_position = 0.0
    
    try:
        q = supabase.table("gsc_metrics").select("*").gte("created_at", cutoff)
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(200).execute()
        rows = res.data or []
        
        if rows:
            total_clicks = sum(r.get("clicks", 0) for r in rows)
            total_impressions = sum(r.get("impressions", 0) for r in rows)
            avg_ctr = round((total_clicks / max(1, total_impressions)) * 100, 2)
            avg_position = round(sum(r.get("position", 0.0) for r in rows) / len(rows), 1)
    except Exception as e:
        logger.warning(f"Error querying analytics: {e}")

    return {
        "success": True,
        "website_id": website_id,
        "days": days,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": avg_ctr,
        "avg_position": avg_position,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/conversions")
async def get_conversion_metrics(website_id: Optional[str] = Query(None)):
    """Retrieve GA4 organic conversion events and goal completions."""
    supabase = get_supabase()
    try:
        q = supabase.table("ga4_conversions").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(50).execute()
        return {"success": True, "data": res.data or []}
    except Exception:
        return {"success": True, "data": []}


@router.get("/traffic-breakdown")
async def get_traffic_breakdown(website_id: Optional[str] = Query(None)):
    """Retrieve top landing pages and keyword traffic drivers."""
    supabase = get_supabase()
    try:
        q = supabase.table("content_performance").select("title, slug, clicks, impressions, rank, updated_at")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("clicks", desc=True).limit(20).execute()
        return {"success": True, "data": res.data or []}
    except Exception:
        return {"success": True, "data": []}
