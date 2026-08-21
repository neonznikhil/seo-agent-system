import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, WebSocket, Request, HTTPException
from fastapi.responses import StreamingResponse
import uuid

logger = logging.getLogger("backend.services.reporting_service")

router = APIRouter()
active_connections: Dict[str, List[WebSocket]] = {}


async def report_problem(
    website_id: str,
    alert_type: str,
    severity: str,
    title: str,
    description: str = "",
    data: Dict[str, Any] = None,
    source_monitor: str = "unknown"
) -> Dict[str, Any]:
    """
    ALWAYS report user - nothing is silent.
    Creates realtime_alerts row and pushes to all channels.
    """
    from ..database import get_supabase
    from .slack_service import send_slack_alert
    from .email_service import send_email_alert
    from .sse_service import push_sse_alert
    
    try:
        alert = {
            "id": str(uuid.uuid4()),
            "website_id": website_id,
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "description": description,
            "data": json.dumps(data or {}),
            "source_monitor": source_monitor,
            "is_read": False,
            "is_actioned": False,
            "requires_human_approval": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = get_supabase().table("realtime_alerts").insert(alert).execute()
        if result.data:
            alert = result.data[0]
        
        web_data = json.dumps({
            "type": "alert",
            "data": alert,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        asyncio.create_task(push_sse_alert(website_id, web_data))
        
        try:
            website = get_supabase().table("websites").select("slack_webhook_url, alert_email").eq("id", website_id).single().execute().data
            if website:
                if website.get("slack_webhook_url"):
                    asyncio.create_task(send_slack_alert(website["slack_webhook_url"], alert))
                if website.get("alert_email") and severity in ("critical", "high"):
                    asyncio.create_task(send_email_alert(website["alert_email"], alert))
        except Exception as e:
            logger.warning(f"Integration alert failed: {e}")
        
        return alert
        
    except Exception as e:
        logger.error(f"report_problem failed: {e}")
        return {"error": str(e), "status": "failed"}


async def log_monitoring(
    website_id: str,
    monitor_type: str,
    status: str,
    checked_urls: int,
    issues_found: int,
    execution_ms: int,
    error_message: str = None
) -> None:
    """Log monitor execution for metrics."""
    from ..database import get_supabase
    
    try:
        get_supabase().table("monitoring_logs").insert({
            "website_id": website_id,
            "monitor_type": monitor_type,
            "status": status,
            "checked_urls": checked_urls,
            "issues_found": issues_found,
            "execution_ms": execution_ms,
            "error_message": error_message,
            "created_at": datetime.utcnow()
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log monitoring: {e}")


async def generate_strategy_from_alert(alert: Dict[str, Any], website_id: str) -> Dict[str, Any]:
    """Auto-generate strategy and content based on alert."""
    from ..database import get_supabase
    from ..agents.tools.keyword_tools import KeywordTools
    
    try:
        if alert["alert_type"] in ("rank_drop", "rank_opportunity", "keyword_opportunity"):
            kw = alert["data"].get("keyword", "")
            if not kw:
                return {"status": "no_keyword"}
            
            keyword_tools = KeywordTools()
            keyword_tools.set_website_id(website_id)
            
            from ..agent import NIM_LLM
            llm = NIM_LLM()
            
            prompt = f"""You are SEO strategist. Generate topic clusters for keyword "{kw}" based on knowledge_base and gsc_keywords. Return JSON with pillar_topic, pillar_keyword, clusters (list of title/keyword/word_count)."""
            
            result = llm.call(prompt)
            
            try:
                clusters = json.loads(result)
            except:
                clusters = {"pillar_topic": kw, "clusters": []}
            
            cluster_id = str(uuid.uuid4())
            get_supabase().table("topic_clusters").insert({
                "website_id": website_id,
                "pillar_topic": kw,
                "pillar_keyword": kw,
                "clusters": clusters,
                "created_from_alert_id": alert["id"],
                "created_at": datetime.utcnow()
            }).execute()
            
            return {
                "status": "strategy_generated",
                "cluster_id": cluster_id,
                "clusters": clusters.get("clusters", [])
            }
    except Exception as e:
        logger.error(f"Strategy generation failed: {e}")
    
    return {"status": "strategy_failed"}


@router.get("/api/monitoring/{website_id}/alerts")
async def get_alerts(website_id: str, filter: str = "unread"):
    """Get alerts for website."""
    from ..database import get_supabase
    
    query = get_supabase().table("realtime_alerts").select("*").eq("website_id", website_id)
    
    if filter == "unread":
        query = query.eq("is_read", False)
    elif filter == "critical":
        query = query.eq("severity", "critical")
    elif filter == "high":
        query = query.in_("severity", ["critical", "high"])
    
    return query.order("created_at", desc=True).limit(100).execute().data or []


@router.post("/api/monitoring/{website_id}/alerts/{alert_id}/read")
async def mark_read(website_id: str, alert_id: str, request: Request):
    """Mark alert as read - requires human."""
    from ..database import get_supabase
    
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(403, "Human approval required - provide X-User-Id header")
    
    result = get_supabase().table("realtime_alerts").update({
        "is_read": True,
        "is_actioned": True,
        "action_taken": f"marked_read_by_{user_id}"
    }).eq("id", alert_id).eq("website_id", website_id).execute()
    
    return result.data[0] if result.data else {"status": "not_found"}


@router.get("/api/monitoring/{website_id}/live")
async def live_alerts(website_id: str):
    """SSE stream of new alerts."""
    from ..database import get_supabase
    
    async def event_generator():
        yield "event: connected\n\n"
        while True:
            try:
                alerts = get_supabase().table("realtime_alerts").select("*").eq("website_id", website_id).eq("is_read", False).order("created_at", desc=True).limit(1).execute().data
                if alerts:
                    for alert in alerts:
                        yield f"event: alert\n"
                        yield f"data: {json.dumps(alert)}\n\n"
                await asyncio.sleep(5)
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(30)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/monitoring/{website_id}/logs")
async def get_logs(website_id: str):
    """Get recent monitoring logs."""
    from ..database import get_supabase
    
    return get_supabase().table("monitoring_logs").select("*").eq("website_id", website_id).order("created_at", desc=True).limit(100).execute().data or []


@router.get("/api/monitoring/{website_id}/stats")
async def get_stats(website_id: str):
    """Get monitoring stats."""
    from ..database import get_supabase
    from datetime import datetime, timedelta
    
    since = datetime.utcnow() - timedelta(hours=24)
    
    alerts = get_supabase().table("realtime_alerts").select("severity, created_at").eq("website_id", website_id).gte("created_at", since.isoformat()).execute().data or []
    
    critical = len([a for a in alerts if a.get("severity") == "critical"])
    high = len([a for a in alerts if a.get("severity") == "high"])
    medium = len([a for a in alerts if a.get("severity") == "medium"])
    
    monitors = ["rank_monitor", "serp_monitor", "competitor_monitor", "tech_monitor", "structure_monitor"]
    monitor_status = {}
    for m in monitors:
        last_log = get_supabase().table("monitoring_logs").select("status, created_at").eq("website_id", website_id).eq("monitor_type", m).order("created_at", desc=True).limit(1).execute().data
        if last_log:
            age = (datetime.utcnow() - datetime.fromisoformat(last_log[0]["created_at"])).total_seconds()
            monitor_status[m] = "ok" if age < 3600 else "stale"
        else:
            monitor_status[m] = "never_run"
    
    return {
        "total_alerts_24h": len(alerts),
        "critical": critical,
        "high": high,
        "medium": medium,
        "monitors": monitor_status,
        "all_monitors_ok": all(v == "ok" for v in monitor_status.values())
    }