"""Router for ranked prioritized action list.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
try:
    from backend.services.action_prioritization_service import (
        get_top_10_actions,
        execute_prioritized_action,
    )
except ImportError:
    from services.action_prioritization_service import (
        get_top_10_actions,
        execute_prioritized_action,
    )

router = APIRouter(prefix="/api/actions", tags=["Prioritized Actions"])


class ExecuteActionRequest(BaseModel):
    author: Optional[str] = "Admin Operator"


@router.get("/{website_id}/top-10")
@router.get("/{website_id}/top10")
def top_10_actions(website_id: str):
    """Retrieve the ranked Top 10 actions to take now, sorted by estimated traffic impact."""
    return get_top_10_actions(website_id)


@router.post("/{website_id}/{action_id}/execute")
def apply_action(website_id: str, action_id: str, payload: Optional[ExecuteActionRequest] = None):
    """Execute a prioritized action with guardrail safety snapshotting."""
    author = payload.author if payload else "Admin Operator"
    result = execute_prioritized_action(website_id, action_id, author=author)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/{website_id}/{action_id}/dismiss")
def dismiss_action(website_id: str, action_id: str):
    """Dismiss or snooze a prioritized action."""
    return {
        "status": "success",
        "message": f"Action {action_id} snoozed. Will recalculate on next crawl.",
        "action_id": action_id,
        "website_id": website_id,
    }
