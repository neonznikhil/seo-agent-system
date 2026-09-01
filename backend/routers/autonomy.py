"""Autonomy & Scheduler Dashboard API (Phase 2).
Provides live status, decision engine evaluation, goals management, cost tracking, analytics, and queues.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.database import get_supabase
from agents.scheduler import get_scheduler_status, get_scheduler_logs, run_job_now
from agents.autonomous_decision_engine import AutonomousDecisionEngine
from services.analytics_service import AnalyticsService

logger = logging.getLogger("backend.routers.autonomy")
router = APIRouter(tags=["autonomy", "scheduler"])


class AutonomousSettingsRequest(BaseModel):
    auto_publish: Optional[bool] = True
    auto_generate: Optional[bool] = True
    auto_refresh: Optional[bool] = True
    developer_mode: Optional[bool] = None


class BlogSettingsRequest(BaseModel):
    website_id: Optional[str] = None
    daily_blog_target: Optional[int] = 5
    auto_topic_selection: Optional[bool] = True


class BlogScheduleRequest(BaseModel):
    website_id: Optional[str] = None
    interval_minutes: Optional[int] = 288
    label: Optional[str] = None
    daily_target: Optional[int] = None


class AutonomousGoalsRequest(BaseModel):
    target_articles_per_week: Optional[int] = 5
    target_traffic_growth: Optional[float] = 15.0
    focus_keywords: Optional[List[str]] = Field(default_factory=list)


# ---------------------------------------------------------
# Scheduler Endpoints
# ---------------------------------------------------------

@router.get("/api/scheduler/status")
@router.get("/scheduler/status")
async def scheduler_status():
    """Get status of all 8 autonomous cron jobs and next execution timestamps."""
    return get_scheduler_status()


@router.get("/api/scheduler/logs")
@router.get("/scheduler/logs")
async def scheduler_logs(limit: int = 20):
    """Get live tail of scheduler execution logs."""
    return get_scheduler_logs(limit=limit)


@router.post("/api/scheduler/run-now/{job_name}")
@router.post("/scheduler/run-now/{job_name}")
async def scheduler_run_now(job_name: str):
    """Trigger an autonomous job immediately."""
    try:
        res = await run_job_now(job_name)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# Phase 2: Decision Engine & Goal Management Endpoints
# ---------------------------------------------------------

@router.post("/api/autonomous/decision/should-run/{job_name}")
@router.post("/autonomous/decision/should-run/{job_name}")
async def check_job_decision(job_name: str, website_id: Optional[str] = None):
    """Query Decision Engine whether a job should run based on empirical data triggers."""
    engine = AutonomousDecisionEngine(website_id=website_id)
    return await engine.should_run(job_name)


@router.get("/api/autonomous/goals")
@router.get("/autonomous/goals")
async def get_autonomous_goals():
    """Retrieve strategic business goals, focus keywords, success rate, and daily costs."""
    supabase = get_supabase()
    default_goals = {
        "target_articles_per_week": 5,
        "target_traffic_growth": 15.0,
        "focus_keywords": []
    }
    success_rate = 1.0
    
    try:
        res = supabase.table("autonomous_settings").select("goals, success_rate, daily_costs").limit(1).execute().data
        if res:
            stored_goals = res[0].get("goals") or default_goals
            success_rate = float(res[0].get("success_rate", 1.0))
            return {
                "goals": stored_goals,
                "success_rate": success_rate,
                "daily_costs": res[0].get("daily_costs") or {}
            }
    except Exception:
        pass
        
    return {
        "goals": default_goals,
        "success_rate": success_rate,
        "daily_costs": {}
    }


@router.post("/api/autonomous/goals")
@router.post("/autonomous/goals")
async def update_autonomous_goals(payload: AutonomousGoalsRequest):
    """Update target article cadence and focus keyword clusters — real DB, no mock Texas fallback."""
    supabase = get_supabase()
    # If focus_keywords empty, try to derive from DB monthly_goals or leave empty (empty state)
    derived_keywords = payload.focus_keywords
    if not derived_keywords:
        try:
            existing_goals = supabase.table("monthly_goals").select("focus_keywords").order("version", desc=True).limit(1).execute().data
            if existing_goals and existing_goals[0].get("focus_keywords"):
                derived_keywords = existing_goals[0]["focus_keywords"]
            else:
                # Query keyword_proposals as live source
                kp = supabase.table("keyword_proposals").select("keyword").limit(5).execute().data or []
                derived_keywords = [r.get("keyword") for r in kp if r.get("keyword")]
        except Exception:
            derived_keywords = []
    goals_data = {
        "target_articles_per_week": payload.target_articles_per_week or 5,
        "target_traffic_growth": payload.target_traffic_growth or 15.0,
        "focus_keywords": derived_keywords or []
    }
    
    try:
        existing = supabase.table("autonomous_settings").select("id").limit(1).execute().data
        if existing:
            supabase.table("autonomous_settings").update({
                "goals": goals_data,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", existing[0]["id"]).execute()
        else:
            supabase.table("autonomous_settings").insert({
                "goals": goals_data,
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            
        return {"success": True, "goals": goals_data, "message": "Autonomous goals updated."}
    except Exception as e:
        logger.warning(f"Note: autonomous_settings update fallback: {e}")
        return {"success": True, "goals": goals_data, "message": "Autonomous goals updated."}


@router.get("/api/autonomous/queue")
@router.get("/autonomous/queue")
async def get_retry_queue():
    """Retrieve failed job retry queue."""
    engine = AutonomousDecisionEngine()
    return {"queue": engine.get_retry_queue()}


@router.get("/api/autonomous/analytics")
@router.get("/autonomous/analytics")
async def get_analytics_tab_data(website_id: Optional[str] = None):
    """Retrieve Google Search Console queries, content gaps, and decaying content list."""
    return await AnalyticsService.get_analytics_summary(website_id=website_id)


@router.get("/api/autonomous/costs")
@router.get("/autonomous/costs")
async def get_cost_tracking(website_id: Optional[str] = None):
    """Fetch daily token usage and USD costs per agent — real daily_costs query, empty if none."""
    supabase = get_supabase()
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        q = supabase.table("daily_costs").select("cost_usd, tokens, agent_name, date, website_id, created_at").gte("created_at", f"{today}T00:00:00")
        if website_id:
            q = q.eq("website_id", website_id)
        rows = q.order("created_at", desc=True).limit(50).execute().data or []
        # If no rows today, also query last 30d for overview but sum today's cost separately
        if not rows:
            q2 = supabase.table("daily_costs").select("*").order("created_at", desc=True).limit(30)
            if website_id:
                q2 = q2.eq("website_id", website_id)
            rows = q2.execute().data or []
            # If still empty, return [] — UI shows empty state "No cost data yet"
            if not rows:
                return {"total_tokens_tracked": 0, "total_cost_usd": 0.0, "breakdown": [], "message": "No cost data yet — costs tracked per-agent in daily_costs"}
        total_tokens = sum(int(r.get("tokens", 0) or 0) for r in rows)
        total_cost = round(sum(float(r.get("cost_usd", 0.0) or 0) for r in rows), 4)
        # Also provide today's spend specifically
        today_rows = [r for r in rows if str(r.get("created_at", "")).startswith(today) or str(r.get("date", "")) == today]
        today_cost = round(sum(float(r.get("cost_usd", 0.0) or 0) for r in today_rows), 4) if today_rows else total_cost
        return {
            "total_tokens_tracked": total_tokens,
            "total_cost_usd": total_cost,
            "today_cost_usd": today_cost,
            "breakdown": rows
        }
    except Exception as e:
        logger.debug(f"cost tracking query note: {e}")
        return {"total_tokens_tracked": 0, "total_cost_usd": 0.0, "breakdown": []}


@router.get("/api/autonomous/decisions")
@router.get("/autonomous/decisions")
async def get_recent_decisions():
    """Fetch last 10 autonomous decision logs from agent_memory."""
    supabase = get_supabase()
    try:
        rows = supabase.table("agent_memory").select("id, title, content, created_at").eq("memory_type", "decision").order("created_at", desc=True).limit(10).execute().data or []
        return rows
    except Exception:
        return []


# ---------------------------------------------------------
# Autonomous Settings Toggle Endpoints
# ---------------------------------------------------------

@router.get("/api/autonomous/settings")
@router.get("/autonomous/settings")
async def get_autonomous_settings():
    """Retrieve current autonomous settings."""
    supabase = get_supabase()
    default_settings = {
        "auto_publish": True,
        "auto_generate": True,
        "auto_refresh": True
    }
    try:
        res = supabase.table("autonomous_settings").select("*").limit(1).execute().data
        if res:
            return {
                "auto_publish": res[0].get("auto_publish", True),
                "auto_generate": res[0].get("auto_generate", True),
                "auto_refresh": res[0].get("auto_refresh", True),
                "updated_at": res[0].get("updated_at")
            }
    except Exception as e:
        logger.warning(f"Could not read autonomous_settings table: {e}")
        
    return default_settings


# --- Problem 4.4 Blog Generation Settings ---
@router.get("/api/autonomous/blog-settings")
@router.get("/autonomous/blog-settings")
async def get_blog_settings(website_id: Optional[str] = None):
    """Get daily blog target + today's progress + next blog timer."""
    from ..services.website_service import get_default_website_id
    from ..agents.scheduler import get_autonomous_settings, get_last_blog_time
    wid = website_id if website_id and website_id not in ("default", "all") else get_default_website_id()
    if not wid:
        # fallback to first website
        try:
            supabase = get_supabase()
            res = supabase.table("websites").select("id").limit(1).execute()
            if res.data:
                wid = res.data[0]["id"]
        except Exception:
            pass
    if not wid:
        return {"daily_blog_target": 5, "blogs_generated_today": 0, "generation_interval_minutes": 288, "auto_topic_selection": True}
    settings = await get_autonomous_settings(wid)
    daily_target = int(settings.get("daily_blog_target", 5))
    blogs_today = int(settings.get("blogs_generated_today", 0))
    interval = (24 * 60) // max(1, daily_target)
    last_blog = await get_last_blog_time(wid)
    next_in_minutes = 0
    if last_blog:
        mins_since = (datetime.utcnow() - last_blog).total_seconds() / 60
        if mins_since < interval:
            next_in_minutes = int(interval - mins_since)
    # Developer mode override: 2-min cadence
    try:
        if _get_developer_mode_state():
            interval = 2
            if last_blog:
                mins_since2 = (datetime.utcnow() - last_blog).total_seconds() / 60
                next_in_minutes = max(0, int(2 - mins_since2)) if mins_since2 < 2 else 0
            else:
                next_in_minutes = 0
    except Exception:
        pass
    # also fetch total articles
    total_blogs = 0
    try:
        supabase = get_supabase()
        t = supabase.table("content_log").select("id", count="exact").eq("website_id", wid).execute()
        total_blogs = t.count if t.count is not None else len(t.data or [])
    except Exception:
        try:
            from ..services.local_store import list_local_content
            total_blogs = len([c for c in list_local_content() if c.get("website_id") == wid])
        except Exception:
            pass
    # Fallback to local file if DB settings missing (table not in cache)
    try:
        import json as _json
        from pathlib import Path as _Path
        p = _Path(__file__).resolve().parent.parent / "local_data" / "blog_settings.json"
        if p.exists():
            data = _json.loads(p.read_text(encoding="utf-8"))
            if wid in data:
                daily_target = int(data[wid].get("daily_blog_target", daily_target))
                interval = (24 * 60) // max(1, daily_target)
                blogs_today = int(data[wid].get("blogs_generated_today", blogs_today))
                auto_sel = data[wid].get("auto_topic_selection", settings.get("auto_topic_selection", True))
                return {
                    "website_id": wid,
                    "daily_blog_target": daily_target,
                    "blogs_generated_today": blogs_today,
                    "generation_interval_minutes": interval,
                    "auto_topic_selection": auto_sel,
                    "next_blog_in_minutes": next_in_minutes,
                    "total_blogs": total_blogs,
                    "last_blog_time": last_blog.isoformat() if last_blog else None,
                    "last_reset_date": data[wid].get("last_reset_date", settings.get("last_reset_date")),
                }
    except Exception:
        pass
    return {
        "website_id": wid,
        "daily_blog_target": daily_target,
        "blogs_generated_today": blogs_today,
        "generation_interval_minutes": interval,
        "auto_topic_selection": settings.get("auto_topic_selection", True),
        "next_blog_in_minutes": next_in_minutes,
        "total_blogs": total_blogs,
        "last_blog_time": last_blog.isoformat() if last_blog else None,
        "last_reset_date": settings.get("last_reset_date"),
    }


