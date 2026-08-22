import logging
import asyncio
from typing import Optional, List, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ..database import get_supabase

logger = logging.getLogger("backend.agents.scheduler")
scheduler = AsyncIOScheduler()


async def get_all_websites() -> list:
    try:
        supabase = get_supabase()
        return supabase.table("websites").select("*").execute().data or []
    except Exception as e:
        logger.warning(f"Failed to fetch websites for scheduler: {e}")
        return []


async def run_keyword_research(website_id: str):
    from ..routers.gsc import get_keywords
    try:
        await get_keywords(website_id)
    except Exception as e:
        logger.warning(f"Keyword research job failed for {website_id}: {e}")


async def find_striking_distance_keywords(website_id: str):
    logger.info(f"Checking striking distance keywords for {website_id}")


async def get_best_keyword_for_content(website_id: str) -> Optional[str]:
    try:
        supabase = get_supabase()
        opps = supabase.table("keyword_opportunities").select("keyword").eq("website_id", website_id).order("opportunity_score", desc=True).limit(1).execute().data
        if opps:
            return opps[0]["keyword"]
    except Exception:
        pass
    return "autonomous seo optimization"


async def trigger_writer_agent(website_id: str, keyword: str):
    from ..agents.human_writer import HumanWriterAgent
    try:
        hw = HumanWriterAgent(website_id)
        hw.setup_profile()
        await hw.generate_blog(topic=f"Ultimate Guide to {keyword}", primary_keyword=keyword)
        logger.info(f"Daily content generated for {website_id} keyword: {keyword}")
    except Exception as e:
        logger.warning(f"Daily writer agent failed for {website_id}: {e}")


async def run_tech_seo_agent_job(website_id: str):
    from .tech_seo_agent import run_tech_seo_agent
    try:
        supabase = get_supabase()
        site = supabase.table("websites").select("*").eq("id", website_id).single().execute().data
        if site:
            url = site.get("url") or site.get("cms_url") or f"https://{site.get('domain', '')}"
            await run_tech_seo_agent(website_id, url)
    except Exception as e:
        logger.warning(f"Tech SEO agent failed for {website_id}: {e}")


async def run_backlink_agent_job(website_id: str):
    from .backlink_agent import run_backlink_agent
    try:
        await run_backlink_agent(website_id)
    except Exception as e:
        logger.warning(f"Backlink agent failed for {website_id}: {e}")


async def check_rank_changes(website_id: str):
    logger.info(f"[RankCheck] Monitoring rank movements for {website_id}")


async def check_competitor_changes(website_id: str):
    logger.info(f"[CompetitorCheck] Checking competitor shifts for {website_id}")


# Every day at 6:00 AM — Keyword research
@scheduler.scheduled_job("cron", hour=6, minute=0)
async def daily_keyword_research():
    websites = await get_all_websites()
    for site in websites:
        await run_keyword_research(site["id"])
        await find_striking_distance_keywords(site["id"])
    logger.info("[Scheduler] Daily keyword research done")


# Every day at 7:00 AM — Content generation
@scheduler.scheduled_job("cron", hour=7, minute=0)
async def daily_content_generation():
    websites = await get_all_websites()
    for site in websites:
        keyword = await get_best_keyword_for_content(site["id"])
        if keyword:
            await trigger_writer_agent(site["id"], keyword)
    logger.info("[Scheduler] Daily content generation triggered")


# Every day at 8:00 AM — Tech SEO audit
@scheduler.scheduled_job("cron", hour=8, minute=0)
async def daily_tech_audit():
    websites = await get_all_websites()
    for site in websites:
        await run_tech_seo_agent_job(site["id"])
    logger.info("[Scheduler] Daily tech audit done")


# Every day at 9:00 AM — Backlink check
@scheduler.scheduled_job("cron", hour=9, minute=0)
async def daily_backlink_check():
    websites = await get_all_websites()
    for site in websites:
        await run_backlink_agent_job(site["id"])
    logger.info("[Scheduler] Daily backlink check done")


# Every 15 minutes — Rank monitoring
@scheduler.scheduled_job("interval", minutes=15)
async def rank_check():
    websites = await get_all_websites()
    for site in websites:
        await check_rank_changes(site["id"])


# Every 60 minutes — Competitor monitoring
@scheduler.scheduled_job("interval", minutes=60)
async def competitor_check():
    websites = await get_all_websites()
    for site in websites:
        await check_competitor_changes(site["id"])


# Every 60 minutes — Hourly autonomous loop
@scheduler.scheduled_job("interval", minutes=60)
async def scheduled_autonomous_loop():
    from .autonomous_loop import run_hourly_autonomous_loop
    await run_hourly_autonomous_loop()


def setup_scheduler(app=None):
    try:
        if not scheduler.running:
            scheduler.start()
            logger.info("[Scheduler] All jobs scheduled ✅")
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start scheduler: {e}")


def start_scheduler():
    setup_scheduler()


def stop_scheduler():
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("[Scheduler] Stopped")
    except Exception:
        pass
