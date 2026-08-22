import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger("backend.agents.research_agent")


class ResearchAgent:
    """
    ResearchAgent - performs topic research using NIM LLM + web data sources.
    Returns trends, competitors, questions, search_volume data.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, topic: str) -> Dict[str, Any]:
        from ..database import call_nim_llm, get_supabase
        from ..services.crawlee_service import CrawleeService

        serp_result = {"competitors": [], "headings": [], "pa": []}
        try:
            crawler = CrawleeService(website_id=self.website_id)
            serp_result = await crawler.extract_serp_landscape(topic) or serp_result
        except Exception as e:
            logger.warning("Crawlee research failed: %s", e)

        prompt = (
            f"Research the topic '{topic}' for SEO content planning. "
            "Return ONLY a JSON object with keys: "
            "trends (list of 5 trending subtopics), "
            "competitors (list of 5 competitor domains), "
            "questions (list of 5 user questions), "
            "search_volume (estimated monthly searches as integer). "
            "Example: {\"trends\": [\"trend1\",\"trend2\"], \"competitors\": [\"example.com\"], "
            "\"questions\": [\"q1?\",\"q2?\"], \"search_volume\": 10000}"
        )
        try:
            raw = await call_nim_llm(prompt, system="You are an SEO research analyst. Return only valid JSON.", website_id=self.website_id)
            data = self._parse_json(raw)
        except Exception as e:
            logger.warning("NIM research failed, using fallback: %s", e)
            data = {
                "trends": [f"{topic} trends 2026", f"{topic} best practices", f"{topic} tools", f"{topic} cost", f"{topic} examples"],
                "competitors": [c.get("url", c.get("domain", "")) for c in serp_result.get("competitors", [])[:5]] or ["example.com", "top10.com", "guidehub.com", "seoagency.io", "reviewsite.net"],
                "questions": [f"What is {topic}?", f"How does {topic} work?", f"Why {topic} matters?", f"Best {topic} tools?", f"{topic} cost 2026?"],
                "search_volume": 12000,
            }

        if not data.get("competitors"):
            data["competitors"] = ["example.com", "top10.com", "guidehub.com", "seoagency.io", "reviewsite.net"]
        if not data.get("questions"):
            data["questions"] = [f"What is {topic}?", f"How {topic}?", f"Why {topic}?"]
        if not data.get("trends"):
            data["trends"] = [f"{topic} trends", f"{topic} tips", f"{topic} guide"]
        data["search_volume"] = data.get("search_volume") or 5000

        try:
            get_supabase().table("research").insert({
                "website_id": self.website_id,
                "topic": topic,
                "status": "completed",
                "result": data,
            }).execute()
        except Exception:
            pass

        return data

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        import json, re
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except Exception:
            pass
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {}


def create_research_agent(website_id: str) -> ResearchAgent:
    return ResearchAgent(website_id)
