import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_supabase

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
    total_impressions = 0
    impressions_change_pct = 0.0
    blogs_published_last_30d = 0
    technical_health_score = 90
    backlinks_total = 0
    backlinks_new_7d = 0

    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
    supabase = get_supabase()

    # 1. GSC impressions
    try:
        gsc_res = (
            supabase.table("gsc_data")
            .select("clicks, impressions")
            .eq("website_id", website_id)
            .gte("date", thirty_days_ago)
            .execute()
        )
        gsc_data = gsc_res.data or []
        if gsc_data:
            total_impressions = sum(item.get("impressions", 0) for item in gsc_data)
            sixty_days_ago = (datetime.utcnow() - timedelta(days=60)).isoformat()
            try:
                prev_gsc_res = (
                    supabase.table("gsc_data")
                    .select("impressions")
                    .eq("website_id", website_id)
                    .gte("date", sixty_days_ago)
                    .lt("date", thirty_days_ago)
                    .execute()
                )
                prev_gsc_data = prev_gsc_res.data or []
                prev_impressions = sum(item.get("impressions", 0) for item in prev_gsc_data)
                if prev_impressions > 0:
                    impressions_change_pct = ((total_impressions - prev_impressions) / prev_impressions) * 100
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[ROI] gsc_data query note: {e}")

    # 2. Published blogs
    try:
        blogs_res = (
            supabase.table("content_log")
            .select("id")
            .eq("website_id", website_id)
            .eq("status", "published")
            .gte("created_at", thirty_days_ago)
            .execute()
        )
        blogs_published_last_30d = len(blogs_res.data or [])
    except Exception as e:
        logger.debug(f"[ROI] content_log query note: {e}")

    # 3. Technical health score
    try:
        tech_res = (
            supabase.table("technical_audits")
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
    except Exception as e:
        logger.debug(f"[ROI] technical_audits query note: {e}")

    # 4. Backlinks
    try:
        backlinks_total_res = (
            supabase.table("backlinks")
            .select("id", count="exact")
            .eq("website_id", website_id)
            .execute()
        )
        backlinks_total = backlinks_total_res.count or 0
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        backlinks_new_res = (
            supabase.table("backlinks")
            .select("id", count="exact")
            .eq("website_id", website_id)
            .gte("discovered_at", seven_days_ago)
            .execute()
        )
        backlinks_new_7d = backlinks_new_res.count or 0
    except Exception as e:
        # Fallback to brain_memory backlink items
        try:
            mem_res = (
                supabase.table("brain_memory")
                .select("id", count="exact")
                .eq("website_id", website_id)
                .ilike("memory_type", "%backlink%")
                .execute()
            )
            backlinks_total = mem_res.count or 0
        except Exception:
            pass

    return ROIMetrics(
        impressions_last_30d=total_impressions,
        blogs_published_last_30d=blogs_published_last_30d,
        technical_health_score=technical_health_score,
        backlinks_total=backlinks_total,
        backlinks_new_7d=backlinks_new_7d,
        impressions_change_pct=impressions_change_pct
    )