"""Competitor Intelligence & Head-to-Head Tracking Service.
Provides competitor domain monitoring, Share of Voice (SOV) calculation,
competitor new pages feed, and head-to-head outranking gap matrix.
"""

import logging
from typing import Dict, List, Any, Optional

try:
    from backend.services.local_store import (
        save_local_competitor,
        list_local_competitors,
        delete_local_competitor,
        list_local_competitor_pages,
        get_local_website,
        list_local_keywords,
    )
except ImportError:
    from services.local_store import (
        save_local_competitor,
        list_local_competitors,
        delete_local_competitor,
        list_local_competitor_pages,
        get_local_website,
        list_local_keywords,
    )

logger = logging.getLogger("backend.services.competitor_intelligence_service")


def _normalize_domain(domain: str) -> str:
    """Strip protocols, paths, and www for clean domain comparison."""
    clean = domain.strip().lower()
    clean = clean.replace("https://", "").replace("http://", "")
    if clean.startswith("www."):
        clean = clean[4:]
    return clean.split("/")[0]


def get_competitors(website_id: str) -> List[Dict[str, Any]]:
    """Retrieve user-added competitor domains. Empty until user adds one."""
    return list_local_competitors(website_id)


def add_competitor(website_id: str, domain: str, label: Optional[str] = None) -> Dict[str, Any]:
    """Add a competitor domain to monitor. Stats stay null until measured."""
    clean_domain = _normalize_domain(domain)
    record = {
        "domain": clean_domain,
        "label": label or f"Competitor ({clean_domain})",
        "domain_authority": None,
        "organic_keywords_count": None,
        "est_monthly_visits": None,
        "verification": "pending — run SERP research to measure",
    }
    return save_local_competitor(website_id, record)


def remove_competitor(website_id: str, competitor_id: str) -> bool:
    """Remove a tracked competitor domain."""
    return delete_local_competitor(website_id, competitor_id)


def calculate_share_of_voice(website_id: str) -> Dict[str, Any]:
    """Own visibility from measured rank_tracking positions.

    Competitor shares stay null until head-to-head SERP comparison runs.
    """
    competitors = get_competitors(website_id)
    site = get_local_website(website_id)
    site_domain = _normalize_domain(site.get("domain", "Our Site")) if site else "Our Site"

    positions: List[float] = []
    try:
        from backend.database import get_supabase
    except (ImportError, ValueError):
        from database import get_supabase
    try:
        supabase = get_supabase()
        rows = supabase.table("rank_tracking").select("current_position").eq("website_id", website_id).execute().data or []
        for r in rows:
            try:
                if r.get("current_position") is not None:
                    positions.append(float(r["current_position"]))
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.debug(f"[sov] rank lookup note: {e}")

    if not positions:
        keywords = list_local_keywords(website_id)
        return {
            "website_id": website_id,
            "target_domain": site_domain,
            "our_sov_percentage": None,
            "our_sov_trend": None,
            "total_keywords_analyzed": len(keywords),
            "tracked_with_positions": 0,
            "market_leader": None,
            "competitors": [],
            "message": "No measured positions yet. Run rank tracking (POST /api/rankings/check) to populate.",
        }

    top3 = sum(1 for p in positions if p <= 3)
    top10 = sum(1 for p in positions if p <= 10)
    striking = sum(1 for p in positions if 11 <= p <= 20)
    avg_pos = round(sum(positions) / len(positions), 1)

    return {
        "website_id": website_id,
        "target_domain": site_domain,
        "our_sov_percentage": None,
        "our_sov_trend": None,
        "total_keywords_analyzed": len(positions),
        "tracked_with_positions": len(positions),
        "own_visibility": {
            "top_3_count": top3,
            "top_10_count": top10,
            "striking_distance_11_20": striking,
            "average_position": avg_pos,
        },
        "market_leader": None,
        "competitors": [
            {
                "domain": comp.get("domain"),
                "label": comp.get("label", comp.get("domain")),
                "sov_percentage": None,
                "top_3_rankings": None,
                "top_10_rankings": None,
                "authority": comp.get("domain_authority"),
                "trend": None,
            }
            for comp in competitors
        ],
        "message": "Own visibility measured from rank tracking. Competitor shares need head-to-head SERP comparison.",
    }


def get_competitor_new_pages(website_id: str) -> List[Dict[str, Any]]:
    """New competitor pages found by research. Empty until research runs."""
    return list_local_competitor_pages(website_id)


def get_outranking_gap_matrix(website_id: str) -> List[Dict[str, Any]]:
    """Striking-distance keywords from measured rank_tracking.

    Competitor side stays null until head-to-head SERP comparison runs —
    our positions and URLs are real, rival claims are not invented.
    """
    site = get_local_website(website_id)
    site_domain = _normalize_domain(site.get("domain", "")) if site else ""
    try:
        from backend.database import get_supabase
    except (ImportError, ValueError):
        from database import get_supabase
    try:
        supabase = get_supabase()
        rows = supabase.table("rank_tracking").select("target_keyword, current_position, wp_url").eq("website_id", website_id).gte("current_position", 11).lte("current_position", 20).order("current_position").limit(20).execute().data or []
    except Exception as e:
        logger.debug(f"[gaps] rank lookup note: {e}")
        rows = []
    gaps = []
    for r in rows:
        kw = r.get("target_keyword") or ""
        if not kw:
            continue
        gaps.append({
            "keyword": kw,
            "query": kw,
            "search_volume": None,
            "our_position": r.get("current_position"),
            "competitor_position": None,
            "competitor_domain": None,
            "competitor_url": None,
            "our_url": r.get("wp_url"),
            "monthly_clicks_lost": None,
            "potential_mrr_loss": None,
            "primary_gap_reason": "Ranking page 2 — needs CTR/title push to page 1. Rival comparison not yet measured.",
            "recommended_action": "Optimize title hook and internal links for this query.",
        })
    return gaps
