"""RankForge portfolio intelligence.

Implements the six product capabilities:
  1. multi-site portfolio view
  2. prioritized action list ranked by estimated traffic impact
  3. lead attribution and cost per lead by keyword
  4. guardrails: preview diff, apply, undo, change log, YMYL gating
  5. competitor share of voice, new pages, outrank gaps
  6. 28-day lift measurement with a control set

Design rules enforced here:
  * no fabricated values - unconfigured inputs surface as ``unconfigured``
  * every derived number carries its inputs in ``evidence``
  * attribution is labelled with its method and confidence
"""

import difflib
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services import intelligence_store as store

logger = logging.getLogger("backend.services.intelligence")

# ---------------------------------------------------------------------------
# CTR curve
#
# Organic click-through rate by SERP position. These are mid-range values from
# published organic CTR studies and are deliberately a single documented table
# rather than a black box, so projections can be reproduced and audited.
# Anything beyond position 20 is treated as out of reach (0 clicks).
# ---------------------------------------------------------------------------
CTR_BY_POSITION: Dict[int, float] = {
    1: 0.284,
    2: 0.152,
    3: 0.099,
    4: 0.071,
    5: 0.053,
    6: 0.041,
    7: 0.033,
    8: 0.027,
    9: 0.023,
    10: 0.020,
    11: 0.014,
    12: 0.012,
    13: 0.011,
    14: 0.010,
    15: 0.009,
    16: 0.008,
    17: 0.007,
    18: 0.006,
    19: 0.005,
    20: 0.004,
}


def ctr_for_position(position: Optional[float]) -> float:
    """Organic CTR for a SERP position. Beyond position 20 returns 0.0."""
    if position is None or position <= 0:
        return 0.0
    idx = int(round(position))
    if idx < 1:
        idx = 1
    return CTR_BY_POSITION.get(idx, 0.0)


DQ = "unconfigured"
OK = "ok"


def _integration(name: str, configured: bool, detail: str = "") -> Dict[str, Any]:
    return {
        "name": name,
        "status": OK if configured else DQ,
        "detail": detail or ("ready" if configured else "credentials not set"),
    }


# ===========================================================================
# Bullet 1: multi-site portfolio
# ===========================================================================

def compute_health_score(critical: int, high: int, medium: int) -> Tuple[int, str]:
    """Health = 100 - weighted issue count, floored at 0.

    Weights: critical 5, high 2, medium 1. The formula is returned alongside the
    score so the UI can show the arithmetic instead of a bare number.
    """
    score = 100 - (5 * critical) - (2 * high) - (1 * medium)
    score = max(0, min(100, score))
    formula = f"100 - (5 x {critical}) - (2 x {high}) - (1 x {medium}) = {score}"
    return score, formula


def portfolio_overview(account_id: Optional[str] = None) -> Dict[str, Any]:
    """One table of all sites: health, indexation, clicks, open issues."""
    sites = _load_sites(account_id)
    integrations = integration_status()

    rows: List[Dict[str, Any]] = []
    for site in sites:
        site_id = str(site.get("id") or "")
        metrics = _latest_metrics(site_id)
        issues = _issue_counts(site_id)
        critical = issues["critical"]
        high = issues["high"]
        medium = issues["medium"]
        health, formula = compute_health_score(critical, high, medium)

        rows.append({
            "website_id": site_id,
            "domain": site.get("domain") or site.get("url") or "(unnamed)",
            "status": site.get("status") or "active",
            "health_score": health if metrics or issues["total"] else None,
            "health_formula": formula,
            "indexed_pages": metrics.get("indexed_pages") if metrics else None,
            "excluded_pages": metrics.get("excluded_pages") if metrics else None,
            "errors": metrics.get("errors") if metrics else None,
            "clicks": metrics.get("clicks") if metrics else None,
            "impressions": metrics.get("impressions") if metrics else None,
            "avg_position": metrics.get("avg_position") if metrics else None,
            "open_issues": issues["total"],
            "critical_issues": critical,
            "metrics_as_of": metrics.get("metric_date") if metrics else None,
        })

    # Sites with no metrics are still listed; the UI shows "no data" for them.
    # Data availability reflects whether metrics were actually collected, not
    # whether a connector is configured. Stored metrics can exist from an
    # import while the live connector is off, and the totals must not then
    # claim "no data" while the per-site rows show real clicks.
    any_metrics = any(r["metrics_as_of"] for r in rows)
    any_clicks = any(r["clicks"] is not None for r in rows)

    totals = {
        "sites": len(rows),
        "clicks": sum(r["clicks"] or 0 for r in rows) if any_clicks else None,
        "open_issues": sum(r["open_issues"] or 0 for r in rows),
        "critical_issues": sum(r["critical_issues"] or 0 for r in rows),
    }
    return {
        "sites": rows,
        "totals": totals,
        "storage": store.storage_backend(),
        "integrations": integrations,
        "data_available": any_metrics,
        "note": (
            "Live per-site metrics collected."
            if any_metrics
            else "No site metrics collected yet. Sites are listed; health, "
            "indexation and clicks stay blank until metrics are ingested."
        ),
    }


