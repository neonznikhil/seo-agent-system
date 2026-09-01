import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from database import get_supabase
from services.brain_service import BrainService
from services.serper_service import serper_service
from autonomous_decision_engine import AutonomousDecisionEngine
from research_agent import ResearchAgent
from keyword_agent import KeywordAgent
from seo_agent import SEOAgent
from tech_seo_agent import TechSEOAgent
from backlink_agent import BacklinkAgent
from strategy_agent import StrategyAgent
from supervisor_agent import SupervisorAgent

logger = logging.getLogger("backend.agents.seo_agent_group")

# In-memory registry of the 7 SEO agents' live lifecycle states
_SEO_AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "ResearchAgent": {
        "role": "Real-time SERP trends and competitor gap analysis via Serper.dev",
        "state": "idle",
        "last_run": None,
        "next_scheduled": "09:00 IST Daily",
        "last_result": None,
        "consecutive_failures": 0,
        "memory_inputs": ["fact", "experience"],
        "memory_outputs": ["fact", "experience"]
    },
    "KeywordAgent": {
        "role": "Difficulty calculation, intent classification, and semantic clustering",
        "state": "idle",
        "last_run": None,
        "next_scheduled": "Triggered by Supervisor / GoalCadence",
        "last_result": None,
        "consecutive_failures": 0,
        "memory_inputs": ["preference", "outcome"],
        "memory_outputs": ["fact", "experience"]
    },
    "SEOAgent": {
        "role": "Metadata optimization (title, meta desc, slug, density, internal links)",
        "state": "idle",
        "last_run": None,
        "next_scheduled": "Triggered on content pipeline stage",
        "last_result": None,
        "consecutive_failures": 0,
        "memory_inputs": ["preference", "experience"],
        "memory_outputs": ["experience"]
    },
    "TechSEOAgent": {
        "role": "Full audit: Core Web Vitals, XML sitemap, redirect chains, orphan pages",
        "state": "idle",
        "last_run": None,
        "next_scheduled": "12:00 IST Daily",
        "last_result": None,
        "consecutive_failures": 0,
        "memory_inputs": ["failure", "fact"],
        "memory_outputs": ["fact", "failure"]
    },
    "BacklinkAgent": {
        "role": "4-module live prospecting (broken link, resource, competitor, guest post)",
        "state": "idle",
        "last_run": None,
        "next_scheduled": "11:30 IST Daily",
        "last_result": None,
        "consecutive_failures": 0,
        "memory_inputs": ["preference", "experience"],
        "memory_outputs": ["experience", "preference"]
    },
    "StrategyAgent": {
        "role": "Strategic cluster planning and self-healing alternative execution generation",
        "state": "idle",
        "last_run": None,
        "next_scheduled": "On Alert / Recurring Failure Intervention",
        "last_result": None,
        "consecutive_failures": 0,
        "memory_inputs": ["experience", "failure", "preference"],
        "memory_outputs": ["preference", "experience"]
    },
    "SupervisorAgent": {
        "role": "Orchestrator of the 7-agent pipeline & 14-day outcome self-improvement",
        "state": "idle",
        "last_run": None,
        "next_scheduled": "10:00 IST (Outcome Learning) | 11:00 IST (Pipeline)",
        "last_result": None,
        "consecutive_failures": 0,
        "memory_inputs": ["all"],
        "memory_outputs": ["outcome", "preference"]
    }
}


