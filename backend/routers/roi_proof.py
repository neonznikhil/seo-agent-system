"""Router for ROI Proof & 28-Day Post-Fix Impact Verification."""

import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

try:
    from backend.services.roi_proof_service import (
        list_tracked_fixes,
        calculate_roi_summary,
        track_new_fix,
    )
except ImportError:
    from services.roi_proof_service import (
        list_tracked_fixes,
        calculate_roi_summary,
        track_new_fix,
    )

logger = logging.getLogger("backend.routers.roi_proof")

router = APIRouter(prefix="/api/roi-proof", tags=["ROI Proof & Impact"])


class TrackFixRequest(BaseModel):
    target_url: str
    fix_title: str
    category: str
    target_keyword: str
    baseline_position: float
    baseline_monthly_clicks: int
    action_id: Optional[str] = None


@router.get("/{website_id}/proof-list")
async def get_site_proof_list(website_id: str):
    """Retrieve 28-day post-fix performance list demonstrating traffic and rank lifts."""
    try:
        fixes = list_tracked_fixes(website_id)
        return {"website_id": website_id, "tracked_fixes": fixes, "count": len(fixes)}
    except Exception as e:
        logger.error(f"Error fetching ROI proof list for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{website_id}/summary")
async def get_site_roi_summary(website_id: str):
    """Calculate aggregate ROI multiple, monthly traffic gain, and pipeline value."""
    try:
        return calculate_roi_summary(website_id)
    except Exception as e:
        logger.error(f"Error calculating ROI summary for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{website_id}/track")
async def register_new_tracked_fix(website_id: str, payload: TrackFixRequest):
    """Register a new shipped fix to track for 28 days."""
    try:
        fix = track_new_fix(
            website_id=website_id,
            target_url=payload.target_url,
            fix_title=payload.fix_title,
            category=payload.category,
            target_keyword=payload.target_keyword,
            baseline_position=payload.baseline_position,
            baseline_monthly_clicks=payload.baseline_monthly_clicks,
            action_id=payload.action_id,
        )
        return {"status": "success", "tracked_fix": fix}
    except Exception as e:
        logger.error(f"Error registering tracked fix for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