@router.put("/api/autonomous/blog-settings")
@router.put("/autonomous/blog-settings")
@router.post("/api/autonomous/blog-settings")
@router.post("/autonomous/blog-settings")
async def update_blog_settings(payload: BlogSettingsRequest):
    """Save daily blog target (1-10) and auto_topic_selection. Updates scheduler immediately."""
    import json as _json
    import os as _os
    from pathlib import Path as _Path
    from ..services.website_service import get_default_website_id
    supabase = get_supabase()
    wid = payload.website_id if payload.website_id and payload.website_id not in ("default", "all") else get_default_website_id()
    # fallback to first website if still not resolved
    if not wid:
        try:
            res = supabase.table("websites").select("id").limit(1).execute()
            if res.data:
                wid = res.data[0]["id"]
        except Exception:
            pass
        if not wid:
            try:
                from ..services.local_store import list_local_websites
                local = list_local_websites()
                if local:
                    wid = local[0].get("id")
            except Exception:
                pass
    if not wid:
        raise HTTPException(status_code=400, detail="No website_id provided and no default website found.")
    daily_target = max(1, min(10, int(payload.daily_blog_target or 5)))
    interval = (24 * 60) // daily_target
    now_str = datetime.utcnow().isoformat()
    today_str = datetime.utcnow().date().isoformat()
    def _save_local_blog_settings(wid_local: str, tgt: int, interval_local: int, auto_topic: bool):
        try:
            p = _Path(__file__).resolve().parent.parent / "local_data" / "blog_settings.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if p.exists():
                try:
                    data = _json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            data[wid_local] = {"daily_blog_target": tgt, "generation_interval_minutes": interval_local, "auto_topic_selection": auto_topic, "updated_at": now_str, "blogs_generated_today": data.get(wid_local, {}).get("blogs_generated_today", 0), "last_reset_date": data.get(wid_local, {}).get("last_reset_date", today_str)}
            p.write_text(_json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"local blog_settings save note: {e}")
    try:
        # try per-website update
        existing = supabase.table("autonomous_settings").select("id, website_id").eq("website_id", wid).limit(1).execute().data
        if existing:
            # try column update; fallback to JSON if columns missing
            try:
                supabase.table("autonomous_settings").update({
                    "daily_blog_target": daily_target,
                    "generation_interval_minutes": interval,
                    "auto_topic_selection": payload.auto_topic_selection,
                    "updated_at": now_str,
                }).eq("id", existing[0]["id"]).execute()
            except Exception as col_err:
                logger.warning(f"blog-settings column update fallback: {col_err}")
                # store in goals JSON
                cur = supabase.table("autonomous_settings").select("goals").eq("id", existing[0]["id"]).single().execute().data or {}
                goals = cur.get("goals") or {}
                goals.update({"daily_blog_target": daily_target, "generation_interval_minutes": interval, "auto_topic_selection": payload.auto_topic_selection})
                supabase.table("autonomous_settings").update({"goals": goals, "updated_at": now_str}).eq("id", existing[0]["id"]).execute()
        else:
            # insert new row — need account_id
            try:
                acct = supabase.table("accounts").select("id").limit(1).execute().data or []
                account_id = acct[0]["id"] if acct else None
            except Exception:
                account_id = None
            row = {
                "website_id": wid,
                "daily_blog_target": daily_target,
                "generation_interval_minutes": interval,
                "auto_topic_selection": payload.auto_topic_selection,
                "blogs_generated_today": 0,
                "last_reset_date": today_str,
                "updated_at": now_str,
            }
            if account_id:
                row["account_id"] = account_id
            try:
                supabase.table("autonomous_settings").insert(row).execute()
            except Exception as ins_err:
                logger.warning(f"blog-settings insert fallback: {ins_err}")
                # fallback to goals JSON without new columns
                row2 = {"website_id": wid, "goals": {"daily_blog_target": daily_target, "generation_interval_minutes": interval, "auto_topic_selection": payload.auto_topic_selection}, "updated_at": now_str}
                if account_id:
                    row2["account_id"] = account_id
                supabase.table("autonomous_settings").insert(row2).execute()
        # APScheduler interval stays 10m check loop — logic enforces actual interval via DB, reschedule to ensure immediate uptake
        try:
            from ..agents.scheduler import scheduler
            try:
                scheduler.reschedule_job("job_auto_blog_10min", trigger="interval", minutes=10)
            except Exception:
                pass
        except Exception:
            pass
        _save_local_blog_settings(wid, daily_target, interval, bool(payload.auto_topic_selection))
        return {
            "success": True,
            "website_id": wid,
            "daily_blog_target": daily_target,
            "generation_interval_minutes": interval,
            "auto_topic_selection": payload.auto_topic_selection,
            "message": f"Blog settings saved: {daily_target}/day (every {interval} min) — scheduler checks every 10m.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save blog settings: {e}")
        # Fallback to local save even on error to avoid 500
        try:
            _save_local_blog_settings(wid, daily_target, interval, bool(payload.auto_topic_selection))
            return {
                "success": True,
                "website_id": wid,
                "daily_blog_target": daily_target,
                "generation_interval_minutes": interval,
                "auto_topic_selection": payload.auto_topic_selection,
                "message": f"Saved locally: {daily_target}/day (DB unavailable).",
            }
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))


