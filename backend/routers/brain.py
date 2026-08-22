import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("backend.routers.brain")

router = APIRouter()


class BrainMemoryIn(BaseModel):
    title: str
    content: str
    memory_type: Optional[str] = "preference"
    website_id: Optional[str] = None
    confidence: Optional[float] = 0.9


@router.get("/brain")
async def list_all_brain_memories(
    website_id: Optional[str] = None,
    query: str = "",
    memory_type: Optional[str] = None,
    limit: int = 50,
):
    from ..database import get_supabase
    supabase = get_supabase()
    q = supabase.table("brain_memory").select("*")
    if website_id:
        q = q.eq("website_id", website_id)
    if memory_type:
        q = q.eq("memory_type", memory_type)
    if query:
        q = q.ilike("title", f"%{query}%")
    return q.order("created_at", desc=True).limit(limit).execute().data or []


@router.post("/brain")
async def create_brain_memory(body: BrainMemoryIn):
    from ..database import get_supabase, get_embedding
    supabase = get_supabase()
    
    # Resolve website_id if not given
    wid = body.website_id
    if not wid:
        try:
            sites = supabase.table("websites").select("id").limit(1).execute().data
            if sites:
                wid = sites[0]["id"]
        except Exception:
            pass

    # Optional embedding
    emb = None
    try:
        emb = await get_embedding(f"{body.title}: {body.content}")
    except Exception:
        pass

    row = {
        "title": body.title,
        "content": body.content,
        "memory_type": body.memory_type or "preference",
        "confidence": body.confidence or 0.9,
    }
    if wid:
        row["website_id"] = wid
    if emb:
        row["embedding"] = emb

    res = supabase.table("brain_memory").insert(row).execute()
    return res.data[0] if res.data else {"status": "created"}


@router.delete("/brain/{memory_id}")
async def delete_brain_memory(memory_id: str):
    from ..database import get_supabase
    get_supabase().table("brain_memory").delete().eq("id", memory_id).execute()
    return {"status": "deleted", "id": memory_id}


@router.get("/brain/{website_id}/backlink-memories")
async def get_backlink_memories(website_id: str):
    from ..database import get_supabase

    supabase = get_supabase()
    memories = (
        supabase.table("brain_memory")
        .select("*")
        .eq("website_id", website_id)
        .eq("source_type", "backlink")
        .execute()
        .data
        or []
    )
    return memories


@router.get("/brain/{website_id}/memories")
async def get_memories(
    website_id: str,
    query: str = "",
    memory_type: str = None,
    top_k: int = 5,
    min_confidence: float = 0.6,
):
    from ..services.brain_service import BrainService

    brain = BrainService(website_id)
    if query:
        memories = await brain.recall(
            website_id=website_id,
            query=query,
            memory_type=memory_type,
            top_k=top_k,
            min_confidence=min_confidence,
        )
    else:
        from ..database import get_supabase
        supabase = get_supabase()
        q = supabase.table("brain_memory").select("*").eq("website_id", website_id)
        if memory_type:
            q = q.eq("memory_type", memory_type)
        memories = q.order("created_at", desc=True).limit(top_k).execute().data or []

    return memories


@router.get("/brain/{website_id}/brand-brain")
async def get_brand_brain(website_id: str):
    from ..services.brain_service import BrainService

    brain = BrainService(website_id)
    return await brain.get_brand_brain(website_id)


@router.get("/brain/{website_id}/performance/{content_id}")
async def get_content_performance(website_id: str, content_id: str):
    from ..database import get_supabase

    supabase = get_supabase()
    perf = (
        supabase.table("brain_content_performance")
        .select("*")
        .eq("content_id", content_id)
        .eq("website_id", website_id)
        .order("learned_at", desc=True)
        .execute()
        .data
        or []
    )
    return perf


