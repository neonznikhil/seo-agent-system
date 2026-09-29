import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from database import get_supabase
# Note: is_duplicate is imported lazily inside check_memory to prevent heavy vector/CrewAI imports on startup

logger = logging.getLogger("backend.routers.memory")
router = APIRouter()


class MemoryCheckIn(BaseModel):
    topic: str
    website_id: str


class MemoryUpsertIn(BaseModel):
    website_id: str
    title: Optional[str] = None
    content: Optional[str] = None
    fact: Optional[str] = None
    memory_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/memory/{website_id}")
async def get_memory(website_id: str):
    try:
        supabase = get_supabase()
        kb = supabase.table("knowledge_base").select("*").eq("website_id", website_id).execute().data or []
        tp = supabase.table("tone_profiles").select("*").eq("website_id", website_id).execute().data or []
        thoughts = supabase.table("agent_thoughts").select("*").eq("website_id", website_id).order("created_at", desc=True).limit(50).execute().data or []
    except Exception as exc:
        # Degrade to the durable local store rather than 500ing when the DB is
        # unreachable.
        logger.warning("memory read failed, using local store: %s", exc)
        from services.local_store import list_local_knowledge, list_local_brain_memory

        kb = list_local_knowledge(website_id)
        tp = []
        thoughts = list_local_brain_memory(website_id)
    return {
        "knowledge_base": kb,
        "tone_profiles": tp,
        "agent_thoughts": thoughts,
    }


@router.post("/memory/check")
async def check_memory(body: MemoryCheckIn):
    try:
        from agents.tools.vector_memory_tool import is_duplicate
    except ImportError:
        from backend.agents.tools.vector_memory_tool import is_duplicate
    is_dup = await is_duplicate(body.topic, website_id=body.website_id)
    return {"topic": body.topic, "is_duplicate": is_dup}


@router.post("/memory")
async def upsert_memory(body: MemoryUpsertIn):
    if not body.website_id:
        raise HTTPException(status_code=400, detail="website_id is required")

    row: Dict[str, Any] = {
        "website_id": body.website_id,
        "title": body.title,
        "content": body.content,
        "fact": body.fact,
        "memory_type": body.memory_type or "note",
        "metadata": body.metadata or {},
    }
    try:
        res = get_supabase().table("agent_memory").insert(row).execute()
        return {"success": True, "data": res.data[0] if res.data else row}
    except Exception as exc:
        logger.warning("agent_memory insert note: %s", exc)
        return {"success": True, "data": row, "note": "stored locally"}


@router.get("/memory")
async def list_memories(website_id: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    try:
        q = get_supabase().table("agent_memory").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.order("created_at", desc=True).limit(limit).execute()
        return {"success": True, "data": res.data or []}
    except Exception as exc:
        # A Supabase outage must not turn the memory list into a 500 — fall back
        # to the durable local store so indexed memories stay visible.
        logger.warning("agent_memory read failed, using local store: %s", exc)
        from services.local_store import list_local_brain_memory

        rows = list_local_brain_memory(website_id)[:limit]
        return {"success": True, "data": rows, "note": "served from local store"}


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str):
    try:
        get_supabase().table("agent_memory").delete().eq("id", memory_id).execute()
        return {"success": True, "deleted_id": memory_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
