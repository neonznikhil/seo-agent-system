"""Rankings API Router.
Endpoints for fetching Google ranking performance metrics, trigger checks, and view history.
"""

from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from database import get_supabase, set_account_context
from middleware.auth import get_current_account_id
from services.rank_tracker import (
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
    from services.run_service import run_with_envelope

    def _snapshot(updated):
        rows = updated.get("result", updated) if isinstance(updated, dict) else updated
        rows = rows if isinstance(rows, list) else updated.get("rankings", [])
        ids = []
        for r in rows or []:
            if isinstance(r, dict) and (r.get("keyword") or r.get("query")):
                ids.append(f"{r.get('keyword') or r.get('query')}:pos={r.get('current_position')}")
        return {"issue_ids": ids}

    enveloped = await run_with_envelope(
        target_wid, "rank_tracking_check",
        lambda: check_keyword_rankings(target_wid),
        _snapshot)
    rankings = enveloped.get("result", []) if isinstance(enveloped, dict) else []
    return {
        "website_id": target_wid,
        "updated_count": len(rankings) if isinstance(rankings, list) else 0,
        "rankings": rankings,
        "run": enveloped.get("_run") if isinstance(enveloped, dict) else None,
    }
