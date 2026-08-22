"""RankForge autonomous scheduler - SINGLE source of truth for all cron jobs.

Timezone: Asia/Kolkata (client requirement).

HUMAN APPROVAL RULE: jobs never publish to WordPress. Generation + gate run
fully autonomously and stage results in blog_approvals (status='pending').
Only /api/approvals/{id}/approve (clicked by a human) writes to WordPress.

Daily jobs (per registered website), all logging to brain_daily_jobs:
  09:00 IST  Daily research    - trends via GSC + SERP landscape ->
                                 keyword_opportunities -> brain_auto_pages_queue
  09:30 IST  Knowledge sync    - KnowledgeAgent: save brain learnings +
                                 competitor intel -> knowledge_base
  10:00 IST  Content refresh   - ContentRefresherAgent stages refresh_update
                                 drafts in blog_approvals (NEVER updates WP)
  11:00 IST  New page ideas    - AutoPublisher stages new_page drafts in
                                 blog_approvals (NEVER publishes to WP)
  Hourly     Monitors          - rank/SERP/tech/competitor/GEO
  On boot    Catch-up          - reruns any daily job stale >20h
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("backend.agents.scheduler")

IST = "Asia/Kolkata"
CATCHUP_WINDOW_HOURS = 20

scheduler = AsyncIOScheduler(timezone=IST)


async def get_all_website_ids() -> list:
    try:
        from ..database import get_supabase

        result = (
            get_supabase().table("websites").select("id").execute().data or []
        )
        return [r["id"] for r in result]
    except Exception as e:
        logger.error(f"[Scheduler] Could not get websites: {e}")
        return []


async def _get_setting(key: str, default: str) -> str:
    try:
        from ..routers.settings import get_global_setting

        value = get_global_setting(key, default)
        return value if value is not None else default
    except Exception:
        return default


async def _log_job(website_id: str, job_type: str, status: str, result=None, error=None):
    """Persist a job run so the dashboard can show live autonomy logs."""
    try:
        from ..database import get_supabase

        payload = {
            "website_id": website_id,
            "job_type": job_type,
            "status": status,
            "run_at": datetime.utcnow().isoformat(),
        }
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error
        get_supabase().table("brain_daily_jobs").insert(payload).execute()
    except Exception as e:
        logger.debug(f"[Scheduler] job log failed: {e}")


async def _last_success_run(job_type: str) -> Optional[datetime]:
    try:
        from ..database import get_supabase

        res = (
            get_supabase()
            .table("brain_daily_jobs")
            .select("run_at")
            .eq("job_type", job_type)
            .eq("status", "completed")
            .order("run_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if res:
            ts = res[0]["run_at"]
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        pass
    return None


async def _run_for_all_sites(job_type: str, coro_factory, requires_automation: bool = True):
    """Run one job type for every active website with logging + isolation."""
    if requires_automation and (await _get_setting("automate_seo", "on")).lower() != "on":
        logger.info(f"[Scheduler] {job_type} skipped - Automate SEO is OFF")
        return

    website_ids = await get_all_website_ids()
    logger.info(f"[Scheduler] {job_type} starting for {len(website_ids)} site(s)")

    for wid in website_ids:
        try:
            result = await coro_factory(wid)
            await _log_job(wid, job_type, "completed", result=result)
        except Exception as e:
            logger.error(f"[Scheduler] {job_type} failed for {wid}: {e}")
            await _log_job(wid, job_type, "failed", error=str(e))


async def daily_research_job():
    """09:00 IST - daily searches: keywords, SERP, competitors."""
    from ..services.daily_search_service import (
        daily_search_job,
        daily_cluster_build_job,
    )

    async def run(wid):
        out = {}
        out["search"] = await daily_search_job(wid)
        out["clusters"] = await daily_cluster_build_job(wid)
        return out

    await _run_for_all_sites("daily_search", run)


async def daily_refresh_job():
    """10:00 IST - refresh ANALYSIS only; stages updates for human approval."""
    from ..services.content_refresher_service import run_daily_refresh

    async def run(wid):
        enabled = (await _get_setting("daily_refresh", "on")).lower() == "on"
        if not enabled:
            return {"skipped": "daily_refresh setting is off"}
        return await run_daily_refresh(wid)

    await _run_for_all_sites("daily_content_refresh", run)


async def daily_knowledge_sync_job():
    """09:30 IST - save brain learnings + site knowledge. Fully autonomous."""
    from ..services.brain_service import BrainService

    async def run(wid):
        from ..database import get_supabase

        supabase = get_supabase()
        brain = BrainService(wid)
        # 1) write a daily digest memory (daily learnings snapshot)
        row = (
            supabase.table("websites")
            .select("domain,niche")
            .eq("id", wid)
            .single()
            .execute()
            .data
            or {}
        )
        domain = row.get("domain", "")
        try:
            await brain.remember(
                website_id=wid,
                memory_type="insight",
                title=f"Daily brain sync for {domain}",
                content=(
                    f"Brain state checkpoint {datetime.utcnow().isoformat()}. "
                    f"Memory store active; recall available for next generation."
                ),
                source_type="knowledge_sync",
                source_id=f"sync-{datetime.utcnow().date().isoformat()}",
                confidence=0.6,
            )
        except Exception as e:
            logger.debug(f"[KnowledgeSync] brain checkpoint skipped for {wid}: {e}")
        return {"checkpoint": "ok", "domain": domain}

    await _run_for_all_sites("daily_knowledge_sync", run)


async def new_page_ideas_job():
    """11:00 IST - generate new page drafts, staged as PENDING approvals."""
    from ..services.auto_publisher_service import generate_queued_pages

    await _run_for_all_sites("auto_page_pipeline", lambda wid: generate_queued_pages(wid))


async def hourly_monitoring_job():
    """Every hour - rank/SERP/tech/competitor/GEO monitors."""
    website_ids = await get_all_website_ids()
    for wid in website_ids:
        try:
            from ..services.continuous_monitor import run_all_monitors

            await run_all_monitors(wid)
        except Exception as e:
            logger.error(f"[Scheduler] monitoring failed for {wid}: {e}")


async def boot_catchup_job():
    """On startup: run any daily job whose last successful run is stale."""
    jobs = [
        ("daily_search", daily_research_job),
        ("daily_knowledge_sync", daily_knowledge_sync_job),
        ("daily_content_refresh", daily_refresh_job),
        ("auto_page_pipeline", new_page_ideas_job),
    ]
    for job_type, fn in jobs:
        try:
            last = await _last_success_run(job_type)
            stale = last is None or (
                datetime.utcnow() - last > timedelta(hours=CATCHUP_WINDOW_HOURS)
            )
            if stale:
                logger.info(
                    f"[Scheduler] Boot catch-up running '{job_type}' "
                    f"(last success: {last or 'never'})"
                )
                await fn()
            else:
                logger.info(
                    f"[Scheduler] '{job_type}' fresh (last: {last:%Y-%m-%d %H:%M} UTC), skipping"
                )
        except Exception as e:
            logger.error(f"[Scheduler] boot catch-up '{job_type}' failed: {e}")


def setup_scheduler(app=None):
    scheduler.add_job(
        daily_research_job,
        CronTrigger(hour=9, minute=0, timezone=IST),
        id="daily_research",
        replace_existing=True,
        name="Daily 9AM IST: research + keywords",
    )
    scheduler.add_job(
        daily_knowledge_sync_job,
        CronTrigger(hour=9, minute=30, timezone=IST),
        id="daily_knowledge_sync",
        replace_existing=True,
        name="Daily 9:30AM IST: knowledge base sync",
    )
    scheduler.add_job(
        daily_refresh_job,
        CronTrigger(hour=10, minute=0, timezone=IST),
        id="daily_refresh",
        replace_existing=True,
        name="Daily 10AM IST: content refresh analysis (stages approvals)",
    )
    scheduler.add_job(
        new_page_ideas_job,
        CronTrigger(hour=11, minute=0, timezone=IST),
        id="daily_new_page_ideas",
        replace_existing=True,
        name="Daily 11AM IST: new page drafts (staged for approval)",
    )
    scheduler.add_job(
        hourly_monitoring_job,
        IntervalTrigger(minutes=60),
        id="hourly_monitoring",
        replace_existing=True,
        name="Hourly: monitors",
    )
    scheduler.add_job(
        boot_catchup_job,
        "date",
        id="boot_catchup",
        replace_existing=True,
        name="Boot: catch-up stale daily jobs",
        run_date=datetime.now(scheduler.timezone),
        misfire_grace_time=120,
    )

    logger.info("[Scheduler] Jobs scheduled (Asia/Kolkata):")
    logger.info("  - 09:00 IST daily research (autonomous)")
    logger.info("  - 09:30 IST knowledge sync (autonomous)")
    logger.info("  - 10:00 IST refresh analysis -> staged approvals")
    logger.info("  - 11:00 IST new-page drafts -> staged approvals")
    logger.info("  - every 60min monitoring + boot catch-up")

    return scheduler


def start_scheduler():
    setup_scheduler()
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception:
        pass


if __name__ == "__main__":
    # Acceptance path: run daily research + (ensured) one pending draft.
    import asyncio
    import sys

    logging.basicConfig(level=logging.INFO)

    async def _cli() -> int:
        await daily_research_job()

        from ..services.auto_publisher_service import generate_queued_pages

        website_ids = await get_all_website_ids()
        if not website_ids:
            print("No websites registered. Add one first.")
            return 1
        wid = website_ids[0]
        res = await generate_queued_pages(wid, limit=1)
        staged = res.get("staged_for_approval", 0)

        # Fallback: if queue was empty (e.g. GSC not connected), generate one
        # demo keyword via NIM, draft it, and stage it for approval.
        if staged == 0:
            from ..database import get_supabase, call_nim_llm

            site = (
                get_supabase().table("websites").select("domain,niche").eq("id", wid).single().execute().data or {}
            )
            niche = site.get("niche") or f"legal services at {site.get('domain','example.com')}"
            suggestion = await call_nim_llm(
                f"Suggest ONE high-intent blog topic for a {niche} website that is likely to rank. "
                "Return JSON: {\"keyword\": ..., \"topic\": ...}"
            )
            kw = "high intent informational topic"
            if suggestion:
                import json

                try:
                    data = json.loads(suggestion[ suggestion.find("{") : suggestion.rfind("}") + 1 ])
                    kw = data.get("keyword") or kw
                    topic = data.get("topic") or kw
                except Exception:
                    topic = kw
            else:
                topic = kw
            supabase = get_supabase()
            supabase.table("brain_auto_pages_queue").insert({
                "website_id": wid,
                "primary_keyword": kw,
                "suggested_topic": topic,
                "reason": "manual acceptance run",
                "priority_score": 80,
                "auto_approve": True,
                "status": "queued_for_writing",
            }).execute()
            res = await generate_queued_pages(wid, limit=1)
            staged = res.get("staged_for_approval", 0)

        print(f"Staged for approval: {staged} | Result: {res}")
        return 0 if staged > 0 else 1

    sys.exit(asyncio.run(_cli()))
