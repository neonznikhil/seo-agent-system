import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import asyncio
import json
from fastapi import APIRouter, Request, HTTPException, Depends, Body, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import get_supabase, call_nim_llm
from ..agents.writer_agent import WriterPipeline
from ..agents.human_writer import HumanWriterAgent
from ..services.wordpress_service import WordPressService

logger = logging.getLogger("backend.routers.writer")
router = APIRouter()

# Frontend placeholder strings that must never reach the database.
FORBIDDEN_TITLE_FRAGMENTS = [
    "or let ai suggest", "e.g.", "example", "placeholder",
    "lorem ipsum", "your content here", "enter your blog title", "a blog",
]


def validate_title(title: str) -> Optional[str]:
    t = (title or "").strip().lower()
    if not t:
        return "Title is required"
    for frag in FORBIDDEN_TITLE_FRAGMENTS:
        if frag in t:
            return f"Invalid title: appears to contain placeholder text ('{frag}')"
    if len(t) < 8:
        return "Title is too short to be a real article title"
    return None


class GenerateContentIn(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    keywords: Optional[List[str]] = None
    primary_keyword: Optional[str] = None
    tone: Optional[str] = "authoritative, engaging and SEO-optimized"


@router.post("/writer/{website_id}/generate")
async def generate_content_endpoint(
    website_id: str,
    body: GenerateContentIn,
    background_tasks: BackgroundTasks,
    request: Request = None,
):
    """Manual override generation entry point.

    Runs the full autonomous WriterPipeline in the background and returns the
    job id immediately. Clients subscribe to GET /api/writer/{job_id}/stream
    to watch sections appear in real time.
    """
    raw_title = (body.title or body.topic or "").strip()

    # 1. Placeholder validation — UI suggestion chips must never become articles.
    validation_error = validate_title(raw_title)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    # 2. NIM availability gate
    try:
        from ..database import is_nim_available, get_nim_state
        if not await is_nim_available():
            state = get_nim_state()
            raise HTTPException(
                status_code=503,
                detail=f"NVIDIA NIM unavailable — {state.get('diagnostic') or 'check your API key in Connectors'}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"NIM availability check error: {e}")

    topic = raw_title
    keywords = body.keywords or ([body.primary_keyword] if body.primary_keyword else [topic])
    primary_kw = body.primary_keyword or (keywords[0] if keywords else topic)

    pipeline = WriterPipeline(website_id)

    async def _run():
        try:
            result = await pipeline.generate(topic=topic, primary_keyword=primary_kw)
            logger.info(f"[WriterAPI] Pipeline finished for {result.get('content_id')}: {result.get('status')}")
        except Exception as e:
            logger.exception(f"[WriterAPI] Background pipeline crashed: {e}")
            from ..services.event_bus import publish
            channel = getattr(pipeline, "sse_channel", None)
            if channel:
                publish(channel, {"event": "pipeline_failed", "error": str(e)[:300]})

    background_tasks.add_task(_run)

    return {
        "success": True,
        "job_id": getattr(pipeline, "content_id", None),
        "content_id": getattr(pipeline, "content_id", None),
        "status": "started",
        "message": "Generation started — subscribe to the stream endpoint for live progress.",
        "stream_url": f"/api/writer/job/{getattr(pipeline, 'content_id', '')}/stream",
    }


@router.get("/writer/job/{job_id}/stream")
@router.get("/api/writer/job/{job_id}/stream")
async def stream_writer_job(job_id: str):
    """Server-Sent Events stream of live article generation progress."""
    from ..services.event_bus import stream as bus_stream, get_history

    async def event_generator():
        async for event in bus_stream(f"writer:{job_id}"):
            if event.get("keepalive"):
                yield ": keepalive\n\n"
                continue
            payload = json.dumps(event, default=str)
            yield f"data: {payload}\n\n"
            if event.get("event") in ("pipeline_completed", "pipeline_failed",
                                      "pipeline_blocked", "pipeline_needs_revision"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/writer/{website_id}/stream/{content_id}")
@router.get("/api/writer/{website_id}/stream/{content_id}")
async def stream_writer_content(website_id: str, content_id: str):
    """SSE stream alias scoped by website (used by the writer page right panel)."""
    return await stream_writer_job(content_id)


@router.get("/writer/{website_id}/pipeline/{content_id}")
async def get_pipeline_logs(website_id: str, content_id: str):
    """Fetch real-time pipeline step logs for polling clients."""
    supabase = get_supabase()
    try:
        logs = supabase.table("content_pipeline_logs").select("*").eq("content_id", content_id).order("step_number").execute().data or []
        reviews = supabase.table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    except Exception:
        logs = []
        reviews = []

    return {
        "logs": logs,
        "expert_reviews": reviews,
        "current_phase": logs[-1]["phase"] if logs else None,
        "total_steps": len(logs),
    }


@router.get("/writer/{website_id}/content")
async def list_content(website_id: str, limit: int = 50, status: Optional[str] = None):
    """List all content drafts and published blogs for a website."""
    supabase = get_supabase()
    query = supabase.table("content_log").select("*").eq("website_id", website_id)
    if status:
        query = query.eq("status", status)
    try:
        return query.order("created_at", desc=True).limit(limit).execute().data or []
    except Exception:
        return []


@router.get("/writer/{website_id}/content/{content_id}")
async def get_content_detail(website_id: str, content_id: str):
    """Get single content article with logs and review status."""
    supabase = get_supabase()
    try:
        content = supabase.table("content_log").select("*").eq("id", content_id).eq("website_id", website_id).single().execute().data
    except Exception:
        content = None

    if not content:
        raise HTTPException(404, "Content not found")

    try:
        logs = supabase.table("content_pipeline_logs").select("*").eq("content_id", content_id).order("step_number").execute().data or []
        reviews = supabase.table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    except Exception:
        logs = []
        reviews = []

    return {
        **content,
        "logs": logs,
        "expert_reviews": reviews,
        "current_phase": logs[-1]["phase"] if logs else None,
        "total_steps": len(logs),
    }


@router.post("/writer/{website_id}/content/{content_id}/approve-draft")
async def approve_draft_endpoint(
    website_id: str,
    content_id: str,
    request: Request = None,
):
    """Creates a DRAFT in WordPress (status: draft) upon human approval."""
    user_id = request.headers.get("X-User-Id", "admin") if request else "admin"
    supabase = get_supabase()

    content = supabase.table("content_log").select("*").eq("id", content_id).single().execute().data
    if not content:
        raise HTTPException(404, "Content not found")

    wp_service = WordPressService(website_id)
    title = content.get("title", "Autonomous SEO Article")
    content_text = content.get("content", "")
    keywords = [content.get("keyword", "SEO")]

    wp_result = None
    try:
        wp_result = await wp_service.create_draft(website_id, title, content_text, keywords)
    except Exception as e:
        logger.warning(f"WordPress draft creation attempt error: {e}")

    wp_post_id = wp_result.get("wp_post_id") if wp_result else None
    wp_draft_url = wp_result.get("edit_url") if wp_result else None

    update_payload = {
        "status": "draft",
        "approved_by": user_id,
    }
    if wp_post_id:
        update_payload["wp_post_id"] = wp_post_id
    if wp_draft_url:
        update_payload["wp_draft_url"] = wp_draft_url

    try:
        supabase.table("content_log").update(update_payload).eq("id", content_id).execute()
    except Exception as e:
        logger.warning(f"Could not update content_log on approval: {e}")

    return {
        "status": "draft",
        "wp_post_id": wp_post_id,
        "edit_url": wp_draft_url,
        "message": "Draft created in WordPress" if wp_post_id else "Article saved as local draft",
    }


@router.post("/writer/{website_id}/content/{content_id}/publish")
async def publish_content_endpoint(
    website_id: str,
    content_id: str,
    request: Request = None,
):
    """Publishes the post live to WordPress upon human approval."""
    user_id = request.headers.get("X-User-Id", "admin") if request else "admin"

    supabase = get_supabase()
    content = supabase.table("content_log").select("*").eq("id", content_id).single().execute().data
    if not content:
        raise HTTPException(404, "Content not found")

    wp_post_id = content.get("wp_post_id")
    wp_service = WordPressService(website_id)

    if not wp_post_id:
        # Draft-first then publish — one click for the human.
        try:
            draft = await wp_service.create_draft(
                website_id, content.get("title", ""), content.get("content", ""),
                [content.get("keyword")] if content.get("keyword") else [],
            )
            wp_post_id = draft.get("wp_post_id")
            if wp_post_id:
                supabase.table("content_log").update({"wp_post_id": wp_post_id}).eq("id", content_id).execute()
        except Exception as e:
            logger.warning(f"WordPress draft-before-publish failed: {e}")

    if wp_post_id:
        try:
            await wp_service.publish_post(website_id, wp_post_id, user_id)
        except Exception as e:
            logger.warning(f"WordPress publish remote call warning: {e}")

    try:
        supabase.table("content_log").update({
            "status": "published",
            "approved_by": user_id,
        }).eq("id", content_id).execute()
        supabase.table("blog_approvals").update({
            "status": "published",
            "wordpress_post_id": wp_post_id,
            "approved_at": datetime.utcnow().isoformat(),
        }).eq("blog_id", content_id).execute()
    except Exception as e:
        logger.warning(f"Could not mark content as published: {e}")

    try:
        from ..services.slack_intelligence_service import notify_content_published
        await notify_content_published(
            website_id=website_id,
            title=content.get("title", ""),
            wordpress_url=None,
        )
    except Exception:
        pass

    return {
        "status": "published",
        "published": True,
        "wp_post_id": wp_post_id,
        "message": "Post published live to WordPress",
    }


@router.get("/writer/{website_id}/expert-reviews/{content_id}")
async def expert_reviews(website_id: str, content_id: str):
    supabase = get_supabase()
    try:
        reviews = supabase.table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    except Exception:
        reviews = []

    scores = [r.get("score") for r in reviews if isinstance(r.get("score"), (int, float))]
    average_score = round(sum(scores) / len(scores), 1) if scores else None

    return {
        "summary": {
            "total": len(reviews),
            "passed": len([r for r in reviews if r.get("passed")]),
            "failed": len([r for r in reviews if not r.get("passed")]),
            "average_score": average_score,
        },
        "reviews": reviews,
    }
