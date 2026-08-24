import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.calendar")
router = APIRouter()


class RescheduleRequest(BaseModel):
    item_id: str
    target_table: Optional[str] = "content_calendar"
    new_date: str


@router.get("/calendar/{website_id}")
@router.get("/api/calendar/{website_id}")
async def get_calendar(website_id: str):
    """Auto-populating calendar built from real data sources.

    Sources:
    1. content_log rows -> dated by created_at (or their explicit scheduled_date)
    2. blog_approvals rows -> target publish date defaults to created_at + 48h
    3. content_calendar rows -> explicit scheduling entries
    4. APScheduler next-run times -> shown as 'Scheduled Agent Run' events
    The calendar is never empty if the website has any content history.
    """
    try:
        supabase = get_supabase()

        unified_items: List[Dict[str, Any]] = []

        # 1. Content calendar entries
        calendar_items = []
        try:
            res_c = (
                supabase.table("content_calendar").select("*").eq("website_id", website_id).execute()
            )
            calendar_items = res_c.data or []
        except Exception:
            pass

        for c in calendar_items:
            keywords = c.get("keywords") or []
            unified_items.append({
                "id": c.get("id"),
                "source_table": "content_calendar",
                "title": c.get("title") or "Scheduled Article",
                "status": c.get("status") or "draft",
                "date": (c.get("scheduled_date") or c.get("created_at") or "")[:10],
                "keyword": keywords[0] if isinstance(keywords, list) and keywords else None,
                "type": "content",
                "draggable": True,
            })

        # 2. Blog approvals scoped to this website; publish date = created_at + 48h
        approval_items = []
        try:
            res_a = (
                supabase.table("blog_approvals")
                .select("id, title, status, keyword, created_at, approved_at")
                .eq("website_id", website_id)
                .order("created_at", desc=True)
                .limit(60)
                .execute()
            )
            approval_items = res_a.data or []
        except Exception as e:
            logger.debug(f"[Calendar] approvals query failed: {e}")

        for a in approval_items:
            created = a.get("created_at")
            status_val = "published" if a.get("status") == "published" else "pending_approval"
            # Target publish date: approved date, else created_at + 48h review window
            base_dt = None
            if created:
                try:
                    base_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    base_dt = None
            if status_val != "published" and base_dt:
                target = base_dt + timedelta(hours=48)
            else:
                target = base_dt or datetime.utcnow()
            unified_items.append({
                "id": a.get("id"),
                "source_table": "blog_approvals",
                "title": a.get("title") or "Blog Post",
                "status": status_val,
                "date": target.strftime("%Y-%m-%d"),
                "keyword": a.get("keyword") or "Editorial",
                "type": "content",
                "draggable": True,
            })

        # 3. Content log rows
        content_items = []
        try:
            res_cl = (
                supabase.table("content_log")
                .select("id, title, status, keyword, created_at, scheduled_date")
                .eq("website_id", website_id)
                .limit(60)
                .execute()
            )
            content_items = res_cl.data or []
        except Exception:
            pass

        seen_ids = {i["id"] for i in unified_items}
        for cl in content_items:
            if cl.get("id") in seen_ids:
                continue
            status_val = (
                "published" if cl.get("status") == "published"
                else "draft" if cl.get("status") in ("in_progress", "draft", "generating")
                else "pending_approval"
            )
            d_str = (cl.get("scheduled_date") or cl.get("created_at") or "")[:10]
            unified_items.append({
                "id": cl.get("id"),
                "source_table": "content_log",
                "title": cl.get("title") or "Draft Article",
                "status": status_val,
                "date": d_str or datetime.utcnow().strftime("%Y-%m-%d"),
                "keyword": cl.get("keyword") or "Content",
                "type": "content",
                "draggable": False,
            })

        # 4. Scheduled agent runs from APScheduler next-run times
        try:
            from ..agents.scheduler import get_scheduler_status
            sched = get_scheduler_status()
            for job in sched.get("jobs", []):
                nrt = job.get("next_run")
                if not nrt:
                    continue
                run_day = str(nrt)[:10]
                unified_items.append({
                    "id": f"sched_{job['id']}",
                    "source_table": "scheduler",
                    "title": f"Scheduled Agent Run: {job['name']}",
                    "status": "agent_run",
                    "date": run_day,
                    "keyword": None,
                    "type": "agent_run",
                    "draggable": False,
                    "next_run": nrt,
                })
        except Exception as e:
            logger.debug(f"[Calendar] scheduler events unavailable: {e}")

        # Build 30-day view centered on today
        today = datetime.utcnow().date()
        calendar_view = []
        for i in range(-5, 25):
            day_date = today + timedelta(days=i)
            day_str = day_date.isoformat()
            day_posts = [item for item in unified_items if item.get("date") == day_str]
            calendar_view.append({
                "date": day_str,
                "day": day_date.strftime("%A"),
                "is_today": i == 0,
                "items": day_posts,
                "count": len(day_posts),
            })

        return {
            "success": True,
            "data": {
                "calendar": calendar_view,
                "items": unified_items,
                "total_items": len(unified_items),
                "summary": {
                    "draft": sum(1 for x in unified_items if x["status"] == "draft"),
                    "pending_approval": sum(1 for x in unified_items if x["status"] == "pending_approval"),
                    "published": sum(1 for x in unified_items if x["status"] == "published"),
                    "agent_runs": sum(1 for x in unified_items if x["status"] == "agent_run"),
                },
            },
        }
    except Exception as e:
        logger.error(f"Error building calendar: {e}")
        return {"success": False, "error": str(e)}


@router.post("/calendar/{website_id}/schedule")
@router.post("/api/calendar/{website_id}/schedule")
async def schedule_content(website_id: str, data: dict):
    try:
        supabase = get_supabase()
        entry = {
            "website_id": website_id,
            "title": data.get("title") or "Planned Post",
            "keywords": data.get("keywords", []),
            "scheduled_date": data.get("scheduled_date") or (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "status": "draft",
            "priority": data.get("priority", 5),
            "created_at": datetime.utcnow().isoformat(),
        }
        res = supabase.table("content_calendar").insert(entry).execute()
        return {"success": True, "data": res.data[0] if res.data else entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calendar/{website_id}/reschedule")
@router.post("/api/calendar/{website_id}/reschedule")
async def reschedule_content(website_id: str, body: RescheduleRequest):
    """Update scheduled date on drag and drop."""
    supabase = get_supabase()
    try:
        if body.target_table == "content_log":
            supabase.table("content_log").update({"scheduled_date": body.new_date}).eq("id", body.item_id).execute()
        else:
            supabase.table("content_calendar").update({"scheduled_date": body.new_date}).eq("id", body.item_id).execute()
        return {"success": True, "item_id": body.item_id, "new_date": body.new_date}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