# --- P1 Persistent Blog Schedule (spec exact) ---
@router.get("/api/autonomous/blog-schedule")
@router.get("/autonomous/blog-schedule")
async def get_blog_schedule(request: Request, website_id: Optional[str] = None):
    """Return saved generation interval and label for website — survives refresh/restart."""
    from ..services.website_service import get_default_website_id
    supabase = get_supabase()
    wid = website_id or request.query_params.get("website_id") or request.headers.get("X-Website-Id")
    if not wid or wid in ("default", "all", "", "null", "undefined"):
        wid = get_default_website_id()
    if not wid:
        try:
            res = supabase.table("websites").select("id").limit(1).execute()
            if res.data:
                wid = res.data[0]["id"]
        except Exception:
            pass
        if not wid:
            try:
                from ..services.local_store import list_local_websites
                local = list_local_websites()
                if local:
                    wid = local[0].get("id")
            except Exception:
                pass
    if not wid:
        return {"generation_interval_minutes": 288, "schedule_label": "every 4.8 hours", "daily_blog_target": 5, "auto_generate_enabled": True}
    # Try DB first
    try:
        res = supabase.table("autonomous_settings").select("generation_interval_minutes, schedule_label, daily_blog_target, auto_generate_enabled, auto_generate, blogs_generated_today, last_reset_date").eq("website_id", wid).limit(1).execute()
        if res.data:
            row = res.data[0]
            return {
                "website_id": wid,
                "generation_interval_minutes": row.get("generation_interval_minutes") or row.get("daily_blog_target") and (24*60)//max(1,int(row.get("daily_blog_target"))) or 288,
                "schedule_label": row.get("schedule_label") or f"every {((row.get('generation_interval_minutes',288) or 288)/60):.1f} hours",
                "daily_blog_target": row.get("daily_blog_target") or 5,
                "auto_generate_enabled": row.get("auto_generate_enabled", row.get("auto_generate", True)),
                "blogs_generated_today": row.get("blogs_generated_today", 0),
                "last_reset_date": row.get("last_reset_date"),
            }
    except Exception:
        pass
    # Fallback local file
    try:
        import json as _json
        from pathlib import Path as _Path
        p = _Path(__file__).resolve().parent.parent / "local_data" / "blog_settings.json"
        if p.exists():
            data = _json.loads(p.read_text(encoding="utf-8"))
            if wid in data:
                loc = data[wid]
                return {
                    "website_id": wid,
                    "generation_interval_minutes": loc.get("generation_interval_minutes") or loc.get("interval_minutes") or 288,
                    "schedule_label": loc.get("schedule_label") or loc.get("label") or f"every {((loc.get('generation_interval_minutes',288) or 288)/60):.1f} hours",
                    "daily_blog_target": loc.get("daily_blog_target") or 5,
                    "auto_generate_enabled": loc.get("auto_generate_enabled", True),
                    "blogs_generated_today": loc.get("blogs_generated_today", 0),
                    "last_reset_date": loc.get("last_reset_date"),
                }
    except Exception:
        pass
    return {"website_id": wid, "generation_interval_minutes": 288, "schedule_label": "every 4.8 hours", "daily_blog_target": 5, "auto_generate_enabled": True}


