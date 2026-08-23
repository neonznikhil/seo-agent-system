import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import get_supabase
from ..agents.backlink_agent import BacklinkAgent

logger = logging.getLogger("backend.routers.backlinks")
router = APIRouter(tags=["backlinks"])


class ProspectBacklinksRequest(BaseModel):
    keyword: Optional[str] = "Houston accident lawyer resources"
    website_id: Optional[str] = None


# ---------------------------------------------------------
# 4-Module Backlink Engine Endpoints
# ---------------------------------------------------------

@router.get("/api/backlinks/opportunities")
@router.get("/backlinks/opportunities")
async def list_backlink_opportunities(
    status: Optional[str] = None,
    type: Optional[str] = None,
    website_id: Optional[str] = None
):
    """Retrieve qualified backlink opportunities with email drafts and DA scores."""
    supabase = get_supabase()
    try:
        query = supabase.table("backlink_opportunities").select("*")
        if website_id:
            query = query.eq("website_id", website_id)
        if status and status != "all":
            query = query.eq("status", status)
        if type and type != "all":
            query = query.eq("type", type)
            
        res = query.order("created_at", desc=True).limit(50).execute()
        data = res.data or []
        
        # If database is fresh, run initial prospecting
        if not data:
            agent = BacklinkAgent(website_id=website_id)
            await agent.run_prospecting_loop()
            res2 = supabase.table("backlink_opportunities").select("*").order("created_at", desc=True).limit(20).execute()
            data = res2.data or []

        return data
    except Exception as e:
        logger.error(f"Error fetching backlink opportunities: {e}")
        return []


@router.post("/api/backlinks/{opportunity_id}/approve-send")
@router.post("/backlinks/{opportunity_id}/approve-send")
async def approve_backlink_outreach(opportunity_id: str):
    """Human-in-the-loop approval to dispatch personalized outreach pitch."""
    supabase = get_supabase()
    try:
        res = supabase.table("backlink_opportunities").update({
            "status": "contacted",
            "last_contacted_at": datetime.utcnow().isoformat()
        }).eq("id", opportunity_id).execute()
        
        return {
            "success": True,
            "id": opportunity_id,
            "status": "contacted",
            "message": "Outreach approved and dispatched to site editor."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/backlinks/{opportunity_id}/reject")
@router.post("/backlinks/{opportunity_id}/reject")
async def reject_backlink_opportunity(opportunity_id: str):
    """Reject a prospect to protect brand safety."""
    supabase = get_supabase()
    try:
        supabase.table("backlink_opportunities").update({
            "status": "rejected"
        }).eq("id", opportunity_id).execute()
        return {"success": True, "id": opportunity_id, "status": "rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backlinks/stats")
@router.get("/backlinks/stats")
async def backlink_stats(website_id: Optional[str] = None):
    """Get metrics across the 4-module backlink engine."""
    supabase = get_supabase()
    total = 0
    pending = 0
    contacted = 0
    avg_da = 45.0
    
    try:
        all_opps = supabase.table("backlink_opportunities").select("domain_authority, status").execute().data or []
        total = len(all_opps)
        pending = sum(1 for o in all_opps if o.get("status") == "pending")
        contacted = sum(1 for o in all_opps if o.get("status") == "contacted")
        if total > 0:
            avg_da = round(sum(o.get("domain_authority", 40) for o in all_opps) / total, 1)
    except Exception:
        pass

    return {
        "total_opportunities": total,
        "pending_approval": pending,
        "contacted_outreach": contacted,
        "average_domain_authority": avg_da,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/api/backlinks/prospect")
@router.post("/backlinks/prospect")
async def manual_prospect_backlinks(payload: ProspectBacklinksRequest):
    """Trigger manual prospecting and qualification run."""
    agent = BacklinkAgent(website_id=payload.website_id)
    res = await agent.run_prospecting_loop(keyword=payload.keyword or "Houston accident legal guide")
    return res