def _load_sites(account_id: Optional[str]) -> List[Dict[str, Any]]:
    try:
        from services.local_store import list_local_websites

        local = list_local_websites(account_id)
    except Exception:  # noqa: BLE001
        local = []

    client = store._client()  # reuse the guarded client accessor
    if client is None:
        return local
    try:
        query = client.table("websites").select("*")
        if account_id:
            query = query.eq("account_id", account_id)
        rows = query.execute().data or []
        known = {str(r.get("id")) for r in rows}
        for lr in local:
            if str(lr.get("id")) not in known:
                rows.append(lr)
        return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("[portfolio] websites fetch fell back to local: %s", exc)
        return local


def _latest_metrics(website_id: str) -> Dict[str, Any]:
    rows = store.select(
        "site_metrics_daily",
        {"website_id": website_id},
        order_by="metric_date",
        desc=True,
        limit=1,
    )
    return rows[0] if rows else {}


def _issue_counts(website_id: str) -> Dict[str, int]:
    """Count open issues by severity from action_items/change log if present."""
    items = store.select("action_items", {"website_id": website_id})
    open_items = [i for i in items if (i.get("status") or "open") == "open"]
    critical = sum(1 for i in open_items if i.get("severity") == "critical")
    high = sum(1 for i in open_items if i.get("severity") == "high")
    medium = sum(1 for i in open_items if i.get("severity") == "medium")
    return {
        "critical": critical,
        "high": high,
        "medium": medium,
        "total": len(open_items),
    }


def integration_status() -> Dict[str, Dict[str, Any]]:
    supabase = store.supabase_configured()
    return {
        "supabase": _integration("supabase", supabase),
        "site_metrics": _integration("gsc", supabase, "Google Search Console metrics"),
        "ga4": _integration(
            "ga4",
            bool(os.getenv("GA4_CREDENTIALS_PATH") or os.getenv("GA4_PROPERTY_ID")),
            "conversion export",
        ),
        "serp": _integration(
            "serp",
            bool(
                os.getenv("SERPER_API_KEY")
                or os.getenv("SERPAPI_KEY")
                or os.getenv("SERPAPI_KEY")
            ),
            "competitor position data",
        ),
        "wordpress": _integration(
            "wordpress",
            bool(os.getenv("WP_SITE_URL") or os.getenv("WORDPRESS_URL")),
            "change application target",
        ),
    }


# ===========================================================================
# Bullet 2: prioritized action list
# ===========================================================================

def score_action(
    search_volume: Optional[int],
    current_position: Optional[float],
    target_position: Optional[float],
    confidence: float = 0.6,
    effort_minutes: int = 30,
) -> Dict[str, Any]:
    """Project traffic impact for one action and return full arithmetic.

    estimated_clicks_gain = search_volume x (ctr(target) - ctr(current))
    priority_score        = estimated_clicks_gain x confidence

    Ranking is by estimated traffic impact, as specified. The efficiency view
    (impact per hour) is exposed separately for planning.
    """
    ctr_now = ctr_for_position(current_position)
    ctr_target = ctr_for_position(target_position)
    ctr_gain = max(0.0, ctr_target - ctr_now)

    if search_volume is None or search_volume <= 0:
        return {
            "projected_ctr_gain": None,
            "projected_clicks_gain": None,
            "priority_score": 0.0,
            "impact_per_hour": None,
            "scorable": False,
            "reason": "search volume unavailable - not scored rather than guessed",
        }

    projected_clicks = float(search_volume) * ctr_gain
    priority = projected_clicks * confidence
    hours = max(effort_minutes, 1) / 60.0

    return {
        "projected_ctr_gain": round(ctr_gain, 6),
        "projected_clicks_gain": round(projected_clicks, 2),
        "priority_score": round(priority, 2),
        "impact_per_hour": round(projected_clicks / hours, 2),
        "scorable": True,
        "evidence": {
            "search_volume": search_volume,
            "ctr_current": round(ctr_now, 6),
            "ctr_target": round(ctr_target, 6),
            "ctr_gain": round(ctr_gain, 6),
            "current_position": current_position,
            "target_position": target_position,
            "confidence": confidence,
            "formula": (
                f"{search_volume} x ({round(ctr_target, 6)} - {round(ctr_now, 6)}) "
                f"= {round(projected_clicks, 2)} clicks x {confidence} "
                f"= {round(priority, 2)}"
            ),
        },
    }


