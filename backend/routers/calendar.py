import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.calendar")
router = APIRouter()


class BlogItem(BaseModel):
    id: str
    title: str
    status: str
    agent_name: Optional[str] = None


class DayData(BaseModel):
    date: str  # YYYY-MM-DD format
    blogs: List[BlogItem]


class CalendarResponse(BaseModel):
    days: List[DayData]


@router.get("/calendar/{website_id}")
async def get_content_calendar(
    website_id: str,
    days: int = Query(7, ge=1, le=30)
):
    """
    Get content calendar for the last N days showing blogs scheduled/published each day.
    Returns array of days with blog items for each day.
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days-1)
        
        # Get blogs from content_log within date range
        blogs_res = (
            get_supabase()
            .table("content_log")
            .select("id, title, status, agent_name, created_at")
            .eq("website_id", website_id)
            .gte("created_at", start_date.isoformat())
            .lt("created_at", (end_date + timedelta(days=1)).isoformat())
            .order("created_at", desc=True)
            .execute()
        )
        blogs = blogs_res.data or []
        
        # Group blogs by date
        days_map = {}
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            days_map[date_str] = []
            current_date += timedelta(days=1)
        
        for blog in blogs:
            # Extract date part from created_at
            blog_date_str = blog["created_at"][:10]  # YYYY-MM-DD
            if blog_date_str in days_map:
                days_map[blog_date_str].append(BlogItem(
                    id=blog["id"],
                    title=blog["title"],
                    status=blog["status"],
                    agent_name=blog.get("agent_name")
                ))
        
        # Convert to list format sorted by date
        days_list = []
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            days_list.append(DayData(
                date=date_str,
                blogs=days_map.get(date_str, [])
            ))
            current_date += timedelta(days=1)
        
        return CalendarResponse(days=days_list)
        
    except Exception as e:
        logger.error(f"Error getting calendar for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))