"""Unified dashboard metrics with multi-tenant account isolation.
Single source of truth: every number queries tenant-isolated Supabase tables.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from database import get_supabase, set_account_context
from middleware.auth import get_current_account_id

logger = logging.getLogger("backend.routers.dashboard")
router = APIRouter(tags=["dashboard"])

AGENT_NAMES = [
    "WriterPipeline",
    "BrainAutopilot",
    "ContinuousMonitor",
    "BacklinkScout",
    "TechSEOAgent",
    "AuthorityCalibration",
]

_TASK_AGENT_ALIASES = {
    "WriterPipeline": ["writer_pipeline", "WriterPipeline", "writer", "human_writer_agent"],
    "BrainAutopilot": ["brain_autopilot", "BrainAutopilotAgent", "supervisor_agent"],
    "ContinuousMonitor": ["continuous_monitor", "monitor", "api"],
    "BacklinkScout": ["backlink_scout", "opportunity_scout", "backlink_agent", "BacklinkAgent"],
    "TechSEOAgent": ["tech_seo", "tech_seo_agent", "TechSEOAgent"],
    "AuthorityCalibration": ["authority_calibration", "AuthorityCalibrationAgent"],
}


def _count(supabase, table: str, filters: Optional[dict] = None,
           gte_field=None, gte_value=None) -> int:
    try:
        q = supabase.table(table).select("id", count="exact")
        for k, v in (filters or {}).items():
            if v is not None:
                q = q.eq(k, v)
        if gte_field and gte_value:
            q = q.gte(gte_field, gte_value)
        res = q.execute()
        return getattr(res, "count", None) or len(res.data or [])
    except Exception as e:
        logger.debug(f"[Dashboard] count {table} failed: {e}")
        return 0


async def _count_async(supabase, table: str, filters: Optional[dict] = None,
           gte_field=None, gte_value=None) -> int:
    """Async wrapper for _count to allow asyncio.gather parallelism."""
    return await asyncio.to_thread(_count, supabase, table, filters, gte_field, gte_value)


async def _agent_statuses(supabase, website_id: str, account_id: str) -> list:
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    statuses = []
    
    def _fetch_tasks():
        try:
            res = (
                supabase.table("tasks")
                .select("agent_name, status, result, payload, created_at")
                .gte("created_at", (datetime.utcnow() - timedelta(days=7)).isoformat())
                .order("created_at", desc=True)
                .limit(100)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.debug(f"[Dashboard] tasks query note: {e}")
            return []

    recent_tasks = await asyncio.to_thread(_fetch_tasks)

    for display_name in AGENT_NAMES:
        aliases = _TASK_AGENT_ALIASES.get(display_name, [display_name])
        alias_set = set(aliases)
        site_rows = [r for r in recent_tasks if r.get("agent_name") in alias_set]

        last_success = None
        last_failure = None
        summary = None

        ok = next((r for r in site_rows if r.get("status") in ("completed", "success")), None)
        if ok:
            last_success = ok.get("created_at")
            result = ok.get("result") or {}
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except Exception:
                    result = {}
            if isinstance(result, dict):
                summary = (result.get("summary") or result.get("message") or "")[:120]

        bad = next((r for r in site_rows if r.get("status") == "failed"), None)
        if bad:
            last_failure = bad

        if last_failure and (not last_success or last_failure.get("created_at", "") >= last_success):
            err = ((last_failure.get("payload") or {}).get("error")
                   or (last_failure.get("result") or {}).get("error")
                   or "Unknown error")
            state = {"name": display_name, "state": "ERROR", "last_run": last_failure.get("created_at"),
                     "summary": None, "error": str(err)[:200]}
        elif last_success and last_success >= cutoff:
            state = {"name": display_name, "state": "ACTIVE", "last_run": last_success,
                     "summary": summary, "error": None}
        else:
            state = {"name": display_name, "state": "IDLE",
                     "last_run": last_success, "summary": summary, "error": None}
        statuses.append(state)
    return statuses


_METRICS_CACHE: dict = {}
_METRICS_CACHE_TS: dict = {}


@router.get("/dashboard/{website_id}/metrics")
@router.get("/api/dashboard/{website_id}/metrics")
async def get_dashboard_metrics(website_id: str, request: Request):
    """All dashboard metrics from tenant-isolated Supabase sources with 10s TTL cache."""
    account_id = get_current_account_id(request)

    import time
    cache_key = f"{account_id}:{website_id}"
    now = time.time()
    if cache_key in _METRICS_CACHE and (now - _METRICS_CACHE_TS.get(cache_key, 0)) < 10.0:
        return _METRICS_CACHE[cache_key]

    supabase = get_supabase()
    set_account_context(supabase, account_id)

    wid = website_id
    if wid in ("default", "default-website-id", "", "null", "undefined"):
        try:
            sites = supabase.table("websites").select("id").eq("account_id", account_id).order("created_at").limit(1).execute().data or []
            wid = sites[0]["id"] if sites else None
        except Exception:
            wid = None
    if not wid:
        raise HTTPException(status_code=404, detail="No websites connected yet")

    # --- Shared counters: single source of truth with /api/stats.
    # Local-store max() merge preserves offline-created rows; DB counts
    # come from services/dashboard_metrics.py (no floors, no invented 94).
    from services.local_store import (
        list_local_content, list_local_approvals, list_local_knowledge, list_local_brain_memory
    )
    from services.dashboard_metrics import get_site_counts

    counts = await get_site_counts(supabase, wid)
    total_content_log = counts["total_articles"]
    published_approvals = counts["published_articles"]
    pending_approval = counts["pending_articles"]
    alerts_count_db = counts["monitored_alerts"]
    memories_count_db = counts["memories_count"]
    backlinks_count_db = counts["backlinks_count"]
    opportunities_count_db = counts["backlink_opportunities"]
    knowledge_count_db = counts["knowledge_count"]

    local_c = len(list_local_content(wid))
    local_app_pub = len(list_local_approvals(wid, "published"))
    local_app_pen = len(list_local_approvals(wid, "pending"))
    local_kb = len(list_local_knowledge(wid))
    local_mem = len(list_local_brain_memory(wid))

    total_articles = max(total_content_log, local_c)
    published_articles = max(published_approvals, local_app_pub)
    pending_approval_count = max(pending_approval, local_app_pen)
    # HONEST COUNTS ONLY: no floors. Empty DB returns 0, never an invented number.
    alerts_count = alerts_count_db
    backlinks_count = max(backlinks_count_db, 0)
    opportunities_count = max(opportunities_count_db, 0)
    memories_count = max(memories_count_db, local_mem)
    knowledge_count = max(knowledge_count_db, local_kb)

    # --- SEO health comes from the shared helper (latest real audit or None).
    seo_health_score = counts["health_score"]
    seo_health_label = counts.get("health_label") or "No audit yet"
    last_audit_date = counts.get("last_audit_date")

    # --- Recent content stream ---
    recent_content = []
    try:
        rows = (
            supabase.table("content_log")
            .select("id, title, keyword, status, pipeline_status, created_at")
            .eq("website_id", wid)
            .order("created_at", desc=True)
            .limit(8)
            .execute()
            .data or []
        )
        for r in rows:
            recent_content.append({
                "id": r["id"],
                "title": r.get("title") or "",
                "keyword": r.get("keyword"),
                "status": r.get("status"),
                "pipeline_status": r.get("pipeline_status"),
                "approval_id": None,
                "wordpress_url": None,
                "approval_status": r.get("status"),
                "created_at": r.get("created_at"),
            })
    except Exception as e:
        logger.debug(f"[Dashboard] recent content query failed: {e}")

    # Merge local content
    for lc in list_local_content(wid)[:8]:
        if not any(rc["id"] == lc.get("id") for rc in recent_content):
            recent_content.append({
                "id": lc.get("id"),
                "title": lc.get("title") or "",
                "keyword": lc.get("keyword"),
                "status": lc.get("status"),
                "pipeline_status": lc.get("pipeline_status"),
                "approval_id": None,
                "wordpress_url": None,
                "approval_status": lc.get("status"),
                "created_at": lc.get("created_at"),
            })

    agents = await _agent_statuses(supabase, wid, account_id)
    publishing_schedule = []

    res_dict = {
        "success": True,
        "website_id": wid,
        "total_articles": total_articles,
        "published_articles": published_articles,
        "pending_articles": pending_approval_count,
        "seo_health_score": seo_health_score,
        "seo_health_label": seo_health_label if seo_health_score is None else "Latest technical audit",
        "last_audit_date": last_audit_date,
        "monitored_alerts": alerts_count,
        "memories_count": memories_count,
        "knowledge_count": knowledge_count,
        "backlinks_count": backlinks_count,
        "backlink_opportunities": opportunities_count,
        "recent_content": recent_content,
        "agents": agents,
        "publishing_schedule": publishing_schedule,
        "generated_at": datetime.utcnow().isoformat(),
    }
    _METRICS_CACHE[cache_key] = res_dict
    _METRICS_CACHE_TS[cache_key] = now
    return res_dict


@router.get("/dashboard/overview")
@router.get("/api/dashboard/overview")
async def get_dashboard_overview(request: Request, website_id: Optional[str] = None):
    """SEO-outcomes-first dashboard: indexation, GSC performance, striking
    distance, issues, decay, pipeline, last runs.

    Every section is honest about provenance: null means no data (with a
    fix hint), never an invented number. All section queries run in
    parallel; one section failing never fails the whole response.
    """
    from services.run_service import get_last_run_summary, get_recent_runs

    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    wid = website_id or request.query_params.get("website_id")
    if not wid or wid in ("default", "default-website-id", "", "null", "undefined"):
        try:
            sites = supabase.table("websites").select("id").eq(
                "account_id", account_id).order("created_at").limit(1).execute().data or []
            wid = sites[0]["id"] if sites else None
        except Exception:
            wid = None
    if not wid:
        return {"error": "No site selected", "connected": False}

    results = await asyncio.gather(
        _overview_indexation(wid),
        _overview_gsc(wid),
        _overview_striking(wid),
        _overview_issues(wid),
        _overview_decay(wid),
        _overview_pipeline(wid),
        get_last_run_summary(wid),
        get_recent_runs(wid, 5),
        return_exceptions=True,
    )

    def safe(result, fallback):
        if isinstance(result, Exception):
            logger.debug(f"[Dashboard] overview section note: {result}")
            return fallback
        return result

    return {
        "website_id": wid,
        "indexation": safe(results[0], {"rate": None, "label": "No check yet"}),
        "gsc": safe(results[1], {"impressions": None, "clicks": None,
                                 "avg_position": None, "connected": False,
                                 "fix": "Connect GSC in /connectors"}),
        "striking_distance": safe(results[2], {"count": None, "entering": None,
                                               "leaving": None}),
        "open_issues": safe(results[3], {"count": None}),
        "decaying_pages": safe(results[4], {"count": None}),
        "pending_approvals": safe(results[5], {"count": 0}),
        "last_run": safe(results[6], {"summary": "No runs yet"}),
        "recent_runs": safe(results[7], []),
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _overview_indexation(wid: str) -> dict:
    try:
        from services.indexation_service import get_indexation_summary
    except (ImportError, ValueError):
        from backend.services.indexation_service import get_indexation_summary
    summary = await get_indexation_summary(wid)
    if summary.get("rate") is None:
        summary["fix"] = "Run POST /api/indexation/{site}/check (connect GSC for indexed count)"
    return summary


async def _overview_gsc(wid: str) -> dict:
    from routers.gsc import get_performance
    perf = await get_performance(wid, None, None)
    if not perf.get("connected") or not perf.get("keywords"):
        return {"impressions": None, "clicks": None, "avg_position": None,
                "connected": bool(perf.get("connected")),
                "fix": perf.get("message") or "Connect GSC in /connectors"}
    return {"impressions": perf.get("total_impressions"),
            "clicks": perf.get("total_clicks"),
            "avg_position": perf.get("average_position"),
            "connected": True,
            "keywords": len(perf.get("keywords", [])),
            "start_date": perf.get("start_date"), "end_date": perf.get("end_date")}


async def _overview_striking(wid: str) -> dict:
    """Count striking-distance keywords from rank_tracking with real
    entering/leaving deltas derived from each row's position_history."""
    try:
        from seo_constants import STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX, is_striking_distance
    except (ImportError, ValueError):
        from backend.seo_constants import (STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX,
                                           is_striking_distance)
    supabase = get_supabase()
    try:
        rows = supabase.table("rank_tracking").select(
            "keyword, target_keyword, current_position, position_history"
        ).eq("website_id", wid).execute().data or []
    except Exception:
        rows = []
    if not rows:
        return {"count": None, "entering": None, "leaving": None,
                "range": [STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX],
                "fix": "Run rank tracking (POST /api/rankings/check) to populate positions"}
    count, entering, leaving = 0, 0, 0
    for r in rows:
        cur = r.get("current_position")
        if cur is None:
            continue
        now_in = is_striking_distance(cur)
        if now_in:
            count += 1
        hist = r.get("position_history") or []
        prev_pos = None
        for h in reversed(hist[:-1] if len(hist) > 1 else []):
            if isinstance(h, dict) and h.get("position") is not None:
                prev_pos = h["position"]
                break
        if prev_pos is None:
            continue
        was_in = is_striking_distance(prev_pos)
        if now_in and not was_in:
            entering += 1
        elif was_in and not now_in:
            leaving += 1
    return {"count": count, "entering": entering, "leaving": leaving,
            "range": [STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX]}


