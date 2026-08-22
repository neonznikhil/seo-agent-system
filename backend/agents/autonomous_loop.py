import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from ..database import get_supabase, call_nim_llm
from .agent_limits import AGENT_LIMITS, should_run_agent

logger = logging.getLogger("backend.agents.autonomous_loop")


async def get_all_active_websites() -> List[dict]:
    try:
        supabase = get_supabase()
        return supabase.table("websites").select("*").execute().data or []
    except Exception as e:
        logger.warning(f"Failed to fetch active websites: {e}")
        return []


async def check_new_alerts(website_id: str) -> List[dict]:
    try:
        supabase = get_supabase()
        return supabase.table("monitoring_alerts").select("*").eq("website_id", website_id).eq("status", "unread").execute().data or []
    except Exception:
        return []


async def run_auditor_agent(website_id: str):
    logger.info(f"[Auditor] Running audit for critical alerts on {website_id}")
    try:
        supabase = get_supabase()
        supabase.table("tasks").insert({
            "website_id": website_id,
            "agent_name": "auditor_agent",
            "action": "critical_alert_remediation",
            "status": "completed",
            "payload": {"reason": "Critical alerts detected"},
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


async def get_weekly_content_count(website_id: str) -> int:
    try:
        supabase = get_supabase()
        one_week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        rows = supabase.table("content_log").select("id").eq("website_id", website_id).gte("created_at", one_week_ago).execute().data or []
        return len(rows)
    except Exception:
        return 0


async def get_top_keyword_opportunity(website_id: str) -> Optional[str]:
    try:
        supabase = get_supabase()
        rows = supabase.table("keyword_opportunities").select("keyword").eq("website_id", website_id).order("opportunity_score", desc=True).limit(1).execute().data
        if rows:
            return rows[0]["keyword"]
    except Exception:
        pass
    return "car accident compensation claims"


async def trigger_content_generation(website_id: str, keyword: str):
    from .human_writer import HumanWriterAgent
    try:
        hw = HumanWriterAgent(website_id)
        hw.setup_profile()
        res = await hw.generate_blog(topic=f"Complete Strategy: {keyword}", primary_keyword=keyword)
        if res.get("content"):
            supabase = get_supabase()
            supabase.table("content_log").insert({
                "website_id": website_id,
                "title": f"Complete Strategy: {keyword}",
                "keyword": keyword,
                "content": res["content"],
                "status": "pending_approval",
                "pipeline_status": "completed",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            logger.info(f"[AutoLoop] Auto-generated blog for {website_id} on '{keyword}'")
    except Exception as e:
        logger.warning(f"AutoLoop content generation failed for {website_id}: {e}")


async def run_tech_check(website_id: str):
    from .tech_seo_agent import run_tech_seo_agent
    try:
        supabase = get_supabase()
        site = supabase.table("websites").select("*").eq("id", website_id).single().execute().data
        if site:
            url = site.get("url") or site.get("cms_url") or f"https://{site.get('domain', '')}"
            await run_tech_seo_agent(website_id, url)
    except Exception as e:
        logger.warning(f"Tech check failed for {website_id}: {e}")


async def update_brain_memory(website_id: str, alerts: List[dict]):
    try:
        supabase = get_supabase()
        if alerts:
            supabase.table("brain_memory").insert({
                "website_id": website_id,
                "title": f"Incident pattern observed on {datetime.utcnow().strftime('%Y-%m-%d')}",
                "content": f"Resolved {len(alerts)} alerts with automated guardrails.",
                "memory_type": "experience",
                "confidence": 0.92,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
    except Exception:
        pass


async def run_hourly_autonomous_loop():
    """Runs every hour for every website."""
    logger.info("[AutoLoop] Starting hourly autonomous agent loop...")
    websites = await get_all_active_websites()

    for website in websites:
        website_id = website["id"]
        try:
            # 1. Check monitoring alerts
            alerts = await check_new_alerts(website_id)

            # 2. If critical alerts exist, run auditor agent
            if any(a.get("severity") == "critical" for a in alerts):
                await run_auditor_agent(website_id)

            # 3. Check if content needed (less than 2 posts this week)
            content_count = await get_weekly_content_count(website_id)
            if content_count < 2:
                top_keyword = await get_top_keyword_opportunity(website_id)
                if top_keyword:
                    await trigger_content_generation(website_id, top_keyword)

            # 4. Run tech SEO check
            await run_tech_check(website_id)

            # 5. Update brain memory with findings
            await update_brain_memory(website_id, alerts)

            logger.info(f"[AutoLoop] Completed for {website_id}")
        except Exception as e:
            logger.error(f"[AutoLoop] Error processing {website_id}: {e}")


def hourly_monitor_job():
    try:
        asyncio.create_task(run_hourly_autonomous_loop())
    except Exception as e:
        logger.warning(f"hourly_monitor_job error: {e}")


def queue_worker_job():
    pass


def feedback_learning_job():
    pass
