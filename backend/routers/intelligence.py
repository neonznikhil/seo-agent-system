"""Intelligence Router.

API surface for the six portfolio capabilities:
  * /intelligence/portfolio          - multi-site view
  * /intelligence/actions            - prioritized action list
  * /intelligence/leads/cpl          - cost per lead by keyword
  * /intelligence/guardrails/*       - preview, apply, undo, change log
  * /intelligence/competitors/*      - share of voice, new pages, gaps
  * /intelligence/measurement/*      - 28-day lift proof
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

try:
    from middleware.auth import get_current_account_id
except (ImportError, ValueError):
    from backend.middleware.auth import get_current_account_id

from services import intelligence_service as intel

logger = logging.getLogger("backend.routers.intelligence")
router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def _account(request: Request) -> Optional[str]:
    try:
        return get_current_account_id(request)
    except Exception:  # noqa: BLE001 - portfolio view is readable without auth
        return None


def _parse_date(value: Optional[str], field: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} must be YYYY-MM-DD")


# --------------------------------------------------------------------------
# Bullet 1: multi-site portfolio
# --------------------------------------------------------------------------

@router.get("/portfolio")
async def get_portfolio(request: Request):
    """One table of all sites with health, indexation, clicks and open issues."""
    return intel.portfolio_overview(_account(request))


@router.get("/integrations")
async def get_integrations():
    """Which data sources are live, and which still need credentials."""
    return intel.integration_status()


# --------------------------------------------------------------------------
# Bullet 2: prioritized actions
# --------------------------------------------------------------------------

@router.get("/actions/{website_id}")
async def list_actions(
    website_id: str,
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("traffic_impact", pattern="^(traffic_impact|effort)$"),
):
    """Ranked 'do these N things now', sorted by estimated traffic impact."""
    return intel.prioritized_actions(website_id, limit=limit, sort_by=sort_by)


@router.post("/actions/{website_id}")
async def create_action(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Add an action. Search volume and positions decide its traffic impact."""
    title = payload.get("title")
    category = payload.get("category")
    if not title or not category:
        raise HTTPException(status_code=400, detail="title and category are required")

    return intel.create_action(
        website_id=website_id,
        title=title,
        category=category,
        target_url=payload.get("target_url"),
        keyword=payload.get("keyword"),
        search_volume=payload.get("search_volume"),
        current_position=payload.get("current_position"),
        target_position=payload.get("target_position"),
        effort_minutes=int(payload.get("effort_minutes") or 30),
        confidence=float(payload.get("confidence") or 0.6),
        severity=payload.get("severity") or "medium",
        source=payload.get("source") or "manual",
    )


@router.get("/actions/{website_id}/score-preview")
async def score_preview(
    search_volume: Optional[int] = Query(None),
    current_position: Optional[float] = Query(None),
    target_position: Optional[float] = Query(None),
    confidence: float = Query(0.6, ge=0, le=1),
    effort_minutes: int = Query(30, ge=1),
):
    """Show the impact arithmetic without creating anything."""
    return intel.score_action(
        search_volume, current_position, target_position, confidence, effort_minutes
    )


@router.get("/ctr-curve")
async def ctr_curve():
    """The published CTR table used for every traffic projection."""
    return {
        "curve": intel.CTR_BY_POSITION,
        "note": "Organic CTR by SERP position; positions past 20 score zero.",
    }


# --------------------------------------------------------------------------
# Bullet 3: leads and cost per lead
# --------------------------------------------------------------------------

