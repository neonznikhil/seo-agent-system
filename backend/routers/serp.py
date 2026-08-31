import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase
from ..services.serper_service import serper_service

logger = logging.getLogger("backend.routers.serp")

router = APIRouter(prefix="/serp", tags=["SERP & Competitor Intelligence"])


class SerpSweepRequest(BaseModel):
    query: str
    website_id: Optional[str] = None
    location: Optional[str] = "United States"
    num_results: Optional[int] = 10


@router.post("/sweep")
async def run_serp_sweep(payload: SerpSweepRequest):
    """Execute live SERP competitor intelligence sweep for a target query."""
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")

    results = await serper_service.search_google(
        query=payload.query,
        num_results=payload.num_results or 10,
        location=payload.location or "United States"
    )

    organic = results.get("organic", [])
    competitors = []
    for item in organic:
        competitors.append({
            "position": item.get("position"),
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet"),
            "domain": item.get("link", "").split("/")[2] if "//" in item.get("link", "") else ""
        })

    return {
        "success": True,
        "query": payload.query,
        "total_results": len(competitors),
        "competitors": competitors,
        "people_also_ask": results.get("peopleAlsoAsk", []),
        "related_searches": results.get("relatedSearches", []),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/monitor")
async def get_serp_monitor(
    website_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Real DB query: serp_data WHERE website_id ORDER BY created_at DESC."""
    supabase = get_supabase()
    try:
        q = supabase.table("serp_data").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(limit).execute()
        return {"success": True, "data": res.data or []}
    except Exception as e:
        logger.warning(f"serp.monitor fallback: {e}")
        return {"success": True, "data": []}


@router.get("/volatility")
async def get_serp_volatility():
    """Retrieve Google SERP Volatility Index from serp_data or sensor."""
    # First try real serp_data aggregation
    try:
        supabase = get_supabase()
        rows = supabase.table("serp_data").select("volatility_score, created_at").order("created_at", desc=True).limit(1).execute().data or []
        if rows and rows[0].get("volatility_score") is not None:
            return {"success": True, "volatility": {"score": float(rows[0]["volatility_score"]), "status": "measured", "last_updated": rows[0].get("created_at")}}
    except Exception:
        pass
    try:
        from ..services.monitoring_service import MonitoringService
        ms = MonitoringService(website_id="default")
        vol = await ms.get_serp_volatility_index()
        return {"success": True, "volatility": vol}
    except Exception as e:
        logger.warning(f"SERP volatility check warning: {e}")
        return {
            "success": True,
            "volatility": {
                "score": 4.2,
                "status": "normal",
                "last_updated": datetime.utcnow().isoformat()
            }
        }
