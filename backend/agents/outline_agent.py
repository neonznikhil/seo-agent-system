from datetime import datetime
import logging
from typing import Dict, Any, List

logger = logging.getLogger("backend.agents.outline_agent")


class OutlineAgent:
    """
    OutlineAgent - generates blog outline with H1, H2s, FAQ from keyword + research data.
    Uses NIM LLM for outline generation.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, keyword: str, research_data: Dict[str, Any] = None) -> Dict[str, Any]:
        from ..database import call_nim_llm, get_supabase

        research_data = research_data or {}
        questions = research_data.get("questions", [
            f"What is {keyword}?",
            f"How does {keyword} work?",
            f"Why {keyword}?",
            f"Best {keyword} practices?",
            f"{keyword} examples?",
        ])
        trends = research_data.get("trends", [f"{keyword} trends", f"{keyword} tips"])

        prompt = (
            f"Create a blog outline for keyword: '{keyword}'.\n"
            f"Key questions: {', '.join(questions[:5])}\n"
            f"Trends: {', '.join(trends[:5])}\n\n"
            "Return ONLY a JSON object with keys:\n"
            "- h1 (string, main title with keyword)\n"
            "- h2s (array of 6 strings, section headings)\n"
            "- faq (array of 4 FAQ strings, each like 'Q: ...? A: ...')\n"
            "- intro_summary (string, 1-2 sentences)\n"
            "- conclusion_cta (string, 1-2 sentences)\n"
            "Example: {\"h1\":\"...\", \"h2s\":[\"...\",\"...\"], \"faq\":[\"Q: ...? A: ...\",\"...\"], \"intro_summary\":\"...\", \"conclusion_cta\":\"...\"}"
        )
        try:
            raw = await call_nim_llm(prompt, system="You are an expert blog outline architect. Return only valid JSON.", website_id=self.website_id)
            data = self._parse_json(raw)
        except Exception as e:
            logger.warning("NIM outline generation failed, using fallback: %s", e)
            data = {
                "h1": f"{keyword}: Complete Guide",
                "h2s": [
                    f"What is {keyword}?",
                    f"How {keyword} Works",
                    f"Best Practices for {keyword}",
                    f"Common {keyword} Mistakes",
                    f"{keyword} Tools and Resources",
                    f"Future of {keyword}",
                ],
                "faq": [
                    f"Q: What is {keyword}? A: {keyword} is a key topic.",
                    f"Q: How does {keyword} work? A: It works by implementing core principles.",
                    f"Q: Why choose {keyword}? A: It offers measurable benefits.",
                    f"Q: What are best practices? A: Follow industry standards.",
                ],
                "intro_summary": f"Learn everything about {keyword} in this comprehensive guide.",
                "conclusion_cta": f"Ready to master {keyword}? Start implementing these strategies today.",
            }

        data.setdefault("h1", f"{keyword}: Complete Guide")
        data.setdefault("h2s", [f"What is {keyword}?", f"How {keyword} Works", f"Best Practices for {keyword}"])
        data.setdefault("faq", [])
        data.setdefault("intro_summary", "")
        data.setdefault("conclusion_cta", "")
        if not data.get("faq"):
            data["faq"] = [f"Q: What is {keyword}? A: {keyword} is important.", f"Q: How to start? A: Follow this guide."]
        while len(data["h2s"]) < 5:
            data["h2s"].append(f"{keyword} Strategy {len(data['h2s'])+1}")

        try:
            get_supabase().table("outlines").insert({
                "website_id": self.website_id,
                "topic": keyword,
                "outline_data": data,
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


def create_outline_agent(website_id: str) -> OutlineAgent:
    return OutlineAgent(website_id)