@router.post("/leads/conversions/{website_id}")
async def add_conversion(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Import one GA4 conversion row."""
    when = _parse_date(payload.get("conversion_date"), "conversion_date")
    if not when:
        raise HTTPException(status_code=400, detail="conversion_date is required")
    if not payload.get("landing_page"):
        raise HTTPException(status_code=400, detail="landing_page is required")

    return intel.record_conversion(
        website_id=website_id,
        landing_page=payload["landing_page"],
        conversion_date=when,
        count=int(payload.get("conversion_count") or 0),
        value=float(payload.get("conversion_value") or 0),
        session_source=payload.get("session_source") or "google / organic",
    )


@router.post("/leads/effort-cost/{website_id}")
async def add_effort_cost(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Record production effort so cost per lead has a real numerator."""
    when = _parse_date(payload.get("cost_date"), "cost_date")
    if not when:
        raise HTTPException(status_code=400, detail="cost_date is required")

    return intel.record_effort_cost(
        website_id=website_id,
        cost_date=when,
        category=payload.get("category") or "seo_work",
        minutes=float(payload.get("minutes") or 0),
        hourly_rate=float(payload.get("hourly_rate") or 0),
        api_cost=float(payload.get("api_cost") or 0),
    )


@router.post("/leads/cpl/{website_id}")
async def compute_cpl(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Cost per lead by keyword, with attribution limits stated explicitly."""
    start = _parse_date(payload.get("period_start"), "period_start")
    end = _parse_date(payload.get("period_end"), "period_end")
    if not start or not end:
        raise HTTPException(status_code=400, detail="period_start and period_end required")

    pairs = payload.get("keyword_page_pairs")
    if not isinstance(pairs, list) or not pairs:
        raise HTTPException(status_code=400, detail="keyword_page_pairs must be a non-empty list")

    return intel.cost_per_lead_by_keyword(
        website_id=website_id,
        keyword_page_pairs=pairs,
        period_start=start,
        period_end=end,
        hourly_rate=float(payload.get("hourly_rate") or 0),
    )


# --------------------------------------------------------------------------
# Bullet 4: guardrails
# --------------------------------------------------------------------------

@router.post("/guardrails/preview/{website_id}")
async def preview_guardrail_change(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Create a previewable change. Nothing touches the live site here."""
    target_url = payload.get("target_url")
    after_content = payload.get("after_content")
    if not target_url or after_content is None:
        raise HTTPException(status_code=400, detail="target_url and after_content are required")

    return intel.preview_change(
        website_id=website_id,
        target_url=target_url,
        change_type=payload.get("change_type") or "content_update",
        after_content=after_content,
        before_content=payload.get("before_content") or "",
        actor=payload.get("actor") or "system",
    )


@router.post("/guardrails/changes/{change_id}/apply")
async def apply_guardrail_change(change_id: str, payload: Dict[str, Any] = Body(default={})):
    """Apply after the human gate. YMYL changes need a second reviewer."""
    result = intel.apply_change(
        change_id,
        approver=payload.get("approver"),
        second_reviewer=payload.get("second_reviewer"),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=403, detail=result.get("error"))
    return result


@router.post("/guardrails/changes/{change_id}/undo")
async def undo_guardrail_change(change_id: str, payload: Dict[str, Any] = Body(default={})):
    """Undo an applied change using its stored inverse payload."""
    result = intel.undo_change(change_id, actor=payload.get("actor") or "system")
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/guardrails/changes/{website_id}")
async def get_change_log(website_id: str, limit: int = Query(50, ge=1, le=500)):
    """Change log: every preview, apply and undo with its diff."""
    return intel.change_log(website_id, limit=limit)


@router.get("/guardrails/classify")
async def classify_url(url: str = Query(...)):
    """Check whether a URL falls under legal/medical/financial YMYL rules."""
    is_ymyl, reason = intel.classify_ymyl(url)
    return {"url": url, "is_ymyl": is_ymyl, "reason": reason,
            "review_required": is_ymyl}


# --------------------------------------------------------------------------
# Bullet 5: competitors
# --------------------------------------------------------------------------

@router.post("/competitors/rankings/{website_id}")
async def add_competitor_ranking(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Store one observed competitor position."""
    when = _parse_date(payload.get("captured_date"), "captured_date")
    if not payload.get("competitor_domain") or not payload.get("keyword"):
        raise HTTPException(status_code=400,
                            detail="competitor_domain and keyword are required")
    return intel.record_competitor_ranking(
        website_id=website_id,
        competitor_domain=payload["competitor_domain"],
        keyword=payload["keyword"],
        position=payload.get("position"),
        captured_date=when or date.today(),
        url=payload.get("url"),
    )


@router.post("/competitors/share-of-voice/{website_id}")
async def compute_sov(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Share of voice across the tracked keyword set."""
    ours = payload.get("our_positions")
    theirs = payload.get("competitor_positions")
    if not isinstance(ours, dict):
        raise HTTPException(status_code=400, detail="our_positions must be an object")
    if not isinstance(theirs, dict):
        raise HTTPException(status_code=400, detail="competitor_positions must be an object")

    return intel.share_of_voice(website_id, ours, theirs)


@router.get("/competitors/gaps/{website_id}")
async def get_gaps(website_id: str, our_domain: str = Query(...)):
    """Where competitors outrank us.

    Position rows for ``our_domain`` are read as ours; every other domain on the
    same keywords is treated as a competitor. ``our_domain`` is required so the
    comparison is never silently made against an empty baseline.
    """
    from services import intelligence_store as store

    rows = store.select("competitor_rankings", {"website_id": website_id})
    if not rows:
        return {
            "website_id": website_id,
            "gaps": [],
            "has_data": False,
            "note": "No ranking data stored. Provide SERP data to populate.",
        }

    ours: Dict[str, Optional[int]] = {}
    theirs: Dict[str, Dict[str, Optional[int]]] = {}
    for r in rows:
        kw = str(r.get("keyword"))
        dom = str(r.get("competitor_domain"))
        pos = r.get("position")
        if dom.lower() == our_domain.lower():
            ours[kw] = pos
        else:
            theirs.setdefault(dom, {})[kw] = pos

    if not ours:
        return {
            "website_id": website_id,
            "our_domain": our_domain,
            "gaps": [],
            "has_data": False,
            "note": (
                f"No stored positions for {our_domain}. Record our own rankings "
                "under the same domain string to enable the comparison."
            ),
        }

    gaps = intel.outrank_gaps(ours, theirs)
    return {
        "website_id": website_id,
        "our_domain": our_domain,
        "our_keyword_count": len(ours),
        "competitor_count": len(theirs),
        "gaps": gaps,
        "has_data": True,
        "count": len(gaps),
    }


@router.post("/competitors/new-pages/{website_id}")
async def find_new_pages(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Diff a competitor's current page list against the recorded one."""
    domain = payload.get("competitor_domain")
    urls = payload.get("current_urls")
    if not domain or not isinstance(urls, list):
        raise HTTPException(status_code=400,
                            detail="competitor_domain and current_urls are required")
    return intel.detect_new_competitor_pages(website_id, domain, urls)


@router.get("/competitors/sov-history/{website_id}")
async def sov_history(website_id: str, limit: int = Query(30, ge=1, le=365)):
    """Share-of-voice trend over time."""
    from services import intelligence_store as store

    rows = store.select("sov_snapshots", {"website_id": website_id},
                        order_by="snapshot_date", desc=True, limit=limit)
    return {"website_id": website_id, "count": len(rows), "history": rows}


# --------------------------------------------------------------------------
# Bullet 6: prove the work
# --------------------------------------------------------------------------

@router.post("/measurement/windows/{website_id}")
async def open_window(website_id: str, payload: Dict[str, Any] = Body(...)):
    """Open a 28-day window for a shipped fix."""
    target_url = payload.get("target_url")
    if not target_url:
        raise HTTPException(status_code=400, detail="target_url is required")
    start = _parse_date(payload.get("window_start"), "window_start")

    return intel.create_measurement_window(
        website_id=website_id,
        target_url=target_url,
        keyword=payload.get("keyword"),
        change_event_id=payload.get("change_event_id"),
        baseline_clicks=float(payload.get("baseline_clicks") or 0),
        baseline_impressions=float(payload.get("baseline_impressions") or 0),
        baseline_position=payload.get("baseline_position"),
        control_urls=payload.get("control_urls") or [],
        baseline_control_clicks=float(payload.get("baseline_control_clicks") or 0),
        window_start=start,
    )


@router.post("/measurement/windows/{window_id}/snapshot")
async def add_snapshot(window_id: str, payload: Dict[str, Any] = Body(...)):
    """Record a day 0 / 7 / 14 / 28 observation."""
    offset = payload.get("day_offset")
    if offset is None:
        raise HTTPException(status_code=400, detail="day_offset is required")
    try:
        return intel.record_snapshot(
            window_id=window_id,
            day_offset=int(offset),
            clicks=float(payload.get("clicks") or 0),
            impressions=float(payload.get("impressions") or 0),
            position=payload.get("position"),
            control_clicks=float(payload.get("control_clicks") or 0),
            control_impressions=float(payload.get("control_impressions") or 0),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/measurement/windows/{window_id}/report")
async def window_report(window_id: str):
    """The 28-day lift: raw and control-adjusted."""
    result = intel.measurement_report(window_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@router.get("/measurement/change/{change_id}")
async def change_measurement(change_id: str):
    """Lift report for the window tied to a specific shipped change."""
    result = intel.measure_applied_change(change_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@router.get("/measurement/windows/site/{website_id}")
async def list_windows(website_id: str):
    """All measurement windows for a site."""
    from services import intelligence_store as store

    rows = store.select("measurement_windows", {"website_id": website_id},
                        order_by="window_start", desc=True)
    return {"website_id": website_id, "count": len(rows), "windows": rows,
            "expected_offsets": list(intel.SNAPSHOT_OFFSETS)}