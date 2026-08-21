import logging
import json
from datetime import datetime, timedelta

import redis

from .agent_limits import AGENT_LIMITS, should_run_agent
from .crew import plan_blogs_for_website
from .tools.shared_utils import generate_learning_from_rejection
from ..database import get_supabase
from ..agents.knowledge_agent import run_knowledge_agent
from ..agents.tools.shared_utils import is_homepage

logger = logging.getLogger("backend.agents.autonomous_loop")


def get_redis():
    from ..config import REDIS_URL
    return redis.from_url(REDIS_URL)


def hourly_monitor_job() -> None:
    try:
        r = get_redis()
        websites = get_supabase().table("websites").select("id, url, domain").eq("status", "active").execute().data or []
        for site in websites:
            wid = site["id"]
            url = site.get("url") or site.get("cms_url") or f"https://{site.get('domain', '')}"
            if not is_homepage(url):
                continue

            tone_res = get_supabase().table("tone_profiles").select("id").eq("website_id", wid).limit(1).execute()
            if not tone_res.data:
                logger.info("Knowledge missing for %s, running knowledge_agent first", wid)
                try:
                    run_knowledge_agent(wid, url)
                    get_supabase().table("agent_thoughts").insert({
                        "website_id": wid,
                        "agent_name": "manager",
                        "thought": "Knowledge agent ran first because tone_profiles missing",
                        "created_at": datetime.utcnow().isoformat(),
                    }).execute()
                except Exception as e:
                    logger.error("Knowledge agent failed for %s: %s", wid, e)
                continue

            for agent_name in AGENT_LIMITS:
                if agent_name == "llms_txt":
                    continue
                can_run, reason = should_run_agent(agent_name, wid)
                if can_run:
                    task = {"website_id": wid, "agent": agent_name, "reason": reason}
                    r.lpush("agent_queue", json.dumps(task))
                    logger.info("Manager queued %s for website %s: %s", agent_name, wid, reason)
                    try:
                        get_supabase().table("agent_thoughts").insert({
                            "website_id": wid,
                            "agent_name": "manager",
                            "thought": f"Queued {agent_name}: {reason}",
                            "created_at": datetime.utcnow().isoformat(),
                        }).execute()
                    except Exception:
                        pass
                else:
                    logger.debug("Manager skipped %s for %s: %s", agent_name, wid, reason)
    except Exception as e:
        logger.error("hourly_monitor_job failed: %s", e)


def queue_worker_job() -> None:
    try:
        r = get_redis()
        while True:
            task_raw = r.brpop("agent_queue", timeout=5)
            if not task_raw:
                break
            task = json.loads(task_raw[1])
            website_id = task.get("website_id")
            agent = task.get("agent")
            logger.info("Running %s for %s", agent, website_id)
            if agent in ("writer", "auditor", "editor"):
                try:
                    result = plan_blogs_for_website(website_id)
                    get_supabase().table("agent_thoughts").insert({
                        "website_id": website_id,
                        "agent_name": agent,
                        "thought": f"CrewAI kickoff completed: {str(result)[:500]}",
                        "created_at": datetime.utcnow().isoformat(),
                    }).execute()
                except Exception as e:
                    logger.error("CrewAI kickoff failed for %s: %s", website_id, e)
            elif agent == "tech_seo":
                from ..agents.tech_seo_agent import run_tech_seo_agent
                site = get_supabase().table("websites").select("url", "cms_url", "domain").eq("id", website_id).single().execute().data
                if site:
                    base_url = site.get("url") or site.get("cms_url") or f"https://{site.get('domain', '')}"
                    try:
                        run_tech_seo_agent(website_id, base_url)
                    except Exception as e:
                        logger.error("Tech SEO failed for %s: %s", website_id, e)
            elif agent == "backlink":
                from ..agents.backlink_agent import run_backlink_agent
                try:
                    run_backlink_agent(website_id)
                except Exception as e:
                    logger.error("Backlink failed for %s: %s", website_id, e)
    except Exception as e:
        logger.error("queue_worker_job failed: %s", e)


def feedback_learning_job() -> None:
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        feedbacks = (
            get_supabase()
            .table("agent_feedback")
            .select("*")
            .gte("created_at", cutoff)
            .is_("learning", "null")
            .limit(50)
            .execute()
            .data
            or []
        )
        for fb in feedbacks:
            learning = generate_learning_from_rejection(
                fb.get("rejected_type", "unknown"),
                fb.get("rejected_value", ""),
                fb.get("human_feedback", ""),
                fb.get("website_id", ""),
            )
            get_supabase().table("agent_feedback").update({"learning": learning}).eq("id", fb["id"]).execute()
            get_supabase().table("agent_thoughts").insert({
                "website_id": fb.get("website_id", ""),
                "agent_name": "manager",
                "thought": f"Learning from rejection: {learning}",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
    except Exception as e:
        logger.error("feedback_learning_job failed: %s", e)
