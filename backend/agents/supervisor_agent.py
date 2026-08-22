from datetime import datetime
import json
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("backend.agents.supervisor_agent")


class SupervisorAgent:
    """
    SupervisorAgent - orchestrates the full content pipeline:
    research -> keyword -> outline -> write -> seo -> elementor -> wordpress -> backlinks
    Manages state, error handling, and cost tracking.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id
        self.state = "idle"
        self.error = None
        self.cost_tokens = {}
        self.start_time = None
        self.end_time = None

    async def run(self, keyword: str) -> Dict[str, Any]:
        self.start_time = time.time()
        self.state = "running"
        self.error = None
        self.cost_tokens = {}
        result = {
            "keyword": keyword,
            "research": None,
            "keywords": None,
            "outline": None,
            "blog_html": None,
            "seo_meta": None,
            "elementor_html": None,
            "wp_draft_url": None,
            "backlinks": None,
            "status": "failed",
            "errors": [],
            "total_time": 0,
            "tokens_used": {},
        }

        try:
            research = await self._safe_step("research", self._run_research, keyword)
            result["research"] = research

            keyword_data = await self._safe_step("keyword", self._run_keyword, research)
            result["keywords"] = keyword_data

            outline = await self._safe_step("outline", self._run_outline, keyword_data.get("primary_keyword", keyword), research)
            result["outline"] = outline

            blog = await self._safe_step("writer", self._run_writer, keyword_data.get("primary_keyword", keyword), outline)
            result["blog_html"] = blog

            seo = await self._safe_step("seo", self._run_seo, blog.get("content", ""), keyword_data.get("primary_keyword", keyword))
            result["seo_meta"] = seo

            elementor = await self._safe_step("elementor", self._run_elementor, seo.get("optimized_html", seo.get("html", "")))
            result["elementor_html"] = elementor

            wp = await self._safe_step("wordpress", self._run_wordpress, f"{keyword}: Complete Guide", elementor.get("clean_html", ""), {"seo_keyword": keyword})
            result["wp_draft_url"] = wp.get("wp_url") or wp.get("edit_url")

            backlinks = await self._safe_step("backlinks", self._run_backlinks, keyword_data.get("primary_keyword", keyword))
            result["backlinks"] = backlinks

            result["status"] = "completed"
            self.state = "completed"
        except Exception as e:
            self.state = "failed"
            self.error = str(e)
            result["errors"].append(str(e))
            logger.error("Supervisor pipeline failed: %s", e)

        self.end_time = time.time()
        result["total_time"] = round(self.end_time - self.start_time, 2)
        result["tokens_used"] = dict(self.cost_tokens)
        return result

    async def _safe_step(self, name: str, fn, *args, **kwargs):
        step_start = time.time()
        try:
            out = await fn(*args, **kwargs)
            self.cost_tokens[name] = self.cost_tokens.get(name, 0) + 1
            elapsed = round(time.time() - step_start, 2)
            logger.info("[Supervisor] %s - OK - %.2fs", name, elapsed)
            return out
        except Exception as e:
            elapsed = round(time.time() - step_start, 2)
            logger.error("[Supervisor] %s - FAIL - %.2fs - %s", name, elapsed, e)
            raise

    async def _run_research(self, topic: str) -> Dict[str, Any]:
        from .research_agent import create_research_agent
        agent = create_research_agent(self.website_id)
        return await agent.run(topic)

    async def _run_keyword(self, research: Dict[str, Any]) -> Dict[str, Any]:
        from .keyword_agent import create_keyword_agent
        agent = create_keyword_agent(self.website_id)
        return await agent.run(research)

    async def _run_outline(self, keyword: str, research: Dict[str, Any]) -> Dict[str, Any]:
        from .outline_agent import create_outline_agent
        agent = create_outline_agent(self.website_id)
        return await agent.run(keyword, research)

    async def _run_writer(self, keyword: str, outline: Dict[str, Any]) -> Dict[str, Any]:
        from .writer_agent import WriterPipeline
        pipeline = WriterPipeline(self.website_id)
        return await pipeline.generate(keyword, keyword)

    async def _run_seo(self, raw_html: str, keyword: str) -> Dict[str, Any]:
        from .seo_agent import create_seo_agent
        agent = create_seo_agent(self.website_id)
        return await agent.run(raw_html, keyword)

    async def _run_elementor(self, seo_html: str) -> Dict[str, Any]:
        from .elementor_agent import create_elementor_agent
        agent = create_elementor_agent(self.website_id)
        return await agent.run(seo_html)

    async def _run_wordpress(self, title: str, content_html: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """HUMAN APPROVAL GATE - never publishes to WordPress directly.

        Stages the generated post in blog_approvals with status='pending'.
        Only /api/approvals/{id}/approve (human click) writes to WordPress.
        """
        from ..services.auto_publisher_service import _stage_for_approval

        seo = meta.get("seo_meta") or {}
        return await _stage_for_approval(
            website_id=self.website_id,
            title=title,
            html_content=content_html,
            seo_title=seo.get("seo_title", title),
            meta_description=seo.get("meta_description", ""),
            slug=seo.get("slug", ""),
            keyword=meta.get("seo_keyword", ""),
            seo_score=seo.get("seo_score", 0),
            approval_type="new_post",
            wordpress_action="create",
            blog_id=meta.get("blog_id"),
        )

    async def _run_backlinks(self, keyword: str) -> Dict[str, Any]:
        from .backlink_agent import run_backlink_agent
        return run_backlink_agent(self.website_id)


def create_supervisor_agent(website_id: str) -> SupervisorAgent:
    return SupervisorAgent(website_id)