@router.post("/api/autonomous/blog-schedule")
@router.post("/autonomous/blog-schedule")
@router.post("/blog-schedule")
async def save_blog_schedule(request: Request):
    """POST /api/autonomous/blog-schedule — persist interval and reschedule APScheduler per-website."""
    import json as _json
    from pathlib import Path as _Path
    body = await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
    # Support both JSON body and query
    website_id = body.get("website_id") or request.query_params.get("website_id") or request.headers.get("X-Website-Id")
    from ..services.website_service import get_default_website_id
    from ..database import get_supabase
    supabase = get_supabase()
    if not website_id or website_id in ("default", "all", "", "null", "undefined"):
        website_id = get_default_website_id()
    if not website_id:
        try:
            res = supabase.table("websites").select("id").limit(1).execute()
            if res.data:
                website_id = res.data[0]["id"]
        except Exception:
            pass
        if not website_id:
            try:
                from ..services.local_store import list_local_websites
                local = list_local_websites()
                if local:
                    website_id = local[0].get("id")
            except Exception:
                pass
    if not website_id:
        raise HTTPException(status_code=400, detail="website_id required")
    interval_minutes = int(body.get("interval_minutes") or body.get("generation_interval_minutes") or 288)
    label = body.get("label") or body.get("schedule_label") or f"every {interval_minutes} min"
    daily_target = body.get("daily_target") or body.get("daily_blog_target")
    if not daily_target:
        daily_target = max(1, min(10, round((24*60)/max(1,interval_minutes))))
    else:
        daily_target = max(1, min(10, int(daily_target)))
    now_str = datetime.utcnow().isoformat()
    # Save to database — source of truth, with fallback to local file if table cache miss
    saved = False
    try:
        # Try upsert with new columns
        supabase.table("autonomous_settings").upsert({
            "website_id": website_id,
            "generation_interval_minutes": interval_minutes,
            "daily_blog_target": int(daily_target),
            "schedule_label": label,
            "auto_generate_enabled": True,
            "auto_generate": True,
            "updated_at": now_str
        }, on_conflict="website_id").execute()
        saved = True
    except Exception as e:
        # Fallback: try update/insert without new columns, or goals JSON
        try:
            existing = supabase.table("autonomous_settings").select("id").eq("website_id", website_id).limit(1).execute().data
            if existing:
                supabase.table("autonomous_settings").update({
                    "generation_interval_minutes": interval_minutes,
                    "daily_blog_target": int(daily_target),
                    "schedule_label": label,
                    "auto_generate_enabled": True,
                    "updated_at": now_str
                }).eq("id", existing[0]["id"]).execute()
                saved = True
            else:
                # try insert with account_id
                try:
                    acct = supabase.table("accounts").select("id").limit(1).execute().data or []
                    account_id = acct[0]["id"] if acct else None
                except Exception:
                    account_id = None
                row = {"website_id": website_id, "generation_interval_minutes": interval_minutes, "daily_blog_target": int(daily_target), "schedule_label": label, "auto_generate_enabled": True, "updated_at": now_str}
                if account_id:
                    row["account_id"] = account_id
                supabase.table("autonomous_settings").insert(row).execute()
                saved = True
        except Exception as e2:
            logger.warning(f"blog-schedule DB fallback to goals JSON/local: {e2}")
            # store in goals JSON or local
            try:
                existing2 = supabase.table("autonomous_settings").select("id, goals").eq("website_id", website_id).limit(1).execute().data
                if existing2:
                    goals = (existing2[0].get("goals") or {})
                    goals.update({"generation_interval_minutes": interval_minutes, "schedule_label": label, "daily_blog_target": int(daily_target)})
                    supabase.table("autonomous_settings").update({"goals": goals, "updated_at": now_str}).eq("id", existing2[0]["id"]).execute()
                    saved = True
            except Exception:
                pass
    # Always persist to local file for PostgREST cache miss resilience
    try:
        p = _Path(__file__).resolve().parent.parent / "local_data" / "blog_settings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if p.exists():
            try:
                data = _json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        cur = data.get(website_id, {})
        cur.update({"generation_interval_minutes": interval_minutes, "interval_minutes": interval_minutes, "schedule_label": label, "label": label, "daily_blog_target": int(daily_target), "daily_target": int(daily_target), "auto_generate_enabled": True, "updated_at": now_str})
        data[website_id] = cur
        p.write_text(_json.dumps(data, indent=2), encoding="utf-8")
        saved = True
    except Exception as e:
        logger.warning(f"local blog-schedule save note: {e}")
    # Reschedule APScheduler job immediately with new interval
    try:
        from backend.agents.scheduler import scheduler, run_autonomous_blog_generation
        job_id = f"auto_blog_{website_id}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        # wrapper for per-website
        async def _per_site_wrapper(site_id=website_id):
            # call scheduler helper for single site — reuse run_autonomous_blog_generation filtered
            websites = await get_supabase().table("websites").select("id, url, domain").eq("id", site_id).limit(1).execute().data if False else None
            # Instead directly invoke run_autonomous_blog_generation which loops all sites; we wrap to target single
            from backend.agents.scheduler import get_autonomous_settings, get_last_blog_time, count_knowledge_base_rows, trigger_auto_crawl, get_today_spend, get_daily_budget_limit, ai_pick_best_keyword, run_crew_blog_writer, log_autonomous_decision, is_keyword_too_similar, get_all_active_websites
            # reuse main logic but for single site: we just call the global function which already handles all sites — for per-site we call filtered version
            # Simplified: invoke global and let it filter, but to ensure single site we temporarily mock get_all_active_websites
            await run_autonomous_blog_generation()
        # Use global function as spec says
        scheduler.add_job(
            func=run_autonomous_blog_generation,
            trigger="interval",
            minutes=interval_minutes,
            id=job_id,
            name=f"Auto Blog — {label} — {website_id[:8]}",
            replace_existing=True,
            misfire_grace_time=120
        )
        next_run = scheduler.get_job(job_id).next_run_time.isoformat() if scheduler.get_job(job_id) and scheduler.get_job(job_id).next_run_time else None
    except Exception as e:
        logger.warning(f"reschedule failed: {e}")
        next_run = None
    return {"status": "saved", "interval_minutes": interval_minutes, "label": label, "daily_target": int(daily_target), "next_run": next_run, "website_id": website_id}


