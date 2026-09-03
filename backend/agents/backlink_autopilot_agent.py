import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import get_supabase
from services.internal_link_service import build_internal_link_graph
from services.backlink_prospect_service import find_backlink_prospects, monitor_backlinks
from services.reporting_service import report_problem

logger = logging.getLogger("backend.agents.backlink_autopilot")


async def _run_one_backlink_cycle() -> None:
    """Single backlink cycle — called by APScheduler (single authority)."""
    try:
        supabase = get_supabase()
        websites = (
            supabase.table("websites")
            .select("id")
            .execute()
            .data
            or []
        )
        for website in websites:
            website_id = website["id"]

            try:
                await build_internal_link_graph(website_id)
                job = {
                    "website_id": website_id,
                    "job_type": "daily_backlink_check",
                    "status": "completed",
                    "result": {"task": "internal_graph"},
                    "run_at": datetime.utcnow().isoformat(),
                }
                supabase.table("brain_daily_jobs").insert(job).execute()
            except Exception as exc:
                logger.error("Internal graph job failed for %s: %s", website_id, exc)
                try:
                    supabase.table("brain_daily_jobs").insert(
                        {
                            "website_id": website_id,
                            "job_type": "daily_backlink_check",
                            "status": "failed",
                            "error": str(exc)[:500],
                            "run_at": datetime.utcnow().isoformat(),
                        }
                    ).execute()
                except Exception:
                    pass

            try:
                from services.gsc_miner_service import GSCMinerService
                from services.gsc_service import GSCService

                miner = GSCMinerService(website_id)
                gsc_data = await miner.mine_and_cluster(max_clusters=5, row_limit=2000)
                keywords: List[str] = []
                if not gsc_data.get("error"):
                    articles = (
                        supabase.table("cluster_articles")
                        .select("keyword,current_position")
                        .eq("website_id", website_id)
                        .gte("current_position", 11)
                        .lte("current_position", 20)
                        .limit(5)
                        .execute()
                        .data
                        or []
                    )
                    for art in articles:
                        kw = art.get("keyword")
                        if kw:
                            keywords.append(kw)

                if not keywords:
                    website_row = (
                        supabase.table("websites")
                        .select("domain,gsc_property")
                        .eq("id", website_id)
                        .single()
                        .execute()
                        .data
                        or {}
                    )
                    gsc_url = website_row.get("gsc_property") or f"https://{website_row.get('domain', '')}"
                    gsc = GSCService(website_url=gsc_url)
                    if gsc.is_connected():
                        perf = await gsc.get_keyword_performance(row_limit=2000)
                        for kw in perf.get("keywords", []):
                            pos = kw.get("position") or 0
                            if 11 <= pos <= 20:
                                keywords.append(kw.get("keyword", ""))
                                if len(keywords) >= 5:
                                    break

                prospects_found = 0
                for kw in keywords[:5]:
                    try:
                        await find_backlink_prospects(website_id, kw)
                        prospects_found += 1
                    except Exception as exc:
                        logger.error("Prospect job failed for kw %s: %s", kw, exc)

                job = {
                    "website_id": website_id,
                    "job_type": "daily_backlink_check",
                    "status": "completed" if prospects_found else "failed",
                    "result": {
                        "task": "prospects",
                        "keywords_processed": len(keywords[:5]),
                        "prospects_found": prospects_found,
                    },
                    "run_at": datetime.utcnow().isoformat(),
                }
                supabase.table("brain_daily_jobs").insert(job).execute()
            except Exception as exc:
                logger.error("Prospect job failed for %s: %s", website_id, exc)

            try:
                await monitor_backlinks(website_id)
                job = {
                    "website_id": website_id,
                    "job_type": "daily_backlink_check",
                    "status": "completed",
                    "result": {"task": "monitor"},
                    "run_at": datetime.utcnow().isoformat(),
                }
                supabase.table("brain_daily_jobs").insert(job).execute()
            except Exception as exc:
                logger.error("Monitor job failed for %s: %s", website_id, exc)

    except Exception as exc:
        logger.error("Backlink autopilot cycle error: %s", exc)
        try:
            await report_problem(
                website_id="global",
                alert_type="system_error",
                severity="high",
                title="Backlink autopilot cycle error",
                description=str(exc)[:500],
                source_monitor="backlink_autopilot_agent",
            )
        except Exception:
            pass


async def run_backlink_daily_jobs() -> None:
    """Deprecated infinite loop — retained for backwards compat but scheduler is single authority.

    If called directly (e.g. from old lifespan), runs a single cycle then sleeps 60s
    before yielding to scheduler. New code should call _run_one_backlink_cycle via scheduler.
    """
    logger.warning("[BacklinkAutopilot] run_backlink_daily_jobs called — delegating to single-cycle scheduler authority")
    await asyncio.sleep(60)
    await _run_one_backlink_cycle()
    # No infinite loop; scheduler owns scheduling
    logger.info("[BacklinkAutopilot] Single cycle complete — scheduler will invoke next run")
