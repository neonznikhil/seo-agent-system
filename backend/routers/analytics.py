import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from database import get_supabase

logger = logging.getLogger("backend.routers.analytics")

router = APIRouter(prefix="/analytics", tags=["Analytics & Telemetry"])


def _clicks_fallback(row: Dict[str, Any]) -> int:
    """Clicks for a row, falling back to an estimated `views // 3` ONLY when the
    `clicks` field is genuinely absent.

    `r.get("clicks", 0) or r.get("views", 0) // 3` is wrong: `0 or X` evaluates
    to X, so a real zero-click row was silently replaced by an invented number.
    """
    clicks = row.get("clicks")
    if clicks is not None:
        try:
            return int(clicks)
        except (TypeError, ValueError):
            pass
    views = row.get("views")
    if views is not None:
        try:
            return int(views) // 3
        except (TypeError, ValueError):
            return 0
    return 0


@router.get("/overview")
async def get_analytics_overview(website_id: Optional[str] = Query(None), days: int = Query(30, ge=1, le=365)):
    """Retrieve aggregated organic search performance from analytics_data (real DB)."""
    supabase = get_supabase()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    total_clicks = 0
    total_impressions = 0
    avg_ctr = 0.0
    avg_position = 0.0
    # A failed read must never be rendered as "traffic collapsed to zero".
    data_available = True
    read_error: Optional[str] = None

    # Primary: analytics_data table (spec requirement)
    try:
        q = supabase.table("analytics_data").select("*").gte("created_at", cutoff)
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(200).execute()
        rows = res.data or []

        if rows:
            total_clicks = sum(_clicks_fallback(r) for r in rows)
            total_impressions = sum(r.get("impressions", 0) or r.get("views", 0) for r in rows)
            if total_impressions:
                avg_ctr = round((total_clicks / max(1, total_impressions)) * 100, 2)
            positions = [float(r.get("position") or r.get("avg_position") or 0) for r in rows if r.get("position") or r.get("avg_position")]
            if positions:
                avg_position = round(sum(positions) / len(positions), 1)

        # Fallback to gsc_metrics if analytics_data empty
        if not rows:
            q2 = supabase.table("gsc_metrics").select("*").gte("created_at", cutoff)
            if website_id:
                q2 = q2.eq("website_id", website_id)
            res2 = q2.order("created_at", desc=True).limit(200).execute()
            rows2 = res2.data or []
            if rows2:
                total_clicks = sum(r.get("clicks", 0) for r in rows2)
                total_impressions = sum(r.get("impressions", 0) for r in rows2)
                avg_ctr = round((total_clicks / max(1, total_impressions)) * 100, 2)
                avg_position = round(sum(r.get("position", 0.0) for r in rows2) / len(rows2), 1)
    except Exception as e:
        logger.warning(f"Error querying analytics: {e}")
        data_available = False
        read_error = str(e)[:200]

    response: Dict[str, Any] = {
        "success": data_available,
        "website_id": website_id,
        "days": days,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": avg_ctr,
        "avg_position": avg_position,
        # Consumers must be able to tell "couldn't read" from "genuinely zero".
        "data_available": data_available,
        "timestamp": datetime.utcnow().isoformat()
    }
    if not data_available:
        response["error"] = read_error
        response["message"] = "Analytics data could not be read; the zeros above are not measured values."
    return response


@router.get("/conversions")
async def get_conversion_metrics(website_id: Optional[str] = Query(None)):
    """Retrieve GA4 organic conversion events and goal completions."""
    supabase = get_supabase()
    try:
        q = supabase.table("ga4_conversions").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(50).execute()
        return {"success": True, "data": res.data or [], "data_available": True}
    except Exception as e:
        logger.warning(f"Error querying GA4 conversions: {e}")
        return {
            "success": False,
            "data": [],
            "data_available": False,
            "error": str(e)[:200],
            "message": "Conversions could not be read; the empty list is not 'no conversions'.",
        }


@router.get("/traffic-breakdown")
async def get_traffic_breakdown(website_id: Optional[str] = Query(None)):
    """Retrieve top landing pages and keyword traffic drivers."""
    supabase = get_supabase()
    try:
        q = supabase.table("content_performance").select("title, slug, clicks, impressions, rank, updated_at")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("clicks", desc=True).limit(20).execute()
        return {"success": True, "data": res.data or [], "data_available": True}
    except Exception as e:
        logger.warning(f"Error querying traffic breakdown: {e}")
        return {
            "success": False,
            "data": [],
            "data_available": False,
            "error": str(e)[:200],
            "message": "Traffic breakdown could not be read; the empty list is not 'no traffic'.",
        }


try:
    from services.analytics_service import AnalyticsService
except (ImportError, ValueError):
    from backend.services.analytics_service import AnalyticsService


@router.get("/summary")
async def get_analytics_summary(website_id: Optional[str] = Query(None)):
    """Aggregate high level metrics for the dashboard Analytics tab — real DB only."""
    return await AnalyticsService.get_analytics_summary(website_id)


@router.get("/content-gaps")
async def get_content_gaps(website_id: Optional[str] = Query(None)):
    """Identify high-impression, low-CTR queries ranking in positions 5-15."""
    gaps = await AnalyticsService.get_content_gaps(website_id)
    return {"success": True, "data": gaps, "total": len(gaps)}


@router.get("/decaying-content")
async def get_decaying_content(website_id: Optional[str] = Query(None)):
    """Find blog posts where views dropped > 30%."""
    decaying = await AnalyticsService.get_decaying_content(website_id)
    return {"success": True, "data": decaying, "total": len(decaying)}


class SyncGscRequest(BaseModel):
    website_id: Optional[str] = None


@router.post("/sync-gsc")
async def sync_gsc_data(website_id: Optional[str] = Query(None), body: Optional[SyncGscRequest] = None):
    """Pull live keyword rows from GSC API and persist into analytics_data."""
    target_id = website_id or (body.website_id if body else None)
    return await AnalyticsService.sync_gsc_data(target_id)
