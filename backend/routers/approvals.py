"""Approvals API - human gate for WordPress create/update with multi-tenant account isolation.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..database import get_supabase, set_account_context
from ..middleware.auth import get_current_account_id

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


def _markdown_to_html(md: str) -> str:
    """Deterministic minimal markdown -> HTML."""
    import re as _re
    if not md:
        return ""
    if md.lstrip().startswith("<"):
        return md
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


async def reconcile_pending_approvals(website_id: Optional[str] = None, account_id: Optional[str] = None) -> dict:
    """Create blog_approvals rows for any content_log pending_approval rows missing one."""
    supabase = get_supabase()
    created = 0
    scanned = 0

    try:
        q = supabase.table("content_log").select(
            "id, website_id, title, keyword, content, status, final_scores, created_at, account_id"
        )
        q = q.or_("status.eq.pending_approval,pipeline_status.eq.pending_approval")
        if website_id:
            q = q.eq("website_id", website_id)
        if account_id:
            q = q.eq("account_id", account_id)
        rows = q.order("created_at", desc=True).limit(200).execute().data or []
    except Exception as e:
        logger.warning(f"[ApprovalsSync] content_log query failed: {e}")
        return {"created": 0, "scanned": 0, "error": str(e)[:200]}

    for row in rows:
        scanned += 1
        cl_id = row.get("id")
        wid = row.get("website_id") or website_id
        acc_id = row.get("account_id") or account_id
        title = row.get("title") or "Untitled draft"
        content = row.get("content") or ""
        if not content or len(content) < 100 or "draft:" in title.lower():
            continue

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
                if existing[0].get("status") == "pending" and row.get("status") == "published":
                    supabase.table("blog_approvals").update({"status": "published"}).eq("id", existing[0]["id"]).execute()
                continue
        except Exception as e:
            logger.warning(f"[ApprovalsSync] existing check failed: {e}")
            continue

        scores_raw = row.get("final_scores") or {}
        if isinstance(scores_raw, str):
            try:
                scores_raw = json.loads(scores_raw)
            except Exception:
                scores_raw = {}
        expert_score = None
        if isinstance(scores_raw, dict):
            expert_score = scores_raw.get("expert_review_score") or scores_raw.get("quality_score") or scores_raw.get("overall_score")

        html_body = _markdown_to_html(content)
        insert_payload = {
            "blog_id": cl_id,
            "website_id": wid,
            "account_id": acc_id,
            "title": title,
            "html_content": html_body,
            "keyword": row.get("keyword"),
            "seo_score": expert_score,
            "type": "new_post",
            "status": "pending",
            "auto_generated": True,
            "wordpress_action": "create",
            "created_at": row.get("created_at") or datetime.utcnow().isoformat(),
        }

        try:
            supabase.table("blog_approvals").insert(insert_payload).execute()
            created += 1
        except Exception as e:
            logger.warning(f"[ApprovalsSync] insert failed for {cl_id}: {e}")

    return {"created": created, "scanned": scanned}


@router.post("/sync")
async def sync_approvals(request: Request, website_id: Optional[str] = None):
    account_id = get_current_account_id(request)
    set_account_context(get_supabase(), account_id)
    result = await reconcile_pending_approvals(website_id=website_id, account_id=account_id)
    return {"success": True, **result}


@router.get("")
async def list_approvals(
    request: Request,
    status: str = Query("pending"),
    website_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    await reconcile_pending_approvals(website_id=website_id, account_id=account_id)

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
async def approval_stats(request: Request, website_id: Optional[str] = None):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    def _count(status_val: str) -> int:
        q = supabase.table("blog_approvals").select("id", count="exact").eq("status", status_val)
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
async def get_approval(approval_id: str, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    res = (
        supabase
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
async def edit_approval(approval_id: str, body: ApprovalEdit, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    res = (
        supabase
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

    try:
        row = supabase.table("blog_approvals").select("blog_id").eq("id", approval_id).maybe_single().execute().data or {}
        if row.get("blog_id"):
            mirror = {}
            if updates.get("title"):
                mirror["title"] = updates["title"]
            if updates.get("keyword"):
                mirror["keyword"] = updates["keyword"]
            if updates.get("html_content"):
                mirror["content"] = updates["html_content"]
            if mirror:
                supabase.table("content_log").update(mirror).eq("id", row["blog_id"]).execute()
    except Exception:
        pass

    return {"updated": list(updates.keys())}


@router.post("/{approval_id}/reject")
async def reject_approval(approval_id: str, request: Request, body: Optional[dict] = None):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    res = supabase.table("blog_approvals").select("status,title").eq("id", approval_id).maybe_single().execute()
    if not (res and res.data):
        raise HTTPException(404, "Approval not found")
    if res.data.get("status") != "pending":
        raise HTTPException(400, f"Cannot reject status '{res.data.get('status')}'")

    reason = (body or {}).get("reason", "")
    _update_approval(approval_id, {"status": "rejected", "rejection_reason": reason[:500] or None})

    try:
        row = supabase.table("blog_approvals").select("blog_id").eq("id", approval_id).maybe_single().execute().data or {}
        if row.get("blog_id"):
            supabase.table("content_log").update({"status": "rejected"}).eq("id", row["blog_id"]).execute()
    except Exception:
        pass

    logger.info(f"[Approvals] Rejected: {res.data.get('title')}")
    return {"id": approval_id, "status": "rejected"}


@router.post("/{approval_id}/approve")
async def approve_and_publish(approval_id: str, request: Request, user_id: str = Query("dashboard")):
    """Human approved -> NOW touch WordPress. This is the only WP write path."""
    import json
    from ..services.wordpress_service import get_wordpress_service

    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

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

    lowered = title.lower()
    if "draft:" in lowered or "or let ai suggest" in lowered or len(title.strip()) < 8:
        raise HTTPException(400, f"Refusing to publish invalid article title: '{title[:60]}'")

    wp = get_wordpress_service(website_id)
    site = wp._get_site_config()

    _update_approval(approval_id, {"status": "approved", "approved_at": datetime.utcnow().isoformat()})

    action = (row.get("wordpress_action") or "create").lower()
    wp_post_id = row.get("wordpress_post_id")
    wordpress_url = None

    try:
        if action == "update" and wp_post_id:
            upd = await wp.update_post(website_id=website_id, wp_post_id=wp_post_id, content=html, title=title)
            if not upd.get("success"):
                raise HTTPException(502, f"WordPress update failed: {upd.get('message')}")
            wordpress_url = f"{(site.get('base_url') or '').rstrip('/')}/?p={wp_post_id}"
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
        _update_approval(approval_id, {"status": "pending", "approved_at": None})
        raise
    except Exception as e:
        _update_approval(approval_id, {"status": "pending", "approved_at": None})
        raise HTTPException(502, f"Publish failed: {e}")


@router.delete("/{approval_id}")
async def delete_approval(approval_id: str, request: Request):
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    blog_id = None
    try:
        res = supabase.table("blog_approvals").select("blog_id, title, content").eq("id", approval_id).execute()
        if res.data:
            target = res.data[0]
            blog_id = target.get("blog_id")
            # Snapshot
            supabase.table("deleted_content_log").insert({
                "original_id": approval_id,
                "account_id": account_id,
                "title": target.get("title"),
                "content": target.get("content"),
                "snapshot_data": target,
                "deleted_by": "operator",
                "deleted_at": datetime.utcnow().isoformat(),
            }).execute()
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
