"""
backend/services/web_research_provider.py
REAL WebResearchProvider - TinyFish-ready abstraction
Wraps TinyFish (free) -> Serper (paid) -> Tavily
GOOD FIT: Search/web discovery, competitor research, JS-heavy pages
BAD FIT: GSC performance, indexing status, WP publishing, internal DB calcs
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ResearchResult:
    source: str
    status: str
    data: Any
    provenance: str
    fetched_at: str
    cost_cents: int = 0
    evidence: Optional[Dict] = None

class WebResearchProvider:
    def __init__(self):
        from .tinyfish_service import get_tinyfish_service
        try:
            from .serper_service import SerperService
            self.serper = SerperService() if os.getenv("SERPER_API_KEY") else None
        except:
            self.serper = None
        from .tinyfish_service import get_tinyfish_service
        self.tinyfish = get_tinyfish_service()
        self.daily_cost_cents = 0
        self.daily_cap_cents = int(os.getenv("WEB_RESEARCH_DAILY_CAP_CENTS", "500"))
        self.cache: Dict[str, ResearchResult] = {}

    def _check_quota(self) -> bool:
        if self.daily_cost_cents >= self.daily_cap_cents:
            logger.warning(f"[WebResearchProvider] Daily cap ${self.daily_cap_cents/100} reached")
            return False
        return True

    async def search(self, query: str, limit: int = 10, use_tinyfish_first: bool = True, website_id: Optional[str] = None) -> ResearchResult:
        cache_key = f"search:{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        if not self._check_quota():
            return ResearchResult(source="web_research_provider", status="degraded", data={"organic": [], "reason": "Daily cost cap reached"}, provenance="observed", fetched_at=datetime.utcnow().isoformat())
        if use_tinyfish_first and self.tinyfish.is_configured:
            result = await self.tinyfish.search(query, limit=limit)
            if result["status"] == "success" and result.get("organic"):
                rr = ResearchResult(source="tinyfish_search", status="success", data=result, provenance="observed", fetched_at=result["fetched_at"], cost_cents=0, evidence={"query": query, "provider": "tinyfish_search"})
                self.cache[cache_key] = rr
                return rr
        if self.serper and hasattr(self.serper, 'is_configured') and self.serper.is_configured():
            try:
                serper_result = await self.serper.search(query, num_results=limit)
                if serper_result.get("organic"):
                    self.daily_cost_cents += 1
                    rr = ResearchResult(source="serper", status="success", data=serper_result, provenance="observed", fetched_at=datetime.utcnow().isoformat(), cost_cents=1, evidence={"query": query, "provider": "serper"})
                    self.cache[cache_key] = rr
                    return rr
            except Exception as e:
                logger.warning(f"Serper failed: {e}")
        return ResearchResult(source="web_research_provider", status="degraded", data={"organic": [], "reason": "All search providers failed"}, provenance="observed", fetched_at=datetime.utcnow().isoformat(), evidence={"query": query})

    async def fetch(self, urls: List[str], render_js: bool = True, website_id: Optional[str] = None) -> ResearchResult:
        if not urls:
            return ResearchResult(source="web_research_provider", status="success", data={"results": []}, provenance="observed", fetched_at=datetime.utcnow().isoformat())
        if self.tinyfish.is_configured:
            result = await self.tinyfish.fetch(urls, format="markdown")
            if result["status"] == "success" and result.get("results"):
                return ResearchResult(source="tinyfish_fetch", status="success", data=result, provenance="observed", fetched_at=result["fetched_at"], cost_cents=0, evidence={"urls": urls, "provider": "tinyfish_fetch", "token_efficient": True})
        return ResearchResult(source="web_research_provider", status="degraded", data={"results": [], "reason": "TinyFish not configured"}, provenance="observed", fetched_at=datetime.utcnow().isoformat(), evidence={"urls": urls})

    async def browser_task(self, url: str, goal: str, max_steps: int = 10, website_id: Optional[str] = None) -> ResearchResult:
        if not self._check_quota():
            return ResearchResult(source="web_research_provider", status="degraded", data={"reason": "Daily cost cap"}, provenance="observed", fetched_at=datetime.utcnow().isoformat())
        if not self.tinyfish.is_configured:
            return ResearchResult(source="web_research_provider", status="degraded", data={"reason": "TINYFISH_API_KEY not configured"}, provenance="observed", fetched_at=datetime.utcnow().isoformat())
        result = await self.tinyfish.agent_run(url, goal, max_steps=max_steps)
        if result["status"] == "success":
            self.daily_cost_cents += 5
            return ResearchResult(source="tinyfish_agent", status="success", data=result, provenance="observed", fetched_at=result["fetched_at"], cost_cents=5, evidence={"url": url, "goal": goal, "provider": "tinyfish_agent"})
        return ResearchResult(source="tinyfish_agent", status="failed", data=result, provenance="observed", fetched_at=result["fetched_at"], evidence={"url": url, "goal": goal})

_web_provider: Optional[WebResearchProvider] = None
def get_web_research_provider() -> WebResearchProvider:
    global _web_provider
    if _web_provider is None:
        _web_provider = WebResearchProvider()
    return _web_provider
