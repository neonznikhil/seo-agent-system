import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from database import get_supabase

logger = logging.getLogger("backend.routers.report")

router = APIRouter(prefix="/report", tags=["Executive Reports"])


@router.get("/weekly")
async def get_weekly_report(website_id: Optional[str] = Query(None)):
    """Retrieve the latest weekly autonomous executive report."""
    supabase = get_supabase()
    try:
        q = supabase.table("weekly_reports").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(1).execute()
        if res.data:
            return {"success": True, "report": res.data[0]}
    except Exception as e:
        logger.warning(f"Error fetching weekly report: {e}")

    # Return structured live summary from tasks table
    try:
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        tq = supabase.table("tasks").select("*").gte("created_at", cutoff)
        if website_id:
            tq = tq.eq("website_id", website_id)
        tasks = tq.execute().data or []
        
        completed = [t for t in tasks if t.get("status") == "completed"]
        failed = [t for t in tasks if t.get("status") == "failed"]
        
        return {
            "success": True,
            "report": {
                "website_id": website_id or "default",
                "period": "Past 7 Days",
                "total_tasks_run": len(tasks),
                "completed_tasks": len(completed),
                "failed_tasks": len(failed),
                "success_rate": round((len(completed) / max(1, len(tasks))) * 100, 1) if tasks else 100.0,
                "created_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        return {"success": True, "report": None, "error": str(e)}


@router.get("/seo")
async def get_seo_report(website_id: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100)):
    """Real DB query: seo_reports WHERE website_id ORDER BY created_at DESC."""
    supabase = get_supabase()
    try:
        q = supabase.table("seo_reports").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(limit).execute()
        return {"success": True, "data": res.data or []}
    except Exception as e:
        logger.warning(f"seo report query note: {e}")
        return {"success": True, "data": []}


@router.get("/summary")
async def get_executive_summary(website_id: Optional[str] = Query(None)):
    """Get high-level summary of articles published, backlinks acquired, and health."""
    supabase = get_supabase()
    try:
        cq = supabase.table("content_log").select("id, status")
        if website_id:
            cq = cq.eq("website_id", website_id)
        content = cq.execute().data or []

        bq = supabase.table("backlink_opportunities").select("id, status")
        if website_id:
            bq = bq.eq("website_id", website_id)
        backlinks = bq.execute().data or []

        published = sum(1 for c in content if c.get("status") in ("published", "approved"))
        pending = sum(1 for c in content if c.get("status") not in ("published", "approved"))

        return {
            "success": True,
            "website_id": website_id or "default",
            "published_articles": published,
            "pending_approvals": pending,
            "total_backlink_targets": len(backlinks),
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"success": True, "error": str(e)}
