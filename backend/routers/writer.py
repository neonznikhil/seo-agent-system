import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Body
from fastapi.background import BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json

logger = logging.getLogger("backend.routers.writer")

router = APIRouter()


class GenerateContentIn(BaseModel):
    topic: str
    primary_keyword: Optional[str] = None


@router.post("/writer/{website_id}/generate")
async def generate_content(
    website_id: str,
    body: GenerateContentIn,
    background_tasks: BackgroundTasks,
    request: Request = None
):
    from ..agents.writer_agent import generate_content
    from ..middleware.human_gate import human_approval_required
    
    user_id = request.headers.get("X-User-Id") if request else None
    
    result = await generate_content(website_id, body.topic, body.primary_keyword)
    
    return result


@router.get("/writer/{website_id}/pipeline/{content_id}")
async def get_pipeline_logs(
    website_id: str,
    content_id: str
):
    from ..database import get_supabase
    
    logs = get_supabase().table("content_pipeline_logs").select("*").eq("content_id", content_id).eq("website_id", website_id).order("step_number").execute().data or []
    
    expert_reviews = get_supabase().table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    
    return {
        "logs": logs,
        "expert_reviews": expert_reviews,
        "current_phase": logs[-1]["phase"] if logs else None,
        "total_steps": len(logs)
    }


@router.get("/writer/{website_id}/content")
async def list_content(
    website_id: str,
    limit: int = 50,
    status: str = None
):
    from ..database import get_supabase
    
    query = get_supabase().table("content_log").select("*").eq("website_id", website_id)
    
    if status:
        query = query.eq("status", status)
    
    return query.order("created_at", desc=True).limit(limit).execute().data or []


@router.get("/writer/{website_id}/content/{content_id}")
async def get_content_detail(website_id: str, content_id: str):
    from ..database import get_supabase
    
    content = get_supabase().table("content_log").select("*").eq("id", content_id).eq("website_id", website_id).single().execute().data
    
    if not content:
        raise HTTPException(404, "Content not found")
    
    logs = get_supabase().table("content_pipeline_logs").select("*").eq("content_id", content_id).eq("website_id", website_id).order("step_number").execute().data or []
    
    expert_reviews = get_supabase().table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    
    return {
        **content,
        "logs": logs,
        "expert_reviews": expert_reviews,
        "current_phase": logs[-1]["phase"] if logs else None,
        "total_steps": len(logs)
    }


@router.post("/writer/{website_id}/content/{content_id}/preview")
async def preview_content(
    website_id: str,
    content_id: str
):
    from ..database import get_supabase
    
    content = get_supabase().table("content_log").select("*").eq("id", content_id).eq("website_id", website_id).single().execute().data
    
    if not content:
        raise HTTPException(404, "Content not found")
    
    return {
        "title": content.get("title"),
        "content": content.get("content", "")[:2000] + "...",
        "pipeline_status": content.get("pipeline_status"),
        "ai_search_score": content.get("ai_search_score"),
        "information_gain_score": content.get("information_gain_score")
    }


@router.post("/writer/{website_id}/content/{content_id}/publish")
async def publish_content(
    website_id: str,
    content_id: str,
    request: Request = None
):
    from ..database import get_supabase
    from ..middleware.human_gate import require_human_for_request
    from ..services.wordpress_service import get_wordpress_service
    
    user_id = await require_human_for_request(request)
    
    content = get_supabase().table("content_log").select("*").eq("id", content_id).eq("website_id", website_id).single().execute().data
    
    if not content:
        raise HTTPException(404, "Content not found")
    
    if content.get("status") != "pending_approval":
        raise HTTPException(400, f"Content status is {content.get('status')}, not pending_approval")
    
    wp_service = get_wordpress_service(website_id)
    result = await wp_service.publish_post(content.get("wordpress_draft_id"), user_id)
    
    if result:
        get_supabase().table("content_log").update({
            "status": "published",
            "published_at": datetime.utcnow()
        }).eq("id", content_id).execute()
        
        return {"status": "published", "wordpress_id": result.get("id")}
    
    raise HTTPException(500, "Failed to publish")


@router.post("/writer/{website_id}/content/{content_id}/approve-draft")
async def approve_draft(
    website_id: str,
    content_id: str,
    request: Request = None
):
    from ..database import get_supabase
    from ..middleware.human_gate import require_human_for_request
    
    user_id = await require_human_for_request(request)
    
    content = get_supabase().table("content_log").select("*").eq("id", content_id).eq("website_id", website_id).single().execute().data
    
    if not content:
        raise HTTPException(404, "Content not found")
    
    if not content.get("wordpress_draft_id"):
        raise HTTPException(400, "No WordPress draft ID found")
    
    get_supabase().table("content_log").update({
        "approved_by": user_id,
        "approved_at": datetime.utcnow().isoformat(),
        "status": "draft"
    }).eq("id", content_id).execute()
    
    return {"status": "approved", "message": "Content approved, still draft. Ready for publish."}


@router.get("/writer/{website_id}/expert-reviews/{content_id}")
async def expert_reviews(website_id: str, content_id: str):
    from ..database import get_supabase
    
    reviews = get_supabase().table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    
    summary = {
        "total": len(reviews),
        "passed": len([r for r in reviews if r.get("passed")]),
        "failed": len([r for r in reviews if not r.get("passed")]),
        "average_score": sum(r.get("score", 0) for r in reviews) / len(reviews) if reviews else 0
    }
    
    return {"summary": summary, "reviews": reviews}


@router.get("/writer/{website_id}/pipeline/{content_id}/live")
async def pipeline_live(website_id: str, content_id: str):
    from ..database import get_supabase
    
    async def event_generator():
        try:
            yield "event: connected\n\n"
            last_step = 0
            while True:
                try:
                    logs = get_supabase().table("content_pipeline_logs").select("*").eq("content_id", content_id).eq("website_id", website_id).order("step_number").execute().data or []
                    reviews = get_supabase().table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
                    current_step = logs[-1]["step_number"] if logs else 0
                    if current_step > last_step:
                        last_step = current_step
                        payload = {
                            "logs": logs,
                            "expert_reviews": reviews,
                            "current_step": current_step,
                            "total_steps": len(logs),
                            "current_phase": logs[-1]["phase"] if logs else None,
                        }
                        yield f"event: update\ndata: {json.dumps(payload)}\n\n"
                    if logs and logs[-1].get("status") in ("completed", "blocked", "needs_revision"):
                        yield f"event: complete\ndata: {{'status': '{logs[-1]['status']}'}}\n\n"
                        break
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Pipeline SSE error: {e}")
                    await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")