"""Shared dashboard counters — single source of truth.

Both /api/stats (main.py) and /api/dashboard/{id}/metrics (dashboard.py)
must report the SAME numbers for the same site. They previously computed
overlapping metrics from different queries with different fallbacks (94
health, 6-alert floor, different pending definitions). All shared counting
lives here; endpoints only shape responses.

Honesty rules: counts are real DB counts (0 when empty, never floored);
health is the latest technical_audits row or None ("No audit yet").
"""
import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("backend.services.dashboard_metrics")


def _count_sync(supabase, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
    try:
        q = supabase.table(table).select("id", count="exact")
        for k, v in (filters or {}).items():
            if v is not None:
                q = q.eq(k, v)
        res = q.execute()
        return getattr(res, "count", None) or len(res.data or [])
    except Exception as e:
        logger.debug(f"[DashboardMetrics] count {table} note: {e}")
        return 0


async def _count(supabase, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
    return await asyncio.to_thread(_count_sync, supabase, table, filters)


async def get_site_health(supabase, website_id: Optional[str]) -> Dict[str, Any]:
    """Latest technical audit health or explicit no-data. Never a fallback."""
    def _q():
        try:
            q = supabase.table("technical_audits").select("health_score, created_at")
            if website_id:
                q = q.eq("website_id", website_id)
            return q.order("created_at", desc=True).limit(1).execute().data or []
        except Exception as e:
            logger.debug(f"[DashboardMetrics] health note: {e}")
            return []

    audits = await asyncio.to_thread(_q)
    if audits and audits[0].get("health_score") is not None:
        try:
            return {"health_score": round(float(audits[0]["health_score"])),
                    "health_label": "Latest technical audit",
                    "last_audit_date": audits[0].get("created_at")}
        except (TypeError, ValueError):
            pass
    return {"health_score": None, "health_label": "No audit yet",
            "last_audit_date": None}


async def get_site_counts(supabase, website_id: Optional[str] = None) -> Dict[str, Any]:
    """One parallel pass for every shared counter. Same input, same output,
    whichever endpoint calls it."""
    filt = {"website_id": website_id} if website_id else {}
    (content_total, appr_pub, appr_pen, alerts_total, mem_total,
     backlinks_total, kb_total, health) = await asyncio.gather(
        _count(supabase, "content_log", filt or None),
        _count(supabase, "blog_approvals", {**filt, "status": "published"} or {"status": "published"}),
        _count(supabase, "blog_approvals", {**filt, "status": "pending"} or {"status": "pending"}),
        _count(supabase, "realtime_alerts", filt or None),
        _count(supabase, "brain_memory", filt or None),
        _count(supabase, "backlinks", filt or None),
        _count(supabase, "knowledge_base", filt or None),
        get_site_health(supabase, website_id),
    )
    # backlink_opportunities is its own table when present; never an alias
    # of backlinks_count (that alias was a bug).
    try:
        opps = await _count(supabase, "backlink_opportunities", filt or None)
    except Exception:
        opps = 0
    return {
        "total_articles": content_total,
        "published_articles": appr_pub,
        "pending_articles": appr_pen,
        "monitored_alerts": alerts_total,
        "memories_count": mem_total,
        "backlinks_count": backlinks_total,
        "backlink_opportunities": opps,
        "knowledge_count": kb_total,
        **health,
    }
