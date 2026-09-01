import asyncio
import json
import logging

from backend.database import get_supabase, get_embedding
from backend.agents.tools.shared_utils import is_homepage

logger = logging.getLogger("backend.agents.knowledge_agent")


async def run_knowledge_agent(website_id: str, homepage_url: str, max_pages: int = 50) -> dict:
    """
    Full-site KnowledgeAgent: delegates to KnowledgeService.watch_business_website
    which performs recursive sitemap discovery + BFS crawl of all internal subpages
    (up to max_pages) and indexes 3200-char chunks with 1536-dim embeddings.
    
    Also extracts tone profile & knowledge triples from homepage for legacy callers.
    """
    logger.info(f"[KnowledgeAgent] Starting full-site crawl for {website_id} ({homepage_url}) max_pages={max_pages}")
    try:
        from ..services.knowledge_service import KnowledgeService
        ks = KnowledgeService(website_id=website_id)
        crawl_res = await ks.watch_business_website(target_site=homepage_url, max_pages=max_pages)
        pages_saved = int(crawl_res.get("new_pages_ingested", 0) + crawl_res.get("updated_pages", 0))
        total_chunks = int(crawl_res.get("total_chunks_indexed", 0))
        urls_scanned = int(crawl_res.get("urls_scanned", 0))
        logger.info(f"[KnowledgeAgent] Crawl finished for {website_id}: {pages_saved} pages, {total_chunks} chunks, {urls_scanned} urls scanned")
        # Optional tone / extraction for compatibility
        tone_result = None
        knowledge_result = None
        try:
            from .tools.tone_analyzer_tool import ToneAnalyzerTool
            from .tools.knowledge_extractor_tool import KnowledgeExtractorTool
            import httpx
            from bs4 import BeautifulSoup
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(homepage_url, headers={"User-Agent": "RankForge-Knowledge-Crawler/2.0"})
                html = resp.text if resp.status_code == 200 else ""
            if html:
                tone_analyzer = ToneAnalyzerTool()
                tone_analyzer.set_website_id(website_id)
                tone_analyzer.set_agent_name("knowledge_agent")
                # ToneAnalyzer expects text, use simple _run sync fallback
                try:
                    tone_result = tone_analyzer._run(html[:8000])
                except Exception:
                    tone_result = None
                knowledge_extractor = KnowledgeExtractorTool()
                knowledge_extractor.set_website_id(website_id)
                knowledge_extractor.set_agent_name("knowledge_agent")
                try:
                    knowledge_result = knowledge_extractor._run(html[:8000])
                except Exception:
                    knowledge_result = None
        except Exception as e:
            logger.debug(f"[KnowledgeAgent] Tone/extraction supplementary step skipped: {e}")

        return {
            "pages_saved": pages_saved,
            "total_chunks_indexed": total_chunks,
            "urls_scanned": urls_scanned,
            "crawl_result": crawl_res,
            "tone": tone_result,
            "knowledge": knowledge_result,
            "success": True,
        }
    except Exception as e:
        logger.error(f"[KnowledgeAgent] Full-site crawl failed for {website_id}: {e}", exc_info=True)
        return {"pages_saved": 0, "total_chunks_indexed": 0, "urls_scanned": 0, "error": str(e), "success": False}


# Synchronous wrapper for legacy callers that do not await
def run_knowledge_agent_sync(website_id: str, homepage_url: str, max_pages: int = 50) -> dict:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # create new loop in thread if already running
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(asyncio.run, run_knowledge_agent(website_id, homepage_url, max_pages))
                return fut.result(timeout=120)
        else:
            return loop.run_until_complete(run_knowledge_agent(website_id, homepage_url, max_pages))
    except RuntimeError:
        return asyncio.run(run_knowledge_agent(website_id, homepage_url, max_pages))


# Backwards-compat: if someone does `from knowledge_agent import run_knowledge_agent` and calls without await,
# we keep a sync alias but the async one is primary. Caller should await.