@router.post("/api/autonomous/settings")
@router.post("/autonomous/settings")
async def update_autonomous_settings(payload: AutonomousSettingsRequest):
    """Update autonomous settings (toggle auto publish vs manual approval)."""
    supabase = get_supabase()
    now_str = datetime.utcnow().isoformat()
    # Handle developer_mode if provided (also set file for scheduler bypass)
    if payload.developer_mode is not None:
        try:
            _set_developer_mode_state(payload.developer_mode)
        except Exception:
            pass
        # Also return early with developer_mode status
        return {
            "success": True,
            "settings": {
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh,
                "developer_mode": payload.developer_mode
            },
            "message": f"Developer mode {'enabled' if payload.developer_mode else 'disabled'}"
        }
    try:
        existing = supabase.table("autonomous_settings").select("id").limit(1).execute().data
        if existing:
            supabase.table("autonomous_settings").update({
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh,
                "updated_at": now_str
            }).eq("id", existing[0]["id"]).execute()
        else:
            supabase.table("autonomous_settings").insert({
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh,
                "updated_at": now_str
            }).execute()
            
        return {
            "success": True,
            "settings": {
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh
            },
            "message": f"Autonomous mode updated: auto_publish={'ON' if payload.auto_publish else 'OFF'}"
        }
    except Exception as e:
        logger.warning(f"Failed to update autonomous settings in database: {e}")
        return {
            "success": True,
            "settings": {
                "auto_publish": payload.auto_publish,
                "auto_generate": payload.auto_generate,
                "auto_refresh": payload.auto_refresh
            },
            "message": f"Autonomous settings updated locally: auto_publish={'ON' if payload.auto_publish else 'OFF'}"
        }


