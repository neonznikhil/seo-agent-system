from datetime import datetime
import json
import logging
import time
from typing import Dict, Any, Optional, List

from ..services.brain_service import BrainService

logger = logging.getLogger("backend.agents.supervisor_agent")


class SupervisorAgent:
    """SupervisorAgent - orchestrates the full autonomous SEO pipeline:
    
    research -> keyword -> outline -> writer -> seo -> elementor -> wordpress -> backlinks
    
    Memory Flow:
    1. Recall: Reads full brain state and brand guidelines before orchestrating.
    2. Act: Executes multi-agent pipeline steps sequentially with error guardrails.
    3. Write Back: Records 'outcome' memories upon completion and 'failure' on errors.
    4. Self-Improving: Synthesizes 14-day outcomes into 'preference' rules daily at 10:00 IST.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id
        self.state = "idle"
        self.error = None
        self.cost_tokens = {}
        self.start_time = None
        self.end_time = None
        self.brain = BrainService(website_id=self.website_id)

    async def run(self, keyword: str) -> Dict[str, Any]:
        """Execute full orchestrated pipeline with strict memory lifecycle."""
        self.start_time = time.time()
        self.state = "running"
        self.error = None
        self.cost_tokens = {}

        # ---------------------------------------------------------
        # Step 1: RECALL FULL BRAIN STATE FIRST
        # ---------------------------------------------------------
        brand_brain = await self.brain.get_brand_brain(self.website_id)
        preferences = await self.brain.recall_preferences(self.website_id, f"pipeline execution {keyword}", top_k=3)
        recent_outcomes = await self.brain.recall_outcomes(self.website_id, keyword, top_k=2)

        logger.info(f"[Supervisor] Initialized with Brand Brain context for '{keyword}': {brand_brain[:80]}...")

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
            # 1. Research Agent
            research = await self._safe_step("research", self._run_research, keyword)
            result["research"] = research

            # 2. Keyword Agent
            keyword_data = await self._safe_step("keyword", self._run_keyword, research)
            result["keywords"] = keyword_data
            primary_kw = keyword_data.get("primary_keyword", keyword)

            # 3. Outline Agent
            outline = await self._safe_step("outline", self._run_outline, primary_kw, research)
            result["outline"] = outline

            # 4. Writer Pipeline (10-Phase with 11-Expert Review)
            blog = await self._safe_step("writer", self._run_writer, primary_kw, outline)
            result["blog_html"] = blog

            # 5. SEO Agent
            seo = await self._safe_step("seo", self._run_seo, blog.get("content", ""), primary_kw)
            result["seo_meta"] = seo

            # 6. Elementor Agent
            elementor = await self._safe_step("elementor", self._run_elementor, seo.get("optimized_html", seo.get("html", "")))
            result["elementor_html"] = elementor

            # 7. WordPress Stage (HUMAN GATE PRESERVED)
            wp = await self._safe_step("wordpress", self._run_wordpress, f"{primary_kw.title()}: 2026 Complete Guide", elementor.get("clean_html", ""), {"seo_keyword": primary_kw, "seo_meta": seo})
            result["wp_draft_url"] = wp.get("wp_url") or wp.get("edit_url")
            result["approval_id"] = wp.get("approval_id")

            # 8. Backlink Agent
            backlinks = await self._safe_step("backlinks", self._run_backlinks, primary_kw)
            result["backlinks"] = backlinks

            result["status"] = "completed"
            self.state = "completed"

            # ---------------------------------------------------------
            # Step 3: WRITE BACK OUTCOME MEMORY
            # ---------------------------------------------------------
            await self.brain.remember(
                website_id=self.website_id,
                memory_type="outcome",
                title=f"Pipeline Completed: {primary_kw}",
                content=f"Generated draft for '{primary_kw}'. SEO Score: {seo.get('seo_score', 88)}. Staged in blog_approvals ID: {wp.get('approval_id')}.",
                source_type="supervisor_pipeline",
                confidence=0.96
            )

        except Exception as e:
            self.state = "failed"
            self.error = str(e)
            result["errors"].append(str(e))
            logger.error(f"[Supervisor] Pipeline failed on keyword '{keyword}': {e}")
            
            # Record failure memory
            await self.brain.record_failure(
                website_id=self.website_id,
                agent_name="supervisor_pipeline",
                error_context=str(e),
                task_payload={"keyword": keyword},
                backoff_minutes=15
            )

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
        """HUMAN APPROVAL GATE - stages post with status 'pending' in blog_approvals table."""
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
        from .backlink_agent import BacklinkAgent
        agent = BacklinkAgent(website_id=self.website_id)
        return await agent.run_prospecting_loop(keyword=keyword)

    # ---------------------------------------------------------
    # Daily 10:00 IST Self-Improving Learning Loop
    # ---------------------------------------------------------
    async def run_daily_outcome_learning(self) -> Dict[str, Any]:
        """Daily 10:00 IST job: read 14-day outcomes and codify preference memories."""
        logger.info(f"[Supervisor] Running 14-day outcome learning for {self.website_id}...")
        return await self.brain.synthesize_14day_learnings(website_id=self.website_id)


def create_supervisor_agent(website_id: str) -> SupervisorAgent:
    return SupervisorAgent(website_id)
