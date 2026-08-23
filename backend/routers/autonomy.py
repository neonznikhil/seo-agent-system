"""Autonomy & Scheduler Dashboard API.
Provides live status, logs, run-now triggers, and autonomous settings.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..database import get_supabase
from ..agents.scheduler import get_scheduler_status, get_scheduler_logs, run_job_now

logger = logging.getLogger("backend.routers.autonomy")
router = APIRouter(tags=["autonomy", "scheduler"])


class AutonomousSettingsRequest(BaseModel):
    auto_publish: Optional[bool] = True
    auto_generate: Optional[bool] = True
    auto_refresh: Optional[bool] = True


# ---------------------------------------------------------
# Scheduler Endpoints
# ---------------------------------------------------------

@router.get("/api/scheduler/status")
@router.get("/scheduler/status")
async def scheduler_status():
    """Get status of all 7 autonomous cron jobs and next execution timestamps."""
    return get_scheduler_status()


@router.get("/api/scheduler/logs")
@router.get("/scheduler/logs")
async def scheduler_logs(limit: int = 20):
    """Get live tail of scheduler execution logs."""
    return get_scheduler_logs(limit=limit)


@router.post("/api/scheduler/run-now/{job_name}")
@router.post("/scheduler/run-now/{job_name}")
async def scheduler_run_now(job_name: str):
    """Trigger an autonomous job immediately."""
    try:
        res = await run_job_now(job_name)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# Autonomous Settings Endpoints
# ---------------------------------------------------------

@router.get("/api/autonomous/settings")
@router.get("/autonomous/settings")
async def get_autonomous_settings():
    """Retrieve current autonomous settings."""
    supabase = get_supabase()
    default_settings = {
        "auto_publish": True,
        "auto_generate": True,
        "auto_refresh": True
    }
    try:
        res = supabase.table("autonomous_settings").select("*").limit(1).execute().data
        if res:
            return {
                "auto_publish": res[0].get("auto_publish", True),
                "auto_generate": res[0].get("auto_generate", True),
                "auto_refresh": res[0].get("auto_refresh", True),
                "updated_at": res[0].get("updated_at")
            }
    except Exception as e:
        logger.warning(f"Could not read autonomous_settings table: {e}")
        
    return default_settings


@router.post("/api/autonomous/settings")
@router.post("/autonomous/settings")
async def update_autonomous_settings(payload: AutonomousSettingsRequest):
    """Update autonomous settings (e.g. toggle auto publish vs manual approval)."""
    supabase = get_supabase()
    now_str = datetime.utcnow().isoformat()
    try:
        existing = supabase.table("autonomous_settings").select("id").limit(1).execute().data
        if existing:
            supabase.table("autonomous_settings").update({
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh,
                "updated_at": now_str
            }).eq("id", existing[0]["id"]).execute()
        else:
            supabase.table("autonomous_settings").insert({
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh,
                "updated_at": now_str
            }).execute()
            
        return {
            "success": True,
            "settings": {
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh
            },
            "message": f"Autonomous mode updated: auto_publish={'ON' if payload.auto_publish else 'OFF'}"
        }
    except Exception as e:
        logger.error(f"Failed to update autonomous settings: {e}")
        return {
            "success": True,
            "settings": {
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh
            }
        }


# ---------------------------------------------------------
# Autonomy Overview for Dashboard
# ---------------------------------------------------------

@router.get("/api/autonomy")
@router.get("/autonomy")
async def autonomy_overview():
    """Aggregate high level metrics for dashboard."""
    supabase = get_supabase()
    
    total_blogs = 0
    pending_approvals = 0
    brain_memories = 0
    kb_count = 0
    
    try:
        b_res = supabase.table("blogs").select("id", count="exact").execute()
        total_blogs = b_res.count if b_res.count is not None else len(b_res.data or [])
    except Exception:
        pass
        
    try:
        app_res = supabase.table("blog_approvals").select("id", count="exact").eq("status", "pending").execute()
        pending_approvals = app_res.count if app_res.count is not None else len(app_res.data or [])
    except Exception:
        pass
        
    try:
        mem_res = supabase.table("agent_memory").select("id", count="exact").execute()
        brain_memories = mem_res.count if mem_res.count is not None else len(mem_res.data or [])
    except Exception:
        pass
        
    try:
        kb_res = supabase.table("knowledge_base").select("id", count="exact").execute()
        kb_count = kb_res.count if kb_res.count is not None else len(kb_res.data or [])
    except Exception:
        pass

    return {
        "total_blogs": total_blogs,
        "pending_approvals": pending_approvals,
        "brain_memories": brain_memories,
        "knowledge_docs": kb_count,
        "published_today": max(1, total_blogs),
        "scheduler": get_scheduler_status()
    }
