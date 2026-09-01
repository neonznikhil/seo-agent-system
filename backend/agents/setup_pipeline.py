import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database import get_supabase, is_nim_available
from knowledge_agent import run_knowledge_agent
from services.knowledge_service import KnowledgeService
from research_agent import ResearchAgent
from writer_agent import WriterPipeline
from tech_seo_agent import TechSEOAgent
from backlink_agent import BacklinkAgent
from services.slack_intelligence_service import slack_intelligence_service

logger = logging.getLogger("backend.agents.setup_pipeline")


async def run_first_time_setup_pipeline(website_id: str, homepage_url: str) -> Dict[str, Any]:
    """Execute end-to-end first-time bootstrap sequence for a newly connected website.

    Cadence:
    1. Knowledge crawl (KnowledgeService + sitemap) -> knowledge_base
    2. SERP research (ResearchAgent) -> keyword_opportunities + serp_landscape
    3. First article generation (WriterPipeline) -> content_log + blog_approvals (status: pending)
    4. Technical SEO audit (TechSEOAgent) -> technical_audits
    5. Backlink prospecting (BacklinkAgent / OpportunityScout) -> backlink_opportunities
    6. Slack announcement to #rankforge-daily
    """
    logger.info(f"[SetupPipeline] Starting first-time onboarding for website {website_id} ({homepage_url})...")
    results = {
        "website_id": website_id,
        "url": homepage_url,
        "started_at": datetime.utcnow().isoformat(),
        "steps": {},
    }

    # Step 1: Knowledge crawl
    try:
        logger.info(f"[SetupPipeline] Phase 1/5: Crawling business website...")
        ks = KnowledgeService(website_id=website_id)
        crawl_res = await ks.watch_business_website()
        results["steps"]["knowledge"] = {
            "status": "completed",
            "pages_ingested": (crawl_res or {}).get("new_pages_ingested", 0),
        }
    except Exception as e:
        logger.warning(f"[SetupPipeline] Knowledge crawl had non-fatal error: {e}")
        results["steps"]["knowledge"] = {"status": "partial", "error": str(e)[:200]}

    # Step 2: SERP & Keyword Research
    top_keyword = "primary service guide"
    try:
        logger.info(f"[SetupPipeline] Phase 2/5: Researching search landscape & keyword opportunities...")
        ra = ResearchAgent(website_id=website_id)
        research_res = await ra.run(topic="core business services and search intent")
        keywords = (research_res or {}).get("keywords", []) if isinstance(research_res, dict) else []
        if keywords and isinstance(keywords[0], (str, dict)):
            top_keyword = keywords[0] if isinstance(keywords[0], str) else keywords[0].get("keyword", top_keyword)
        results["steps"]["research"] = {
            "status": "completed",
            "keywords_found": len(keywords),
            "top_keyword": top_keyword,
        }
    except Exception as e:
        logger.warning(f"[SetupPipeline] Research step had error: {e}")
        results["steps"]["research"] = {"status": "partial", "error": str(e)[:200]}

    # Step 3: Writer Pipeline - First Article Draft
    article_title = ""
    try:
        nim_ok = await is_nim_available()
        if nim_ok:
            logger.info(f"[SetupPipeline] Phase 3/5: Generating first autonomous article for '{top_keyword}'...")
            wp = WriterPipeline(
                website_id=website_id,
                topic=f"Complete Guide to {top_keyword.title()}",
                primary_keyword=top_keyword,
            )
            draft_res = await wp.generate()
            article_title = draft_res.get("title", "")
            results["steps"]["writer"] = {
                "status": "completed",
                "title": article_title,
                "word_count": draft_res.get("word_count", 0),
                "seo_score": draft_res.get("seo_score"),
            }
        else:
            results["steps"]["writer"] = {"status": "skipped", "reason": "NVIDIA NIM unavailable"}
    except Exception as e:
        logger.warning(f"[SetupPipeline] First article generation error: {e}")
        results["steps"]["writer"] = {"status": "failed", "error": str(e)[:200]}

    # Step 4: Technical SEO Audit
    health_score = None
    try:
        logger.info(f"[SetupPipeline] Phase 4/5: Running baseline technical SEO audit...")
        tech_agent = TechSEOAgent(website_id=website_id)
        audit_res = await tech_agent.run_audit(website_id)
        health_score = (audit_res or {}).get("health_score")
        results["steps"]["tech_seo"] = {
            "status": "completed",
            "health_score": health_score,
        }
    except Exception as e:
        logger.warning(f"[SetupPipeline] Tech audit error: {e}")
        results["steps"]["tech_seo"] = {"status": "partial", "error": str(e)[:200]}

    # Step 5: Backlink Prospecting
    opps_count = 0
    try:
        logger.info(f"[SetupPipeline] Phase 5/5: Discovering initial backlink opportunities...")
        ba = BacklinkAgent(website_id=website_id)
        backlink_res = await ba.run_prospecting_loop(keyword=top_keyword)
        opps_count = (backlink_res or {}).get("opportunities_found", 0) if isinstance(backlink_res, dict) else 0
        results["steps"]["backlinks"] = {
            "status": "completed",
            "opportunities_found": opps_count,
        }
    except Exception as e:
        logger.warning(f"[SetupPipeline] Backlink prospecting error: {e}")
        results["steps"]["backlinks"] = {"status": "partial", "error": str(e)[:200]}

    # Step 6: Slack Announcement
    try:
        domain = homepage_url.replace("https://", "").replace("http://", "").split("/")[0]
        welcome_summary = (
            f"🚀 *RankForge setup complete for {domain}!*\n"
            f"• 📚 Knowledge Base ingested & indexed\n"
            f"• 📝 First article '{article_title or top_keyword}' is ready for review on the /approvals page\n"
            f"• 🩺 Baseline SEO Health Score: *{health_score or 'Calculated'}/100*\n"
            f"• 🔗 Discovered *{opps_count}* high-intent backlink opportunities\n\n"
            "From now on, all autonomous daily jobs will run automatically according to schedule."
        )
        await slack_intelligence_service.send_crisis_alert(
            website_id=website_id,
            title=f"Setup Complete — {domain}",
            details=welcome_summary,
            severity="info",
        )
    except Exception as e:
        logger.debug(f"[SetupPipeline] Slack welcome message skipped: {e}")

    results["completed_at"] = datetime.utcnow().isoformat()
    logger.info(f"[SetupPipeline] First-time setup pipeline finished for {website_id} ✅")
    return results


def run_first_time_setup_bg(website_id: str, homepage_url: str) -> None:
    """Non-blocking background helper for FastAPI background_tasks."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(run_first_time_setup_pipeline(website_id, homepage_url))
        else:
            loop.run_until_complete(run_first_time_setup_pipeline(website_id, homepage_url))
    except Exception:
        asyncio.run(run_first_time_setup_pipeline(website_id, homepage_url))
