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
    try:
        supabase = get_supabase()
        
        # 1. Fetch content calendar
        calendar_items = []
        try:
            res_c = supabase.table("content_calendar").select("*").eq("website_id", website_id).execute()
            calendar_items = res_c.data or []
        except Exception:
            pass

        # 2. Fetch blog approvals (pending_approval, published)
        approval_items = []
        try:
            res_a = supabase.table("blog_approvals").select("id, title, status, keyword, created_at, approved_at").execute()
            approval_items = res_a.data or []
        except Exception:
            pass

        # 3. Fetch content log (draft, in_progress, published)
        content_items = []
        try:
            res_cl = supabase.table("content_log").select("id, title, status, keyword, created_at, scheduled_date").eq("website_id", website_id).limit(40).execute()
            content_items = res_cl.data or []
        except Exception:
            pass

        # 4. Fetch decaying content
        decay_items = []
        try:
            res_d = supabase.table("content_decay_logs").select("id, original_url, decay_percent, detected_at, status").eq("website_id", website_id).execute()
            decay_items = res_d.data or []
        except Exception:
            pass

        # Unified items mapping
        unified_items = []
        
        for c in calendar_items:
            unified_items.append({
                "id": c.get("id"),
                "source_table": "content_calendar",
                "title": c.get("title") or "Scheduled Article",
                "status": c.get("status") or "draft",
                "date": (c.get("scheduled_date") or c.get("created_at") or "")[:10],
                "keyword": c.get("keywords", ["SEO"])[0] if isinstance(c.get("keywords"), list) and c.get("keywords") else "SEO"
            })

        for a in approval_items:
            status_val = "published" if a.get("status") == "published" else "pending_approval"
            d_str = (a.get("approved_at") or a.get("created_at") or "")[:10]
            unified_items.append({
                "id": a.get("id"),
                "source_table": "blog_approvals",
                "title": a.get("title") or "Blog Post",
                "status": status_val,
                "date": d_str or datetime.utcnow().strftime("%Y-%m-%d"),
                "keyword": a.get("keyword") or "Editorial"
            })

        for cl in content_items:
            status_val = "published" if cl.get("status") == "published" else ("draft" if cl.get("status") in ("in_progress", "draft") else "pending_approval")
            d_str = (cl.get("scheduled_date") or cl.get("created_at") or "")[:10]
            unified_items.append({
                "id": cl.get("id"),
                "source_table": "content_log",
                "title": cl.get("title") or "Draft Article",
                "status": status_val,
                "date": d_str or datetime.utcnow().strftime("%Y-%m-%d"),
                "keyword": cl.get("keyword") or "Content"
            })

        for d in decay_items:
            unified_items.append({
                "id": d.get("id"),
                "source_table": "content_decay_logs",
                "title": f"Refresh: {d.get('original_url', '').split('/')[-1] or 'Decaying Post'}",
                "status": "decaying" if d.get("status") != "refreshing" else "refreshing",
                "date": (d.get("detected_at") or "")[:10] or datetime.utcnow().strftime("%Y-%m-%d"),
                "keyword": "Content Decay"
            })

        # Build 30-day view
        today = datetime.utcnow()
        calendar_view = []
        for i in range(-5, 25):
            day_date = today + timedelta(days=i)
            day_str = day_date.strftime("%Y-%m-%d")
            day_posts = [item for item in unified_items if item.get("date") == day_str]
            calendar_view.append({
                "date": day_str,
                "day": day_date.strftime("%A"),
                "is_today": i == 0,
                "items": day_posts,
                "count": len(day_posts)
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
                    "refreshing": sum(1 for x in unified_items if x["status"] == "refreshing"),
                    "decaying": sum(1 for x in unified_items if x["status"] == "decaying"),
                }
            }
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
            "title": data.get("title", "Planned Post"),
            "keywords": data.get("keywords", ["SEO Strategy"]),
            "scheduled_date": data.get("scheduled_date") or (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "status": "draft",
            "priority": data.get("priority", 5),
            "created_at": datetime.utcnow().isoformat()
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