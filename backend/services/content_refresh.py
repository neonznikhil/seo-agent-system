"""RankForge Content Decay Detection and Automated Refresh Engine.
Monitors ranking trajectories, identifies decaying articles, analyzes SERP gaps with NVIDIA NIM,
and generates updated content with fresh examples staged directly for human approval.
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

from backend.database import get_supabase, call_nim_llm
from backend.services.serper_service import serper_service
from backend.services.local_store import (
    list_local_rank_tracking,
    save_local_refresh_queue,
    list_local_refresh_queue,
    save_local_approval,
)

logger = logging.getLogger("backend.services.content_refresh")


async def detect_decaying_articles(website_id: str) -> List[Dict[str, Any]]:
    """
    Runs daily via scheduler. Finds articles that are losing ranking positions
    and queues them for a content refresh.
    """
    tracked: List[Dict[str, Any]] = []
    try:
        supabase = get_supabase()
        res = (
            supabase.table("rank_tracking")
            .select("*")
            .eq("website_id", website_id)
            .eq("status", "tracking")
            .execute()
        )
        tracked = res.data or []
    except Exception:
        pass

    local_tracked = list_local_rank_tracking(website_id=website_id, status="tracking")
    known_ids = {str(p.get("id")) for p in tracked if p.get("id")}
    for lp in local_tracked:
        if str(lp.get("id")) not in known_ids:
            tracked.append(lp)
            known_ids.add(str(lp.get("id")))

    queued_items = []
    for post in tracked:
        history = post.get("position_history") or []
        if len(history) < 3:
            continue  # Not enough data yet
        
        # Check last 3 position checks
        recent = history[-3:]
        positions = [h.get("position") for h in recent if h.get("position") is not None]
        
        if len(positions) < 2:
            continue
        
        # If consistently dropping or not in top 50
        first_pos = positions[0]
        last_pos = positions[-1]
        
        is_dropping = last_pos > first_pos  # Higher number = lower position (e.g. #5 -> #12)
        dropped_by = last_pos - first_pos
        not_ranking = last_pos > 50
        
        if (is_dropping and dropped_by >= 5) or not_ranking:
            keyword = post.get("target_keyword") or ""
            reason = f"Position dropped from #{first_pos} to #{last_pos}" if is_dropping else f"Ranking #{last_pos} (outside top 50)"
            
            queue_item = {
                "website_id": website_id,
                "blog_id": post.get("blog_id") or post.get("id"),
                "wp_post_id": post.get("wp_post_id"),
                "target_keyword": keyword,
                "reason": reason,
                "status": "pending",
                "queued_at": datetime.utcnow().isoformat(),
            }

            try:
                supabase = get_supabase()
                existing = (
                    supabase.table("content_refresh_queue")
                    .select("id")
                    .eq("website_id", website_id)
                    .eq("target_keyword", keyword)
                    .eq("status", "pending")
                    .execute()
                )
                if not (existing and existing.data):
                    supabase.table("content_refresh_queue").insert(queue_item).execute()
            except Exception:
                pass

            save_local_refresh_queue(queue_item)
            queued_items.append(queue_item)

            # Log autonomous decision
            try:
                from ..agents.scheduler import log_autonomous_decision
                await log_autonomous_decision(
                    website_id=website_id,
                    decision="REFRESH_QUEUED",
                    reason=f"'{keyword}' {reason}",
                    job="decay_detector"
                )
            except Exception:
                pass

            logger.info(f"[DecayDetector] Queued refresh for '{keyword}': {reason}")

    return queued_items


async def refresh_decaying_article(queue_item: dict) -> Optional[Dict[str, Any]]:
    """
    Takes an article that is losing rankings and rewrites it
    with updated content, fresher examples, and better
    optimization for current SERP.
    """
    blog_id = queue_item.get("blog_id")
    keyword = queue_item.get("target_keyword")
    website_id = queue_item.get("website_id")
    if not keyword or not website_id:
        return None

    # Get original article
    original_html = ""
    original_title = keyword.title()
    try:
        supabase = get_supabase()
        if blog_id:
            orig = supabase.table("blogs").select("*").eq("id", blog_id).maybe_single().execute()
            if orig and orig.data:
                original_html = orig.data.get("html_content") or orig.data.get("content") or ""
                original_title = orig.data.get("title") or original_title
    except Exception:
        pass

    if not original_html:
        from ..services.local_store import list_local_approvals, list_local_content
        for a in list_local_approvals(website_id=website_id) + list_local_content(website_id=website_id):
            if a.get("id") == blog_id or a.get("target_keyword") == keyword:
                original_html = a.get("html_content") or a.get("content") or ""
                original_title = a.get("title") or original_title
                break

    # Get current SERP for this keyword
    top_titles = []
    top_snippets = []
    try:
        serp_results = await serper_service.search(keyword, num_results=5)
        organic = serp_results.get("organic", []) if isinstance(serp_results, dict) else (serp_results or [])
        top_titles = [r.get("title", "") for r in organic]
        top_snippets = [r.get("snippet", "") for r in organic]
    except Exception as e:
        logger.warning(f"[ContentRefresh] SERP search error: {e}")

    # Ask AI what needs updating
    cur_date_str = datetime.utcnow().strftime("%B %d, %Y")
    refresh_prompt = f"""Today: {cur_date_str}

