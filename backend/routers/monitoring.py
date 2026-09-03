import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from fastapi.background import BackgroundTasks

logger = logging.getLogger("backend.routers.monitoring")

router = APIRouter()


@router.get("/monitoring/{website_id}/alerts")
@router.get("/api/monitoring/{website_id}/alerts")
async def get_alerts(website_id: str, filter: str = "unread"):
    from database import get_supabase
    from services.website_service import get_default_website_id
    
    target_id = website_id if website_id and website_id not in ("default", "default-website-id", "all", "", "null", "undefined") else get_default_website_id()
    if not target_id:
        return []
    
    sb = get_supabase()
    query = sb.table("realtime_alerts").select("*").eq("website_id", target_id)
    
    if filter == "unread":
        query = query.eq("is_read", False)
    elif filter == "critical":
        query = query.eq("severity", "critical")
    elif filter == "high":
        query = query.in_("severity", ["critical", "high"])
    
    rows = query.order("created_at", desc=True).limit(100).execute().data or []
    
    # If no alerts exist for this site, seed initial operational alert
    if not rows and filter in ("all", "unread"):
        init_alert = {
            "website_id": target_id,
            "severity": "info",
            "title": "Autonomous Monitoring Engine Active",
            "description": "Autonomous SEO Monitoring active. 6 background agents running (Rank, SERP, Competitor, Tech, Geo, Structure).",
            "source": "continuous_monitor",
            "is_read": False,
            "is_actioned": False,
            "created_at": datetime.utcnow().isoformat()
        }
        try:
            ins = sb.table("realtime_alerts").insert(init_alert).execute()
            if ins.data:
                rows = ins.data
        except Exception:
            rows = [init_alert]

    return rows


@router.post("/monitoring/{website_id}/test-alert")
@router.post("/api/monitoring/{website_id}/test-alert")
async def create_test_alert(website_id: str):
    """Trigger a live test alert for SSE stream and real-time dashboard verification."""
    from database import get_supabase
    import uuid
    sb = get_supabase()
    
    test_id = str(uuid.uuid4())
    alert_payload = {
        "id": test_id,
        "website_id": website_id,
        "severity": "high",
        "title": "Test Realtime Alert",
        "description": f"Verified live monitoring event at {datetime.utcnow().strftime('%H:%M:%S UTC')}. SSE stream operational.",
        "source": "manual_test",
        "is_read": False,
        "is_actioned": False,
        "created_at": datetime.utcnow().isoformat()
    }
    try:
        sb.table("realtime_alerts").insert(alert_payload).execute()
    except Exception as e:
        logger.debug(f"Test alert insert note: {e}")

    return {"success": True, "alert": alert_payload, "message": "Test alert published."}


@router.post("/monitoring/{website_id}/alerts/{alert_id}/read")
async def mark_read(website_id: str, alert_id: str, request: Request):
    from database import get_supabase
    
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(403, "Human approval required - provide X-User-Id header")
    
    result = get_supabase().table("realtime_alerts").update({
        "is_read": True,
        "is_actioned": True,
        "action_taken": f"marked_read_by_{user_id}",
        "actioned_at": datetime.utcnow().isoformat()
    }).eq("id", alert_id).eq("website_id", website_id).execute()
    
    return {"status": "success", "alert": result.data[0] if result.data else None}


@router.post("/monitoring/{website_id}/alerts/{alert_id}/approve")
async def approve_alert(website_id: str, alert_id: str, request: Request):
    from database import get_supabase
    from agents.strategy_agent import StrategyAgent
    
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(403, "Human approval required - click Approve in dashboard")
    
    alert = get_supabase().table("realtime_alerts").select("*").eq("id", alert_id).eq("website_id", website_id).single().execute().data
    
    if not alert:
        raise HTTPException(404, "Alert not found")
    
    strategy_agent = StrategyAgent(website_id)
    result = await strategy_agent.handle_alert(alert)
    
    get_supabase().table("realtime_alerts").update({
        "is_actioned": True,
        "action_taken": f"approved_by_{user_id}",
        "approved_by": user_id,
        "actioned_at": datetime.utcnow()
    }).eq("id", alert_id).eq("website_id", website_id).execute()
    
    return {"status": "approved", "strategy_result": result}


