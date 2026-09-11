"""Brand voice guides: versioned per-site writing contract API."""
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("backend.routers.brand_voice")
router = APIRouter()


class BrandVoiceIn(BaseModel):
    website_id: str
    tone: Optional[str] = None
    structure_rules: Optional[list] = None
    formatting_rules: Optional[list] = None
    banned_phrases: Optional[list] = None
    required_phrases: Optional[list] = None
    good_examples: Optional[list] = None
    bad_examples: Optional[list] = None
    verified_facts: Optional[list] = None
    approved_articles: Optional[list] = None
    rejected_articles: Optional[list] = None


class BrandVoiceExampleIn(BaseModel):
    website_id: str
    article_html: str
    approved: bool = True
    reason: str = ""


@router.get("/brand-voice/{website_id}")
@router.get("/api/brand-voice/{website_id}")
async def get_brand_voice(website_id: str):
    """Latest guide for a site, or explicit defaults (is_default=True)."""
    from services.brand_voice_service import load_brand_voice
    guide = await load_brand_voice(website_id)
    return {"success": True, "website_id": website_id, "guide": guide}


@router.post("/brand-voice")
@router.post("/api/brand-voice")
async def save_brand_voice(body: BrandVoiceIn):
    """Save a new versioned guide row."""
    from services.brand_voice_service import save_brand_voice
    if not body.website_id:
        raise HTTPException(status_code=400, detail="website_id is required")
    row = await save_brand_voice(body.website_id, body.model_dump(exclude_none=True))
    return {"success": True, "guide": row}


@router.post("/brand-voice/example")
@router.post("/api/brand-voice/example")
async def add_brand_voice_example(body: BrandVoiceExampleIn):
    """Record an approved/rejected example so future prompts improve."""
    from services.brand_voice_service import record_article_example
    if not body.website_id or not body.article_html:
        raise HTTPException(status_code=400, detail="website_id and article_html are required")
    await record_article_example(body.website_id, body.article_html,
                                 body.approved, body.reason)
    return {"success": True}

class BrandVoiceRollbackIn(BaseModel):
    website_id: str
    version: int


@router.get("/brand-voice/{website_id}/history")
@router.get("/api/brand-voice/{website_id}/history")
async def brand_voice_history(website_id: str):
    """All saved versions, newest first — so history is verifiable, not claimed."""
    from database import get_supabase
    try:
        rows = get_supabase().table("brand_voice_guides").select(
            "id, version, tone, updated_at, created_at"
        ).eq("website_id", website_id).order("version", desc=True).execute().data or []
    except Exception:
        rows = []
    return {"success": True, "website_id": website_id, "versions": rows}


@router.post("/brand-voice/rollback")
@router.post("/api/brand-voice/rollback")
async def brand_voice_rollback(body: BrandVoiceRollbackIn):
    """Restore a prior version by saving it as a new version (history is
    append-only — rollback never deletes)."""
    from database import get_supabase
    from services.brand_voice_service import save_brand_voice
    if not body.website_id or not body.version:
        raise HTTPException(status_code=400, detail="website_id and version are required")
    try:
        old = get_supabase().table("brand_voice_guides").select("*").eq(
            "website_id", body.website_id).eq("version", body.version).limit(1).execute().data or []
    except Exception:
        old = []
    if not old:
        raise HTTPException(status_code=404, detail=f"Version {body.version} not found")
    payload = {k: old[0].get(k) for k in (
        "tone", "structure_rules", "formatting_rules", "banned_phrases",
        "required_phrases", "good_examples", "bad_examples", "verified_facts",
        "approved_articles", "rejected_articles") if old[0].get(k) is not None}
    row = await save_brand_voice(body.website_id, payload)
    return {"success": True, "restored_from_version": body.version, "guide": row}
