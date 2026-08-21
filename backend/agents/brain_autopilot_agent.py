import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger("backend.agents.brain_autopilot")


async def _run_job(website_id: str, job_type: str, job_func) -> Dict[str, Any]:
    """Run a single job with error isolation."""
    from ..database import get_supabase
    from ..services.reporting_service import report_problem

    supabase = get_supabase()
    try:
        supabase.table("brain_daily_jobs").insert(
            {
                "website_id": website_id,
                "job_type": job_type,
                "status": "running",
                "run_at": datetime.utcnow().isoformat(),
            }
        ).execute()
    except Exception:
        pass

    try:
        result = await job_func(website_id)
        try:
            supabase.table("brain_daily_jobs").insert(
                {
                    "website_id": website_id,
                    "job_type": job_type,
                    "status": "completed",
                    "result": str(result),
                    "run_at": datetime.utcnow().isoformat(),
                }
            ).execute()
        except Exception:
            pass
        return result
    except Exception as e:
        logger.error(f"[BrainAutopilot] {job_type} failed for {website_id}: {e}")
        try:
            supabase.table("brain_daily_jobs").insert(
                {
                    "website_id": website_id,
                    "job_type": job_type,
                    "status": "failed",
                    "error": str(e),
                    "run_at": datetime.utcnow().isoformat(),
                }
            ).execute()
        except Exception:
            pass
        try:
            await report_problem(
                website_id=website_id,
                alert_type="monitor_error",
                severity="high",
                title=f"Brain autopilot failed: {job_type}",
                description=str(e),
                data={"website_id": website_id, "job_type": job_type},
                source_monitor="brain_autopilot",
            )
        except Exception:
            pass
        return {"error": str(e)}


async def _run_all_jobs():
    """Run all 6 daily jobs for every registered website."""
    from ..database import get_supabase

    try:
        websites = (
            get_supabase().table("websites").select("id").execute().data or []
        )
    except Exception as e:
        logger.error(f"[BrainAutopilot] Failed to fetch websites: {e}")
        return

    for website in websites:
        website_id = website["id"]
        try:
            await _run_job(website_id, "daily_search", _daily_search_job)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"[BrainAutopilot] daily_search error for {website_id}: {e}")

        try:
            await _run_job(website_id, "daily_cluster_build", _daily_cluster_build_job)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"[BrainAutopilot] daily_cluster_build error for {website_id}: {e}")

        try:
            await _run_job(website_id, "daily_geo_check", _daily_geo_check_job)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"[BrainAutopilot] daily_geo_check error for {website_id}: {e}")

        try:
            await _run_job(website_id, "daily_refresh_check", _daily_refresh_check_job)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"[BrainAutopilot] daily_refresh_check error for {website_id}: {e}")

        try:
            await _run_job(
                website_id, "daily_new_page_suggestion", _daily_new_page_suggestion_job
            )
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(
                f"[BrainAutopilot] daily_new_page_suggestion error for {website_id}: {e}"
            )

        try:
            await _run_job(website_id, "daily_backlink_check", _daily_backlink_check_job)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"[BrainAutopilot] daily_backlink_check error for {website_id}: {e}")


async def _daily_search_job(website_id: str) -> Dict[str, Any]:
    from .daily_search_service import daily_search_job
    return await daily_search_job(website_id)


async def _daily_cluster_build_job(website_id: str) -> Dict[str, Any]:
    from .daily_search_service import daily_cluster_build_job
    return await daily_cluster_build_job(website_id)


async def _daily_geo_check_job(website_id: str) -> Dict[str, Any]:
    from .daily_search_service import daily_geo_check_job
    return await daily_geo_check_job(website_id)


async def _daily_refresh_check_job(website_id: str) -> Dict[str, Any]:
    from .daily_search_service import daily_refresh_check_job
    return await daily_refresh_check_job(website_id)


async def _daily_new_page_suggestion_job(website_id: str) -> Dict[str, Any]:
    from .daily_search_service import daily_new_page_suggestion_job
    return await daily_new_page_suggestion_job(website_id)


async def _daily_backlink_check_job(website_id: str) -> Dict[str, Any]:
    from .daily_search_service import daily_backlink_check_job
    return await daily_backlink_check_job(website_id)


async def run_daily_autopilot():
    """Runs forever loop. Runs immediately on boot, then at scheduled UTC times each day."""
    logger.info("[BrainAutopilot] Starting daily autopilot...")
    await _run_all_jobs()

    last_run_dates: Dict[str, str] = {}
    scheduled_jobs = [
        ("daily_search", 6),
        ("daily_cluster_build", 7),
        ("daily_geo_check", 8),
        ("daily_refresh_check", 9),
        ("daily_new_page_suggestion", 10),
        ("daily_backlink_check", 11),
    ]

    while True:
        try:
            now = datetime.utcnow()
            date_str = now.date().isoformat()

            for job_type, hour in scheduled_jobs:
                if last_run_dates.get(job_type) != date_str and now.hour == hour:
                    last_run_dates[job_type] = date_str
                    from ..database import get_supabase

                    websites = (
                        get_supabase().table("websites").select("id").execute().data or []
                    )
                    for website in websites:
                        website_id = website["id"]
                        job_func = {
                            "daily_search": _daily_search_job,
                            "daily_cluster_build": _daily_cluster_build_job,
                            "daily_geo_check": _daily_geo_check_job,
                            "daily_refresh_check": _daily_refresh_check_job,
                            "daily_new_page_suggestion": _daily_new_page_suggestion_job,
                            "daily_backlink_check": _daily_backlink_check_job,
                        }.get(job_type)
                        if job_func:
                            asyncio.create_task(_run_job(website_id, job_type, job_func))

            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[BrainAutopilot] Loop error: {e}")
            await asyncio.sleep(60)
