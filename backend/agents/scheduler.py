import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .agent_limits import AGENT_LIMITS, should_run_agent
from .crew import plan_blogs_for_website
from .autonomous_loop import hourly_monitor_job, queue_worker_job, feedback_learning_job
from ..database import get_supabase
from .tools.shared_utils import is_homepage

logger = logging.getLogger("backend.agents.scheduler")


scheduler = AsyncIOScheduler()


def _redis_lock(lock_key: str, ttl: int = 3600) -> bool:
    from ..config import REDIS_URL
    import redis
    r = redis.from_url(REDIS_URL)
    result = r.set(lock_key, "1", nx=True, ex=ttl)
    r.close()
    return result


@scheduler.scheduled_job("cron", hour=2, minute=0)
async def daily_coordinated_job() -> None:
    lock_key = "scheduler:daily_job"
    if not _redis_lock(lock_key):
        logger.info("Daily job already running, skipping")
        return
    try:
        websites = get_supabase().table("websites").select("id, url").eq("status", "active").execute().data or []
        for site in websites:
            wid = site["id"]
            url = site["url"]
            if not is_homepage(url):
                continue
            for agent_name in AGENT_LIMITS:
                can_run, reason = should_run_agent(agent_name, wid)
                if can_run:
                    try:
                        if agent_name in ("writer", "auditor", "editor"):
                            plan_blogs_for_website(wid)
                        elif agent_name == "tech_seo":
                            from .tech_seo_agent import run_tech_seo_agent
                            await run_tech_seo_agent(wid, url)
                        elif agent_name == "backlink":
                            from .backlink_agent import run_backlink_agent
                            await run_backlink_agent(wid)
                    except Exception as e:
                        logger.error("Agent %s failed for %s: %s", agent_name, wid, e)
    except Exception as e:
        logger.error("daily_coordinated_job failed: %s", e)
    finally:
        from ..config import REDIS_URL
        import redis
        r = redis.from_url(REDIS_URL)
        r.delete(lock_key)
        r.close()


@scheduler.scheduled_job("interval", hours=1)
async def hourly_queue_job() -> None:
    hourly_monitor_job()


@scheduler.scheduled_job("interval", minutes=10)
async def feedback_job() -> None:
    feedback_learning_job()


def start_scheduler() -> None:
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    scheduler.shutdown()
    logger.info("Scheduler stopped")
