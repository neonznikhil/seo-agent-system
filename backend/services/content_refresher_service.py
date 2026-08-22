"""ContentRefresherAgent - daily refresh analysis WITH human approval gate.

Daily at 10:00 IST: pick up to 2 published posts older than 30 days,
regenerate the body grounded in knowledge_base facts + brain memories,
validate through the SEO quality gate, then STAGE in blog_approvals as
type='refresh_update', status='pending'.

WordPress is NEVER updated by this agent - only via human approval.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("backend.services.content_refresher")

MAX_REFRESH_PER_RUN = 2
MIN_AGE_DAYS = 30


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


async def _collect_grounding(website_id: str, keyword: str) -> Dict[str, Any]:
    """Gather KB facts + brain memories relevant to this post's keyword."""
    from ..database import get_supabase
    from .brain_service import BrainService

    supabase = get_supabase()
    facts: List[str] = []
    try:
        kb = (
            supabase.table("knowledge_base")
            .select("content")
            .eq("website_id", website_id)
            .limit(50)
            .execute()
            .data
            or []
        )
        facts = [f.get("content", "") for f in kb if f.get("content")]
    except Exception as e:
        logger.warning(f"Refresher: KB fetch failed: {e}")

    memories: List[str] = []
    try:
        brain = BrainService(website_id)
        recalled = await brain.recall(website_id, keyword, top_k=5)
        memories = [m.get("title", "") + ": " + m.get("content", "") for m in recalled]
    except Exception as e:
        logger.warning(f"Refresher: brain recall failed: {e}")

    return {"facts": facts[:30], "memories": memories[:5]}


async def _refresh_html(keyword: str, title: str, old_html: str, grounding: Dict[str, Any]) -> str:
    """Ask NIM to refresh the post. Grounded only on provided facts."""
    from ..database import call_nim_llm

    facts_block = "\n".join(f"- {f}" for f in grounding["facts"][:20]) or "- (no stored facts)"
    memory_block = "\n".join(f"- {m}" for m in grounding["memories"]) or "- (none)"
    old_text = _strip_tags(old_html)[:6000]

    prompt = f"""You are refreshing an existing blog post so it stays accurate and current.

POST TITLE: {title}
PRIMARY KEYWORD: {keyword}

VERIFIED FACTS (use ONLY these for statistics, laws, dates, names - never invent data):
{facts_block}

PAST LEARNINGS (what worked before):
{memory_block}

CURRENT CONTENT (to preserve structure and intent):
{old_text}

TASK: Rewrite/refresh the article keeping a similar structure, but:
1. Update any outdated information using ONLY the verified facts above.
2. Add an "Updated {datetime.utcnow().strftime('%B %Y')}" note in the intro.
3. Keep keyword '{keyword}' density between 1% and 2%.
4. Output clean HTML only using h2/h3/p/ul/li/strong/a/table tags (Elementor-safe).
5. Include exactly 3 internal links using placeholder hrefs like <a href="/related-topic">.
6. 700-1200 words. No scripts, styles, iframes, or inline JS.

Return ONLY the HTML article."""

    refreshed = await call_nim_llm(prompt, max_tokens=3000, temperature=0.5)
    return (refreshed or "").strip()


async def run_daily_refresh(website_id: str) -> Dict[str, Any]:
    """Analyze + refresh up to MAX_REFRESH_PER_RUN old posts; stages for approval."""
    from ..database import get_supabase
    from .seo_quality_gate import validate_content
    from .brain_service import BrainService
    from .auto_publisher_service import _stage_for_approval

    supabase = get_supabase()
    brain = BrainService(website_id)
    result = {"candidates": 0, "staged_for_approval": 0, "skipped": 0, "failed": 0}

    cutoff = (datetime.utcnow() - timedelta(days=MIN_AGE_DAYS)).isoformat()
    try:
        candidates = (
            supabase.table("content_log")
            .select("id,title,content,keyword,wp_post_id,status")
            .eq("website_id", website_id)
            .not_.is_("wp_post_id", "null")
            .lt("created_at", cutoff)
            .order("created_at", desc=False)  # oldest first
            .limit(MAX_REFRESH_PER_RUN)
            .execute()
            .data
            or []
        )
    except Exception as e:
        logger.error(f"[Refresher] candidate fetch failed: {e}")
        candidates = []

    result["candidates"] = len(candidates)

    for post in candidates:
        # Skip if an identical refresh is already pending approval
        try:
            existing = (
                supabase.table("blog_approvals")
                .select("id")
                .eq("wordpress_post_id", post.get("wp_post_id"))
                .eq("type", "refresh_update")
                .in_("status", ["pending"])
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing:
                result["skipped"] += 1
                continue
        except Exception:
            pass

        title = post.get("title") or ""
        keyword = post.get("keyword") or ""
        old_html = post.get("content") or ""

        try:
            grounding = await _collect_grounding(website_id, keyword or title)
            refreshed = await _refresh_html(keyword or title, title, old_html, grounding)

            if len(refreshed.strip()) < 300 or "<h2" not in refreshed.lower():
                result["skipped"] += 1
                continue

            seo_title = title  # keep existing ranking title unless too long
            gate = await validate_content(
                website_id=website_id,
                title=seo_title,
                meta_description=f"{title} - updated with the latest information and insights.",
                keyword=keyword,
                html=refreshed,
            )
            # Refresher keeps the original indexed URL/title, so a failed gate
            # must NOT be staged for WP update.
            if not gate["passed"]:
                await brain.remember(
                    website_id=website_id,
                    memory_type="failure",
                    title=f"Refresh gate rejected: {title}",
                    content=f"Issues: {gate['issues'][:5]}",
                    source_type="content_refresher",
                    source_id=post["id"],
                    confidence=0.7,
                )
                result["failed"] += 1
                continue

            # Gate passed -> stage as refresh_update. Human approves the update.
            await _stage_for_approval(
                website_id=website_id,
                title=title,
                html_content=refreshed,
                seo_title=seo_title,
                meta_description=f"{title} - updated with the latest information and insights.",
                slug="",
                keyword=keyword,
                seo_score=gate["score"],
                approval_type="refresh_update",
                wordpress_action="update",
                wordpress_post_id=post.get("wp_post_id"),
                blog_id=post.get("id"),
            )

            supabase.table("content_log").update(
                {"status": post.get("status") or "published"}
            ).eq("id", post["id"]).execute()

            await brain.remember(
                website_id=website_id,
                memory_type="success",
                title=f"Refresh staged for approval: {title}",
                content=(
                    f"Refreshed version generated (score {gate['score']}) and queued in "
                    f"blog_approvals - awaiting human approval before WP update."
                ),
                source_type="content_refresher",
                source_id=str(post.get("wp_post_id")),
                confidence=0.8,
            )
            result["staged_for_approval"] += 1
        except Exception as e:
            logger.error(f"[Refresher] failed for post {post.get('id')}: {e}")
            result["failed"] += 1

    logger.info(f"[Refresher] website={website_id} result={result}")
    return result
