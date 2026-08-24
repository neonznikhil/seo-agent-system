"""Approvals API - human gate for WordPress create/update.

Everything else in the system stays fully autonomous. ONLY WordPress
write operations go through this approval layer.

Data integrity contract:
- Every content_log row that reaches status 'pending_approval' MUST have a
  matching blog_approvals row. A Postgres trigger enforces this in real time,
  and POST /api/approvals/sync reconciles any historical drift.
- The approvals list joins blog_approvals with content_log so each card has
  the full article body, keyword, word count and quality scores.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase

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


# ---------------------------------------------------------
# Reconciliation: content_log <-> blog_approvals
# ---------------------------------------------------------

def _markdown_to_html(md: str) -> str:
    """Deterministic minimal markdown -> HTML (same rules as WriterPipeline)."""
    import re as _re
    if not md:
        return ""
    if md.lstrip().startswith("<"):
        return md  # already HTML
    html_lines = []
    in_list = False
    for line in md.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item = _re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', stripped[2:].strip())
            html_lines.append(f"<li>{item}</li>")
            continue
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        if stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith(">"):
            html_lines.append(f"<blockquote>{stripped.lstrip('> ')}</blockquote>")
        elif stripped.startswith("---"):
            html_lines.append("<hr/>")
        elif stripped:
            para = _re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', stripped)
            html_lines.append(f"<p>{para}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


async def reconcile_pending_approvals(website_id: Optional[str] = None) -> dict:
    """Create blog_approvals rows for any content_log pending_approval rows missing one."""
    supabase = get_supabase()
    created = 0
    scanned = 0

    try:
        q = supabase.table("content_log").select(
            "id, website_id, title, keyword, content, status, final_scores, created_at"
        )
        # A row is awaiting human action when status OR pipeline_status says so
        q = q.or_("status.eq.pending_approval,pipeline_status.eq.pending_approval")
        if website_id:
            q = q.eq("website_id", website_id)
        rows = q.order("created_at", desc=True).limit(200).execute().data or []
    except Exception as e:
        logger.warning(f"[ApprovalsSync] content_log query failed: {e}")
        return {"created": 0, "scanned": 0, "error": str(e)[:200]}

    for row in rows:
        scanned += 1
        cl_id = row.get("id")
        wid = row.get("website_id") or website_id
        title = row.get("title") or "Untitled draft"
        content = row.get("content") or ""
        if not content or len(content) < 100 or "draft:" in title.lower():
            # Skip junk/failed generations — they are cleaned up separately.
            continue

        # Skip when an approval row already exists for this content id
        try:
            existing = (
                supabase.table("blog_approvals")
                .select("id, status")
                .eq("blog_id", cl_id)
                .limit(1)
                .execute()
                .data or []
            )
            if existing:
                # Heal status drift both directions
                if existing[0].get("status") == "pending" and row.get("status") == "published":
                    supabase.table("blog_approvals").update({"status": "published"}).eq("id", existing[0]["id"]).execute()
                continue
        except Exception as e:
            logger.warning(f"[ApprovalsSync] existing check failed for {cl_id}: {e}")
            continue

        scores_raw = row.get("final_scores") or {}
        if isinstance(scores_raw, str):
            try:
                scores_raw = json.loads(scores_raw)
            except Exception:
                scores_raw = {}
        expert_score = None
        if isinstance(scores_raw, dict):
            expert_score = scores_raw.get("expert")

        try:
            supabase.table("blog_approvals").insert({
                "blog_id": cl_id,
                "title": title,
                "html_content": _markdown_to_html(content),
                "keyword": row.get("keyword"),
                "seo_score": float(expert_score) if expert_score else None,
                "type": "new_post",
                "status": "pending",
                "auto_generated": True,
                "wordpress_action": "create",
                "website_id": wid,
                "created_at": row.get("created_at") or datetime.utcnow().isoformat(),
            }).execute()
            created += 1
        except Exception as e:
            logger.warning(f"[ApprovalsSync] insert failed for {cl_id}: {e}")

    return {"created": created, "scanned": scanned}


@router.post("/sync")
async def sync_approvals(website_id: Optional[str] = None):
    """Reconcile content_log and blog_approvals. Runs on every approvals page load."""
    result = await reconcile_pending_approvals(website_id=website_id)
    return {"success": True, **result}


@router.get("")
async def list_approvals(
    status: str = Query("pending"),
    website_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    # Always reconcile first so the page never shows a stale empty queue.
    await reconcile_pending_approvals(website_id=website_id)

    supabase = get_supabase()
    q = (
        supabase.table("blog_approvals")
        .select(
            "id, blog_id, website_id, title, html_content, seo_title, meta_description, "
            "slug, keyword, seo_score, type, status, auto_generated, wordpress_action, "
            "wordpress_post_id, wordpress_url, rejection_reason, created_at, approved_at"
        )
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status != "all":
        if status not in VALID_STATUS:
            raise HTTPException(400, f"Invalid status. Valid: {VALID_STATUS}")
        q = q.eq("status", status)
    if website_id:
        q = q.eq("website_id", website_id)
    res = q.execute()
    rows = res.data or []

    # Join with content_log for word count + pipeline metadata on each card
    blog_ids = [r.get("blog_id") for r in rows if r.get("blog_id")]
    content_map = {}
    if blog_ids:
        try:
            cres = (
                supabase.table("content_log")
                .select("id, keyword, content, final_scores, pipeline_status")
                .in_("id", blog_ids)
                .execute()
            )
            for c in (cres.data or []):
                content_map[c["id"]] = c
        except Exception:
            pass

    enriched = []
    for r in rows:
        c = content_map.get(r.get("blog_id")) or {}
        raw_content = c.get("content") or ""
        word_count = len(raw_content.split()) if raw_content else len((r.get("html_content") or "").split())
        preview_parts = [
            p.strip() for p in _strip_tags(r.get("html_content") or "").split("\n") if p.strip()
        ]
        enriched.append({
            **r,
            "target_keyword": r.get("keyword") or c.get("keyword"),
            "word_count": word_count,
            "preview_paragraphs": preview_parts[:3],
            "pipeline_status": c.get("pipeline_status"),
        })
    return enriched


def _strip_tags(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "\n", html or "")


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

    # Mirror edits back into content_log so both tables stay consistent
    try:
        row = get_supabase().table("blog_approvals").select("blog_id").eq("id", approval_id).maybe_single().execute().data or {}
        if row.get("blog_id"):
            mirror = {}
            if updates.get("title"):
                mirror["title"] = updates["title"]
            if updates.get("keyword"):
                mirror["keyword"] = updates["keyword"]
            if updates.get("html_content"):
                mirror["content"] = updates["html_content"]
            if mirror:
                get_supabase().table("content_log").update(mirror).eq("id", row["blog_id"]).execute()
    except Exception:
        pass

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

    # Mirror rejection into content_log so the pipeline learns
    try:
        row = supabase.table("blog_approvals").select("blog_id").eq("id", approval_id).maybe_single().execute().data or {}
        if row.get("blog_id"):
            supabase.table("content_log").update({"status": "rejected"}).eq("id", row["blog_id"]).execute()
    except Exception:
        pass

    logger.info(f"[Approvals] Rejected: {res.data.get('title')}")
    return {"id": approval_id, "status": "rejected"}


@router.post("/{approval_id}/approve")
async def approve_and_publish(approval_id: str, user_id: str = Query("dashboard")):
    """Human approved -> NOW touch WordPress. This is the only WP write path."""
    import json
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

    # Guard against failed-generation titles reaching WordPress
    lowered = title.lower()
    if "draft:" in lowered or "or let ai suggest" in lowered or len(title.strip()) < 8:
        raise HTTPException(400, f"Refusing to publish invalid article title: '{title[:60]}'")

    # 1) Verify WordPress connection BEFORE approving
    wp = get_wordpress_service(website_id)
    site = wp._get_site_config()
    base_url, wp_user, wp_password = "", "", ""
    try:
        from ..routers.websites import get_decrypted_wordpress_credentials
        base_url, wp_user, wp_password = get_decrypted_wordpress_credentials(website_id)
    except Exception:
        pass
    if not (base_url and wp_user and wp_password) and not (
        site.get("base_url") or site.get("cms_url") or site.get("url")
    ):
        raise HTTPException(
            400,
            "WordPress not connected for this site. Connect via /connectors first.",
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
            wordpress_url = f"{(base_url or site.get('base_url') or '').rstrip('/')}/?p={wp_post_id}"
        else:
            # Create as DRAFT first, then immediately publish — one click total.
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

        # Mark source content_log row as published
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

        try:
            from ..services.slack_intelligence_service import notify_content_published
            await notify_content_published(website_id=website_id, title=title, wordpress_url=wordpress_url)
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


@router.delete("/{approval_id}")
async def delete_approval(approval_id: str):
    """Delete an item from blog_approvals and clean up its content_log counterpart."""
    supabase = get_supabase()
    blog_id = None
    try:
        res = supabase.table("blog_approvals").select("blog_id").eq("id", approval_id).execute()
        if res.data:
            blog_id = res.data[0].get("blog_id")
    except Exception:
        pass

    try:
        supabase.table("blog_approvals").delete().eq("id", approval_id).execute()
        if blog_id:
            supabase.table("content_log").delete().eq("id", blog_id).execute()
        return {"success": True, "deleted_id": approval_id, "detail": "Approval item and draft deleted."}
    except Exception as e:
        logger.error(f"Failed to delete approval {approval_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