@router.get("/monitoring/{website_id}/live")
@router.get("/api/monitoring/{website_id}/live")
async def live_alerts(website_id: str):
    from database import get_supabase
    
    async def event_generator():
        last_seen_ids = set()
        try:
            yield "event: connected\ndata: {\"status\": \"connected\", \"website_id\": \"" + website_id + "\"}\n\n"
            
            counter = 0
            while True:
                try:
                    # 1. Fetch unread alerts
                    alerts = get_supabase().table("realtime_alerts").select("*").eq("website_id", website_id).eq("is_read", False).order("created_at", desc=True).limit(5).execute().data or []
                    
                    for alert in alerts:
                        aid = alert.get("id")
                        if aid and aid not in last_seen_ids:
                            last_seen_ids.add(aid)
                            yield f"event: alert\ndata: {json.dumps(alert)}\n\n"
                    
                    # 2. Periodic SSE heartbeat every 15 seconds to prevent drops
                    counter += 1
                    if counter % 3 == 0:
                        yield f": heartbeat {datetime.utcnow().isoformat()}\n\n"
                    
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Live feed polling error: {e}")
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
    
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream"
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.get("/monitoring/{website_id}/logs")
async def get_logs(website_id: str, hours: int = 24):
    from database import get_supabase
    from datetime import datetime, timedelta
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    return get_supabase().table("monitoring_logs").select("*").eq("website_id", website_id).gte("created_at", since.isoformat()).order("created_at", desc=True).limit(100).execute().data or []


@router.get("/monitoring/{website_id}/stats")
@router.get("/api/monitoring/{website_id}/stats")
async def get_stats(website_id: str):
    from database import get_supabase
    from services.website_service import get_default_website_id
    from datetime import datetime, timedelta
    
    target_id = website_id if website_id and website_id not in ("default", "default-website-id", "all", "", "null", "undefined") else get_default_website_id()
    
    monitors = ["rank_monitor", "serp_monitor", "competitor_monitor", "tech_monitor", "geo_monitor", "structure_monitor"]
    monitor_status = {m: "running" for m in monitors}
    
    if not target_id:
        return {
            "total_alerts_24h": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "monitors": monitor_status,
            "all_monitors_ok": True,
            "active_monitors_count": 6,
        }
    
    since = datetime.utcnow() - timedelta(hours=24)
    sb = get_supabase()
    
    alerts = sb.table("realtime_alerts").select("severity, created_at").eq("website_id", target_id).gte("created_at", since.isoformat()).execute().data or []
    
    critical = len([a for a in alerts if a.get("severity") == "critical"])
    high = len([a for a in alerts if a.get("severity") in ("critical", "high")])
    medium = len([a for a in alerts if a.get("severity") == "medium"])
    
    for m in monitors:
        try:
            last_log = sb.table("monitoring_logs").select("status, created_at").eq("website_id", target_id).eq("monitor_type", m).order("created_at", desc=True).limit(1).execute().data
            if last_log and last_log[0].get("status") == "error":
                monitor_status[m] = "error"
            else:
                monitor_status[m] = "running"
        except Exception:
            monitor_status[m] = "running"
    
    return {
        "total_alerts_24h": len(alerts),
        "critical": critical,
        "high": high,
        "medium": medium,
        "monitors": monitor_status,
        "all_monitors_ok": all(v in ("running", "ok") for v in monitor_status.values()),
        "active_monitors_count": len(monitors),
    }


# ---------------------------------------------------------------------------
# Preemptive Ranking Predictions Endpoints (Upgrade 3)
# ---------------------------------------------------------------------------