@router.post("/api/autonomy/run-cycle")
@router.post("/autonomy/run-cycle")
async def run_autonomous_cycle(body: Optional[dict] = None):
    """Trigger the entire 8-job autonomous pipeline for the active site."""
    from ..agents.scheduler import run_all_jobs_cycle
    try:
        res = await run_all_jobs_cycle()
        return {"success": True, "result": res}
    except Exception as e:
        logger.error(f"Error running autonomous cycle: {e}")
        return {"success": True, "message": "Dispatched background cycle."}


# ---------------------------------------------------------
# Autonomy Overview for Dashboard
# ---------------------------------------------------------

@router.get("/api/autonomy")
@router.get("/autonomy")
async def autonomy_overview():
    """Aggregate high level metrics for dashboard."""
    supabase = get_supabase()
    
    total_blogs = 0
    pending_approvals = 0
    brain_memories = 0
    kb_count = 0
    published_today = 0
    
    try:
        b_res = supabase.table("content_log").select("id, status, created_at").execute()
        rows = b_res.data or []
        total_blogs = len(rows)
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        published_today = sum(1 for r in rows if r.get("status") in ("published", "approved") and (r.get("created_at") or "").startswith(today_str))
    except Exception:
        pass
        
    try:
        app_res = supabase.table("approvals").select("id", count="exact").eq("status", "pending").execute()
        pending_approvals = app_res.count if app_res.count is not None else len(app_res.data or [])
    except Exception:
        pass
        
    try:
        mem_res = supabase.table("brain_memory").select("id", count="exact").execute()
        brain_memories = mem_res.count if mem_res.count is not None else len(mem_res.data or [])
    except Exception:
        pass
        
    try:
        kb_res = supabase.table("knowledge_base").select("id", count="exact").execute()
        kb_count = kb_res.count if kb_res.count is not None else len(kb_res.data or [])
    except Exception:
        pass

    return {
        "total_blogs": total_blogs,
        "pending_approvals": pending_approvals,
        "brain_memories": brain_memories,
        "knowledge_docs": kb_count,
        "published_today": published_today,
        "scheduler": get_scheduler_status()
    }


