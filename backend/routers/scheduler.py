"""Scheduler status router — single authority Asia/Kolkata (Phase 1)."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from database import get_supabase

logger = logging.getLogger("backend.routers.scheduler")

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status")
async def get_scheduler_status_endpoint():
    """APScheduler jobs status — single authority Asia/Kolkata."""
    try:
        from agents.scheduler import get_scheduler_status
        status = get_scheduler_status()
        return {"success": True, **status}
    except Exception as e:
        logger.warning(f"Scheduler status error: {e}")
        return {"success": True, "running": False, "timezone": "Asia/Kolkata", "jobs": [], "jobs_count": 0, "error": str(e)}


@router.get("/logs")
async def get_scheduler_logs_endpoint(limit: int = Query(20, ge=1, le=100)):
    """Circular log buffer for dashboard polling."""
    try:
        from agents.scheduler import get_scheduler_logs
        logs = get_scheduler_logs(limit=limit)
        return {"success": True, "logs": logs}
    except Exception as e:
        return {"success": True, "logs": [], "error": str(e)}


@router.get("/overview")
async def get_scheduler_overview(website_id: Optional[str] = Query(None)):
    """Scheduler overview with pending tasks."""
    supabase = get_supabase()
    try:
        from agents.scheduler import get_scheduler_status
        sched = get_scheduler_status()
    except Exception:
        sched = {"running": False, "jobs": []}

    # Query pending_fixes and brain_daily_jobs for real queue depth
    pending_fixes = 0
    daily_jobs_today = 0
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        pf = supabase.table("pending_fixes").select("id", count="exact").gte("created_at", f"{today}T00:00:00").execute()
        pending_fixes = getattr(pf, "count", len(pf.data or [])) if pf else 0
        dj = supabase.table("brain_daily_jobs").select("id", count="exact").gte("run_at", f"{today}T00:00:00").execute()
        daily_jobs_today = getattr(dj, "count", len(dj.data or [])) if dj else 0
    except Exception:
        pass

    return {
        "success": True,
        "scheduler": sched,
        "pending_fixes": pending_fixes,
        "daily_jobs_today": daily_jobs_today,
        "website_id": website_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
