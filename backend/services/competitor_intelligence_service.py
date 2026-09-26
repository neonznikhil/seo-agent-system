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
    """Share of Voice from measured positions only. Null until research runs."""
    competitors = get_competitors(website_id)
    site = get_local_website(website_id)
    site_domain = _normalize_domain(site.get("domain", "Our Site")) if site else "Our Site"

    keywords = list_local_keywords(website_id)
    if not competitors or not keywords:
        return {
            "website_id": website_id,
            "target_domain": site_domain,
            "our_sov_percentage": None,
            "our_sov_trend": None,
            "total_keywords_analyzed": len(keywords),
            "market_leader": None,
            "competitors": [],
            "message": "Add competitor domains and run keyword research to measure Share of Voice.",
        }

    total_keywords = len(keywords)
    competitor_shares = []
    for comp in competitors:
        competitor_shares.append({
            "domain": comp.get("domain"),
            "label": comp.get("label", comp.get("domain")),
            "sov_percentage": None,
            "top_3_rankings": None,
            "top_10_rankings": None,
            "authority": comp.get("domain_authority"),
            "trend": None,
        })

    return {
        "website_id": website_id,
        "target_domain": site_domain,
        "our_sov_percentage": None,
        "our_sov_trend": None,
        "total_keywords_analyzed": total_keywords,
        "market_leader": None,
        "competitors": competitor_shares,
        "message": "Competitor positions not yet measured. Run SERP research to compute Share of Voice.",
    }


def get_competitor_new_pages(website_id: str) -> List[Dict[str, Any]]:
    """New competitor pages found by research. Empty until research runs."""
    return list_local_competitor_pages(website_id)


def get_outranking_gap_matrix(website_id: str) -> List[Dict[str, Any]]:
    """Queries where competitors outrank us. Empty until SERP research measures both sides."""
    return []