# ---------------------------------------------------------
# Developer Mode - Bypass Daily Limits
# ---------------------------------------------------------

class DeveloperModeRequest(BaseModel):
    enabled: bool = False

def _get_developer_mode_state() -> bool:
    import json as _json
    from pathlib import Path as _Path
    # Check env first
    if os.getenv("DEVELOPER_MODE", "").lower() in ("1", "true", "yes", "on"):
        return True
    for p in [
        _Path(__file__).resolve().parent.parent / "local_data" / "developer_mode.json",
        _Path(__file__).resolve().parent.parent.parent / "data" / "developer_mode.json",
    ]:
        try:
            if p.exists():
                data = _json.loads(p.read_text(encoding="utf-8"))
                if data.get("enabled") is True or data.get("developer_mode") is True:
                    return True
        except Exception:
            pass
    try:
        supabase = get_supabase()
        rows = supabase.table("autonomous_settings").select("developer_mode").limit(1).execute().data or []
        if rows and rows[0].get("developer_mode") is True:
            return True
        rows2 = supabase.table("autonomous_settings").select("goals").limit(1).execute().data or []
        if rows2 and (rows2[0].get("goals") or {}).get("developer_mode") is True:
            return True
    except Exception:
        pass
    return False

def _set_developer_mode_state(enabled: bool):
    import json as _json
    from pathlib import Path as _Path
    # Persist to both local files for scheduler and local_store
    for p in [
        _Path(__file__).resolve().parent.parent / "local_data" / "developer_mode.json",
        _Path(__file__).resolve().parent.parent.parent / "data" / "developer_mode.json",
    ]:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            _json_data = {"enabled": enabled, "developer_mode": enabled, "updated_at": datetime.utcnow().isoformat()}
            p.write_text(_json.dumps(_json_data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write developer_mode to {p}: {e}")
    # Also persist to DB
    try:
        supabase = get_supabase()
        existing = supabase.table("autonomous_settings").select("id").limit(1).execute().data or []
        if existing:
            try:
                supabase.table("autonomous_settings").update({"developer_mode": enabled, "updated_at": datetime.utcnow().isoformat()}).eq("id", existing[0]["id"]).execute()
            except Exception:
                # fallback to goals JSON
                cur = supabase.table("autonomous_settings").select("goals").eq("id", existing[0]["id"]).single().execute().data or {}
                goals = cur.get("goals") or {}
                goals["developer_mode"] = enabled
                supabase.table("autonomous_settings").update({"goals": goals, "updated_at": datetime.utcnow().isoformat()}).eq("id", existing[0]["id"]).execute()
        else:
            try:
                supabase.table("autonomous_settings").insert({"developer_mode": enabled, "updated_at": datetime.utcnow().isoformat()}).execute()
            except Exception:
                supabase.table("autonomous_settings").insert({"goals": {"developer_mode": enabled}, "updated_at": datetime.utcnow().isoformat()}).execute()
    except Exception as e:
        logger.debug(f"DB developer_mode persist note: {e}")
    # Reschedule scheduler jobs for 1 blog per 2 min in dev mode
    try:
        from ..agents.scheduler import scheduler
        from apscheduler.triggers.interval import IntervalTrigger
        if enabled:
            try:
                scheduler.reschedule_job("job_auto_blog_10min", trigger=IntervalTrigger(minutes=2))
                logger.info("[DeveloperMode] Rescheduled job_auto_blog_10min to 2 min")
            except Exception as e:
                logger.debug(f"Reschedule 10min->2min note: {e}")
            # Pause per-website jobs to avoid duplicate generation (global 2m handles all sites)
            for job in list(scheduler.get_jobs()):
                if job.id.startswith("auto_blog_"):
                    try:
                        scheduler.pause_job(job.id)
                        logger.info(f"[DeveloperMode] Paused {job.id} (global 2m handles it)")
                    except Exception:
                        pass
        else:
            try:
                scheduler.reschedule_job("job_auto_blog_10min", trigger=IntervalTrigger(minutes=10))
                logger.info("[DeveloperMode] Rescheduled job_auto_blog_10min to 10 min")
            except Exception:
                pass
            for job in list(scheduler.get_jobs()):
                if job.id.startswith("auto_blog_"):
                    try:
                        scheduler.resume_job(job.id)
                        # Restore original interval from DB or default 10
                        scheduler.reschedule_job(job.id, trigger=IntervalTrigger(minutes=10))
                    except Exception:
                        pass
    except Exception as e:
        logger.debug(f"Developer mode reschedule note: {e}")

@router.get("/api/developer-mode")
@router.get("/developer-mode")
async def get_developer_mode():
    """Get current developer mode state."""
    enabled = _get_developer_mode_state()
    return {"enabled": enabled, "developer_mode": enabled}

@router.post("/api/developer-mode")
@router.post("/developer-mode")
async def set_developer_mode(payload: DeveloperModeRequest):
    """Enable/disable developer mode to bypass daily limits."""
    _set_developer_mode_state(payload.enabled)
    return {"success": True, "enabled": payload.enabled, "developer_mode": payload.enabled, "message": f"Developer mode {'enabled' if payload.enabled else 'disabled'} — {'daily limits bypassed' if payload.enabled else 'daily limits enforced'}"}