def _fingerprint(
    website_id: str, title: str, target_url: Optional[str], keyword: Optional[str]
) -> str:
    """Stable identity for an action so repeated scans refresh instead of duplicate."""
    return "|".join([str(website_id), str(keyword or ""), str(target_url or ""), str(title)])


def create_action(
    website_id: str,
    title: str,
    category: str,
    target_url: Optional[str] = None,
    keyword: Optional[str] = None,
    search_volume: Optional[int] = None,
    current_position: Optional[float] = None,
    target_position: Optional[float] = None,
    effort_minutes: int = 30,
    confidence: float = 0.6,
    severity: str = "medium",
    source: str = "derived",
) -> Dict[str, Any]:
    scored = score_action(
        search_volume, current_position, target_position, confidence, effort_minutes
    )
    record = {
        "website_id": website_id,
        "category": category,
        "title": title,
        "target_url": target_url,
        "keyword": keyword,
        "search_volume": search_volume,
        "current_position": current_position,
        "target_position": target_position,
        "projected_ctr_gain": scored.get("projected_ctr_gain"),
        "projected_clicks_gain": scored.get("projected_clicks_gain"),
        "impact_per_hour": scored.get("impact_per_hour"),
        "effort_minutes": effort_minutes,
        "confidence": confidence,
        "priority_score": scored.get("priority_score") or 0.0,
        "severity": severity,
        "evidence": scored.get("evidence")
        or {"reason": scored.get("reason"), "scorable": False},
        "source": source,
        "status": "open",
        "fingerprint": _fingerprint(website_id, title, target_url, keyword),
        "updated_at": datetime.utcnow().isoformat(),
    }
    row, _created = store.upsert("action_items", record, ["fingerprint"])
    return row


def prioritized_actions(
    website_id: str,
    limit: int = 10,
    sort_by: str = "traffic_impact",
) -> Dict[str, Any]:
    """The ranked 'do these N things now' list."""
    rows = store.select("action_items", {"website_id": website_id})
    open_rows = [r for r in rows if (r.get("status") or "open") == "open"]

    scorable = [r for r in open_rows if (r.get("projected_clicks_gain") or 0) > 0]
    unscorable = [r for r in open_rows if (r.get("projected_clicks_gain") or 0) <= 0]

    if sort_by == "effort":
        scorable.sort(
            key=lambda r: (r.get("impact_per_hour") or 0, r.get("priority_score") or 0),
            reverse=True,
        )
    else:  # default: estimated traffic impact, per product requirement
        scorable.sort(key=lambda r: r.get("priority_score") or 0, reverse=True)

    ranked = scorable[:limit]
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i

    return {
        "website_id": website_id,
        "sort_by": sort_by,
        "count": len(ranked),
        "total_open": len(open_rows),
        "actions": ranked,
        "unscored": unscorable,
        "unscored_note": (
            f"{len(unscorable)} actions lack search volume and are deliberately "
            "excluded from ranking rather than assigned a guessed value."
        ) if unscorable else "",
        "ctr_curve_positions": len(CTR_BY_POSITION),
    }


# ===========================================================================
# Bullet 3: leads and cost per lead
# ===========================================================================

def record_conversion(
    website_id: str,
    landing_page: str,
    conversion_date: date,
    count: int = 0,
    value: float = 0.0,
    session_source: str = "google / organic",
) -> Dict[str, Any]:
    """Record GA4 conversions for a page/date/source. Re-imports overwrite."""
    row, _created = store.upsert("conversions", {
        "website_id": website_id,
        "conversion_date": conversion_date.isoformat(),
        "landing_page": landing_page,
        "session_source": session_source,
        "conversion_count": count,
        "conversion_value": value,
        "source": "ga4",
    }, ["website_id", "conversion_date", "landing_page", "session_source", "source"])
    return row


