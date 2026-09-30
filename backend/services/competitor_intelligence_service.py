"""Competitor Intelligence & Head-to-Head Tracking Service.
Provides competitor domain monitoring, Share of Voice (SOV) calculation,
competitor new pages feed, and head-to-head outranking gap matrix.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    from backend.services.local_store import (
        save_local_competitor,
        list_local_competitors,
        delete_local_competitor,
        list_local_competitor_pages,
        get_local_website,
        list_local_keywords,
        update_local_competitor_metrics,
    )
except ImportError:
    from services.local_store import (
        save_local_competitor,
        list_local_competitors,
        delete_local_competitor,
        list_local_competitor_pages,
        get_local_website,
        list_local_keywords,
        update_local_competitor_metrics,
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
                "sov_percentage": comp.get("sov_percentage"),
                "top_3_rankings": comp.get("top_3_rankings"),
                "top_10_rankings": comp.get("top_10_rankings"),
                "authority": comp.get("domain_authority"),
                "trend": None,
                "verification": comp.get("verification"),
                "measured_at": comp.get("measured_at"),
            }
            for comp in competitors
        ],
        "message": "Own visibility measured from rank tracking. Competitor shares need head-to-head SERP comparison.",
    }


def get_measured_share_of_voice(website_id: str) -> Dict[str, Any]:
    """Share of Voice built from stored live-SERP measurements.

    Returns measured competitor shares when `measure_competitors_serp` has run;
    otherwise the same honest structure with nulls and a message pointing at the
    measure action.
    """
    competitors = get_competitors(website_id)
    site = get_local_website(website_id)
    site_domain = _normalize_domain(site.get("domain", "Our Site")) if site else "Our Site"
    measured = [c for c in competitors if c.get("sov_percentage") is not None]

    if not measured:
        base = calculate_share_of_voice(website_id)
        base["measured"] = False
        return base

    measured_at = max((c.get("measured_at") or "" for c in measured), default="")
    leader = max(measured, key=lambda c: c.get("sov_percentage") or 0)
    own = calculate_share_of_voice(website_id)
    own["competitors"] = [
        {
            "domain": c.get("domain"),
            "label": c.get("label", c.get("domain")),
            "sov_percentage": c.get("sov_percentage"),
            "top_3_rankings": c.get("top_3_rankings"),
            "top_10_rankings": c.get("top_10_rankings"),
            "authority": c.get("domain_authority"),
            "trend": None,
            "verification": c.get("verification"),
            "measured_at": c.get("measured_at"),
        }
        for c in competitors
    ]
    own["measured"] = True
    own["measured_at"] = measured_at
    own["market_leader"] = {"domain": leader.get("domain"), "sov_percentage": leader.get("sov_percentage")}
    own["message"] = f"Competitor shares measured from live SERPs on {measured_at[:10] or 'the last run'}."
    return own


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


def _site_keywords(website_id: str, limit: int = 8) -> List[str]:
    """Real tracked keywords for a site, preferring rank_tracking then local store."""
    queries: List[str] = []
    try:
        try:
            from backend.database import get_supabase
        except (ImportError, ValueError):
            from database import get_supabase
        rows = (
            get_supabase()
            .table("rank_tracking")
            .select("target_keyword")
            .eq("website_id", website_id)
            .limit(limit)
            .execute()
            .data
            or []
        )
        queries = [r.get("target_keyword") for r in rows if r.get("target_keyword")]
    except Exception as e:
        logger.debug(f"[competitors] rank_tracking keywords note: {e}")

    if not queries:
        for kw in list_local_keywords(website_id, limit=limit):
            q = kw.get("keyword") or kw.get("query")
            if q:
                queries.append(q)

    seen = set()
    out = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out[:limit]


async def measure_competitors_serp(website_id: str, max_keywords: int = 8) -> Dict[str, Any]:
    """Measure real head-to-head visibility by querying live SERPs.

    For each tracked keyword we record where our domain and each competitor
    domain appear in the top results. Every number comes from a live SERP call;
    when the provider is unavailable the result is an honest empty measurement
    rather than a fabricated share.
    """
    competitors = get_competitors(website_id)
    site = get_local_website(website_id)
    site_domain = _normalize_domain(site.get("domain", "")) if site else ""
    if not competitors:
        return {
            "success": False,
            "website_id": website_id,
            "measured": False,
            "message": "Add at least one competitor domain before measuring share of voice.",
        }

    keywords = _site_keywords(website_id, limit=max_keywords)
    if not keywords:
        return {
            "success": False,
            "website_id": website_id,
            "measured": False,
            "message": "No tracked keywords for this site yet. Run keyword research or rank tracking first.",
        }

    try:
        from backend.services.serper_service import serper_search_safe
    except ImportError:
        from services.serper_service import serper_search_safe

    tracked = [site_domain] + [_normalize_domain(c.get("domain", "")) for c in competitors if c.get("domain")]
    visibility: Dict[str, Dict[str, int]] = {d: {"top_3": 0, "top_10": 0, "appearances": 0} for d in tracked}
    serp_rows: List[Dict[str, Any]] = []
    serp_available = False

    for kw in keywords:
        try:
            organic = await serper_search_safe(kw, num_results=10)
        except Exception as e:
            logger.debug(f"[competitors] SERP note for '{kw}': {e}")
            organic = []
        if not organic:
            continue
        serp_available = True
        ranks: Dict[str, Dict[str, Any]] = {}
        for idx, item in enumerate(organic, start=1):
            link = item.get("link") or item.get("url") or ""
            dom = _normalize_domain(link)
            for tracked_dom in tracked:
                if tracked_dom and (dom == tracked_dom or dom.endswith("." + tracked_dom)):
                    if tracked_dom not in ranks:
                        ranks[tracked_dom] = {"position": idx, "url": link}
                    visibility[tracked_dom]["appearances"] += 1
                    if idx <= 3:
                        visibility[tracked_dom]["top_3"] += 1
                    if idx <= 10:
                        visibility[tracked_dom]["top_10"] += 1
        serp_rows.append({
            "keyword": kw,
            "our_position": ranks.get(site_domain, {}).get("position"),
            "our_url": ranks.get(site_domain, {}).get("url"),
            "competitor_ranks": [
                {
                    "domain": c.get("domain"),
                    "position": ranks.get(_normalize_domain(c.get("domain", "")), {}).get("position"),
                    "url": ranks.get(_normalize_domain(c.get("domain", "")), {}).get("url"),
                }
                for c in competitors
            ],
            "top_result_domain": _normalize_domain(organic[0].get("link") or "") if organic else None,
        })

    if not serp_available:
        return {
            "success": False,
            "website_id": website_id,
            "measured": False,
            "keywords_attempted": keywords,
            "message": "Live SERP lookups returned no results. Check SERPER_API_KEY in Connectors and try again.",
        }

    total_appearances = sum(v["appearances"] for v in visibility.values())
    measured_at = datetime.utcnow().isoformat()

    def _share(d: str) -> Optional[float]:
        return round((visibility[d]["appearances"] / total_appearances) * 100, 1) if total_appearances else None

    for comp in competitors:
        dom = _normalize_domain(comp.get("domain", ""))
        v = visibility.get(dom, {"top_3": 0, "top_10": 0, "appearances": 0})
        update_local_competitor_metrics(comp["id"], {
            "sov_percentage": _share(dom),
            "top_3_rankings": v["top_3"],
            "top_10_rankings": v["top_10"],
            "appearances": v["appearances"],
            "verification": "measured via live SERP",
            "measured_at": measured_at,
        })

    return {
        "success": True,
        "website_id": website_id,
        "measured": True,
        "keywords_measured": len(serp_rows),
        "measured_at": measured_at,
        "our_domain": site_domain,
        "our_share_of_voice": _share(site_domain),
        "our_visibility": visibility.get(site_domain, {}),
        "competitor_visibility": [
            {"domain": d, **v, "sov_percentage": _share(d)} for d, v in visibility.items() if d != site_domain
        ],
        "serp_results": serp_rows,
        "source": "serper.dev",
    }