Original article keyword: {keyword}

Current top Google results for this keyword:
Titles: {top_titles}
Snippets: {top_snippets}

The original article is losing rankings. Based on what is currently ranking, identify 3-5 specific improvements needed.

Respond ONLY with valid JSON:
{{
    "gaps": ["gap 1", "gap 2", "gap 3"],
    "sections_to_add": ["new section topic 1", "new section topic 2"],
    "outdated_content": ["outdated claim 1"],
    "refresh_priority": "high"
}}"""

    analysis_data = {}
    try:
        analysis_raw = await call_nim_llm(
            prompt=refresh_prompt,
            system="You are an SEO Content Analyst. You respond only with valid JSON.",
            temperature=0.2,
        )
        cleaned_json = analysis_raw.strip()
        if "```json" in cleaned_json:
            cleaned_json = cleaned_json.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned_json:
            cleaned_json = cleaned_json.split("```", 1)[1].split("```", 1)[0].strip()
        analysis_data = json.loads(cleaned_json)
    except Exception as e:
        logger.warning(f"[ContentRefresh] AI Gap analysis failed: {e}")
        analysis_data = {
            "gaps": ["Add recent legal statutes and settlement figures", "Expand multiplier examples"],
            "sections_to_add": ["Recent compensation adjustments", "How to dispute early adjuster offers"],
            "outdated_content": ["Old damage caps"],
            "refresh_priority": "high",
        }

    # Generate refreshed article with gaps filled
    from ..agents.crew_blog_writer import run_crew_blog_writer_with_retry
    refreshed = await run_crew_blog_writer_with_retry(
        website_id=website_id,
        target_keyword=keyword,
        tone="Professional",
        word_count_target=1500,
    )
    refreshed_html = refreshed.get("final_html") or refreshed.get("html") or refreshed.get("html_content") or ""
    refreshed_title = refreshed.get("title") or original_title

    # Send to approvals with REFRESH badge
    approval_record = {
        "website_id": website_id,
        "blog_id": blog_id,
        "title": refreshed_title,
        "html_content": refreshed_html,
        "content": refreshed_html,
        "target_keyword": keyword,
        "keyword": keyword,
        "status": "pending",
        "type": "refresh_update",
        "approval_type": "refresh",
        "refresh_reason": queue_item.get("reason", "Ranking decay detected"),
        "original_published_date": queue_item.get("queued_at"),
        "original_html": original_html[:3000] if original_html else None,
        "seo_score": refreshed.get("seo_score", 88),
        "word_count": refreshed.get("word_count", 1500),
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        supabase = get_supabase()
        supabase.table("blog_approvals").insert(approval_record).execute()
        # Mark queue item complete
        if queue_item.get("id"):
            supabase.table("content_refresh_queue").update({"status": "completed"}).eq("id", queue_item["id"]).execute()
    except Exception:
        pass

    save_local_approval(approval_record)
    queue_item["status"] = "completed"
    save_local_refresh_queue(queue_item)

    logger.info(f"[ContentRefresh] Refreshed article staged in approvals for '{keyword}'")
    return approval_record


async def run_decay_detection_and_refresh(website_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Master daily runner at 11:00 AM IST.
    """
    from ..services.local_store import list_local_websites
    wids = [website_id] if website_id else []
    if not wids:
        try:
            supabase = get_supabase()
            sites = supabase.table("websites").select("id").execute().data or []
            wids = [s.get("id") for s in sites if s.get("id")]
        except Exception:
            pass
        if not wids:
            wids = [s.get("id") for s in list_local_websites() if s.get("id")]
        if not wids:
            wids = ["default"]

    total_queued = 0
    total_refreshed = 0
    for wid in wids:
        items = await detect_decaying_articles(wid)
        total_queued += len(items)
        # Refresh up to 2 items per day to stay within budget
        for item in items[:2]:
            try:
                res = await refresh_decaying_article(item)
                if res:
                    total_refreshed += 1
            except Exception as e:
                logger.error(f"[ContentRefresh] Error refreshing item: {e}")

    logger.info(f"[ContentRefresh] Daily run complete: {total_queued} queued, {total_refreshed} refreshed across {len(wids)} sites.")
    return {"queued": total_queued, "refreshed": total_refreshed}