def record_effort_cost(
    website_id: str,
    cost_date: date,
    category: str,
    minutes: float,
    hourly_rate: float,
    api_cost: float = 0.0,
) -> Dict[str, Any]:
    total = (minutes / 60.0) * hourly_rate + api_cost
    row, _created = store.upsert("effort_costs", {
        "website_id": website_id,
        "cost_date": cost_date.isoformat(),
        "category": category,
        "minutes": minutes,
        "hourly_rate": hourly_rate,
        "api_cost": api_cost,
        "total_cost": round(total, 4),
    }, ["website_id", "cost_date", "category"])
    return row


def cost_per_lead_by_keyword(
    website_id: str,
    keyword_page_pairs: List[Dict[str, str]],
    period_start: date,
    period_end: date,
    hourly_rate: float,
) -> Dict[str, Any]:
    """Attribute conversions to keywords and compute cost per lead.

    GA4 does not expose the organic query behind a conversion, so the join is
    keyword -> landing page via GSC, then landing page -> conversions via GA4.
    That limitation is explicit in ``attribution_method`` and reflected in
    ``attribution_confidence``; the numbers are never presented as exact.

    Cost per lead here is production effort (agent minutes x rate + API cost),
    because organic search has no media spend. If a paid channel is added later
    the media cost should be folded into ``effort_costs``.
    """
    conversions = store.select("conversions", {"website_id": website_id})
    costs = store.select("effort_costs", {"website_id": website_id})

    in_period_conv = [
        c for c in conversions
        if period_start.isoformat() <= str(c.get("conversion_date")) <= period_end.isoformat()
    ]
    in_period_cost = [
        c for c in costs
        if period_start.isoformat() <= str(c.get("cost_date")) <= period_end.isoformat()
    ]

    total_leads_by_page: Dict[str, int] = {}
    for c in in_period_conv:
        page = str(c.get("landing_page") or "")
        total_leads_by_page[page] = total_leads_by_page.get(page, 0) + int(
            c.get("conversion_count") or 0
        )
    total_cost = sum(float(c.get("total_cost") or 0) for c in in_period_cost)

    results: List[Dict[str, Any]] = []
    for pair in keyword_page_pairs:
        keyword = str(pair.get("keyword") or "")
        page = str(pair.get("landing_page") or "")
        clicks = int(pair.get("clicks") or 0)
        leads = total_leads_by_page.get(page, 0)

        page_sessions = int(pair.get("page_sessions") or 0)
        attributed_sessions = int(pair.get("attributed_sessions") or 0)
        if page_sessions > 0:
            confidence = round(min(1.0, attributed_sessions / page_sessions), 3)
        else:
            confidence = 0.0

        # Effort is split across keywords pointing at the same page, by clicks.
        share = 1.0
        same_page = [p for p in keyword_page_pairs
                     if str(p.get("landing_page") or "") == page]
        total_page_clicks = sum(int(p.get("clicks") or 0) for p in same_page)
        if total_page_clicks > 0:
            share = clicks / total_page_clicks
        effort_cost = round(total_cost * share, 2) if total_cost else 0.0

        conversion_rate = round(leads / clicks, 4) if clicks > 0 else None
        cpl = round(effort_cost / leads, 2) if leads > 0 else None

        record = {
            "website_id": website_id,
            "keyword": keyword,
            "landing_page": page,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "clicks": clicks,
            "leads": leads,
            "conversion_rate": conversion_rate,
            "effort_cost": effort_cost,
            "cost_per_lead": cpl,
            "attribution_method": "gsc_query_to_landing_page_join",
            "attribution_confidence": confidence,
        }
        store.insert("keyword_lead_attribution", record)
        results.append(record)

    return {
        "website_id": website_id,
        "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
        "methodology": {
            "cost_basis": "production_effort",
            "cost_note": (
                "Cost per lead uses agent effort minutes x rate plus API cost. "
                "Organic search has no media spend, so this is not ad-cost CPL."
            ),
            "attribution_note": (
                "GA4 cannot expose the organic query behind a conversion. Keywords "
                "are mapped to landing pages via GSC, then to GA4 conversions. "
                "Read cost_per_lead with attribution_confidence."
            ),
        },
        "results": results,
        "total_cost": round(total_cost, 2),
        "total_leads": sum(r["leads"] for r in results),
        "has_data": bool(in_period_conv),
        "data_note": "" if in_period_conv else (
            "No GA4 conversions stored for this period. "
            "Connect GA4 or import a conversion export."
        ),
    }


