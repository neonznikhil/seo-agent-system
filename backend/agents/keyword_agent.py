from datetime import datetime
import logging
import json
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("backend.agents.keyword_agent")


class KeywordAgent:
    """KeywordAgent - evaluates keyword opportunities, difficulty, and clustering.
    
    Memory flow:
    1. Recall: Past converting keyword difficulties and topic cluster outcomes from brain_memory.
    2. Act: Calculate intent, difficulty scoring, and cluster map via NVIDIA NIM LLM.
    3. Write Back: Persist validated keyword opportunities to brain_memory (fact & experience).
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, research_output: Dict[str, Any]) -> Dict[str, Any]:
        from ..database import call_nim_llm, get_supabase
        from ..services.brain_service import BrainService

        brain = BrainService(website_id=self.website_id)

        topic = research_output.get("topic", "general")
        trends = research_output.get("trends", [])
        questions = research_output.get("questions", [])

        # ---------------------------------------------------------
        # Step 1: RECALL FIRST (Historically Converting Difficulty & Outcomes)
        # ---------------------------------------------------------
        difficulty_prefs = await brain.recall_preferences(self.website_id, "keyword difficulty converting range", top_k=2)
        past_outcomes = await brain.recall_outcomes(self.website_id, f"keyword {topic}", top_k=3)

        recalled_rules = []
        if difficulty_prefs:
            recalled_rules.append(f"Difficulty Preference: {difficulty_prefs[0].get('content', '')}")
        if past_outcomes:
            recalled_rules.append(f"Past Outcomes: {'; '.join(o.get('title', '') for o in past_outcomes)}")
        recalled_summary = " | ".join(recalled_rules) if recalled_rules else "Target difficulty 30-60 for fastest conversion."

        # ---------------------------------------------------------
        # Step 2: ACT SECOND (NIM LLM Keyword Clustering)
        # ---------------------------------------------------------
        prompt = (
            f"You are an Elite SEO Keyword Strategist.\n\n"
            f"RECALLED BRAIN PATTERNS:\n{recalled_summary}\n\n"
            f"RESEARCH DATA FOR '{topic}':\n"
            f"- Trends: {', '.join(trends[:5])}\n"
            f"- Questions: {', '.join(questions[:5])}\n\n"
            "Return ONLY a JSON object with keys:\n"
            "- primary_keyword (string: highest-intent main target keyword)\n"
            "- secondary_keywords (array of 6 high-relevance supporting keywords)\n"
            "- difficulty_score (integer 0-100 based on competitive density)\n"
            "- intent (informational|commercial|transactional|navigational)\n"
            "- clusters (array of 3 sub-arrays, each with 2 related semantic phrases)\n"
            "Example: {\"primary_keyword\":\"...\", \"secondary_keywords\":[\"...\"], \"difficulty_score\":45, \"intent\":\"informational\", \"clusters\":[[\"...\",\"...\"],[\"...\",\"...\"],[\"...\",\"...\"]]}"
        )

        try:
            raw = await call_nim_llm(prompt, system="You are an SEO keyword strategist. Return only valid JSON.", website_id=self.website_id)
            data = self._parse_json(raw)
        except Exception as e:
            logger.warning(f"NIM keyword generation error: {e}")
            data = {}

        data.setdefault("primary_keyword", topic)
        data.setdefault("secondary_keywords", [f"{topic} guide", f"best {topic}", f"{topic} tips", f"{topic} examples", f"how to {topic}", f"{topic} cost"])
        data.setdefault("difficulty_score", 45)
        data.setdefault("intent", "informational")
        if not data.get("clusters"):
            sec = data["secondary_keywords"]
            data["clusters"] = [sec[:2], sec[2:4], sec[4:6]]

        # ---------------------------------------------------------
        # Step 3: WRITE BACK AFTER
        # ---------------------------------------------------------
        supabase = get_supabase()
        try:
            supabase.table("gsc_keywords").insert({
                "website_id": self.website_id,
                "keyword": data["primary_keyword"],
                "impressions": research_output.get("search_volume", 5000),
                "clicks": 0,
                "ctr": 0.0,
                "position": 0,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception:
            pass

        # Write to brain_memory
        await brain.remember(
            website_id=self.website_id,
            memory_type="fact",
            title=f"Keyword Target: {data['primary_keyword']}",
            content=f"Primary keyword '{data['primary_keyword']}' evaluated with difficulty {data['difficulty_score']} and intent '{data['intent']}'. 6 secondary keywords clustered.",
            source_type="keyword_agent",
            confidence=0.94
        )

        await brain.remember(
            website_id=self.website_id,
            memory_type="experience",
            title=f"Clustering: {topic}",
            content=f"Formed {len(data['clusters'])} semantic clusters for '{data['primary_keyword']}'.",
            source_type="keyword_agent",
            confidence=0.91
        )

        return data

    def _parse_json(self, raw: str) -> Dict[str, Any]:
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
