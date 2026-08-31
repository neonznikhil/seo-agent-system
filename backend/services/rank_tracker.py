"""RankForge Post-Publish Rank Tracking Service.
Automatically tracks Google positions for published WordPress posts via Serper API,
computes position histories, triggers rank shift alerts, and provides dashboard metrics.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from ..database import get_supabase
from ..services.serper_service import serper_service
from ..services.local_store import (
    save_local_rank_tracking,
    list_local_rank_tracking,
    get_local_rank_tracking,
)

logger = logging.getLogger("backend.services.rank_tracker")


def _normalize_url(url: str) -> str:
    """Normalize URL for resilient domain/path comparison."""
    if not url:
        return ""
    u = url.strip().lower()
    if u.endswith("/"):
        u = u[:-1]
    parsed = urlparse(u)
    netloc = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


async def track_published_post(
    website_id: str,
    wp_post_id: str,
    wp_url: str,
    target_keyword: str,
    blog_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Called automatically after every WordPress publish.
    Sets up rank tracking for the published post.
    """
    record = {
        "website_id": website_id,
        "wp_post_id": str(wp_post_id),
        "wp_url": wp_url,
        "target_keyword": target_keyword,
        "blog_id": blog_id,
        "title": title or target_keyword,
        "status": "tracking",
        "published_at": datetime.utcnow().isoformat(),
        "last_checked_at": None,
        "current_position": None,
        "best_position": None,
        "position_history": [],
    }

    try:
        supabase = get_supabase()
        res = supabase.table("rank_tracking").insert(record).execute()
        if res and res.data:
            record["id"] = res.data[0].get("id")
    except Exception as e:
        logger.debug(f"[RankTracker] Supabase insert note (using local store): {e}")

    saved = save_local_rank_tracking(record)
    logger.info(f"[RankTracker] Initialized rank tracking for '{target_keyword}' ({wp_url})")
    return saved


async def create_rank_alert(
    website_id: str,
    keyword: str,
    change: int,
    current_position: int,
) -> None:
    """
    Create a monitoring alert when a tracked post jumps or drops by >= 5 positions.
    """
    direction = "rose" if change > 0 else "dropped"
    severity = "info" if change > 0 else "warning" if abs(change) < 10 else "critical"
    msg = f"Keyword '{keyword}' {direction} by {abs(change)} positions to #{current_position} on Google."

    alert_data = {
        "website_id": website_id,
        "alert_type": "rank_shift",
        "severity": severity,
        "title": f"Rank Shift: '{keyword}' (#{current_position})",
        "message": msg,
        "metric_name": "google_rank",
        "metric_value": float(current_position),
        "created_at": datetime.utcnow().isoformat(),
        "status": "active",
    }

    try:
        supabase = get_supabase()
        supabase.table("monitoring_alerts").insert(alert_data).execute()
    except Exception as e:
        logger.debug(f"[RankTracker] Alert insert note: {e}")

    logger.info(f"[RankTracker Alert] {msg}")


async def check_keyword_rankings(website_id: str) -> List[Dict[str, Any]]:
    """
    Runs every 6 hours via scheduler.
    For each tracked post, checks current Google ranking using Serper API.
    """
    posts: List[Dict[str, Any]] = []
    try:
        supabase = get_supabase()
        res = (
            supabase.table("rank_tracking")
            .select("*")
            .eq("website_id", website_id)
            .eq("status", "tracking")
            .execute()
        )
        posts = res.data or []
    except Exception as e:
        logger.debug(f"[RankTracker] Query note: {e}")

    local_posts = list_local_rank_tracking(website_id=website_id, status="tracking")
    known_ids = {str(p.get("id")) for p in posts if p.get("id")}
    for lp in local_posts:
        if str(lp.get("id")) not in known_ids:
            posts.append(lp)
            known_ids.add(str(lp.get("id")))

    updated_records = []
    for post in posts:
        keyword = post.get("target_keyword")
        wp_url = post.get("wp_url")
        if not keyword or not wp_url:
            continue

        norm_target = _normalize_url(wp_url)
        position: Optional[int] = None

        try:
            # Search Serper for keyword
            search_data = await serper_service.search(keyword, num_results=100)
            organic_results = search_data.get("organic", []) if isinstance(search_data, dict) else (search_data or [])

            for i, result in enumerate(organic_results):
                result_link = result.get("link", "")
                norm_result = _normalize_url(result_link)
                if wp_url in result_link or (norm_target and norm_target in norm_result):
                    position = i + 1
                    break
        except Exception as e:
            logger.warning(f"[RankTracker] Serper search failed for '{keyword}': {e}")
            position = post.get("current_position")

        # Update tracking record
        history = list(post.get("position_history") or [])
        now_iso = datetime.utcnow().isoformat()
        history.append({
            "date": now_iso,
            "position": position,
        })

        best = post.get("best_position")
        if position is not None and (best is None or position < best):
            best = position

        updates = {
            "current_position": position,
            "best_position": best,
            "position_history": history,
            "last_checked_at": now_iso,
        }

        try:
            supabase = get_supabase()
            if post.get("id"):
                supabase.table("rank_tracking").update(updates).eq("id", post["id"]).execute()
        except Exception:
            pass

        merged = {**post, **updates}
        save_local_rank_tracking(merged)
        updated_records.append(merged)

        # Alert if big rank change
        valid_positions = [h.get("position") for h in history if h.get("position") is not None]
        if len(valid_positions) >= 2:
            prev = valid_positions[-2]
            curr = valid_positions[-1]
            if prev and curr:
                change = prev - curr  # positive = moved up
                if abs(change) >= 5:
                    await create_rank_alert(
                        website_id=website_id,
                        keyword=keyword,
                        change=change,
                        current_position=curr,
                    )

    return updated_records


