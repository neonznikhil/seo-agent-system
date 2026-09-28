"""Lead Attribution Service.
Bridges Google Search Console keyword queries and GA4 conversion events
to attribute leads, conversion rates (CVR), and Cost Per Lead (CPL) by keyword.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from backend.services.local_store import (
        get_local_website,
        list_local_keyword_research,
        get_local_lead_settings,
        save_local_lead_settings,
    )
except ImportError:
    from services.local_store import (
        get_local_website,
        list_local_keyword_research,
        get_local_lead_settings,
        save_local_lead_settings,
    )

logger = logging.getLogger("backend.services.lead_attribution_service")


def get_keyword_lead_attribution(website_id: str) -> Dict[str, Any]:
    """Calculate and return keyword-level lead attribution, CVR %, and CPL."""
    site = get_local_website(website_id)
    domain = site.get("domain", "example.com") if site else "example.com"
    settings = get_local_lead_settings(website_id)

    try:
        monthly_spend = float(settings.get("monthly_seo_spend", 2500.0) or 2500.0)
    except (ValueError, TypeError):
        monthly_spend = 2500.0

    try:
        target_cpl = float(settings.get("target_cpl", 75.0) or 75.0)
    except (ValueError, TypeError):
        target_cpl = 75.0

    # Real keyword rows only — analytics_data (GSC sync) plus gsc_keywords.
    # Conversions stay 0/None until GA4 supplies them. No samples invented.
    agg: Dict[str, Dict[str, Any]] = {}

    def _fold(rows: Any) -> None:
        for kw in rows or []:
            if not isinstance(kw, dict):
                continue
            query = kw.get("keyword") or kw.get("query")
            if not query:
                continue
            try:
                clicks = int(float(kw.get("clicks", 0) or 0))
            except (ValueError, TypeError):
                clicks = 0
            try:
                impressions = int(float(kw.get("impressions", 0) or 0))
            except (ValueError, TypeError):
                impressions = 0
            try:
                pos = float(kw.get("position")) if kw.get("position") is not None else None
            except (ValueError, TypeError):
                pos = None
            page = kw.get("landing_page") or kw.get("page") or kw.get("url") or "/"
            slot = agg.setdefault(query, {"clicks": 0, "impressions": 0, "positions": [], "page": page})
            slot["clicks"] += clicks
            slot["impressions"] += impressions
            if pos is not None:
                slot["positions"].append(pos)

    try:
        from backend.database import get_supabase
    except (ImportError, ValueError):
        from database import get_supabase
    try:
        supabase = get_supabase()
        try:
            rows = supabase.table("analytics_data").select("keyword, clicks, impressions, position").eq("website_id", website_id).limit(500).execute().data or []
            _fold(rows)
        except Exception as e:
            logger.debug(f"[leads] analytics_data note: {e}")
        try:
            grows = supabase.table("gsc_keywords").select("keyword, clicks, impressions, position").eq("website_id", website_id).limit(500).execute().data or []
            _fold(grows)
        except Exception as e:
            logger.debug(f"[leads] gsc_keywords note: {e}")
    except Exception as e:
        logger.debug(f"[leads] supabase note: {e}")

    measured = [
        {
            "query": q,
            "landing_page": v["page"],
            "pos": min(v["positions"]) if v["positions"] else None,
            "clicks": v["clicks"],
            "impressions": v["impressions"],
        }
        for q, v in agg.items()
    ]

    keyword_rows = []
    total_clicks = 0

    for item in measured:
        try:
            clicks = int(float(item["clicks"] or 0))
        except (ValueError, TypeError):
            clicks = 0
        try:
            impressions = int(float(item.get("impressions", 0) or 0))
        except (ValueError, TypeError):
            impressions = 0
        try:
            pos = float(item["pos"]) if item["pos"] is not None else None
        except (ValueError, TypeError):
            pos = None
        total_clicks += clicks
        keyword_rows.append({
            "query": item["query"],
            "keyword": item["query"],
            "landing_page": item["landing_page"],
            "position": pos,
            "clicks": clicks,
            "clicks_28d": clicks,
            "impressions_28d": impressions,
            "conversions": 0,
            "attributed_leads": 0,
            "cvr": None,
            "conversion_rate_pct": None,
            "pipeline_value": 0.0,
            "estimated_value": 0.0,
            "cost_per_lead": None,
            "cpl": None,
            "opportunity_flag": "NEEDS_GA4",
        })

    keyword_rows.sort(key=lambda k: k["clicks"], reverse=True)

    return {
        "website_id": website_id,
        "domain": domain,
        "settings": settings,
        "summary": {
            "total_organic_leads": 0,
            "total_organic_leads_28d": 0,
            "total_organic_clicks": total_clicks,
            "total_organic_clicks_28d": total_clicks,
            "blended_cvr": None,
            "blended_cvr_pct": None,
            "blended_cpl": None,
            "target_cpl": target_cpl,
            "cpl_variance_pct": None,
            "total_pipeline_value": 0.0,
            "monthly_seo_spend": monthly_spend,
            "roi_ratio": None,
            "message": "Connect GA4 conversions to attribute leads. Clicks shown are measured; leads need conversion data.",
        },
        "keywords": keyword_rows,
        "generated_at": datetime.utcnow().isoformat(),
    }


def update_lead_settings(website_id: str, new_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Update website's lead and conversion settings (monthly spend, target CPL, lead value)."""
    saved = save_local_lead_settings(website_id, new_settings)
    result = {
        "status": "success",
        "settings": saved,
        "message": "Lead attribution configuration updated successfully."
    }
    if isinstance(saved, dict):
        result.update(saved)
    return result
