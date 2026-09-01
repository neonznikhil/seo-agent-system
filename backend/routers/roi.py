import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_supabase

logger = logging.getLogger("backend.routers.roi")
router = APIRouter()


class ROIMetrics(BaseModel):
    impressions_last_30d: int
    blogs_published_last_30d: int
    technical_health_score: int
    backlinks_total: int
    backlinks_new_7d: int
    impressions_change_pct: float


@router.get("/roi/{website_id}")
async def get_roi_metrics(website_id: str):
    """
    Get ROI metrics for a website including impressions, blog count, technical health, and backlinks.
    """
    try:
        # Get impressions from GSC (last 30 days) - returns 0 if no data available
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        gsc_res = (
            get_supabase()
            .table("gsc_data")
            .select("clicks, impressions")
            .eq("website_id", website_id)
            .gte("date", thirty_days_ago)
            .execute()
        )
        gsc_data = gsc_res.data or []
        
        if gsc_data:
            total_impressions = sum(item["impressions"] for item in gsc_data)
            sixty_days_ago = (datetime.utcnow() - timedelta(days=60)).isoformat()
            prev_gsc_res = (
                get_supabase()
                .table("gsc_data")
                .select("impressions")
                .eq("website_id", website_id)
                .gte("date", sixty_days_ago)
                .lt("date", thirty_days_ago)
                .execute()
            )
            prev_gsc_data = prev_gsc_res.data or []
            prev_impressions = sum(item["impressions"] for item in prev_gsc_data)
            
            if prev_impressions > 0:
                impressions_change_pct = ((total_impressions - prev_impressions) / prev_impressions) * 100
            else:
                impressions_change_pct = 0.0
        else:
            total_impressions = 0
            impressions_change_pct = 0.0
        
        # Get blogs published in last 30 days
        blogs_res = (
            get_supabase()
            .table("content_log")
            .select("id")
            .eq("website_id", website_id)
            .eq("status", "published")
            .gte("created_at", thirty_days_ago)
            .execute()
        )
        blogs_published_last_30d = len(blogs_res.data or [])
        
        # Get technical health score from latest technical audit
        tech_res = (
            get_supabase()
            .table("technical_audits")
            .select("issues_count")
            .eq("website_id", website_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        tech_data = tech_res.data
        if tech_data and len(tech_data) > 0:
            open_issues = tech_data[0].get("issues_count", 0)
            technical_health_score = max(0, 100 - (open_issues * 5))
        else:
            technical_health_score = 0
        
        # Get total backlinks
        backlinks_total_res = (
            get_supabase()
            .table("backlinks")
            .select("id", count="exact")
            .eq("website_id", website_id)
            .execute()
        )
        backlinks_total = backlinks_total_res.count or 0
        
        # Get new backlinks in last 7 days
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        backlinks_new_res = (
            get_supabase()
            .table("backlinks")
            .select("id", count="exact")
            .eq("website_id", website_id)
            .gte("discovered_at", seven_days_ago)
            .execute()
        )
        backlinks_new_7d = backlinks_new_res.count or 0
        
        return ROIMetrics(
            impressions_last_30d=total_impressions,
            blogs_published_last_30d=blogs_published_last_30d,
            technical_health_score=technical_health_score,
            backlinks_total=backlinks_total,
            backlinks_new_7d=backlinks_new_7d,
            impressions_change_pct=impressions_change_pct
        )
        
    except Exception as e:
        logger.error(f"Error getting ROI metrics for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))