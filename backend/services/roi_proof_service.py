"""ROI Proof & 28-Day Post-Fix Impact Verification Service.
Tracks URLs for 28 days post-remediation to measure and verify position lift,
traffic increase, and tangible ROI value.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from backend.services.local_store import (
        save_local_roi_tracked_fix,
        list_local_roi_tracked_fixes,
        get_local_roi_tracked_fix,
        update_local_roi_tracked_fix,
        get_local_lead_settings,
    )
except ImportError:
    from services.local_store import (
        save_local_roi_tracked_fix,
        list_local_roi_tracked_fixes,
        get_local_roi_tracked_fix,
        update_local_roi_tracked_fix,
        get_local_lead_settings,
    )

logger = logging.getLogger("backend.services.roi_proof_service")


def track_new_fix(
    website_id: str,
    target_url: str,
    fix_title: str,
    category: str,
    target_keyword: str,
    baseline_position: float,
    baseline_monthly_clicks: int,
    action_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a new URL remediation for 28-day post-fix impact tracking."""
    record = {
        "website_id": website_id,
        "action_id": action_id,
        "target_url": target_url,
        "fix_title": fix_title,
        "category": category,
        "target_keyword": target_keyword,
        "baseline_position": baseline_position,
        "baseline_monthly_clicks": baseline_monthly_clicks,
        "shipped_at": datetime.utcnow().isoformat(),
        "status": "TRACKING",
        "days_tracked": 0,
        "current_position": baseline_position,
        "current_monthly_clicks": baseline_monthly_clicks,
        "position_lift": 0.0,
        "traffic_lift_clicks": 0,
        "traffic_lift_percentage": 0.0,
        "monthly_value_generated": 0.0,
        "milestones": [
            {"day": 7, "measured": False, "position": None, "clicks": None},
            {"day": 14, "measured": False, "position": None, "clicks": None},
            {"day": 21, "measured": False, "position": None, "clicks": None},
            {"day": 28, "measured": False, "position": None, "clicks": None},
        ]
    }
    return save_local_roi_tracked_fix(record)


def _refresh_from_measurements(website_id: str, fix: Dict[str, Any]) -> Dict[str, Any]:
    """Refresh one tracked fix from rank_tracking + analytics_data. Never invents."""
    try:
        from backend.database import get_supabase
    except (ImportError, ValueError):
        from database import get_supabase
    keyword = (fix.get("target_keyword") or "").strip()
    baseline_pos = fix.get("baseline_position")
    baseline_clicks = fix.get("baseline_monthly_clicks", 0) or 0
    cur_pos = fix.get("current_position", baseline_pos)
    cur_clicks = fix.get("current_monthly_clicks", baseline_clicks)
    try:
        supabase = get_supabase()
        if keyword:
            try:
                rows = supabase.table("rank_tracking").select("current_position").eq("website_id", website_id).eq("target_keyword", keyword).order("last_checked_at", desc=True).limit(1).execute().data or []
                if rows and rows[0].get("current_position") is not None:
                    cur_pos = float(rows[0]["current_position"])
            except Exception as e:
                logger.debug(f"[roi] rank lookup note: {e}")
            try:
                arows = supabase.table("analytics_data").select("clicks").eq("website_id", website_id).eq("keyword", keyword).execute().data or []
                if arows:
                    cur_clicks = sum(int(r.get("clicks", 0) or 0) for r in arows)
            except Exception as e:
                logger.debug(f"[roi] analytics lookup note: {e}")
    except Exception as e:
        logger.debug(f"[roi] supabase note: {e}")
    try:
        days = (datetime.utcnow() - datetime.fromisoformat(str(fix.get("shipped_at", datetime.utcnow().isoformat())))).days
        days = max(0, min(days, 28))
    except Exception:
        days = fix.get("days_tracked", 0) or 0
    pos_lift = round(float(baseline_pos or 0) - float(cur_pos or 0), 1) if baseline_pos is not None and cur_pos is not None else 0.0
    click_lift = int((cur_clicks or 0) - (baseline_clicks or 0))
    pct = round((click_lift / max(baseline_clicks, 1)) * 100, 1) if baseline_clicks else (100.0 if click_lift > 0 else 0.0)
    milestones = fix.get("milestones") or []
    for m in milestones:
        try:
            if days >= int(m.get("day", 0)) and not m.get("measured"):
                m["measured"] = True
                m["position"] = cur_pos
                m["clicks"] = cur_clicks
        except Exception:
            continue
    updated = dict(fix)
    updated.update({
        "current_position": cur_pos,
        "current_monthly_clicks": cur_clicks,
        "position_lift": pos_lift,
        "traffic_lift_clicks": click_lift,
        "traffic_lift_percentage": pct,
        "days_tracked": days,
        "milestones": milestones,
        "status": "PROVEN_LIFT" if days >= 7 and (pos_lift > 0 or click_lift > 0) else "TRACKING",
    })
    try:
        if updated.get("id"):
            update_local_roi_tracked_fix(updated["id"], updated)
    except Exception as e:
        logger.debug(f"[roi] persist note: {e}")
    return updated


def list_tracked_fixes(website_id: str) -> List[Dict[str, Any]]:
    """Tracked fixes refreshed from live rank + analytics measurements."""
    fixes = list_local_roi_tracked_fixes(website_id)
    return [_refresh_from_measurements(website_id, f) for f in fixes]


def calculate_roi_summary(website_id: str) -> Dict[str, Any]:
    """Calculate aggregated ROI metrics, total clicks won, and dollar value."""
    fixes = list_tracked_fixes(website_id)
    settings = get_local_lead_settings(website_id)
    try:
        monthly_seo_spend = float(settings.get("monthly_seo_spend", 2500.0))
    except (ValueError, TypeError):
        monthly_seo_spend = 2500.0

    total_tracked = len(fixes)
    proven_count = sum(1 for f in fixes if f.get("status") == "PROVEN_LIFT")
    total_clicks_won = sum(f.get("traffic_lift_clicks", 0) for f in fixes)
    total_value_generated = sum(f.get("monthly_value_generated", 0.0) for f in fixes)

    avg_position_gain = 0.0
    if total_tracked > 0:
        avg_position_gain = round(sum(f.get("position_lift", 0.0) for f in fixes) / total_tracked, 1)

    roi_multiple = round(total_value_generated / monthly_seo_spend, 2) if monthly_seo_spend > 0 else 0.0

    return {
        "website_id": website_id,
        "total_fixes_tracked": total_tracked,
        "proven_fixes_count": proven_count,
        "verified_fixes_count": proven_count,
        "total_monthly_clicks_won": total_clicks_won,
        "total_monthly_clicks_gained": total_clicks_won,
        "average_position_lift": avg_position_gain,
        "monthly_value_generated": round(total_value_generated, 2),
        "total_pipeline_value_added": round(total_value_generated, 2),
        "monthly_seo_spend": monthly_seo_spend,
        "roi_multiple": f"{roi_multiple}x",
        "conclusion": (
            f"Over the last 28 days, {proven_count} verified fixes produced a net lift of "
            f"+{total_clicks_won:,} organic clicks/mo generating ${total_value_generated:,.2f} in pipeline value "
            f"({roi_multiple}x return on ${monthly_seo_spend:,.0f}/mo SEO budget)."
        ),
    }
