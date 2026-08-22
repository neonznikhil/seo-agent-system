import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from ..database import get_supabase

router = APIRouter()

@router.get("/calendar/{website_id}")
async def get_calendar(website_id: str):
    try:
        supabase = get_supabase()
        
        # Get content calendar entries
        try:
            calendar_result = supabase.table("content_calendar")\
                .select("*")\
                .eq("website_id", website_id)\
                .order("scheduled_date")\
                .execute()
            calendar_items = calendar_result.data or []
        except Exception:
            calendar_items = []
        
        # Get pending content from content_log
        try:
            pending_result = supabase.table("content_log")\
                .select("id, title, status, keywords, created_at")\
                .eq("website_id", website_id)\
                .order("created_at", desc=True)\
                .limit(20)\
                .execute()
            pending_content = pending_result.data or []
        except Exception:
            pending_content = []
        
        # Build calendar view
        today = datetime.now()
        calendar_view = []
        days_view = []
        
        for i in range(30):
            date = today + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            day_items = [
                item for item in calendar_items
                if item.get('scheduled_date') == date_str
            ]
            day_blogs = [
                item for item in pending_content
                if (item.get('created_at') or '')[:10] == date_str
            ]
            
            day_obj = {
                "date": date_str,
                "day": date.strftime('%A'),
                "items": day_items,
                "blogs": day_blogs or day_items
            }
            calendar_view.append(day_obj)
            days_view.append(day_obj)
        
        return {
            "calendar": calendar_view,
            "days": days_view,
            "pending_content": pending_content,
            "total_scheduled": len(calendar_items),
            "total_pending": len(pending_content)
        }
    except Exception as e:
        return {
            "calendar": [],
            "days": [],
            "pending_content": [],
            "total_scheduled": 0,
            "total_pending": 0,
            "error": str(e)
        }

@router.post("/calendar/{website_id}/schedule")
async def schedule_content(website_id: str, data: dict):
    try:
        supabase = get_supabase()
        
        entry = {
            "website_id": website_id,
            "title": data.get("title", ""),
            "keywords": data.get("keywords", []),
            "scheduled_date": data.get("scheduled_date"),
            "status": "planned",
            "priority": data.get("priority", 5),
            "created_at": datetime.now().isoformat()
        }
        
        result = supabase.table("content_calendar")\
            .insert(entry).execute()
        
        return {"success": True, "item": result.data[0] if result.data else entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))