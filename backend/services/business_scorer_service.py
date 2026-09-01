from datetime import datetime
import json
import logging
from typing import Any, Dict, Optional

from database import call_nim_llm, get_supabase
from services.reporting_service import report_problem

logger = logging.getLogger("backend.services.business_scorer_service")


class BusinessScorerService:
    """AGENT 3 - Score keyword business potential 0-3 using NVIDIA NIM LLM with knowledge context."""

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id

    async def score(self, keyword: str) -> Dict[str, Any]:
        """Score a keyword's business potential (0-3) using LLM and fetch knowledge_sources for context."""
        supabase = get_supabase()

        knowledge_context = ""
        if self.website_id:
            sources = (
                supabase.table("knowledge_sources")
                .select("title,content_extracted")
                .eq("website_id", self.website_id)
                .eq("is_verified", True)
                .limit(20)
                .execute()
                .data
                or []
            )
            if sources:
                knowledge_context = "\n\n".join(
                    f"Source: {s.get('title', '')}\n{s.get('content_extracted', '')[:500]}"
                    for s in sources
                )

        prompt = f"""You are an SEO business strategist. Score the business potential of the following keyword on a scale of 0-3.

Rules:
- 0 = Zero business value, purely informational, no revenue path
- 1 = Low business value, indirect revenue path, generic awareness
- 2 = Medium business value, clear revenue path, customer intent
- 3 = High business value, strong commercial intent, direct revenue path

Keyword: {keyword}

Business Context:
{knowledge_context if knowledge_context else "No additional business knowledge available."}

Return ONLY valid JSON with this exact format:
{{"score": <0-3>, "reason": "<short explanation>"}}"""

        try:
            raw = await call_nim_llm(prompt, website_id=self.website_id)

            cleaned = raw.strip()
            if cleaned.startswith("```"):
                parts = cleaned.split("```")
                if len(parts) >= 2:
                    cleaned = parts[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            score = int(result.get("score", 1))
            reason = str(result.get("reason", ""))
            score = max(0, min(3, score))

            if score <= 1:
                await report_problem(
                    website_id=self.website_id,
                    alert_type="keyword_opportunity",
                    severity="high",
                    title=f"Low business potential keyword blocked: {keyword}",
                    description=f"Score={score}. Pipeline blocked for keyword: {keyword}. Reason: {reason}",
                    data={
                        "keyword": keyword,
                        "score": score,
                        "reason": reason,
                        "action": "pipeline_blocked",
                    },
                    source_monitor="business_scorer_service",
                )

            return {
                "keyword": keyword,
                "score": score,
                "reason": reason,
                "pipeline_blocked": score <= 1,
                "source": "llm",
            }

        except Exception as e:
            logger.error(f"Business scoring failed for keyword '{keyword}': {e}")
            return {
                "keyword": keyword,
                "score": 0,
                "reason": f"Scoring failed: {str(e)}",
                "pipeline_blocked": True,
                "source": "llm",
            }


async def score_keyword_business_potential(website_id: str, keyword: str) -> Dict[str, Any]:
    """Standalone function for AGENT 3."""
    service = BusinessScorerService(website_id)
    return await service.score(keyword)
