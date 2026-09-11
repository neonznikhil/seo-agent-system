"""Indexation endpoints: check now, latest summary, gate state.

All responses are honest about provenance: rate null means unknown
(GSC not connected / no sitemap found), never 0% or a passing gate.
"""
import logging
from fastapi import APIRouter, HTTPException

from database import get_supabase

logger = logging.getLogger("backend.routers.indexation")
router = APIRouter()


@router.post("/indexation/{website_id}/check")
@router.post("/api/indexation/{website_id}/check")
async def run_indexation_check(website_id: str):
    """Run a fresh indexation check for a site and persist it."""
    from services.indexation_service import check_indexation
    result = await check_indexation(website_id)
    if result.get("error") and result.get("method") == "unavailable" and not result.get("checked_at"):
        raise HTTPException(status_code=404, detail=result["error"])
    return {"success": True, "data": result}


@router.get("/indexation/{website_id}/latest")
@router.get("/api/indexation/{website_id}/latest")
async def latest_indexation(website_id: str):
    """Latest persisted indexation check, or an explicit no-data response."""
    from services.indexation_service import get_indexation_summary
    summary = await get_indexation_summary(website_id)
    return {"success": True, "website_id": website_id, **summary}


@router.get("/indexation/{website_id}/gate")
@router.get("/api/indexation/{website_id}/gate")
async def indexation_gate(website_id: str):
    """Current gate state for a site: pass | blocked | warn | unknown."""
    from services.indexation_service import indexation_gate_check
    gate = await indexation_gate_check(website_id)
    return {"success": True, "website_id": website_id, **gate}


@router.get("/indexation/{website_id}/history")
@router.get("/api/indexation/{website_id}/history")
async def indexation_history(website_id: str, limit: int = 30):
    """Check history for trend display. Empty list means no checks yet."""
    supabase = get_supabase()
    try:
        rows = (
            supabase.table("indexation_checks")
            .select("checked_at, submitted_pages, indexed_pages, indexation_rate, method, gate_passed")
            .eq("website_id", website_id)
            .order("checked_at", desc=True)
            .limit(max(1, min(limit, 100)))
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning(f"[Indexation] history note: {e}")
        rows = []
    if not rows:
        try:
            from services.local_store import list_local_indexation_checks
            rows = list_local_indexation_checks(website_id, limit=limit)
        except Exception:
            rows = []
    return {"success": True, "website_id": website_id, "history": rows, "total": len(rows)}