# ===========================================================================
# Bullet 4: guardrails and rollback
# ===========================================================================

YMYL_PATTERNS = [
    "legal", "law", "attorney", "lawyer", "solicitor", "medical", "health",
    "doctor", "clinic", "hospital", "diagnosis", "treatment", "medication",
    "dosage", "financial", "finance", "loan", "mortgage", "invest",
    "insurance", "tax", "bankruptcy", "credit", "pension", "safety",
]


def classify_ymyl(url: str) -> Tuple[bool, Optional[str]]:
    """Flag legal/medical/financial/safety pages that need stricter review."""
    lowered = (url or "").lower()
    hits = [p for p in YMYL_PATTERNS if p in lowered]
    if hits:
        return True, f"matched YMYL terms: {', '.join(sorted(set(hits))[:5])}"
    return False, None


def preview_change(
    website_id: str,
    target_url: str,
    change_type: str,
    after_content: str,
    before_content: str = "",
    actor: str = "system",
) -> Dict[str, Any]:
    """Create a previewable change. Nothing is applied until apply_change().

    The YMYL check runs here so a dangerous page can never be applied by
    accident: it is marked review_required and apply_change refuses it.
    """
    is_ymyl, reason = classify_ymyl(target_url)
    diff_lines = difflib.unified_diff(
        (before_content or "").splitlines(),
        (after_content or "").splitlines(),
        fromfile=f"{target_url} (current)",
        tofile=f"{target_url} (proposed)",
        lineterm="",
    )
    unified = "\n".join(diff_lines)

    now = datetime.utcnow().isoformat()
    record = {
        "website_id": website_id,
        "target_url": target_url,
        "change_type": change_type,
        "actor": actor,
        "before_content": before_content,
        "after_content": after_content,
        "unified_diff": unified,
        "inverse_payload": {
            "target_url": target_url,
            "change_type": change_type,
            "restore_content": before_content,
        },
        "reversible": True,
        "is_ymyl": is_ymyl,
        "ymyl_reason": reason,
        "review_required": is_ymyl,
        "status": "previewed",
        # Full transition trail: a log that only shows current status cannot
        # answer "what happened to this change and who approved it".
        "status_history": [
            {"status": "previewed", "at": now, "actor": actor}
        ],
    }
    saved = store.insert("change_events", record)
    saved["diff_line_count"] = len(unified.splitlines())
    return saved