async def check_all_rankings() -> Dict[str, Any]:
    """
    Master job scheduled every 6 hours across all websites.
    """
    from ..services.local_store import list_local_websites
    websites = []
    try:
        supabase = get_supabase()
        res = supabase.table("websites").select("id, domain").execute()
        websites = res.data or []
    except Exception:
        pass

    local_sites = list_local_websites()
    known_wids = {s.get("id") for s in websites if s.get("id")}
    for ls in local_sites:
        if ls.get("id") not in known_wids:
            websites.append(ls)
            known_wids.add(ls.get("id"))

    if not websites:
        websites = [{"id": "default", "domain": "localhost"}]

    total_checked = 0
    for site in websites:
        wid = site.get("id")
        if wid:
            res = await check_keyword_rankings(wid)
            total_checked += len(res)

    logger.info(f"[RankTracker] 6h ranking check completed: {total_checked} posts updated across {len(websites)} sites.")
    return {"checked_websites": len(websites), "total_posts_checked": total_checked}


def get_tracked_rankings(website_id: str) -> List[Dict[str, Any]]:
    """
    Returns all tracked posts for a website for the Content Performance dashboard widget.
    """
    posts: List[Dict[str, Any]] = []
    try:
        supabase = get_supabase()
        res = (
            supabase.table("rank_tracking")
            .select("*")
            .eq("website_id", website_id)
            .order("published_at", desc=True)
            .execute()
        )
        posts = res.data or []
    except Exception:
        pass

    local_posts = list_local_rank_tracking(website_id=website_id)
    known_ids = {str(p.get("id")) for p in posts if p.get("id")}
    for lp in local_posts:
        if str(lp.get("id")) not in known_ids:
            posts.append(lp)
            known_ids.add(str(lp.get("id")))

    # Enrich each record with change direction & color
    enriched = []
    for p in posts:
        history = p.get("position_history") or []
        valid_pos = [h.get("position") for h in history if h.get("position") is not None]
        change = 0
        if len(valid_pos) >= 2:
            change = valid_pos[-2] - valid_pos[-1]  # positive = improved

        current = p.get("current_position")
        status_label = "Checking..."
        if current is not None:
            if current <= 3:
                status_label = "Top 3"
            elif current <= 10:
                status_label = "Page 1"
            elif current <= 20:
                status_label = "Striking Distance"
            else:
                status_label = "Needs Work"
        elif p.get("last_checked_at"):
            status_label = "Not in Top 100"

        enriched.append({
            "id": p.get("id"),
            "website_id": p.get("website_id"),
            "title": p.get("title") or p.get("target_keyword") or "Untitled Post",
            "target_keyword": p.get("target_keyword") or "",
            "keyword": p.get("target_keyword") or "",
            "wp_url": p.get("wp_url") or "",
            "published_at": p.get("published_at"),
            "last_checked_at": p.get("last_checked_at"),
            "current_position": current,
            "best_position": p.get("best_position"),
            "change": change,
            "status_label": status_label,
            "status": p.get("status", "tracking"),
            "position_history": history,
        })

    return enriched
