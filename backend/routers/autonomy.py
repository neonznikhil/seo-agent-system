"""Autonomy dashboard API - stats proving the system works without humans."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter

from ..database import get_supabase
from ..routers.settings import AUTOMATION_KEYS, _read_global_setting

logger = logging.getLogger("backend.routers.autonomy")
router = APIRouter(prefix="/api/autonomy", tags=["autonomy"])


def _count(table: str, website_id: str = None) -> int:
    try:
        q = get_supabase().table(table).select("id", count="exact")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.execute()
        return getattr(res, "count", None) or len(res.data or [])
    except Exception as e:
        logger.warning(f"count({table}) failed: {e}")
        return 0


@router.get("")
async def autonomy_overview(website_id: Optional[str] = None):
    supabase = get_supabase()
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    kb_docs = _count("knowledge_base", website_id)
    memories = _count("brain_memory", website_id)

    # Last daily job runs by type (freshness proof)
    job_status = {}
    try:
        jobs = (
            supabase.table("brain_daily_jobs")
            .select("job_type,status,result,error,run_at")
            .order("run_at", desc=True)
            .limit(60)
            .execute()
            .data
            or []
        )
        seen = set()
        for j in jobs:
            jt = j.get("job_type") or ""
            if jt and jt not in seen:
                seen.add(jt)
                job_status[jt] = {
                    "status": j.get("status"),
                    "run_at": j.get("run_at"),
                    "result": j.get("result"),
                    "error": j.get("error"),
                }
    except Exception as e:
        logger.warning(f"job status fetch failed: {e}")

    published_week = 0
    refreshed_week = 0
    try:
        rows = (
            supabase.table("content_log")
            .select("status,pipeline_status,id")
            .eq("website_id", website_id)
            .gte("created_at", week_ago)
            .execute()
            .data
            or []
        )
        published_week = sum(1 for r in rows if r.get("status") == "published")
    except Exception:
        pass
    try:
        ref_rows = (
            supabase.table("brain_memory")
            .select("id,title,created_at")
            .eq("website_id", website_id)
            .eq("memory_type", "success")
            .like("title", "Refreshed content%")
            .gte("created_at", (datetime.utcnow() - timedelta(days=2)).isoformat())
            .execute()
            .data
            or []
        )
        refreshed_week = len(ref_rows)
    except Exception:
        pass

    automation = {}
    for key, (default, _desc) in AUTOMATION_KEYS.items():
        stored = _read_global_setting(key)
        automation[key] = stored or default
        if stored is None:
            from ..routers.settings import _write_global_setting

            try:
                _write_global_setting(key, default)
                automation[key] = default
            except Exception:
                pass

    return {
        "knowledge_base_docs": kb_docs,
        "brain_memories": memories,
        "published_this_week": published_week,
        "refreshed_recently": refreshed_week,
        "jobs": job_status,
        "automation": automation,
    }


@router.get("/logs")
async def autonomy_logs(website_id: Optional[str] = None, limit: int = 20):
    try:
        q = (
            get_supabase()
            .table("brain_daily_jobs")
            .select("*")
            .order("run_at", desc=True)
            .limit(max(1, min(limit, 100)))
        )
        if website_id:
            q = q.eq("website_id", website_id)
        return q.execute().data or []
    except Exception as e:
        logger.error(f"logs fetch failed: {e}")
        return []
