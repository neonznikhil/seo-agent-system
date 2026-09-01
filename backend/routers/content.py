import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.database import get_supabase, set_account_context
from middleware.auth import get_current_account_id

logger = logging.getLogger("backend.routers.content")
router = APIRouter()


class ContentIn(BaseModel):
    website_id: str
    title: str
    content: str
    status: Optional[str] = "draft"
    keyword: Optional[str] = None
    content_type: Optional[str] = "blog"


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    content_type: Optional[str] = None


@router.get("/content")
async def list_content(request: Request, website_id: Optional[str] = None, status: Optional[str] = None):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    query = supabase.table("content_log").select("*").eq("account_id", account_id)
    if website_id:
        query = query.eq("website_id", website_id)
    if status:
        query = query.eq("status", status)
    res = query.order("created_at", desc=True).execute()
    return res.data or []


@router.post("/content")
async def create_content(body: ContentIn, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    payload = body.model_dump()
    payload["account_id"] = account_id
    payload["created_at"] = datetime.utcnow().isoformat()
    payload["updated_at"] = datetime.utcnow().isoformat()

    res = supabase.table("content_log").insert(payload).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create content")
    return row


@router.get("/content/{website_id}/{content_id}")
@router.get("/content/{content_id}")
async def get_content(content_id: str, request: Request, website_id: Optional[str] = None):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    res = supabase.table("content_log").select("*").eq("id", content_id).eq("account_id", account_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Content not found")
    return res.data


@router.put("/content/{content_id}")
async def update_content(content_id: str, body: ContentUpdate, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"detail": "no changes"}
    updates["updated_at"] = datetime.utcnow().isoformat()

    res = supabase.table("content_log").update(updates).eq("id", content_id).eq("account_id", account_id).execute()
    return res.data[0] if res.data else {"detail": "updated"}


@router.delete("/content/{content_id}")
async def delete_content(content_id: str, request: Request):
    """Delete a blog draft / article from content_log and associated blog_approvals under tenant account."""
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    # 1. Fetch content row for snapshot
    try:
        content_res = supabase.table("content_log").select("*").eq("id", content_id).eq("account_id", account_id).execute()
        if content_res.data:
            target_row = content_res.data[0]
            # Audit log snapshot
            supabase.table("deleted_content_log").insert({
                "original_id": target_row.get("id"),
                "account_id": account_id,
                "website_id": target_row.get("website_id"),
                "title": target_row.get("title"),
                "target_keyword": target_row.get("keyword"),
                "content": target_row.get("content"),
                "snapshot_data": target_row,
                "deleted_by": "operator",
                "deleted_at": datetime.utcnow().isoformat(),
            }).execute()
    except Exception as e:
        logger.debug(f"Snapshot audit error: {e}")

    # 2. Delete associated blog_approvals
    try:
        supabase.table("blog_approvals").delete().eq("blog_id", content_id).eq("account_id", account_id).execute()
    except Exception as e:
        logger.debug(f"Approval delete note: {e}")

    # 3. Delete from content_log
    try:
        supabase.table("content_log").delete().eq("id", content_id).eq("account_id", account_id).execute()
        return {"success": True, "deleted_id": content_id, "detail": "Article draft deleted."}
    except Exception as e:
        logger.error(f"Error deleting content {content_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete article: {str(e)}")


@router.delete("/content/drafts/all")
async def purge_all_drafts(request: Request):
    """Purge all unapproved drafts for this tenant account."""
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    try:
        supabase.table("blog_approvals").delete().eq("account_id", account_id).neq("status", "published").execute()
        supabase.table("content_log").delete().eq("account_id", account_id).neq("status", "published").execute()
        return {"success": True, "message": "All drafts purged."}
    except Exception as e:
        logger.error(f"Error purging drafts: {e}")
        raise HTTPException(status_code=500, detail="Failed to purge drafts")
