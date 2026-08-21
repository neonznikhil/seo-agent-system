import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_supabase
from ..agents.tools.vector_memory_tool import is_duplicate

logger = logging.getLogger("backend.routers.memory")
router = APIRouter()


class MemoryCheckIn(BaseModel):
    topic: str
    website_id: str


@router.get("/memory/{website_id}")
async def get_memory(website_id: str):
    kb = get_supabase().table("knowledge_base").select("*").eq("website_id", website_id).execute().data or []
    tp = get_supabase().table("tone_profiles").select("*").eq("website_id", website_id).execute().data or []
    thoughts = get_supabase().table("agent_thoughts").select("*").eq("website_id", website_id).order("created_at", desc=True).limit(50).execute().data or []
    return {
        "knowledge_base": kb,
        "tone_profiles": tp,
        "agent_thoughts": thoughts,
    }


@router.post("/memory/check")
async def check_memory(body: MemoryCheckIn):
    is_dup = is_duplicate(body.topic, website_id=body.website_id)
    return {"topic": body.topic, "is_duplicate": is_dup}
