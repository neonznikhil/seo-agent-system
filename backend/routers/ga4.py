"""GA4 traffic + conversion endpoints.

`ga4_service` could already read real GA4 data, but nothing exposed it over
HTTP: the only "GA4" route was `/api/analytics/conversions`, which read a
`ga4_conversions` table that nothing ever writes to. These endpoints surface the
live Data API so the dashboard, leads and CPL sections have a real source.

Every response carries `connected` and, when disconnected, a `message` saying
what to do — a zero is never presented as if it were measured data.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger("backend.routers.ga4")

router = APIRouter(prefix="/api/ga4", tags=["GA4"])

# GA4 treats the funnel as a sequence of events; these are the names a
# conversion is normally reported under. Kept configurable per request.
DEFAULT_CONVERSION_EVENTS = ["generate_lead", "purchase", "submit_lead_form", "contact", "signup"]


def _service():
    try:
        from services.ga4_service import GA4Service
    except ImportError:
        from backend.services.ga4_service import GA4Service
    return GA4Service()


def _not_connected(website_id: str, what: str) -> Dict[str, Any]:
    return {
        "success": True,
        "connected": False,
        "website_id": website_id,
        what: [],
        "message": "GA4 is not connected. Add the Property ID and service-account JSON in Connectors to see real data.",
    }


def _query_failed(website_id: str, error: Exception) -> Dict[str, Any]:
    """Map a GA4 API failure to an actionable message.

    The credentials can be well-formed and still be rejected by Google (a
    deleted service account, or it was never granted access to the property).
    Saying just "query failed" sends the user hunting for the wrong problem.
    """
    detail = str(error)
    if "invalid_grant" in detail.lower() or "account not found" in detail.lower():
        hint = (
            "The GA4 service account is rejected by Google (invalid_grant). "
            "The key may have been deleted, or the service-account email has not been "
            "granted access to the GA4 property. Re-issue the key or add the email as a "
            "viewer in GA4 Admin > Property Access Management."
        )
    elif "permission" in detail.lower() or "403" in detail:
        hint = (
            "Google refused the GA4 request (permission denied). Grant the service-account "
            "email at least Viewer access to the property in GA4 Admin."
        )
    elif "not found" in detail.lower() or "404" in detail:
        hint = "The GA4 property ID was not found. Check the Property ID in Connectors."
    else:
        hint = f"GA4 query failed: {detail[:200]}"
    return {
        "success": False,
        "connected": True,
        "website_id": website_id,
        "message": hint,
        "error": detail[:300],
    }


@router.get("/{website_id}/summary")
async def ga4_summary(
    website_id: str,
    days: int = Query(28, ge=1, le=365),
):
    """Headline GA4 metrics: sessions, users, engagement, page views."""
    svc = _service()
    if not svc.is_connected():
        return _not_connected(website_id, "summary")

    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    import asyncio

    def _call() -> Dict[str, Any]:
        svc._ensure_initialized()
        response = svc._service.properties().runReport(
            property=f"properties/{svc.property_id}",
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "metrics": [
                    {"name": "sessions"},
                    {"name": "totalUsers"},
                    {"name": "screenPageViews"},
                    {"name": "engagementRate"},
                    {"name": "averageSessionDuration"},
                ],
            },
        ).execute()
        rows = response.get("rows", [])
        metrics = rows[0].get("metricValues", []) if rows else []
        get = lambda i: metrics[i].get("value") if len(metrics) > i else None  # noqa: E731
        return {
            "sessions": int(float(get(0) or 0)),
            "total_users": int(float(get(1) or 0)),
            "screen_page_views": int(float(get(2) or 0)),
            "engagement_rate": float(get(3) or 0),
            "avg_session_duration": float(get(4) or 0),
        }

    try:
        data = await asyncio.wait_for(asyncio.to_thread(_call), timeout=25.0)
    except Exception as e:
        logger.warning(f"[ga4] summary failed: {e}")
        return _query_failed(website_id, e)

    return {
        "success": True,
        "connected": True,
        "website_id": website_id,
        "date_range": {"start": start_date, "end": end_date, "days": days},
        "source": "ga4",
        **data,
    }


@router.get("/{website_id}/conversions")
async def ga4_conversions(
    website_id: str,
    days: int = Query(28, ge=1, le=365),
    event: Optional[str] = Query(None, description="Conversion event name; defaults to common lead events"),
):
    """Conversion totals from GA4, broken down by event name.

    Returns an empty list with `connected: True` when GA4 is reachable but the
    property records none of these events — that is a real answer, not an error.
    """
    svc = _service()
    if not svc.is_connected():
        return _not_connected(website_id, "conversions")

    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    events = [event] if event else DEFAULT_CONVERSION_EVENTS

    import asyncio

    def _call() -> Dict[str, Any]:
        svc._ensure_initialized()
        response = svc._service.properties().runReport(
            property=f"properties/{svc.property_id}",
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "dimensions": [{"name": "eventName"}],
                "metrics": [{"name": "eventCount"}],
                "dimensionFilter": {
                    "filter": {
                        "fieldName": "eventName",
                        "inListFilter": {"values": events},
                    }
                },
            },
        ).execute()
        out = []
        total = 0
        for row in response.get("rows", []):
            name = (row.get("dimensionValues") or [{}])[0].get("value", "")
            count = int(float((row.get("metricValues") or [{}])[0].get("value", 0) or 0))
            total += count
            out.append({"event": name, "count": count})
        return {"conversions": out, "total_conversions": total}

    try:
        data = await asyncio.wait_for(asyncio.to_thread(_call), timeout=25.0)
    except Exception as e:
        logger.warning(f"[ga4] conversions failed: {e}")
        return _query_failed(website_id, e)

    return {
        "success": True,
        "connected": True,
        "website_id": website_id,
        "date_range": {"start": start_date, "end": end_date, "days": days},
        "tracked_events": events,
        "source": "ga4",
        **data,
    }


@router.get("/{website_id}/landing-pages")
async def ga4_landing_pages(
    website_id: str,
    days: int = Query(28, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
):
    """Top landing pages by sessions — feeds the leads/CPL section."""
    svc = _service()
    if not svc.is_connected():
        return _not_connected(website_id, "landing_pages")

    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    import asyncio

    def _call() -> Dict[str, Any]:
        svc._ensure_initialized()
        response = svc._service.properties().runReport(
            property=f"properties/{svc.property_id}",
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "dimensions": [{"name": "landingPagePlusQueryString"}],
                "metrics": [{"name": "sessions"}, {"name": "totalUsers"}],
                "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
                "limit": limit,
            },
        ).execute()
        pages = []
        for row in response.get("rows", []):
            dims = row.get("dimensionValues") or [{}]
            mets = row.get("metricValues") or [{}]
            pages.append(
                {
                    "landing_page": dims[0].get("value", ""),
                    "sessions": int(float((mets[0] if len(mets) > 0 else {}).get("value", 0) or 0)),
                    "users": int(float((mets[1] if len(mets) > 1 else {}).get("value", 0) or 0)),
                }
            )
        return {"pages": pages}

    try:
        data = await asyncio.wait_for(asyncio.to_thread(_call), timeout=25.0)
    except Exception as e:
        logger.warning(f"[ga4] landing pages failed: {e}")
        return _query_failed(website_id, e)

    return {
        "success": True,
        "connected": True,
        "website_id": website_id,
        "date_range": {"start": start_date, "end": end_date, "days": days},
        "source": "ga4",
        **data,
    }
