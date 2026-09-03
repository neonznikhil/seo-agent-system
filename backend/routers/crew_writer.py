"""CrewAI 3-Agent API — autonomous WordPress + RAG + Quality Gate."""
import logging
import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import get_supabase
from middleware.auth import get_current_account_id

logger = logging.getLogger("backend.routers.crew_writer")
router = APIRouter(prefix="/crew", tags=["CrewAI 3-Agent"])

class CrewGenerateRequest(BaseModel):
    topic: str
    website_id: Optional[str] = None
    user_id: Optional[str] = None
    tone: Optional[str] = "professional"
    word_count: Optional[int] = 2500
    blog_id: Optional[str] = None

class CrewAutonomousRequest(BaseModel):
    website_id: str
    user_id: Optional[str] = None

async def _run_generation(payload: CrewGenerateRequest):
    """Background task for blog generation."""
    from agents.crew_blog_writer import generate_blog_with_self_healing
    try:
        await generate_blog_with_self_healing(
            topic=payload.topic,
            website_id=payload.website_id or "",
            user_id=payload.user_id,
            tone=payload.tone,
            word_count=payload.word_count
        )
    except Exception as e:
        logger.error(f"[CrewAPI] Background generation failed: {e}")

@router.post("/generate")
@router.post("/api/crew/generate")
async def crew_generate(payload: CrewGenerateRequest, request: Request, background_tasks: BackgroundTasks):
    """POST /api/crew/generate {topic, website_id, tone, word_count} -> starts generation, returns blog_id for SSE."""
    topic = (payload.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic required")
    website_id = payload.website_id or request.headers.get("X-Website-Id")
    if not website_id or website_id in ("default-website-id", "default", "all", "", "null", "undefined"):
        from services.website_service import get_default_website_id
        website_id = get_default_website_id()
    if not website_id:
        raise HTTPException(status_code=400, detail="No website connected — Go to /websites to connect your domain first.")
    
    blog_id = payload.blog_id or str(uuid.uuid4())
    background_tasks.add_task(_run_generation, payload)
    
    return {"success": True, "blog_id": blog_id, "message": "Generation started — connect to SSE for progress"}

@router.post("/generate/autonomous")
async def crew_generate_autonomous(payload: CrewAutonomousRequest, request: Request):
    """POST /api/crew/generate/autonomous {website_id} -> gap-based generation."""
    website_id = payload.website_id
    if not website_id:
        raise HTTPException(status_code=400, detail="website_id required")
    gap_keyword = None
    try:
        from services.analytics_service import AnalyticsService
        from database import get_supabase
        supabase = get_supabase()
        gaps = await AnalyticsService.get_content_gaps(website_id=website_id)
        existing = set()
        try:
            rows = supabase.table("blogs").select("primary_keyword").eq("website_id", website_id).limit(50).execute().data or []
            existing = {r.get("primary_keyword","").lower() for r in rows if r.get("primary_keyword")}
        except Exception:
            pass
        for g in gaps:
            kw = g.get("keyword") or ""
            vol = int(g.get("impressions") or g.get("search_volume") or 0)
            if kw.lower() not in existing and vol > 800:
                gap_keyword = kw
                break
        if not gap_keyword:
            from agents.autonomous_decision_engine import AutonomousDecisionEngine
            engine = AutonomousDecisionEngine(website_id=website_id)
            gap_keyword = await engine.get_next_target_keyword()
    except Exception as e:
        gap_keyword = "Autonomous SEO Content Architecture"
        logger.warning(f"[CrewAPI] gap derivation fallback: {e}")

    try:
        from agents.crew_blog_writer import generate_blog_with_self_healing
        result = await generate_blog_with_self_healing(topic=gap_keyword, website_id=website_id, user_id=payload.user_id)
        return {"success": True, "gap_keyword": gap_keyword, **result}
    except Exception as e:
        msg = str(e)
        if "Knowledge empty" in msg:
            raise HTTPException(status_code=400, detail=msg)
        logger.error(f"[CrewAPI] autonomous generate failed: {e}")
        raise HTTPException(status_code=500, detail=msg[:500])

@router.get("/status/{blog_id}")
async def crew_status(blog_id: str):
    """GET /api/crew/status/{blog_id} -> pipeline logs + blog row."""
    supabase = get_supabase()
    blog = None
    try:
        row = supabase.table("blogs").select("*").eq("id", blog_id).single().execute().data
        if row:
            blog = row
    except Exception:
        pass
    if not blog:
        try:
            row = supabase.table("content_log").select("*").eq("id", blog_id).single().execute().data
            if row:
                blog = row
        except Exception:
            pass
    if not blog:
        try:
            row = supabase.table("blog_approvals").select("*").eq("blog_id", blog_id).single().execute().data
            if row:
                blog = row
        except Exception:
            pass

    if not blog:
        from services.local_store import get_local_content, get_local_approval
        blog = get_local_content(blog_id) or get_local_approval(blog_id)

    if not blog:
        raise HTTPException(status_code=404, detail="blog_id not found")

    logs = []
    try:
        content_id = blog.get("id") or blog_id
        rows = supabase.table("content_pipeline_logs").select("*").eq("content_id", content_id).order("step_number").limit(50).execute().data or []
        if not rows:
            rows = supabase.table("content_pipeline_logs").select("*").eq("content_id", blog.get("blog_id", blog_id)).order("step_number").limit(50).execute().data or []
        logs = rows
    except Exception as e:
        logger.debug(f"[CrewAPI] logs fetch note: {e}")

    return {
        "success": True,
        "blog_id": blog_id,
        "blog": blog,
        "pipeline_logs": logs,
        "seo_score": blog.get("seo_score"),
        "validation_score": blog.get("validation_score"),
        "grounding_score": blog.get("grounding_score"),
        "status": blog.get("status"),
        "wordpress_url": blog.get("wordpress_url"),
    }

@router.get("/status/{blog_id}/stream")
async def crew_status_stream(blog_id: str):
    """SSE streaming for real-time Planner->Writer->Editor progress."""
    from services.event_bus import stream as bus_stream
    import json as _json

    async def event_generator():
        async for event in bus_stream(f"crew:{blog_id}"):
            if event.get("keepalive"):
                yield ": keepalive\n\n"
                continue
            yield f"data: {_json.dumps(event, default=str)}\n\n"
            if event.get("phase") == "complete":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

@router.get("/health")
async def crew_health():
    """Health check: crewai installed, NVIDIA available, knowledge counts."""
    has_crewai = False
    has_nvidia = False
    try:
        import crewai  # noqa: F401
        has_crewai = True
    except Exception:
        pass
    try:
        from database import get_nim_state
        has_nvidia = bool(get_nim_state().get("available"))
    except Exception:
        has_nvidia = bool(__import__("os").getenv("NVIDIA_API_KEY"))
    supabase = get_supabase()
    kb_total = 0
    try:
        res = supabase.table("knowledge_base").select("id", count="exact").limit(1).execute()
        kb_total = getattr(res, "count", len(res.data or [])) if res else 0
    except Exception:
        pass
    return {
        "success": True,
        "crewai_installed": has_crewai,
        "nvidia_available": has_nvidia,
        "knowledge_base_total": kb_total,
        "fallback_mode": not has_crewai,
        "message": "CrewAI 3-Agent ready (direct NIM fallback)" if not has_crewai else "CrewAI 3-Agent ready",
    }
