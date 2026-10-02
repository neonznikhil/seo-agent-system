import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database import get_supabase, is_nim_available
from services.knowledge_service import KnowledgeService
from services.slack_intelligence_service import slack_intelligence_service
try:
    from agents.knowledge_agent import run_knowledge_agent
    from agents.research_agent import ResearchAgent
    from agents.writer_agent import WriterPipeline
    from agents.tech_seo_agent import TechSEOAgent
    from agents.backlink_agent import BacklinkAgent
except ImportError:
    from .knowledge_agent import run_knowledge_agent
    from .research_agent import ResearchAgent
    from .writer_agent import WriterPipeline
    from .tech_seo_agent import TechSEOAgent
    from .backlink_agent import BacklinkAgent


logger = logging.getLogger("backend.agents.setup_pipeline")


def _extract_keywords(research_res: Any) -> list[str]:
    """Pull real search-intent keywords out of a ResearchAgent result.

    ResearchAgent.run() returns SERP-derived fields (relatedSearches, questions,
    peopleAlsoAsk, organic) — never a "keywords" key. Reading the missing key is
    why every newly connected site got a draft about "primary service guide".
    """
    if not isinstance(research_res, dict):
        return []

    out: list[str] = []

    def _add(value: Any) -> None:
        text = str(value or "").strip()
        if text and 2 < len(text) < 120 and text not in out:
            out.append(text)

    for key in ("keywords", "relatedSearches", "people_also_ask", "questions"):
        for item in research_res.get(key) or []:
            if isinstance(item, dict):
                _add(item.get("query") or item.get("question") or item.get("keyword"))
            else:
                _add(item)

    for row in (research_res.get("organic") or [])[:10]:
        if isinstance(row, dict):
            _add(row.get("title"))

    return out[:10]


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
        pages = (crawl_res or {}).get("new_pages_ingested", 0) or 0
        # crawl_site_structure returns [] both when the crawl failed and when the
        # site is genuinely empty, so 0 pages cannot be reported as "completed".
        results["steps"]["knowledge"] = {
            "status": "completed" if pages > 0 else "failed",
            "pages_ingested": pages,
            "error": None if pages > 0 else "knowledge crawl ingested 0 pages (crawler failure or empty site)",
        }
    except Exception as e:
        logger.warning(f"[SetupPipeline] Knowledge crawl had non-fatal error: {e}")
        results["steps"]["knowledge"] = {"status": "failed", "error": str(e)[:200]}

    # Step 2: SERP & Keyword Research
    top_keyword = "primary service guide"
    try:
        logger.info(f"[SetupPipeline] Phase 2/5: Researching search landscape & keyword opportunities...")
        ra = ResearchAgent(website_id=website_id)
        research_res = await ra.run(topic="core business services and search intent")
        # ResearchAgent.run() never returned a "keywords" key, so this used to be
        # always [] and every site's first article was written about the literal
        # string "primary service guide". Derive from the SERP fields it does return.
        keywords = _extract_keywords(research_res)
        if keywords:
            top_keyword = keywords[0]
        results["steps"]["research"] = {
            "status": "completed" if keywords else "failed",
            "keywords_found": len(keywords),
            "top_keyword": top_keyword,
            "error": None if keywords else "research returned no usable keywords",
        }
    except Exception as e:
        logger.warning(f"[SetupPipeline] Research step had error: {e}")
        results["steps"]["research"] = {"status": "failed", "error": str(e)[:200]}

    # Step 3: Writer Pipeline - First Article Draft
    article_title = ""
    try:
        nim_ok = await is_nim_available()
        if nim_ok:
            logger.info(f"[SetupPipeline] Phase 3/5: Generating first autonomous article for '{top_keyword}'...")
            wp = WriterPipeline(website_id=website_id)
            draft_topic = f"Complete Guide to {top_keyword.title()}"
            draft_res = await wp.generate(topic=draft_topic, primary_keyword=top_keyword)
            if draft_res.get("status") in ("failed", "blocked"):
                raise ValueError(draft_res.get("error_message") or draft_res.get("reason") or "writer rejected topic")
            if draft_res.get("status") == "skipped":
                raise ValueError(draft_res.get("reason") or "writer skipped duplicate topic")
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
        results["steps"]["tech_seo"] = {"status": "failed", "error": str(e)[:200]}

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
        results["steps"]["backlinks"] = {"status": "failed", "error": str(e)[:200]}

    # Step 6: Slack Announcement — only ever claims what actually completed.
    steps = results["steps"]
    writer_status = (steps.get("writer") or {}).get("status")
    knowledge_status = (steps.get("knowledge") or {}).get("status")
    fully_complete = (
        knowledge_status == "completed"
        and (steps.get("research") or {}).get("status") == "completed"
        and writer_status == "completed"
    )
    try:
        domain = homepage_url.replace("https://", "").replace("http://", "").split("/")[0]
        if fully_complete:
            headline = f"🚀 *RankForge setup complete for {domain}!*"
            lines = [
                "• 📚 Knowledge Base ingested & indexed",
                f"• 📝 First article '{article_title or top_keyword}' is ready for review on the /approvals page",
            ]
        else:
            # The old message announced completion unconditionally, including when
            # article_title was "" and health_score was None.
            incomplete = [
                name for name, step in steps.items()
                if (step or {}).get("status") not in ("completed", "skipped")
            ]
            headline = f"⚠️ *RankForge setup INCOMPLETE for {domain}*"
            lines = [
                f"• Failed/unfinished steps: {', '.join(incomplete) or 'unknown'}",
                "• No article was confirmed as written — retry from /websites",
            ]
        welcome_summary = "\n".join(
            [headline] + lines + [
                f"• 🩺 Baseline SEO Health Score: *{health_score if health_score is not None else 'not measured'}*",
                f"• 🔗 Discovered *{opps_count}* high-intent backlink opportunities",
            ]
        )
        await slack_intelligence_service.send_crisis_alert(
            website_id=website_id,
            title="Setup Complete" if fully_complete else "Setup Incomplete",
            details=welcome_summary,
            severity="info" if fully_complete else "warning",
        )
    except Exception as e:
        logger.debug(f"[SetupPipeline] Slack welcome message skipped: {e}")

    results["completed_at"] = datetime.utcnow().isoformat()
    results["complete"] = fully_complete

    # The caller marks the durable job "done" whenever this returns normally, and a
    # "done" job is never retried. Returning normally after a total outage therefore
    # stranded the site permanently. Raise so mark_failed runs instead.
    if not fully_complete:
        failed = [
            name for name, step in steps.items()
            if (step or {}).get("status") in ("failed", "error", "partial")
        ]
        raise RuntimeError(
            f"First-time setup incomplete for {website_id} "
            f"(failed/partial steps: {', '.join(failed) or 'writer did not complete'}). "
            f"See results['steps'] for per-step detail."
        )

    logger.info(f"[SetupPipeline] First-time setup pipeline finished for {website_id} ✅")
    return results


def run_first_time_setup_bg(website_id: str, homepage_url: str) -> None:
    """Non-blocking background helper for FastAPI background_tasks."""
    import asyncio
    from utils.job_queue import spawn_background
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            spawn_background(
                run_first_time_setup_pipeline(website_id, homepage_url),
                name=f"setup_pipeline:{website_id}",
            )
        else:
            loop.run_until_complete(run_first_time_setup_pipeline(website_id, homepage_url))
    except Exception:
        asyncio.run(run_first_time_setup_pipeline(website_id, homepage_url))