class SEOAgentGroup:
    """RankForge Autonomous SEO Agent Group Integration Layer.
    
    Coordinates the 7 dedicated agents:
    ResearchAgent, KeywordAgent, SEOAgent, TechSEOAgent, BacklinkAgent, StrategyAgent, SupervisorAgent.
    
    Guarantees:
    1. Self-Triggering via AutonomousDecisionEngine.should_run()
    2. Self-Healing with failure memory logging and StrategyAgent alternate routing
    3. Self-Improving with daily 10:00 IST 14-day outcome synthesis
    4. Human Approval Gate strictly enforced before WordPress publishing
    """

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id
        self.brain = BrainService(website_id=website_id)
        self.decision_engine = AutonomousDecisionEngine(website_id=website_id)

    def _update_state(self, agent_name: str, state: str, result: Optional[Any] = None, error: Optional[str] = None):
        if agent_name in _SEO_AGENT_REGISTRY:
            _SEO_AGENT_REGISTRY[agent_name]["state"] = state
            _SEO_AGENT_REGISTRY[agent_name]["last_run"] = datetime.utcnow().isoformat()
            if error:
                _SEO_AGENT_REGISTRY[agent_name]["last_result"] = {"error": error}
                _SEO_AGENT_REGISTRY[agent_name]["consecutive_failures"] += 1
            else:
                _SEO_AGENT_REGISTRY[agent_name]["last_result"] = result or {"status": "success"}
                _SEO_AGENT_REGISTRY[agent_name]["consecutive_failures"] = 0

    # ---------------------------------------------------------
    # 1. Autonomous Agent Execution with Self-Healing
    # ---------------------------------------------------------
    async def run_agent_with_healing(self, agent_name: str, runner_coro, job_identifier: str, *args, **kwargs) -> Any:
        """Wrap agent execution in decision triggers, failure logging, and StrategyAgent self-healing."""
        # 1. Self-Trigger Check
        decision = await self.decision_engine.should_run(job_identifier)
        if not decision.get("should_run", True):
            logger.info(f"[SEOAgentGroup] {agent_name} skipped: {decision.get('reason')}")
            return {"status": "skipped", "reason": decision.get("reason")}

        # 2. Check Repeated Failure Pattern (Self-Healing Check)
        failed_count = await self.brain.get_repeated_failure_count(self.website_id, job_identifier)
        if failed_count >= 2:
            logger.warning(f"[SEOAgentGroup] Detected {failed_count} repeated failures for '{job_identifier}'. Requesting StrategyAgent alternative.")
            strat = StrategyAgent(website_id=self.website_id or "default")
            alt_strategy = await strat.generate_alternative_strategy(
                job_name=job_identifier,
                failure_pattern=f"repeated_failure_{job_identifier}",
                error_context=f"Failed {failed_count} consecutive attempts"
            )
            kwargs["alternative_strategy"] = alt_strategy

        # 3. Execute
        self._update_state(agent_name, "running")
        try:
            res = await runner_coro(*args, **kwargs)
            self._update_state(agent_name, "completed", result=res)
            return res
        except Exception as e:
            error_str = str(e)
            logger.error(f"[SEOAgentGroup] {agent_name} failed: {error_str}")
            self._update_state(agent_name, "failed", error=error_str)
            
            # Log failure to brain_memory with backoff metadata
            await self.brain.record_failure(
                website_id=self.website_id,
                agent_name=agent_name,
                error_context=error_str,
                task_payload={"job": job_identifier},
                backoff_minutes=15 * (_SEO_AGENT_REGISTRY[agent_name]["consecutive_failures"] or 1)
            )
            return {"status": "failed", "error": error_str}

    # ---------------------------------------------------------
    # 2. Scheduled Cadence Runner Handlers
    # ---------------------------------------------------------
    async def run_0900_research_cadence(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """09:00 IST - ResearchAgent mines SERP trends via Serper.dev connector."""
        target_topic = topic or await self.decision_engine.get_next_target_keyword()
        agent = ResearchAgent(website_id=self.website_id or "default")
        return await self.run_agent_with_healing(
            "ResearchAgent",
            agent.run,
            "daily_search",
            target_topic
        )

    async def run_1000_self_improvement_cadence(self) -> Dict[str, Any]:
        """10:00 IST - SupervisorAgent synthesizes 14-day outcomes into preference memories."""
        supervisor = SupervisorAgent(website_id=self.website_id or "default")
        return await self.run_agent_with_healing(
            "SupervisorAgent",
            supervisor.run_daily_outcome_learning,
            "brain_learn"
        )

    async def run_1100_writer_pipeline_cadence(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        """11:00 IST - SupervisorAgent fires goal-driven article generation through all phases."""
        target_kw = keyword or await self.decision_engine.get_next_target_keyword()
        supervisor = SupervisorAgent(website_id=self.website_id or "default")
        return await self.run_agent_with_healing(
            "SupervisorAgent",
            supervisor.run,
            "auto_new_page",
            target_kw
        )

    async def run_1130_backlink_cadence(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        """11:30 IST - BacklinkAgent runs 4-module prospecting via Serper.dev."""
        target_kw = keyword or await self.decision_engine.get_next_target_keyword()
        agent = BacklinkAgent(website_id=self.website_id or "default")
        return await self.run_agent_with_healing(
            "BacklinkAgent",
            agent.run_prospecting_loop,
            "backlink_prospecting",
            target_kw
        )

    async def run_1200_tech_seo_cadence(self) -> Dict[str, Any]:
        """12:00 IST - TechSEOAgent executes full domain technical audit."""
        agent = TechSEOAgent(website_id=self.website_id or "default")
        return await self.run_agent_with_healing(
            "TechSEOAgent",
            agent.run_audit,
            "seo_report_aeo_tracking",
            self.website_id or "default"
        )

    # ---------------------------------------------------------
    # 3. Comprehensive Status Snapshot
    # ---------------------------------------------------------
    async def get_status_snapshot(self) -> Dict[str, Any]:
        """Compile status of all 7 agents, brain memory breakdown, Serper connector health, and human gate."""
        supabase = get_supabase()

        # 1. Serper Connector Health
        serper_status = await serper_service.check_status()

        # 2. Brain Memory Breakdown
        memory_stats = self.brain.get_memory_breakdown(self.website_id)

        # 3. Human Gate Queue Counts
        pending_blogs = 0
        pending_fixes = 0
        unread_alerts = 0
        try:
            pb = supabase.table("blog_approvals").select("id", count="exact").eq("status", "pending").execute()
            pending_blogs = pb.count if pb.count is not None else len(pb.data or [])
        except Exception:
            pass

        try:
            pf = supabase.table("pending_fixes").select("id", count="exact").eq("status", "pending_approval").execute()
            pending_fixes = pf.count if pf.count is not None else len(pf.data or [])
        except Exception:
            pass

        try:
            ua = supabase.table("realtime_alerts").select("id", count="exact").eq("is_read", False).execute()
            unread_alerts = ua.count if ua.count is not None else len(ua.data or [])
        except Exception:
            pass

        # 4. Schedule Cadence Map
        cadence_info = [
            {"time_ist": "08:30", "agent": "KnowledgeAgent", "action": "Crawl sitemap for new & changed pages", "status": "scheduled"},
            {"time_ist": "09:00", "agent": "ResearchAgent", "action": "Mine SERP trends via Serper.dev connector", "status": "scheduled"},
            {"time_ist": "09:30", "agent": "KnowledgeAgent", "action": "Apply freshness decay & knowledge sync", "status": "scheduled"},
            {"time_ist": "10:00", "agent": "SupervisorAgent", "action": "14-day outcome synthesis -> preference memories", "status": "scheduled"},
            {"time_ist": "10:30", "agent": "RefreshAgent", "action": "Identify and refresh decaying content", "status": "scheduled"},
            {"time_ist": "11:00", "agent": "WriterPipeline", "action": "10-phase generation & 11-expert review", "status": "scheduled"},
            {"time_ist": "11:30", "agent": "BacklinkAgent", "action": "4-module prospecting via Serper.dev", "status": "scheduled"},
            {"time_ist": "12:00", "agent": "TechSEOAgent", "action": "Full audit: CWV, sitemap, redirects, orphans", "status": "scheduled"},
        ]

        # 5. Continuous Monitors (6 loops)
        monitors_info = {
            "rank_monitor": {"cadence": "Every 15 mins", "status": "active"},
            "serp_monitor": {"cadence": "Every 30 mins (Serper.dev)", "status": "active"},
            "competitor_monitor": {"cadence": "Every 60 mins (Serper.dev News)", "status": "active"},
            "tech_monitor": {"cadence": "Every 60 mins", "status": "active"},
            "geo_monitor": {"cadence": "Every 30 mins", "status": "active"},
            "structure_monitor": {"cadence": "Every 6 hours", "status": "active"},
        }

        return {
            "pipeline_name": "RankForge Autonomous SEO Agent Group",
            "orchestrator": "SupervisorAgent",
            "timezone": "Asia/Kolkata",
            "autonomous_mode": "Self-Triggering, Self-Healing, Self-Improving",
            "agent_states": _SEO_AGENT_REGISTRY,
            "serper_connector": serper_status,
            "brain_memory": memory_stats,
            "human_gate": {
                "strict_approval_required": True,
                "pending_blog_approvals": pending_blogs,
                "pending_tech_fixes": pending_fixes,
                "unread_realtime_alerts": unread_alerts,
                "policy": "Autonomous system proposes — humans decide."
            },
            "scheduled_cadence": cadence_info,
            "continuous_monitors": monitors_info,
            "timestamp_utc": datetime.utcnow().isoformat(),
        }


# Global singleton instance
seo_agent_group = SEOAgentGroup()
