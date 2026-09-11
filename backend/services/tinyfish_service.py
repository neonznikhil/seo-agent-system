"""
backend/services/tinyfish_service.py
REAL TinyFish Integration - No Mocks, Production Ready
Search and Fetch are FREE, Agent is metered
Docs: https://docs.tinyfish.ai/ | Key: https://agent.tinyfish.ai/api-keys
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "")
SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
AGENT_URL_SYNC = "https://agent.tinyfish.ai/v1/automation/run"

class TinyFishService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TINYFISH_API_KEY
        self.is_configured = bool(self.api_key and len(self.api_key) > 10)
        self.timeout = httpx.Timeout(30.0, read=60.0)
        if not self.is_configured:
            logger.warning("[TinyFish] TINYFISH_API_KEY not set - degraded, not fake")

    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    async def search(self, query: str, limit: int = 10, recency: Optional[str] = None) -> Dict[str, Any]:
        """Real TinyFish Search API - free, structured JSON, replaces Serper credits burn"""
        if not self.is_configured:
            return {"source": "tinyfish_search", "status": "degraded", "reason": "TINYFISH_API_KEY not configured", "organic": [], "fetched_at": datetime.utcnow().isoformat(), "provenance": "observed"}
        try:
            params = {"query": query, "limit": limit}
            if recency:
                params["recency"] = recency
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(SEARCH_URL, params=params, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                organic = []
                results = data.get("results", []) or data.get("organic", [])
                for item in results[:limit]:
                    organic.append({
                        "title": item.get("title", ""),
                        "link": item.get("url", "") or item.get("link", ""),
                        "snippet": item.get("snippet", "") or item.get("description", ""),
                        "position": item.get("position", 0),
                        "source": "tinyfish_search"
                    })
                return {"source": "tinyfish_search", "status": "success", "organic": organic, "total_results": len(organic), "query": query, "fetched_at": datetime.utcnow().isoformat(), "provenance": "observed", "raw": data}
        except Exception as e:
            logger.error(f"[TinyFish Search] Failed: {e}")
            return {"source": "tinyfish_search", "status": "failed", "reason": str(e), "organic": [], "fetched_at": datetime.utcnow().isoformat(), "provenance": "observed"}

    async def fetch(self, urls: List[str], format: str = "markdown") -> Dict[str, Any]:
        """Real TinyFish Fetch API - free, JS-rendered, clean markdown, replaces httpx.get + BS that fails on SPA"""
        if not self.is_configured:
            return {"source": "tinyfish_fetch", "status": "degraded", "reason": "TINYFISH_API_KEY not configured", "results": [], "fetched_at": datetime.utcnow().isoformat(), "provenance": "observed"}
        if not urls:
            return {"source": "tinyfish_fetch", "status": "success", "results": []}
        urls = urls[:10]
        try:
            payload = {"urls": urls, "format": format}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(FETCH_URL, json=payload, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                results = []
                for item in data.get("results", []):
                    results.append({
                        "url": item.get("url", ""),
                        "markdown": item.get("markdown", "") or item.get("text", ""),
                        "html": item.get("html", ""),
                        "title": item.get("title", ""),
                        "status": "success" if item.get("markdown") else "empty",
                        "source": "tinyfish_fetch"
                    })
                return {"source": "tinyfish_fetch", "status": "success", "results": results, "fetched_at": datetime.utcnow().isoformat(), "provenance": "observed", "token_efficient": True}
        except Exception as e:
            logger.error(f"[TinyFish Fetch] Failed: {e}")
            return {"source": "tinyfish_fetch", "status": "failed", "reason": str(e), "results": [], "fetched_at": datetime.utcnow().isoformat(), "provenance": "observed"}

    async def fetch_single(self, url: str) -> Optional[str]:
        result = await self.fetch([url])
        if result["results"]:
            return result["results"][0].get("markdown")
        return None

    async def agent_run(self, url: str, goal: str, max_steps: int = 10, max_duration_seconds: int = 60) -> Dict[str, Any]:
        """Real TinyFish Agent API - autonomous multi-step browser, metered, use only where no stable API exists"""
        if not self.is_configured:
            return {"source": "tinyfish_agent", "status": "degraded", "reason": "TINYFISH_API_KEY not configured", "result": None, "fetched_at": datetime.utcnow().isoformat()}
        try:
            payload = {"url": url, "goal": goal, "agent_config": {"max_steps": max_steps, "max_duration_seconds": max_duration_seconds}}
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=max_duration_seconds+10)) as client:
                resp = await client.post(AGENT_URL_SYNC, json=payload, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                return {"source": "tinyfish_agent", "status": "success", "result": data.get("result") or data, "url": url, "goal": goal, "fetched_at": datetime.utcnow().isoformat(), "provenance": "observed", "evidence": {"url": url, "goal": goal, "fetched_at": datetime.utcnow().isoformat()}}
        except Exception as e:
            logger.error(f"[TinyFish Agent] Failed: {e}")
            return {"source": "tinyfish_agent", "status": "failed", "reason": str(e), "result": None, "fetched_at": datetime.utcnow().isoformat()}

_tinyfish_service: Optional[TinyFishService] = None
def get_tinyfish_service() -> TinyFishService:
    global _tinyfish_service
    if _tinyfish_service is None:
        _tinyfish_service = TinyFishService()
    return _tinyfish_service
