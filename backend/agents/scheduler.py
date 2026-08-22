from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging
import json
from datetime import datetime, date

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


async def get_all_active_website_ids() -> list:
    try:
        from ..database import get_supabase
        supabase = get_supabase()
        result = supabase.table("websites")\
            .select("id, url")\
            .execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Could not get websites: {e}")
        return []


async def auto_run_tech_audit(website_id: str):
    try:
        logger.info(f"[AutoAudit] Running for {website_id}")
        from .tech_seo_agent import TechSEOAgent
        agent = TechSEOAgent()
        result = await agent.run_audit(website_id)
        logger.info(f"[AutoAudit] Done for {website_id}: score={result.get('health_score')}")
    except Exception as e:
        logger.error(f"[AutoAudit] Failed for {website_id}: {e}")


async def auto_run_content_generation(website_id: str):
    try:
        from ..database import get_supabase, call_nim_llm
        supabase = get_supabase()
        
        # Check if already generated content today
        today = date.today().isoformat()
        existing = supabase.table("content_log")\
            .select("id")\
            .eq("website_id", website_id)\
            .gte("created_at", today)\
            .execute()
        
        if existing.data and len(existing.data) >= 2:
            logger.info(f"[AutoContent] Already generated {len(existing.data)} pieces today for {website_id}")
            return
        
        # Get website info for keyword suggestion
        website = supabase.table("websites")\
            .select("*").eq("id", website_id).single().execute()
        
        if not website.data:
            return
        
        site_url = website.data.get('url', '')
        niche = website.data.get('niche', '')
        
        # Get best keyword opportunity
        kw_result = supabase.table("keyword_opportunities")\
            .select("*")\
            .eq("website_id", website_id)\
            .eq("status", "new")\
            .order("opportunity_score", desc=True)\
            .limit(1)\
            .execute()
        
        if kw_result.data:
            keyword = kw_result.data[0]['keyword']
            title = f"Complete Guide to {keyword} in 2026"
        else:
            # Use NIM to suggest a topic
            prompt = f"""
            Website: {site_url}
            Niche: {niche or 'general'}
            
            Suggest ONE blog post title that would rank well for this website.
            Return ONLY the title, nothing else.
            """
            title = await call_nim_llm(prompt)
            title = title.strip().strip('"')
            keyword = title
        
        if not title or len(title) < 5:
            return
        
        # Generate the blog
        logger.info(f"[AutoContent] Generating: {title}")
        from .writer_agent import WriterAgent
        writer = WriterAgent()
        await writer.generate_blog_post(
            website_id=website_id,
            title=title,
            keywords=[keyword]
        )
        logger.info(f"[AutoContent] Done: {title}")
        
    except Exception as e:
        logger.error(f"[AutoContent] Failed for {website_id}: {e}")


async def run_daily_jobs():
    logger.info("[Scheduler] Running daily jobs...")
    websites = await get_all_active_website_ids()
    for site in websites:
        website_id = site['id']
        await auto_run_tech_audit(website_id)
        await auto_run_content_generation(website_id)
    logger.info(f"[Scheduler] Daily jobs done for {len(websites)} websites")


async def run_hourly_jobs():
    logger.info("[Scheduler] Running hourly monitoring...")
    websites = await get_all_active_website_ids()
    for site in websites:
        try:
            from ..services.continuous_monitor import run_all_monitors
            await run_all_monitors(site['id'])
        except Exception as e:
            logger.error(f"[Scheduler] Monitor failed for {site['id']}: {e}")


def setup_scheduler(app=None):
    # Daily at 6 AM UTC — content generation + tech audit
    scheduler.add_job(
        run_daily_jobs,
        CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="daily_jobs",
        replace_existing=True,
        name="Daily: content + audit"
    )
    
    # Every 60 minutes — monitoring
    scheduler.add_job(
        run_hourly_jobs,
        IntervalTrigger(minutes=60),
        id="hourly_monitoring",
        replace_existing=True,
        name="Hourly monitoring"
    )
    
    logger.info("[Scheduler] Jobs scheduled:")
    logger.info("  - Daily 6AM UTC: tech audit + content generation")
    logger.info("  - Every 60min: monitoring loops")
    
    return scheduler


def start_scheduler():
    setup_scheduler()
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    try:
        if scheduler.running:
            scheduler.shutdown()
    except Exception:
        pass

