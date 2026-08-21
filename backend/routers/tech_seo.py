import logging
from fastapi import APIRouter

from ..database import get_supabase

logger = logging.getLogger("backend.routers.tech_seo")
router = APIRouter()


@router.get("/tech-seo/{website_id}")
async def get_tech_seo(website_id: str):
    res = (
        get_supabase()
        .table("technical_audits")
        .select("*")
        .eq("website_id", website_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return {"health_score": 0, "issues": ["No audit yet"], "audits": []}
    audit = res.data[0]
    issues = audit.get("issues", []) or []
    health_score = max(0.0, 100.0 - len(issues) * 10.0)
    return {
        "health_score": health_score,
        "issues": issues[:20],
        "audit": audit,
    }
