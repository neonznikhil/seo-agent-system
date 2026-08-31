"""Rankings API Router.
Endpoints for fetching Google ranking performance metrics, trigger checks, and view history.
"""

from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from ..database import get_supabase, set_account_context
from ..middleware.auth import get_current_account_id
from ..services.rank_tracker import (
    get_tracked_rankings,
    check_keyword_rankings,
    track_published_post,
)

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.get("")
async def list_rankings(
    request: Request,
    website_id: Optional[str] = Query(None, description="Website ID"),
):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    target_wid = website_id or "default"
    rankings = get_tracked_rankings(target_wid)
    return {
        "website_id": target_wid,
        "total_tracked": len(rankings),
        "rankings": rankings,
    }


@router.post("/check")
async def trigger_rank_check(
    request: Request,
    website_id: Optional[str] = Query(None, description="Website ID"),
):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    target_wid = website_id or "default"
    updated = await check_keyword_rankings(target_wid)
    return {
        "website_id": target_wid,
        "updated_count": len(updated),
        "rankings": updated,
    }
