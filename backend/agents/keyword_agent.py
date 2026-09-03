from datetime import datetime
import logging
import json
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("backend.agents.keyword_agent")


class KeywordAgent:
    """KeywordAgent - evaluates keyword opportunities, difficulty, and clustering.
    
    Memory flow:
    1. Recall: Past converting keyword difficulties, intent patterns, and topic cluster outcomes from brain_memory.
    2. Act: Prioritize winning intent types via Pattern Recognition Engine and calculate clustering via NVIDIA NIM LLM.
    3. Write Back: Persist validated keyword opportunities to brain_memory (fact & experience).
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, research_output: Dict[str, Any]) -> Dict[str, Any]:
        from database import call_nim_llm, get_supabase
        from services.brain_service import BrainService
        from agents.brain_autopilot_agent import get_active_strategic_patterns

        brain = BrainService(website_id=self.website_id)
        topic = research_output.get("topic", "general")
        trends = research_output.get("trends", [])
        questions = research_output.get("questions", [])

        # ---------------------------------------------------------
        # Step 1: RECALL FIRST (Strategic Patterns & Outcomes)
        # ---------------------------------------------------------
        strategic_defaults = await get_active_strategic_patterns(self.website_id)
        preferred_intent = strategic_defaults.get("preferred_intent", "commercial")
        intent_weight = float(strategic_defaults.get("intent_weight", 0.85))

        difficulty_prefs = await brain.recall_preferences(self.website_id, "keyword difficulty converting range", top_k=2)
        past_outcomes = await brain.recall_outcomes(self.website_id, f"keyword {topic}", top_k=3)

        recalled_rules = [f"Strategic Winning Intent: {preferred_intent} (Confidence Weight: {int(intent_weight*100)}%)"]
        if difficulty_prefs:
            recalled_rules.append(f"Difficulty Preference: {difficulty_prefs[0].get('content', '')}")
        if past_outcomes:
            recalled_rules.append(f"Past Outcomes: {'; '.join(o.get('title', '') for o in past_outcomes)}")
        recalled_summary = " | ".join(recalled_rules)

        # ---------------------------------------------------------
        # Step 2: ACT SECOND (NIM LLM Keyword Clustering with Intent Weighting)
        # ---------------------------------------------------------
        prompt = (
            f"You are an Elite SEO Keyword Strategist for RankForge.\n\n"
            f"STRATEGIC BRAIN PATTERNS (APPLY MANDATORY):\n{recalled_summary}\n\n"
            f"RESEARCH DATA FOR '{topic}':\n"
            f"- Trends: {', '.join(trends[:5])}\n"
            f"- Questions: {', '.join(questions[:5])}\n\n"
            f"MANDATE: The strategic pattern engine has identified '{preferred_intent}' intent as the highest 30-day rank mover. "
            f"You MUST select a primary keyword with '{preferred_intent}' search intent.\n\n"
            "Return ONLY a JSON object with keys:\n"
            "- primary_keyword (string: highest-intent main target keyword)\n"
            "- secondary_keywords (array of 6 high-relevance supporting keywords)\n"
            "- difficulty_score (integer 0-100 based on competitive density)\n"
            f"- intent (must be '{preferred_intent}' or match search context)\n"
            "- clusters (array of 3 sub-arrays, each with 2 related semantic phrases)\n"
            "Example: {\"primary_keyword\":\"...\", \"secondary_keywords\":[\"...\"], \"difficulty_score\":45, \"intent\":\"commercial\", \"clusters\":[[\"...\",\"...\"],[\"...\",\"...\"],[\"...\",\"...\"]]}"
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
        data.setdefault("intent", preferred_intent)
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
            content=f"Identified '{data['primary_keyword']}' (Intent: {data['intent']}, Difficulty: {data['difficulty_score']}). Derived using {preferred_intent} pattern.",
            source_type="keyword_agent",
            confidence=intent_weight
        )

        await brain.remember(
            website_id=self.website_id,
            memory_type="experience",
            title=f"Clustering: {data['primary_keyword']}",
            content=f"Created 3 sub-clusters for '{data['primary_keyword']}'. Secondaries: {', '.join(data['secondary_keywords'][:3])}.",
            source_type="keyword_agent",
            confidence=0.90
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
