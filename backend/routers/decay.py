import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger("backend.routers.decay")

router = APIRouter()


@router.post("/decay/{website_id}/detect")
@router.post("/api/decay/{website_id}/detect")
async def detect_decay(website_id: str, manual: bool = False):
    """Detect content decay from live GSC data."""
    from services.decay_detector_service import DecayDetectorService
    
    service = DecayDetectorService(website_id)
    result = await service.detect_decay(website_id, auto_alert=True)
    return {"success": True, "data": result}


@router.get("/decay/{website_id}/list")
@router.get("/api/decay/{website_id}/list")
@router.get("/decay")
@router.get("/api/decay")
async def list_decay(website_id: Optional[str] = None, status: str = "detected"):
    """List decay logs by status."""
    from database import get_supabase
    
    supabase = get_supabase()
    q = supabase.table("content_decay_logs").select("*")
    if website_id:
        q = q.eq("website_id", website_id)
    if status and status != "all":
        q = q.eq("status", status)
        
    decay_logs = q.order("detected_at", desc=True).limit(50).execute().data or []
    
    for log in decay_logs:
        pct = float(log.get("decay_percent") or 24.5)
        log["decay_score"] = int(pct)
        log["severity"] = "critical" if pct > 40 else ("high" if pct > 20 else "medium")
    
    return {"success": True, "data": decay_logs, "decay_logs": decay_logs, "total": len(decay_logs)}


@router.post("/decay/{decay_id}/diagnose")
@router.post("/api/decay/{decay_id}/diagnose")
async def diagnose_decay(decay_id: str, website_id: str):
    """Run full diagnosis on decayed content."""
    from services.decay_diagnosis_service import DecayDiagnosisService
    
    service = DecayDiagnosisService(website_id)
    result = await service.diagnose(decay_id)
    return {"success": True, "data": result}


@router.post("/decay/{decay_id}/refresh")
@router.post("/api/decay/{decay_id}/refresh")
async def queue_refresh(decay_id: str, website_id: str):
    """Queue content for auto-refresh - starts 10-phase pipeline."""
    from agents.refresh_agent import run_refresh_pipeline
    
    result = await run_refresh_pipeline(decay_id, website_id)
    
    return {
        "success": True,
        "status": "refresh_queued",
        "content_id": result.get("content_id"),
        "decay_log_id": decay_id,
        "original_url": result.get("original_url"),
        "phase": 1,
        "total_phases": 10
    }


@router.get("/decay/{website_id}/pipeline/{content_id}")
async def get_refresh_pipeline(website_id: str, content_id: str):
    """Get full pipeline progress (111 steps) for refresh."""
    from database import get_supabase
    
    supabase = get_supabase()
    logs = supabase.table("content_pipeline_logs").select("*").eq("content_id", content_id).eq("website_id", website_id).order("step_number").execute().data or []
    
    expert_reviews = supabase.table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    
    from agents.pipeline_config import TOTAL_STEPS, PHASES
    completed_steps = len([l for l in logs if l.get("status") == "completed"])
    
    phase_progress = {}
    for phase in PHASES:
        phase_logs = [l for l in logs if l.get("phase") == phase["name"]]
        completed = len([l for l in phase_logs if l.get("status") == "completed"])
        phase_progress[phase["name"]] = {
            "current": completed,
            "total": phase["steps"],
            "status": "completed" if completed == phase["steps"] else "running" if completed > 0 else "pending"
        }
    
    return {
        "content_id": content_id,
        "progress_percent": round((completed_steps / TOTAL_STEPS) * 100, 1) if TOTAL_STEPS > 0 else 0,
        "total_steps": TOTAL_STEPS, "completed_steps": completed_steps,
        "phases": phase_progress,
        "logs": logs,
        "expert_reviews": expert_reviews
    }


@router.post("/decay/{decay_id}/approve-publish", dependencies=[])
async def approve_publish(decay_id: str, website_id: str, request: Request = None):
    """Approve and publish refresh - requires X-User-Id."""
    from database import get_supabase
    from middleware.human_gate import require_human_for_request
    
    user_id = await require_human_for_request(request)
    
    supabase = get_supabase()
    
    decay = supabase.table("content_decay_logs").select("*").eq("id", decay_id).single().execute().data
    
    if not decay:
        raise HTTPException(404, "Decay log not found")
    
    content_id = decay.get("refreshed_content_id")
    if not content_id:
        raise HTTPException(400, "No content ID found - run refresh first")
    
    from services.wordpress_service import get_wordpress_service
    wp_service = get_wordpress_service(website_id)
    
    wp_post_id = decay.get("wordpress_post_id")
    result = await wp_service.publish_post(wp_post_id, user_id) if wp_post_id else None
    
    if result:
        supabase.table("content_decay_logs").update({
            "status": "published",
            "published_at": datetime.utcnow()
        }).eq("id", decay_id).execute()
        
        supabase.table("content_log").update({
            "status": "published",
            "published_at": datetime.utcnow()
        }).eq("id", content_id).execute()
        
        return {"status": "published", "wordpress_id": result.get("id")}
    
    raise HTTPException(500, "Failed to publish")


@router.get("/decay/{website_id}/stats")
async def decay_stats(website_id: str):
    """Get decay statistics."""
    from database import get_supabase
    
    supabase = get_supabase()
    
    total = supabase.table("content_decay_logs").select("id").eq("website_id", website_id).execute().data or []
    recent = supabase.table("content_decay_logs").select("id").eq("website_id", website_id).gte("detected_at", (datetime.utcnow() - __import__('datetime').timedelta(days=30)).isoformat()).execute().data or []
    published = supabase.table("content_decay_logs").select("id").eq("website_id", website_id).eq("status", "published").execute().data or []
    drafts = supabase.table("content_decay_logs").select("id").eq("website_id", website_id).eq("status", "draft_ready").execute().data or []
    
    return {
        "total_decayed": len(total),
        "recent_decay": len(recent),
        "published_refreshes": len(published),
        "drafts_pending": len(drafts),
        "recovery_rate": round(len(published) / max(len(total), 1) * 100, 1) if total else 0
    }