def apply_change(
    change_id: str,
    approver: Optional[str] = None,
    second_reviewer: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply a previewed change after the human gate.

    Refuses when the change is YMYL and lacks a distinct second reviewer. The
    runtime site write is the caller's responsibility; this records intent and
    the inverse so undo is always possible.
    """
    change = store.get("change_events", change_id)
    if not change:
        return {"ok": False, "error": "change not found"}
    if change.get("status") == "applied":
        return {"ok": False, "error": "change already applied"}
    if change.get("status") == "undone":
        return {"ok": False, "error": "change was undone; create a new preview"}
    if not approver:
        return {"ok": False, "error": "human approval required (approver missing)"}

    if change.get("is_ymyl"):
        if not second_reviewer:
            return {
                "ok": False,
                "error": (
                    "YMYL page requires a second reviewer before applying"
                ),
                "ymyl_reason": change.get("ymyl_reason"),
            }
        if second_reviewer == approver:
            return {
                "ok": False,
                "error": "second reviewer must differ from the approver",
            }

    patch = {
        "status": "applied",
        "applied_at": datetime.utcnow().isoformat(),
        "actor": approver,
        "second_reviewer": second_reviewer,
    }
    history = list(change.get("status_history") or [])
    history.append({
        "status": "applied",
        "at": patch["applied_at"],
        "actor": approver,
        "second_reviewer": second_reviewer,
    })
    patch["status_history"] = history
    updated = store.update("change_events", change_id, patch) or change
    _open_measurement_window(updated)

    return {
        "ok": True,
        "change": updated,
        "undo_available": True,
        "undo_endpoint": f"/api/intelligence/guardrails/changes/{change_id}/undo",
    }


def undo_change(change_id: str, actor: str = "system") -> Dict[str, Any]:
    """Restore the pre-change content using the stored inverse payload."""
    change = store.get("change_events", change_id)
    if not change:
        return {"ok": False, "error": "change not found"}
    if change.get("status") != "applied":
        return {
            "ok": False,
            "error": f"cannot undo a change in status '{change.get('status')}'",
        }
    if not change.get("reversible"):
        return {"ok": False, "error": "change is marked irreversible"}

    inverse = change.get("inverse_payload") or {}
    restored = inverse.get("restore_content", "")

    now = datetime.utcnow().isoformat()
    history = list(change.get("status_history") or [])
    history.append({"status": "undone", "at": now, "actor": actor})

    updated = store.update("change_events", change_id, {
        "status": "undone",
        "undone_at": now,
        "status_history": history,
    }) or change

    return {
        "ok": True,
        "change": updated,
        "restored_content": restored,
        "note": (
            "Restored content returned for the caller to write back to the CMS. "
            "Verify the live page matches before marking the incident closed."
        ),
    }


def change_log(website_id: str, limit: int = 50) -> Dict[str, Any]:
    rows = store.select(
        "change_events", {"website_id": website_id},
        order_by="created_at", desc=True, limit=limit,
    )
    # Counters come from the transition trail, not the current status, so an
    # applied-then-undone change still shows that it was applied.
    applied = undone = 0
    for row in rows:
        trail = row.get("status_history") or []
        states = {str(step.get("status")) for step in trail} or {str(row.get("status"))}
        if "applied" in states:
            applied += 1
        if "undone" in states:
            undone += 1

    return {
        "website_id": website_id,
        "count": len(rows),
        "changes": rows,
        "counts": {
            "previewed": sum(1 for r in rows if r.get("status") == "previewed"),
            "applied": applied,
            "undone": undone,
            "ymyl": sum(1 for r in rows if r.get("is_ymyl")),
            "awaiting_review": sum(1 for r in rows if r.get("review_required")
                                   and r.get("status") == "previewed"),
        },
    }


def _open_measurement_window(change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Start a 28-day measurement window for an applied change."""
    website_id = change.get("website_id")
    target_url = change.get("target_url")
    if not website_id or not target_url:
        return None
    try:
        return create_measurement_window(
            website_id=str(website_id),
            target_url=str(target_url),
            change_event_id=str(change.get("id")),
            keyword=change.get("keyword"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[intelligence] could not open measurement window: %s", exc)
        return None


# ===========================================================================
# Bullet 5: competitor share of voice
# ===========================================================================

def record_competitor_ranking(
    website_id: str,
    competitor_domain: str,
    keyword: str,
    position: Optional[int],
    captured_date: date,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    """Store an observed position. Same day re-scrapes overwrite."""
    row, _created = store.upsert("competitor_rankings", {
        "website_id": website_id,
        "competitor_domain": competitor_domain,
        "keyword": keyword,
        "position": position,
        "url": url,
        "captured_date": captured_date.isoformat(),
        "source": "serp",
    }, ["website_id", "competitor_domain", "keyword", "captured_date", "source"])
    return row


def _visibility(positions: List[Optional[int]]) -> float:
    """Share-of-voice visibility = sum of CTR-at-position across the keyword set.

    Using the CTR curve makes visibility comparable across competitors and
    keeps the metric auditable, rather than a hand-assigned authority number.
    """
    return round(sum(ctr_for_position(p) for p in positions), 6)


def share_of_voice(
    website_id: str,
    our_positions: Dict[str, Optional[int]],
    competitor_positions: Dict[str, Dict[str, Optional[int]]],
) -> Dict[str, Any]:
    """Share of voice on the tracked keyword set, plus per-competitor detail."""
    keyword_set = set(our_positions.keys())
    for dom_positions in competitor_positions.values():
        keyword_set |= set(dom_positions.keys())

    our_vis = _visibility(list(our_positions.values()))
    breakdown: Dict[str, float] = {name: _visibility(list(pos.values()))
                                   for name, pos in competitor_positions.items()}
    total = our_vis + sum(breakdown.values())

    our_sov = round(our_vis / total, 6) if total > 0 else 0.0
    competitor_sov = {
        name: (round(vis / total, 6) if total > 0 else 0.0)
        for name, vis in breakdown.items()
    }

    snapshot = None
    if keyword_set:
        row, _created = store.upsert("sov_snapshots", {
            "website_id": website_id,
            "snapshot_date": date.today().isoformat(),
            "scope": "tracked_keyword_set",
            "our_visibility": our_vis,
            "total_visibility": round(total, 6),
            "share_of_voice": our_sov,
            "per_competitor": competitor_sov,
            "keyword_count": len(keyword_set),
        }, ["website_id", "snapshot_date", "scope"])
        snapshot = row

    return {
        "website_id": website_id,
        "keyword_count": len(keyword_set),
        "our_visibility": our_vis,
        "our_share_of_voice": our_sov,
        "competitors": [
            {"domain": name, "visibility": breakdown[name], "share_of_voice": sov}
            for name, sov in sorted(competitor_sov.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "total_visibility": round(total, 6),
        "method": "sum of CTR-at-position over the tracked keyword set",
        "sov_sums_to": round(our_sov + sum(competitor_sov.values()), 6),
        "snapshot_id": (snapshot or {}).get("id"),
    }


def outrank_gaps(
    our_positions: Dict[str, Optional[int]],
    competitor_positions: Dict[str, Dict[str, Optional[int]]],
) -> List[Dict[str, Any]]:
    """Keywords where a competitor outranks us, worst gap first."""
    gaps: List[Dict[str, Any]] = []
    for keyword, our_pos in our_positions.items():
        for domain, positions in competitor_positions.items():
            their_pos = positions.get(keyword)
            if their_pos is None:
                continue
            if our_pos is None:
                gaps.append({
                    "keyword": keyword, "competitor": domain,
                    "our_position": None, "their_position": their_pos,
                    "gap": None,
                    "note": "we do not rank; competitor does",
                })
            elif their_pos < our_pos:
                gaps.append({
                    "keyword": keyword, "competitor": domain,
                    "our_position": our_pos, "their_position": their_pos,
                    "gap": round(our_pos - their_pos, 1),
                    "note": "",
                })
    gaps.sort(key=lambda g: (g["gap"] is not None, g["gap"] or 0), reverse=True)
    return gaps


def detect_new_competitor_pages(
    website_id: str,
    competitor_domain: str,
    current_urls: List[Dict[str, str]],
    seen_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Diff a competitor's current page list against what we have recorded."""
    seen_date = seen_date or date.today()
    existing = store.select(
        "competitor_new_pages",
        {"website_id": website_id, "competitor_domain": competitor_domain},
    )
    known = {str(r.get("url")) for r in existing}

    new_pages = []
    for entry in current_urls:
        url = str(entry.get("url") or "").strip()
        if not url or url in known:
            continue
        saved = store.insert("competitor_new_pages", {
            "website_id": website_id,
            "competitor_domain": competitor_domain,
            "url": url,
            "title": entry.get("title"),
            "first_seen": seen_date.isoformat(),
        })
        new_pages.append(saved)

    return {
        "website_id": website_id,
        "competitor_domain": competitor_domain,
        "checked": len(current_urls),
        "known_before": len(known),
        "new_pages": new_pages,
        "new_page_count": len(new_pages),
    }


# ===========================================================================
# Bullet 6: prove the work, 28 days
# ===========================================================================

WINDOW_DAYS = 28
SNAPSHOT_OFFSETS = (0, 7, 14, 28)


def create_measurement_window(
    website_id: str,
    target_url: str,
    keyword: Optional[str] = None,
    change_event_id: Optional[str] = None,
    baseline_clicks: float = 0.0,
    baseline_impressions: float = 0.0,
    baseline_position: Optional[float] = None,
    control_urls: Optional[List[str]] = None,
    baseline_control_clicks: float = 0.0,
    window_start: Optional[date] = None,
) -> Dict[str, Any]:
    window_start = window_start or date.today()
    return store.insert("measurement_windows", {
        "website_id": website_id,
        "change_event_id": change_event_id,
        "target_url": target_url,
        "keyword": keyword,
        "window_start": window_start.isoformat(),
        "baseline_clicks": baseline_clicks,
        "baseline_impressions": baseline_impressions,
        "baseline_position": baseline_position,
        "control_urls": control_urls or [],
        "baseline_control_clicks": baseline_control_clicks,
        "status": "open",
    })


def record_snapshot(
    window_id: str,
    day_offset: int,
    clicks: float,
    impressions: float = 0.0,
    position: Optional[float] = None,
    control_clicks: float = 0.0,
    control_impressions: float = 0.0,
    captured_date: Optional[date] = None,
) -> Dict[str, Any]:
    if day_offset not in SNAPSHOT_OFFSETS:
        raise ValueError(f"day_offset must be one of {SNAPSHOT_OFFSETS}")
    saved = store.insert("measurement_snapshots", {
        "window_id": window_id,
        "day_offset": day_offset,
        "clicks": clicks,
        "impressions": impressions,
        "position": position,
        "control_clicks": control_clicks,
        "control_impressions": control_impressions,
        "captured_date": (captured_date or date.today()).isoformat(),
    })
    if day_offset == WINDOW_DAYS:
        store.update("measurement_windows", window_id, {"status": "complete"})
    return saved


def _weighted_control_delta(
    baseline_control: float,
    control_now: float,
) -> Tuple[float, str]:
    """Expected click change attributable to seasonality, from the control set."""
    if baseline_control <= 0:
        return 0.0, (
            "No control set recorded, so lift is reported unadjusted and should "
            "be treated as directional only."
        )
    ratio = control_now / baseline_control
    expected = baseline_control * (ratio - 1.0)
    return expected, (
        f"Control set moved {round((ratio - 1.0) * 100, 2)}% over the window; "
        "that drift is subtracted from the raw lift."
    )


def measurement_report(window_id: str) -> Dict[str, Any]:
    """28-day position and traffic lift for a shipped change."""
    window = store.get("measurement_windows", window_id)
    if not window:
        return {"ok": False, "error": "measurement window not found"}

    snapshots = store.select(
        "measurement_snapshots", {"window_id": window_id},
        order_by="day_offset", desc=False,
    )
    by_offset = {int(s.get("day_offset") or 0): s for s in snapshots}

    baseline_clicks = float(window.get("baseline_clicks") or 0)
    baseline_control = float(window.get("baseline_control_clicks") or 0)
    baseline_pos = window.get("baseline_position")

    day28 = by_offset.get(WINDOW_DAYS)
    latest = day28 or (snapshots[-1] if snapshots else None)

    if not latest:
        return {
            "ok": True,
            "window": window,
            "status": "awaiting_data",
            "snapshots_recorded": 0,
            "expected_offsets": list(SNAPSHOT_OFFSETS),
            "note": (
                "Window opened. No snapshots captured yet. "
                "GSC data is required at day 0, 7, 14 and 28."
            ),
        }

    clicks_now = float(latest.get("clicks") or 0)
    control_now = float(latest.get("control_clicks") or 0)
    raw_lift = clicks_now - baseline_clicks
    control_delta, control_note = _weighted_control_delta(baseline_control, control_now)
    adjusted_lift = raw_lift - control_delta

    pct = (
        round((adjusted_lift / baseline_clicks) * 100, 2)
        if baseline_clicks > 0 else None
    )

    position_now = latest.get("position")
    position_delta = None
    if position_now is not None and baseline_pos is not None:
        position_delta = round(float(baseline_pos) - float(position_now), 2)

    elapsed = int(latest.get("day_offset") or 0)
    return {
        "ok": True,
        "window": window,
        "status": "complete" if day28 else "in_progress",
        "days_elapsed": elapsed,
        "days_remaining": max(0, WINDOW_DAYS - elapsed),
        "snapshots_recorded": len(snapshots),
        "series": [
            {
                "day": int(s.get("day_offset") or 0),
                "clicks": s.get("clicks"),
                "impressions": s.get("impressions"),
                "position": s.get("position"),
                "control_clicks": s.get("control_clicks"),
            }
            for s in snapshots
        ],
        "lift": {
            "baseline_clicks": baseline_clicks,
            "current_clicks": clicks_now,
            "raw_clicks_lift": round(raw_lift, 2),
            "control_adjustment": round(control_delta, 2),
            "adjusted_clicks_lift": round(adjusted_lift, 2),
            "percent_lift": pct,
            "position_baseline": baseline_pos,
            "position_current": position_now,
            "position_improvement": position_delta,
        },
        "control_note": control_note,
        "method": (
            "Baseline vs day-N clicks, minus the movement of a control URL set, "
            "so seasonality is not reported as success."
        ),
    }


def measure_applied_change(change_id: str) -> Dict[str, Any]:
    """Convenience: report the measurement window belonging to a change."""
    windows = store.select("measurement_windows", {"change_event_id": change_id})
    if not windows:
        return {"ok": False, "error": "no measurement window for this change"}
    return measurement_report(str(windows[0].get("id")))