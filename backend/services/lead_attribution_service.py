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

# GA4 reporting calls are slow; cache per website so a page load that fires
# several attribution requests does not issue several live API round-trips.
_GA4_CACHE: Dict[str, Any] = {}
_GA4_CACHE_TTL_SECONDS = 300


def _get_ga4_conversions(website_id: str, days: int = 28) -> Dict[str, Any]:
    """Live GA4 conversion + landing-page data.

    Returns a dict with `status`:
      - "ok":            `total_conversions` and `page_sessions` are real
      - "not_connected": GA4 has no usable credentials configured
      - "error":         configured but the API call failed (`detail` explains)

    Callers report `None` CPL in the non-"ok" cases rather than presenting an
    unmeasured 0 as a real result.
    """
    now = datetime.utcnow()
    cached = _GA4_CACHE.get(website_id)
    if cached and (now - cached["at"]).total_seconds() < _GA4_CACHE_TTL_SECONDS:
        return cached["data"]

    try:
        from backend.services.ga4_service import GA4Service
    except ImportError:
        from services.ga4_service import GA4Service

    svc = GA4Service()
    if not svc.is_connected():
        result = {"status": "not_connected"}
        _GA4_CACHE[website_id] = {"at": now, "data": result}
        return result

    from datetime import timedelta

    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    def _call() -> Dict[str, Any]:
        svc._ensure_initialized()
        props = f"properties/{svc.property_id}"

        conv_rows = svc._service.properties().runReport(
            property=props,
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "metrics": [{"name": "eventCount"}],
                "dimensionFilter": {
                    "filter": {
                        "fieldName": "eventName",
                        "inListFilter": {
                            "values": ["generate_lead", "purchase", "submit_lead_form", "contact", "signup"]
                        },
                    }
                },
            },
        ).execute()
        total_conversions = 0
        for row in conv_rows.get("rows", []):
            mets = row.get("metricValues") or [{}]
            total_conversions += int(float(mets[0].get("value", 0) or 0))

        page_rows = svc._service.properties().runReport(
            property=props,
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "dimensions": [{"name": "landingPagePlusQueryString"}],
                "metrics": [{"name": "sessions"}],
                "limit": 500,
            },
        ).execute()
        pages: Dict[str, int] = {}
        for row in page_rows.get("rows", []):
            dims = row.get("dimensionValues") or [{}]
            mets = row.get("metricValues") or [{}]
            pages[dims[0].get("value", "")] = int(float(mets[0].get("value", 0) or 0))

        return {"status": "ok", "total_conversions": total_conversions, "page_sessions": pages}

    try:
        data = _call()
    except Exception as e:
        logger.warning(f"[leads] GA4 lookup failed: {e}")
        result = {"status": "error", "detail": str(e)[:200]}
        _GA4_CACHE[website_id] = {"at": now, "data": result}
        return result

    _GA4_CACHE[website_id] = {"at": now, "data": data}
    return data


def _normalise_path(url: str) -> str:
    """Reduce a URL or path to a comparable path segment."""
    if not url:
        return "/"
    path = url.split("://", 1)[-1]
    path = path.split("?", 1)[0].split("#", 1)[0]
    if "/" in path:
        path = "/" + path.split("/", 1)[1]
    return path or "/"


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

    # Real GA4 data, when connected. Conversions are only distributed to keywords
    # proportionally to their measured click share and the result is labelled as
    # an estimate; the summary CVR/CPL below are measured directly.
    ga4 = _get_ga4_conversions(website_id)
    ga4_status = ga4.get("status")
    ga4_ok = ga4_status == "ok"
    total_ga4_sessions = sum(ga4["page_sessions"].values()) if ga4_ok else None
    total_ga4_conversions = ga4["total_conversions"] if ga4_ok else None
    conversions_attributed = ga4_ok

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
            "conversions": None,
            "attributed_leads": None,
            "cvr": None,
            "conversion_rate_pct": None,
            "pipeline_value": 0.0,
            "estimated_value": 0.0,
            "cost_per_lead": None,
            "cpl": None,
            "opportunity_flag": "NEEDS_GA4",
        })

    keyword_rows.sort(key=lambda k: k["clicks"], reverse=True)

    # Distribute measured GA4 conversions across keywords by click share. This is
    # an estimate (GA4 cannot attribute a conversion to a query), so it is
    # explicitly flagged rather than presented as per-keyword truth.
    if conversions_attributed and total_clicks > 0:
        for row in keyword_rows:
            share = row["clicks"] / total_clicks
            conv = round((total_ga4_conversions or 0) * share, 1)
            row["conversions"] = conv
            row["attributed_leads"] = round(conv)
            if row["clicks"] > 0:
                row["cvr"] = round(conv / row["clicks"], 4)
                row["conversion_rate_pct"] = round((conv / row["clicks"]) * 100, 2)
            row["conversion_attribution"] = "estimated_by_click_share"
            row["opportunity_flag"] = "OK"

    blended_cvr = None
    blended_cpl = None
    total_leads = None
    if conversions_attributed:
        total_leads = total_ga4_conversions
        if total_ga4_sessions:
            blended_cvr = round((total_ga4_conversions or 0) / total_ga4_sessions, 4)
        if total_ga4_conversions:
            blended_cpl = round(monthly_spend / total_ga4_conversions, 2)

    cpl_variance = None
    if blended_cpl is not None and target_cpl:
        cpl_variance = round(((blended_cpl - target_cpl) / target_cpl) * 100, 1)

    if ga4_status == "not_connected":
        message = "Connect GA4 conversions to attribute leads. Clicks shown are measured; leads need conversion data."
    elif ga4_status == "error":
        message = (
            "GA4 is configured but the API call failed, so leads and CPL are unavailable. "
            f"{ga4.get('detail', '')[:160]}"
        )
        message = message.strip()
    elif not total_ga4_conversions:
        message = (
            "GA4 is connected but recorded no lead events in this period. "
            "Clicks are measured; CPL cannot be calculated until conversions exist."
        )
    else:
        message = (
            f"GA4 measured {total_ga4_conversions} conversion(s) over {total_ga4_sessions or 0} sessions. "
            "Per-keyword leads are estimated from click share."
        )

    return {
        "website_id": website_id,
        "domain": domain,
        "settings": settings,
        "ga4_connected": conversions_attributed,
        "ga4_status": ga4_status,
        "summary": {
            "total_organic_leads": total_leads,
            "total_organic_leads_28d": total_leads,
            "total_organic_clicks": total_clicks,
            "total_organic_clicks_28d": total_clicks,
            "total_ga4_sessions": total_ga4_sessions,
            "blended_cvr": blended_cvr,
            "blended_cvr_pct": round(blended_cvr * 100, 2) if blended_cvr is not None else None,
            "blended_cpl": blended_cpl,
            "target_cpl": target_cpl,
            "cpl_variance_pct": cpl_variance,
            "total_pipeline_value": 0.0,
            "monthly_seo_spend": monthly_spend,
            "roi_ratio": None,
            "message": message,
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
