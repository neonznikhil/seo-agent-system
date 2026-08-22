from datetime import datetime
import logging
from typing import Dict, Any, List

logger = logging.getLogger("backend.agents.keyword_agent")


class KeywordAgent:
    """
    KeywordAgent - takes research output and returns primary + secondary keywords,
    difficulty scores, and clustering data using NIM LLM.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, research_output: Dict[str, Any]) -> Dict[str, Any]:
        from ..database import call_nim_llm, get_supabase

        topic = research_output.get("topic", "general")
        trends = research_output.get("trends", [])
        questions = research_output.get("questions", [])

        prompt = (
            f"Based on this SEO research for '{topic}':\n"
            f"Trends: {', '.join(trends[:5])}\n"
            f"Questions: {', '.join(questions[:5])}\n\n"
            "Return ONLY a JSON object with keys:\n"
            "- primary_keyword (string, best main keyword)\n"
            "- secondary_keywords (array of 6 strings)\n"
            "- difficulty_score (integer 0-100)\n"
            "- intent (informational|commercial|transactional|navigational)\n"
            "- clusters (array of 3 arrays, each with 2 related keyword phrases)\n"
            "Example: {\"primary_keyword\":\"...\", \"secondary_keywords\":[\"...\"], \"difficulty_score\":65, \"intent\":\"informational\", \"clusters\":[[\"...\",\"...\"],[\"...\",\"...\"],[\"...\",\"...\"]]}"
        )
        try:
            raw = await call_nim_llm(prompt, system="You are an SEO keyword strategist. Return only valid JSON.", website_id=self.website_id)
            data = self._parse_json(raw)
        except Exception as e:
            logger.warning("NIM keyword generation failed, using fallback: %s", e)
            data = {
                "primary_keyword": topic,
                "secondary_keywords": [f"{topic} guide", f"best {topic}", f"{topic} tips", f"{topic} examples", f"how to {topic}", f"{topic} cost"],
                "difficulty_score": 55,
                "intent": "informational",
                "clusters": [[topic, f"{topic} guide"], [f"best {topic}", f"{topic} tips"], [f"how to {topic}", f"{topic} examples"]],
            }

        data.setdefault("primary_keyword", topic)
        data.setdefault("secondary_keywords", [f"{topic} guide", f"best {topic}", f"{topic} tips", f"{topic} examples", f"how to {topic}", f"{topic} cost"])
        data.setdefault("difficulty_score", 55)
        data.setdefault("intent", "informational")
        data.setdefault("clusters", [])
        if not data.get("clusters"):
            sec = data["secondary_keywords"]
            data["clusters"] = [sec[:2], sec[2:4], sec[4:6]]

        try:
            get_supabase().table("gsc_keywords").insert({
                "website_id": self.website_id,
                "keyword": data["primary_keyword"],
                "impressions": research_output.get("search_volume", 5000),
                "clicks": 0,
                "ctr": 0.0,
                "position": 0,
                "is_active": True,
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


def create_keyword_agent(website_id: str) -> KeywordAgent:
    return KeywordAgent(website_id)
