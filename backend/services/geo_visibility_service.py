import json
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("backend.services.geo_visibility")


class GeoVisibilityService:
    """Check GEO (Generative Engine Optimization) visibility using LLM evaluation."""

    def __init__(self, website_id: str = None):
        self.website_id = website_id
        self.supabase = None

    def _get_supabase(self):
        if not self.supabase:
            from ..database import get_supabase
            self.supabase = get_supabase()
        return self.supabase

    async def check_geo_visibility(
        self, keyword: str, website_id: str = None
    ) -> Dict[str, Any]:
        """Evaluate whether content for a keyword would be cited by AI engines."""
        wid = website_id or self.website_id
        if not wid:
            return {"error": "website_id required"}

        from ..database import call_nim_llm

        prompt = (
            f"Given the search keyword '{keyword}', assess if a helpful authoritative summary "
            "would likely be cited by AI search engines (Perplexity, ChatGPT, Google AI Overview). "
            "Respond ONLY with JSON: {\"was_cited\": true/false, \"confidence\": 0-1, \"reason\": \"...\"}"
        )
        try:
            raw = await call_nim_llm(prompt, website_id=wid)
            import json as _json

            data = _json.loads(raw)
        except Exception as e:
            logger.warning(f"Geo visibility LLM failed for {keyword}: {e}")
            data = {"was_cited": False, "confidence": 0.0, "reason": str(e)}

        supabase = self._get_supabase()
        try:
            supabase.table("geo_visibility_logs").insert(
                {
                    "id": str(__import__("uuid").uuid4()),
                    "website_id": wid,
                    "prompt": keyword,
                    "ai_engine": "google_ai_overview",
                    "was_cited": bool(data.get("was_cited")),
                    "citation_text": str(data.get("reason", ""))[:500],
                    "checked_at": datetime.utcnow().isoformat(),
                }
            ).execute()
        except Exception as e:
            logger.warning(f"Geo visibility log insert failed: {e}")

        return data

    async def get_visibility_history(
        self, keyword: str, website_id: str = None
    ) -> List[Dict]:
        wid = website_id or self.website_id
        supabase = self._get_supabase()
        rows = (
            supabase.table("geo_visibility_logs")
            .select("*")
            .eq("website_id", wid)
            .eq("prompt", keyword)
            .order("checked_at", desc=True)
            .limit(20)
            .execute()
            .data
            or []
        )
        return rows
