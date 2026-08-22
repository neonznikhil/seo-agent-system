"""AutoPublisherAgent - autonomous new-page creation WITH human approval gate.

Flow:
  brain_auto_pages_queue (queued_for_writing)
    -> WriterPipeline.generate() with brain recall          [autonomous]
    -> SEOAgent metadata                                     [autonomous]
    -> seo_quality_gate.validate_content() score >= 80       [autonomous]
    -> blog_approvals row, status='pending'                  [autonomous]
    -> HUMAN reviews /approvals and clicks Approve           [approval required]
    -> only then is WordPress create/update performed        [approval required]

WordPress is NEVER touched by this agent directly.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("backend.services.auto_publisher")

MAX_GENERATION_ATTEMPTS = 3


async def _get_setting(key: str, default: str) -> str:
    from ..routers.settings import get_global_setting

    value = get_global_setting(key, default)
    return value if value is not None else default


async def _stage_for_approval(
    website_id: str,
    *,
    title: str,
    html_content: str,
    seo_title: str,
    meta_description: str,
    slug: str,
    keyword: str,
    seo_score: float,
    approval_type: str,
    wordpress_action: str = "create",
    wordpress_post_id=None,
    blog_id: str = None,
    gate_issues: list = None,
) -> Dict[str, Any]:
    """Insert into blog_approvals as pending. Shared by publisher + refresher."""
    from ..database import get_supabase

    row = {
        "website_id": website_id,
        "title": title,
        "html_content": html_content,
        "seo_title": seo_title,
        "meta_description": meta_description,
        "slug": slug,
        "keyword": keyword,
        "seo_score": seo_score,
        "type": approval_type,
        "status": "pending",
        "auto_generated": True,
        "wordpress_action": wordpress_action,
        "gate_issues": gate_issues or [],
    }
    if blog_id:
        row["blog_id"] = blog_id
    if wordpress_post_id is not None:
        row["wordpress_post_id"] = wordpress_post_id

    res = get_supabase().table("blog_approvals").insert(row).execute()
    saved = res.data[0] if res.data else {}
    logger.info(
        f"[ApprovalQueue] Blog ready for approval: {title} "
        f"(type={approval_type}, score={seo_score}) - waiting for human"
    )
    return saved


async def generate_queued_pages(website_id: str, limit: int = 2) -> Dict[str, Any]:
    """Process queued keywords into PENDING APPROVALS (never publishes)."""
    from ..database import get_supabase
    from .seo_quality_gate import validate_content
    from ..agents.writer_agent import generate_content
    from ..agents.seo_agent import SEOAgent
    from .brain_service import BrainService

    supabase = get_supabase()
    brain = BrainService(website_id)
    result = {"processed": 0, "staged_for_approval": 0, "failed": 0, "gate_rejections": 0}

    automate_on = (await _get_setting("automate_seo", "on")).lower() == "on"
    if not automate_on:
        result["skipped"] = "automate_seo is OFF"
        return result

    queue = (
        supabase.table("brain_auto_pages_queue")
        .select("*")
        .eq("website_id", website_id)
        .in_("status", ["queued_for_writing", "draft_ready"])
        .order("priority_score", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )

    for item in queue:
        keyword = item.get("primary_keyword") or ""
        topic = item.get("suggested_topic") or keyword
        if not keyword and not topic:
            continue

        result["processed"] += 1
        supabase.table("brain_auto_pages_queue").update(
            {"status": "writing"}
        ).eq("id", item["id"]).execute()

        staged = False
        last_issues: list = []

        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            attempt_topic = topic if attempt == 1 else f"{topic} ({'v2' if attempt == 2 else 'final'})"
            gen = await generate_content(
                website_id=website_id,
                topic=attempt_topic,
                primary_keyword=keyword or None,
            )
            content_id = gen.get("content_id")
            if not content_id or gen.get("status") != "completed":
                logger.warning(
                    f"[AutoPublisher] generation attempt {attempt} failed for '{keyword}': {gen}"
                )
                continue

            row = (
                supabase.table("content_log")
                .select("id,title,content")
                .eq("id", content_id)
                .single()
                .execute()
                .data
                or {}
            )
            title = row.get("title") or attempt_topic
            html = row.get("content") or ""

            # NIM outage guard: never stage empty/fabricated content
            if len(html.strip()) < 300:
                last_issues = ["Generation returned insufficient real content"]
                result["gate_rejections"] += 1
                continue

            seo = await SEOAgent(website_id).run(raw_html=html, keyword=keyword)
            gate = await validate_content(
                website_id=website_id,
                title=title,
                meta_description=seo.get("meta_description", ""),
                keyword=keyword,
                html=html,
            )

            if not gate["passed"]:
                last_issues = gate["issues"]
                result["gate_rejections"] += 1
                await brain.remember(
                    website_id=website_id,
                    memory_type="failure",
                    title=f"Quality gate rejected: {keyword}",
                    content=f"Score {gate['score']} < {gate['threshold']}. Issues: {last_issues[:5]}",
                    source_type="quality_gate",
                    source_id=str(item["id"]),
                    confidence=0.7,
                )
                continue

            # Gate passed -> stage for HUMAN approval. No WordPress calls here.
            await _stage_for_approval(
                website_id=website_id,
                title=title,
                html_content=html,
                seo_title=seo.get("seo_title", title),
                meta_description=seo.get("meta_description", ""),
                slug=seo.get("slug", ""),
                keyword=keyword,
                seo_score=gate["score"],
                approval_type="new_page",
                wordpress_action="create",
                blog_id=row.get("id"),
                gate_issues=last_issues if last_issues else None,
            )

            supabase.table("content_log").update(
                {"status": "draft_pending_approval", "seo_score": gate["score"]}
            ).eq("id", content_id).execute()

            supabase.table("brain_auto_pages_queue").update(
                {"status": "pending_approval", "source": f"auto_publisher|score={gate['score']}"}
            ).eq("id", item["id"]).execute()

            await brain.remember(
                website_id=website_id,
                memory_type="success",
                title=f"Draft ready for approval: {keyword}",
                content=(
                    f"Generated '{title}' for '{keyword}'. Gate score {gate['score']}. "
                    f"Attempts: {attempt}. Staged in blog_approvals - awaiting human publish."
                ),
                source_type="auto_publisher",
                source_id=str(content_id),
                confidence=0.85,
            )

            result["staged_for_approval"] += 1
            staged = True
            break

        if not staged:
            result["failed"] += 1
            supabase.table("brain_auto_pages_queue").update(
                {
                    "status": "failed",
                    "reason": "; ".join(last_issues[:3]) or "generation failed",
                }
            ).eq("id", item["id"]).execute()

    logger.info(f"[AutoPublisher] website={website_id} result={result}")
    return result


# Backwards-compatible alias used by older call sites.
publish_queued_pages = generate_queued_pages
