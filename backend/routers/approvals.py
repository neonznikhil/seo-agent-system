"""Approvals API - human gate for WordPress create/update.

Everything else in the system stays fully autonomous. ONLY WordPress
write operations go through this approval layer.

Storage: Supabase (persistent) when the table exists, otherwise in-memory
buffer (auto-created by /setup or at startup when service key is provided).
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase
from ..services import approval_store

logger = logging.getLogger("backend.routers.approvals")
router = APIRouter(prefix="/api/approvals", tags=["approvals"])

VALID_STATUS = ("pending", "approved", "rejected", "published")


class ApprovalEdit(BaseModel):
    title: Optional[str] = None
    html_content: Optional[str] = None
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    slug: Optional[str] = None
    keyword: Optional[str] = None


def _update_approval(approval_id: str, updates: dict):
    get_supabase().table("blog_approvals").update(updates).eq("id", approval_id).execute()


@router.get("")
async def list_approvals(
    status: str = Query("pending"),
    website_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    q = get_supabase().table("blog_approvals").select("*").order("created_at", desc=True).limit(limit)
    if status != "all":
        if status not in VALID_STATUS:
            raise HTTPException(400, f"Invalid status. Valid: {VALID_STATUS}")
        q = q.eq("status", status)
    if website_id:
        q = q.eq("website_id", website_id)
    res = q.execute()
    return res.data or []


@router.get("/stats")
async def approval_stats(website_id: Optional[str] = None):
    supabase = get_supabase()

    def _count(status: str) -> int:
        q = supabase.table("blog_approvals").select("id", count="exact").eq("status", status)
        if website_id:
            q = q.eq("website_id", website_id)
        try:
            res = q.execute()
            return getattr(res, "count", None) or len(res.data or [])
        except Exception:
            return 0

    today = datetime.utcnow().date().isoformat()
    published_today = 0
    try:
        rows = (
            supabase.table("blog_approvals")
            .select("id")
            .eq("status", "published")
            .gte("approved_at", today)
            .execute()
            .data
            or []
        )
        published_today = len(rows)
    except Exception:
        pass

    last_job = None
    try:
        job = (
            supabase.table("brain_daily_jobs")
            .select("run_at")
            .order("run_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if job:
            last_job = job[0].get("run_at")
    except Exception:
        pass

    return {
        "pending": _count("pending"),
        "approved": _count("approved"),
        "rejected": _count("rejected"),
        "published_total": _count("published"),
        "published_today": published_today,
        "autonomous_jobs_last_run": last_job,
    }


@router.get("/{approval_id}")
async def get_approval(approval_id: str):
    res = (
        get_supabase()
        .table("blog_approvals")
        .select("*")
        .eq("id", approval_id)
        .maybe_single()
        .execute()
    )
    if not (res and res.data):
        raise HTTPException(404, "Approval not found")
    return res.data


@router.put("/{approval_id}")
async def edit_approval(approval_id: str, body: ApprovalEdit):
    res = (
        get_supabase()
        .table("blog_approvals")
        .select("status")
        .eq("id", approval_id)
        .maybe_single()
        .execute()
    )
    if not (res and res.data):
        raise HTTPException(404, "Approval not found")
    if res.data.get("status") not in ("pending",):
        raise HTTPException(400, "Only pending approvals can be edited")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nothing to update")
    _update_approval(approval_id, updates)
    return {"updated": list(updates.keys())}


@router.post("/{approval_id}/reject")
async def reject_approval(approval_id: str, body: Optional[dict] = None):
    supabase = get_supabase()
    res = supabase.table("blog_approvals").select("status,title").eq("id", approval_id).maybe_single().execute()
    if not (res and res.data):
        raise HTTPException(404, "Approval not found")
    if res.data.get("status") != "pending":
        raise HTTPException(400, f"Cannot reject status '{res.data.get('status')}'")

    reason = (body or {}).get("reason", "")
    _update_approval(approval_id, {"status": "rejected", "rejection_reason": reason[:500] or None})
    logger.info(f"[Approvals] Rejected: {res.data.get('title')}")
    return {"id": approval_id, "status": "rejected"}


@router.post("/{approval_id}/approve")
async def approve_and_publish(approval_id: str, user_id: str = Query("dashboard")):
    """Human approved -> NOW touch WordPress. This is the only WP write path."""
    from ..services.wordpress_service import get_wordpress_service

    supabase = get_supabase()
    res = supabase.table("blog_approvals").select("*").eq("id", approval_id).maybe_single().execute()
    row = res.data if res else None
    if not row:
        raise HTTPException(404, "Approval not found")
    if row.get("status") != "pending":
        raise HTTPException(400, f"Cannot approve status '{row.get('status')}'")

    website_id = row.get("website_id")
    title = row.get("title") or ""
    html = row.get("html_content") or ""
    if not website_id or not html.strip():
        raise HTTPException(400, "Approval row missing website or content")

    # 1) Verify WordPress connection BEFORE approving
    wp = get_wordpress_service(website_id)
    site = wp._get_site_config()
    if not site or not site.get("base_url") or not site.get("user") or not site.get("password"):
        raise HTTPException(
            400,
            "WordPress not connected for this site. Connect via /settings or "
            "the WordPress 1-click flow first.",
        )

    _update_approval(approval_id, {"status": "approved", "approved_at": datetime.utcnow().isoformat()})

    action = (row.get("wordpress_action") or "create").lower()
    slug = row.get("slug") or ""
    meta_description = row.get("meta_description") or ""
    wp_post_id = row.get("wordpress_post_id")
    wordpress_url = None

    try:
        if action == "update" and wp_post_id:
            upd = await wp.update_post(website_id=website_id, wp_post_id=wp_post_id, content=html, title=title)
            if not upd.get("success"):
                raise HTTPException(502, f"WordPress update failed: {upd.get('message')}")
            wordpress_url = f"{site['base_url'].rstrip('/')}/?p={wp_post_id}"
        else:
            draft = await wp.create_draft(
                website_id=website_id,
                title=title,
                content=html,
                keywords=[row.get("keyword")] if row.get("keyword") else [],
            )
            if not draft.get("success"):
                raise HTTPException(502, f"WordPress draft creation failed: {draft.get('message')}")
            wp_post_id = draft.get("wp_post_id")
            await wp.publish_post(website_id=website_id, wp_post_id=wp_post_id, user_id=user_id)
            wordpress_url = draft.get("link") or draft.get("edit_url")

        _update_approval(
            approval_id,
            {
                "status": "published",
                "wordpress_url": wordpress_url,
                "wordpress_post_id": wp_post_id,
            },
        )

        # Mark source blog/content rows as published
        try:
            if row.get("blog_id"):
                supabase.table("content_log").update(
                    {"status": "published", "wp_post_id": wp_post_id}
                ).eq("id", row["blog_id"]).execute()
        except Exception:
            pass

        try:
            from ..services.brain_service import BrainService

            await BrainService(website_id).remember(
                website_id=website_id,
                memory_type="success",
                title=f"Human approved and published: {title}",
                content=f"Type={row.get('type')} action={action}. URL={wordpress_url}",
                source_type="approvals",
                source_id=approval_id,
                confidence=0.95,
            )
        except Exception:
            pass

        logger.info(f"[Approvals] Published {title} -> {wordpress_url}")
        return {
            "id": approval_id,
            "status": "published",
            "wordpress_url": wordpress_url,
            "wordpress_post_id": wp_post_id,
        }
    except HTTPException:
        # Roll back to pending so an approver can retry without losing the draft
        _update_approval(approval_id, {"status": "pending", "approved_at": None})
        raise
    except Exception as e:
        _update_approval(approval_id, {"status": "pending", "approved_at": None})
        raise HTTPException(502, f"Publish failed: {e}")
