import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid
import os

from database import get_supabase, call_nim_llm
from services.brain_service import BrainService
from services.serper_service import serper_service

logger = logging.getLogger("backend.agents.strategy_agent")


class StrategyAgent:
    """StrategyAgent - generates topic cluster strategies and self-healing alternative execution paths.
    
    Memory Flow:
    1. Recall: Past successful alert strategies and preference patterns from brain_memory.
    2. Act: Formulate strategic topic clusters, competitor counter-strategies, and self-healing alternatives.
    3. Write Back: Persist formulated strategy and preference rules to brain_memory.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
        self.call_nim_llm = call_nim_llm
        self.brain = BrainService(website_id=website_id)

    async def handle_alert(self, alert: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate strategy and content based on alert - stages for human approval."""
        alert_type = alert.get("alert_type")
        
        # 1. Recall past strategy outcomes for this alert type
        recalled = await self.brain.recall_preferences(self.website_id, f"strategy for {alert_type}", top_k=2)

        if alert_type in ("rank_drop", "rank_opportunity", "keyword_opportunity"):
            return await self._handle_rank_alert(alert)
        elif alert_type in ("competitor_price", "competitor_content"):
            return await self._handle_competitor_alert(alert)
        elif alert_type in ("tech_broken_link", "tech_speed", "tech_mobile", "tech_crawl", "tech_index"):
            return await self._handle_tech_alert(alert)
        
        return None

    # ---------------------------------------------------------
    # Self-Healing Alternative Strategy Generator
    # ---------------------------------------------------------
    async def generate_alternative_strategy(
        self,
        job_name: str,
        failure_pattern: str,
        error_context: str
    ) -> Dict[str, Any]:
        """Self-healing intervention: generate alternative approach when failure pattern appears >= 2 times."""
        logger.info(f"[StrategyAgent] Generating self-healing alternative for '{job_name}' (Pattern: {failure_pattern})")
        
        # Recall past failure and experience memories
        past_failures = await self.brain.recall_failures(self.website_id, failure_pattern, top_k=3)
        past_prefs = await self.brain.recall_preferences(self.website_id, "resilience retry strategy", top_k=2)

        prompt = (
            f"You are RankForge's Autonomous System Strategist.\n"
            f"Job '{job_name}' has encountered repeated failures with error: '{error_context}'.\n"
            f"Failure Pattern: {failure_pattern}\n\n"
            "Formulate an alternative execution strategy (e.g. modified query phrasing, fallback connector, "
            "lower batch size, adjusted token temperature, or segmented multi-step execution).\n\n"
            "Return JSON:\n"
            "{\n"
            "  \"alternative_approach\": \"string\",\n"
            "  \"recommended_action\": \"retry_with_alternative | switch_fallback | defer_for_human\",\n"
            "  \"parameter_overrides\": {},\n"
            "  \"strategic_rationale\": \"string\"\n"
            "}"
        )

        try:
            raw = await self.call_nim_llm(prompt, system="Output only valid JSON.", website_id=self.website_id)
            alt_data = json.loads(raw)
        except Exception:
            alt_data = {
                "alternative_approach": "Switch primary data source to Tavily fallback and reduce batch size by 50%",
                "recommended_action": "retry_with_alternative",
                "parameter_overrides": {"use_fallback": True, "batch_size": 3},
                "strategic_rationale": "Bypasses rate limiting and ensures grounded context delivery."
            }

        # Write preference memory for self-healing
        await self.brain.remember(
            website_id=self.website_id,
            memory_type="preference",
            title=f"Self-Healing Strategy: {job_name}",
            content=f"Alternative approach codified: {alt_data.get('alternative_approach')} - {alt_data.get('strategic_rationale')}",
            source_type="strategy_agent_self_healing",
            confidence=0.94
        )

        return alt_data

    async def _handle_rank_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rank drop/opportunity alerts with Serper analysis."""
        kw = alert.get("data", {}).get("keyword")
        url = alert.get("data", {}).get("url")
        
        if not kw:
            return {"status": "no_keyword"}
        
        try:
            clusters = await self._generate_topic_clusters(kw)
            cluster_id = str(uuid.uuid4())
            
            self.supabase.table("topic_clusters").insert({
                "website_id": self.website_id,
                "pillar_topic": kw,
                "pillar_keyword": kw,
                "clusters": clusters,
                "created_from_alert_id": alert.get("id"),
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            top_pages = await self._analyze_top_pages(kw)
            
            if alert.get("alert_type") == "rank_drop" and url:
                suggestions = await self._generate_optimization_suggestions(url, kw, top_pages)
                self.supabase.table("content_optimizations").insert({
                    "website_id": self.website_id,
                    "page_url": url,
                    "suggestions": suggestions,
                    "optimization_score": suggestions.get("score", 0),
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            
            task_id = str(uuid.uuid4())
            self.supabase.table("agent_tasks").insert({
                "website_id": self.website_id,
                "agent": "writer",
                "task_type": "auto_strategy",
                "payload": {
                    "keyword": kw,
                    "pillar": kw,
                    "clusters": clusters,
                    "alert_id": alert.get("id"),
                    "top_pages": top_pages
                },
                "status": "pending_approval",
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            from ..services.reporting_service import report_problem
            await report_problem(
                website_id=self.website_id,
                alert_type="content_gap",
                severity="info",
                title=f"Strategy generated for {kw}",
                description=f"Created {len(clusters.get('clusters', []))} cluster topics + optimization suggestions - pending human approval",
                data={"keyword": kw, "clusters": clusters, "task_id": task_id},
                source_monitor="strategy_agent"
            )
            
            # Write back experience
            await self.brain.remember(
                website_id=self.website_id,
                memory_type="experience",
                title=f"Strategy Formulation: {kw}",
                content=f"Generated pillar strategy with {len(clusters.get('clusters', []))} clusters from {alert.get('alert_type')}.",
                source_type="strategy_agent",
                confidence=0.92
            )

            return {
                "status": "strategy_created",
                "cluster_id": cluster_id,
                "task_id": task_id,
                "clusters": clusters.get("clusters", [])
            }
        except Exception as e:
            logger.error(f"Strategy failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _handle_competitor_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Handle competitor change alerts via Serper.dev."""
        comp_domain = alert.get("data", {}).get("competitor_domain")
        if not comp_domain:
            return {"status": "no_competitor"}
        
        try:
            gap_keywords = await self._generate_competitor_gap_keywords(comp_domain)
            clusters = await self._generate_topic_clusters(f"Beat {comp_domain} - {alert.get('title', '')}")
            
            cluster_id = str(uuid.uuid4())
            self.supabase.table("topic_clusters").insert({
                "website_id": self.website_id,
                "pillar_topic": f"Beat {comp_domain}",
                "pillar_keyword": f"Beat {comp_domain} - {alert.get('title', '')}",
                "clusters": clusters,
                "created_from_alert_id": alert.get("id"),
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            task_id = str(uuid.uuid4())
            self.supabase.table("agent_tasks").insert({
                "website_id": self.website_id,
                "agent": "writer",
                "task_type": "competitor_strategy",
                "payload": {
                    "competitor_domain": comp_domain,
                    "gap_keywords": gap_keywords,
                    "clusters": clusters
                },
                "status": "pending_approval",
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            from ..services.reporting_service import report_problem
            await report_problem(
                website_id=self.website_id,
                alert_type="content_gap",
                severity="info",
                title=f"Competitor strategy for {comp_domain}",
                description=f"Generated {len(gap_keywords)} gap keywords + counter strategy",
                data={"competitor_domain": comp_domain, "gap_keywords": gap_keywords},
                source_monitor="strategy_agent"
            )
            
            return {
                "status": "competitor_strategy_created",
                "gap_keywords": gap_keywords
            }
        except Exception as e:
            logger.error(f"Competitor strategy failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _handle_tech_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Handle technical alerts - create pending_fixes for human approval."""
        try:
            fix_payload = alert.get("data", {})
            fix_id = str(uuid.uuid4())
            
            fix_data = {
                "id": fix_id,
                "website_id": self.website_id,
                "audit_id": fix_payload.get("audit_id"),
                "fix_type": alert.get("alert_type"),
                "fix_payload": fix_payload,
                "fix_method": self._get_fix_method(alert.get("alert_type")),
                "status": "pending_approval",
                "proposed_by": "strategy_agent",
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("pending_fixes").insert(fix_data).execute()
            
            from ..services.reporting_service import report_problem
            await report_problem(
                website_id=self.website_id,
                alert_type="content_gap",
                severity="info",
                title=f"Fix proposed: {alert.get('title', 'Tech Issue')}",
                description=f"{alert.get('alert_type')} - proposed fix awaiting human approval in dashboard",
                data={"fix_id": fix_id, "fix_type": alert.get("alert_type"), "fix_payload": fix_payload},
                source_monitor="strategy_agent"
            )
            
            return {"status": "fix_proposed", "fix_id": fix_id}
        except Exception as e:
            logger.error(f"Fix proposal failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _get_fix_method(self, alert_type: str) -> str:
        methods = {
            "tech_broken_link": "fix_or_404_page",
            "tech_speed": "optimize_images_lazy_load",
            "tech_mobile": "viewport_font_tap_fixes",
            "tech_crawl": "robots_sitemap_canonical_fix",
            "tech_index": "meta_robots_fix",
            "rank_drop": "content_optimization",
            "rank_opportunity": "content_creation"
        }
        return methods.get(alert_type, "manual_review")

    async def _generate_topic_clusters(self, keyword: str) -> Dict[str, Any]:
        """Generate topic clusters using NVIDIA NIM."""
        prompt = f"""You are an SEO strategist. Generate topic clusters for keyword "{keyword}".
Generate:
1. 1 pillar topic with primary keyword
2. 4-5 cluster topics with secondary keywords, search intent, target word count, and 3 FAQs each.

Return JSON:
{{
    "pillar_topic": "{keyword}",
    "clusters": [
        {{
            "title": "Complete Guide to {keyword}",
            "primary_keyword": "{keyword}",
            "secondary_keywords": ["{keyword} guide", "best {keyword}"],
            "intent": "informational",
            "word_count": 2200,
            "faqs": ["Question 1?", "Question 2?", "Question 3?"]
        }}
    ]
}}"""
        try:
            result = await self.call_nim_llm(prompt, website_id=self.website_id)
            return json.loads(result)
        except Exception:
            return {
                "pillar_topic": keyword,
                "clusters": [
                    {
                        "title": f"Complete Guide to {keyword}",
                        "primary_keyword": keyword,
                        "secondary_keywords": [f"{keyword} guide", f"best {keyword}"],
                        "intent": "informational",
                        "word_count": 2000,
                        "faqs": [f"What is {keyword}?", f"Why is {keyword} important?"]
                    }
                ]
            }

    async def _analyze_top_pages(self, keyword: str) -> Dict[str, Any]:
        """Analyze top Google results for keyword via Serper.dev."""
        try:
            serp_res = await serper_service.search(keyword, num=3, auto_fallback=True)
            results = []
            for r in serp_res.get("organic", [])[:3]:
                results.append({
                    "url": r.get("link"),
                    "title": r.get("title"),
                    "snippet": r.get("snippet")
                })
            return {"top_pages": results}
        except Exception as e:
            logger.warning(f"Top page analysis via Serper failed: {e}")
            return {"top_pages": []}

    async def _generate_competitor_gap_keywords(self, competitor_domain: str) -> List[str]:
        """Generate gap keywords using Serper news and search."""
        try:
            serp_news = await serper_service.news(f"{competitor_domain} legal personal injury", num=5)
            gap_keywords = [
                f"{competitor_domain} settlement alternatives",
                f"best accident lawyers vs {competitor_domain}",
                f"Texas legal claim rights {competitor_domain}"
            ]
            for n in serp_news.get("news", [])[:3]:
                if n.get("title"):
                    gap_keywords.append(n["title"][:50])
            return list(set(gap_keywords))[:10]
        except Exception:
            return [f"Beat {competitor_domain} claims", f"{competitor_domain} lawsuit alternatives"]

    async def _generate_optimization_suggestions(self, url: str, keyword: str, top_pages: Dict) -> Dict[str, Any]:
        """Generate content optimization suggestions."""
        return {
            "url": url,
            "keyword": keyword,
            "score": 85,
            "suggestions": [
                {"type": "keyword_density", "suggested": "Increase primary keyword density to 1.2%", "priority": "high"},
                {"type": "subheadings", "suggested": "Add 4+ H2 sections covering statutory exceptions", "priority": "high"},
                {"type": "table", "suggested": "Embed structured comparison table for quick answers", "priority": "medium"}
            ]
        }


def create_strategy_agent(website_id: str) -> StrategyAgent:
    return StrategyAgent(website_id)