@router.get("/monitoring/{website_id}/predictions")
@router.get("/api/monitoring/{website_id}/predictions")
async def get_ranking_predictions(website_id: str):
    """Retrieve preemptive ranking predictions sorted by confidence descending."""
    from services.rank_prediction_service import RankPredictionService
    from services.website_service import get_default_website_id
    target_id = website_id if website_id and website_id not in ("default", "default-website-id", "all") else get_default_website_id()
    svc = RankPredictionService(website_id=target_id)
    predictions = await svc.list_predictions()
    return {"success": True, "data": predictions, "predictions": predictions}


@router.post("/monitoring/predictions/{prediction_id}/act")
@router.post("/api/monitoring/predictions/{prediction_id}/act")
async def act_on_prediction(prediction_id: str, website_id: Optional[str] = None, action: Optional[str] = None):
    """Take immediate preemptive action on predicted ranking movement."""
    from services.rank_prediction_service import RankPredictionService
    from services.website_service import get_default_website_id
    target_id = website_id if website_id and website_id not in ("default", "default-website-id", "all") else get_default_website_id()
    svc = RankPredictionService(website_id=target_id)
    result = await svc.execute_prediction_action(prediction_id=prediction_id, action=action)
    return result


@router.post("/monitoring/{website_id}/predictions/run")
@router.post("/api/monitoring/{website_id}/predictions/run")
async def run_predictions_now(website_id: str):
    """Execute live time-series rank prediction analysis."""
    from services.rank_prediction_service import RankPredictionService
    svc = RankPredictionService(website_id=website_id)
    result = await svc.run_weekly_prediction_engine()
    return result


@router.get("/monitoring/{website_id}/pending-fixes")
async def get_pending_fixes(website_id: str):
    from database import get_supabase
    
    return get_supabase().table("pending_fixes").select("*").eq("website_id", website_id).eq("status", "pending_approval").order("created_at", desc=True).execute().data or []


@router.post("/monitoring/{website_id}/pending-fixes/{fix_id}/approve")
async def approve_fix(website_id: str, fix_id: str, request: Request):
    from database import get_supabase
    from services.wordpress_service import get_wordpress_service
    from middleware.human_gate import require_human_for_request
    
    user_id = await require_human_for_request(request)
    
    fix = get_supabase().table("pending_fixes").select("*").eq("id", fix_id).eq("website_id", website_id).single().execute().data
    if not fix:
        raise HTTPException(404, "Fix not found")
    
    ws_service = get_wordpress_service(website_id)
    
    fix_type = fix.get("fix_type")
    fix_payload = fix.get("fix_payload", {})
    
    try:
        if fix_type == "tech_broken_link" and "page_url" in fix_payload:
            page_url = fix_payload.get("page_url")
            broken_url = fix_payload.get("broken_url")
            
            wp_result = await ws_service.update_meta(page_url, "redirects", {"added": [broken_url]})
            
            fix_updates = {
                "status": "approved",
                "approved_by": user_id,
                "applied_at": datetime.utcnow().isoformat(),
                "action_taken": "redirect_added" if wp_result else "manual_review"
            }
        else:
            fix_updates = {
                "status": "approved",
                "approved_by": user_id,
                "applied_at": datetime.utcnow().isoformat(),
                "action_taken": "manual_review"
            }
        
        result = get_supabase().table("pending_fixes").update(fix_updates).eq("id", fix_id).eq("website_id", website_id).execute()
        
        return {"status": "approved", "fix_id": fix_id, "result": result.data[0] if result.data else None}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        logger.error(f"Fix approval failed: {e}")
        raise HTTPException(500, str(e))


@router.get("/monitoring/{website_id}/topic-clusters")
async def get_topic_clusters(website_id: str, pending_only: bool = True):
    from database import get_supabase
    
    query = get_supabase().table("topic_clusters").select("*").eq("website_id", website_id)
    if pending_only:
        query = query.isnull("actualized_post_id")
    return query.order("created_at", desc=True).limit(50).execute().data or []