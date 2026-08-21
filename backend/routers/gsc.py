import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query

from ..database import get_supabase
from ..agents.tools.gsc_tools import fetch_active_keywords

logger = logging.getLogger("backend.routers.gsc")
router = APIRouter()


@router.get("/gsc/keywords/{website_id}")
async def get_keywords(website_id: str):
    keywords = fetch_active_keywords(website_id)
    return {"website_id": website_id, "keywords": keywords}


@router.get("/gsc/roi/{website_id}")
async def get_roi(website_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    keywords = fetch_active_keywords(website_id)
    total_clicks = sum(k.get("clicks", 0) for k in keywords)
    total_impressions = sum(k.get("impressions", 0) for k in keywords)
    return {
        "website_id": website_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "keywords": keywords,
    }
