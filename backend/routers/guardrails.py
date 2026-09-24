"""Router for Guardrails, Previews, Audit Changelog, and 1-Click Rollback."""

import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

try:
    from backend.services.change_guardrail_service import (
        list_changelog,
        get_diff_details,
        rollback_change,
        compute_unified_diff,
        check_ymyl_risk,
    )
except ImportError:
    from services.change_guardrail_service import (
        list_changelog,
        get_diff_details,
        rollback_change,
        compute_unified_diff,
        check_ymyl_risk,
    )

logger = logging.getLogger("backend.routers.guardrails")

router = APIRouter(prefix="/api/guardrails", tags=["Guardrails & Rollback"])


class PreviewDiffRequest(BaseModel):
    before: str
    after: str


class RollbackRequest(BaseModel):
    author: Optional[str] = "Admin Operator"


@router.get("/{website_id}/changelog")
async def get_website_changelog(website_id: str):
    """Retrieve full audit trail of changes applied to this site."""
    try:
        changes = list_changelog(website_id)
        return {"website_id": website_id, "changes": changes, "count": len(changes)}
    except Exception as e:
        logger.error(f"Error fetching changelog for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/change/{change_id}")
async def get_change_diff_view(change_id: str):
    """Get visual diff and YMYL safety check for a specific change."""
    details = get_diff_details(change_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    return details


@router.post("/change/{change_id}/rollback")
async def execute_rollback(change_id: str, payload: Optional[RollbackRequest] = None):
    """Instantly roll back a live site modification."""
    author = payload.author if payload and payload.author else "Admin Operator"
    result = rollback_change(change_id, author=author)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/preview-diff")
async def generate_diff_preview(payload: PreviewDiffRequest):
    """Compute on-the-fly diff and YMYL safety verification for any proposal."""
    diff = compute_unified_diff(payload.before, payload.after)
    ymyl = check_ymyl_risk(payload.before, payload.after)
    return {
        "diff": diff,
        "ymyl_safety": ymyl,
    }