@router.get("/brain/{website_id}/performance/all")
async def get_all_performance(website_id: str, limit: int = 50):
    from ..database import get_supabase

    supabase = get_supabase()
    perf = (
        supabase.table("brain_content_performance")
        .select("*")
        .eq("website_id", website_id)
        .order("learned_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    return perf


@router.get("/brain/{website_id}/auto-queue")
async def get_auto_queue(website_id: str, status: str = None):
    from ..database import get_supabase

    supabase = get_supabase()
    q = supabase.table("brain_auto_pages_queue").select("*").eq("website_id", website_id)
    if status:
        q = q.eq("status", status)
    return q.order("priority_score", desc=True).execute().data or []


@router.post("/brain/{website_id}/auto-queue/{queue_id}/approve")
async def approve_auto_queue(website_id: str, queue_id: str, request: Request):
    from ..database import get_supabase
    from ..agents.writer_agent import generate_content

    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(403, "Human approval required - provide X-User-Id header")

    supabase = get_supabase()
    item = (
        supabase.table("brain_auto_pages_queue")
        .select("*")
        .eq("id", queue_id)
        .eq("website_id", website_id)
        .single()
        .execute()
        .data
    )
    if not item:
        raise HTTPException(404, "Queue item not found")

    supabase.table("brain_auto_pages_queue").update(
        {"status": "queued_for_writing"}
    ).eq("id", queue_id).execute()

    try:
        gen = await generate_content(
            website_id=website_id,
            topic=item.get("suggested_topic", ""),
            primary_keyword=item.get("primary_keyword"),
        )
        new_status = "draft_ready" if gen.get("status") == "completed" else "queued_for_writing"
        supabase.table("brain_auto_pages_queue").update({"status": new_status}).eq("id", queue_id).execute()
        return {"status": new_status, "generation": gen}
    except Exception as e:
        logger.error(f"Auto-queue approve generation failed: {e}")
        return {"status": "queued_for_writing", "error": str(e)}


@router.post("/brain/{website_id}/auto-queue/{queue_id}/reject")
async def reject_auto_queue(website_id: str, queue_id: str, request: Request):
    from ..database import get_supabase

    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(403, "Human approval required - provide X-User-Id header")

    supabase = get_supabase()
    supabase.table("brain_auto_pages_queue").update({"status": "rejected"}).eq("id", queue_id).eq("website_id", website_id).execute()
    return {"status": "rejected"}


@router.get("/brain/{website_id}/daily-jobs")
async def get_daily_jobs(website_id: str, days: int = 7):
    from ..database import get_supabase
    from datetime import timedelta

    supabase = get_supabase()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    jobs = (
        supabase.table("brain_daily_jobs")
        .select("*")
        .eq("website_id", website_id)
        .gte("run_at", cutoff)
        .order("run_at", desc=True)
        .execute()
        .data
        or []
    )
    return jobs


@router.post("/brain/{website_id}/run-now")
async def run_job_now(website_id: str, body: Dict[str, Any]):
    job_type = body.get("job_type")
    if not job_type:
        raise HTTPException(400, "job_type required")

    job_map = {
        "daily_search": _run_job_now_search,
        "daily_cluster_build": _run_job_now_cluster,
        "daily_geo_check": _run_job_now_geo,
        "daily_refresh_check": _run_job_now_refresh,
        "daily_backlink_check": _run_job_now_backlink,
        "daily_new_page_suggestion": _run_job_now_new_page,
    }
    func = job_map.get(job_type)
    if not func:
        raise HTTPException(400, f"Unknown job_type: {job_type}")

    return await func(website_id)


async def _run_job_now_search(website_id: str):
    from .daily_search_service import daily_search_job
    return await daily_search_job(website_id)


async def _run_job_now_cluster(website_id: str):
    from .daily_search_service import daily_cluster_build_job
    return await daily_cluster_build_job(website_id)


async def _run_job_now_geo(website_id: str):
    from .daily_search_service import daily_geo_check_job
    return await daily_geo_check_job(website_id)


async def _run_job_now_refresh(website_id: str):
    from .daily_search_service import daily_refresh_check_job
    return await daily_refresh_check_job(website_id)


async def _run_job_now_backlink(website_id: str):
    from .daily_search_service import daily_backlink_check_job
    return await daily_backlink_check_job(website_id)


async def _run_job_now_new_page(website_id: str):
    from .daily_search_service import daily_new_page_suggestion_job
    return await daily_new_page_suggestion_job(website_id)

