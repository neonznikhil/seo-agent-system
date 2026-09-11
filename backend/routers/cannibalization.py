"""Cannibalization endpoints: detect competing pages, create fix tasks.

GET is read-only detection. POST creates pending_fixes tasks (idempotent)
so findings become work items, not just alerts.
"""
import logging
from fastapi import APIRouter

from database import get_supabase

logger = logging.getLogger("backend.routers.cannibalization")
router = APIRouter()


@router.get("/cannibalization/{website_id}")
@router.get("/api/cannibalization/{website_id}")
async def detect(website_id: str):
    """Detect keywords targeted by 2+ pages. No side effects."""
    from services.cannibalization_service import scan_website
    result = await scan_website(website_id)
    return {"success": True, **result}


@router.post("/cannibalization/{website_id}/scan")
@router.post("/api/cannibalization/{website_id}/scan")
async def scan_and_create_tasks(website_id: str):
    """Detect cannibalization and turn each issue into a pending fix task."""
    from services.cannibalization_service import scan_website, create_cannibalization_tasks
    result = await scan_website(website_id)
    created = await create_cannibalization_tasks(website_id, result.get("issues", []))
    return {"success": True, "tasks_created": created, **result}