async def _overview_issues(wid: str) -> dict:
    supabase = get_supabase()

    def _q():
        try:
            alerts = supabase.table("realtime_alerts").select("id").eq(
                "website_id", wid).eq("is_read", False).execute().data or []
        except Exception:
            alerts = []
        try:
            fixes = supabase.table("pending_fixes").select("id").eq(
                "website_id", wid).eq("status", "pending_approval").execute().data or []
        except Exception:
            fixes = []
        return len(alerts), len(fixes)

    unread, pending = await asyncio.to_thread(_q)
    return {"count": unread + pending, "unread_alerts": unread,
            "pending_fixes": pending}


async def _overview_decay(wid: str) -> dict:
    supabase = get_supabase()
    try:
        rows = await asyncio.to_thread(
            lambda: supabase.table("content_decay_logs").select("id").eq(
                "website_id", wid).eq("status", "detected").execute().data or [])
        return {"count": len(rows)}
    except Exception:
        return {"count": None, "fix": "Run decay detection (POST /api/decay/{site}/detect)"}


async def _overview_pipeline(wid: str) -> dict:
    supabase = get_supabase()

    def _q():
        try:
            appr = supabase.table("blog_approvals").select("id").eq(
                "website_id", wid).eq("status", "pending").execute().data or []
        except Exception:
            appr = []
        return len(appr)

    pending = await asyncio.to_thread(_q)
    return {"count": pending}


@router.get("/dashboard/{website_id}/live")
@router.get("/api/dashboard/{website_id}/live")
async def dashboard_live_stream(website_id: str, request: Request):
    """SSE stream pushing refreshed metrics."""
    from services.event_bus import stream as bus_stream

    async def event_generator():
        try:
            snapshot = await get_dashboard_metrics(website_id, request)
            yield f"data: {json.dumps({'event': 'metrics', 'payload': snapshot}, default=str)}\n\n"
        except Exception:
            pass
        async for event in bus_stream(f"dashboard:{website_id}"):
            if event.get("keepalive"):
                yield ": keepalive\n\n"
                continue
            try:
                snapshot = await get_dashboard_metrics(website_id, request)
                yield f"data: {json.dumps({'event': event.get('event', 'update'), 'payload': snapshot}, default=str)}\n\n"
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
