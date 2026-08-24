import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = logging.getLogger("backend.services.serper_service")

# Global state tracker for connector health
_CONNECTOR_STATE = {
    "enabled": True,
    "last_successful_call": None,
    "last_error": None,
    "total_calls": 0,
    "successful_calls": 0,
    "failed_calls": 0,
    "credits_remaining": None,
}


class SerperService:
    """Real-time search backbone for the SEO agent group via Serper.dev API.
    
    Fallback chain:
    1. Serper.dev API (Primary)
    2. Tavily API (Secondary)
    3. Crawlee SERP Scrape (Tertiary)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY", "")
        self.tavily_key = os.getenv("TAVILY_API_KEY", "")
        self.base_url = "https://google.serper.dev"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def is_enabled(self) -> bool:
        return _CONNECTOR_STATE.get("enabled", True)

    def toggle(self, enabled: bool) -> bool:
        _CONNECTOR_STATE["enabled"] = enabled
        logger.info(f"[SerperService] Connector toggled: {'ENABLED' if enabled else 'DISABLED'}")
        return _CONNECTOR_STATE["enabled"]

    def _log_failure_to_supabase(self, action: str, payload: Dict[str, Any], error: str):
        """Persist API failures to tasks table for self-healing and observability."""
        try:
            from ..database import get_supabase
            supabase = get_supabase()
            supabase.table("tasks").insert({
                "agent_name": "serper_service",
                "action": action,
                "payload": payload,
                "result": {"error": error[:500]},
                "status": "failed",
                "real_api_called": "serper.dev",
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.debug(f"Failed to log task failure to Supabase: {e}")

    # ---------------------------------------------------------
    # 1. SERP Search Method with Tenacity Retry
    # ---------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def _call_serper_search_api(
        self,
        query: str,
        location: Optional[str] = None,
        language: Optional[str] = "en",
        num: int = 10,
        search_type: str = "search"
    ) -> Dict[str, Any]:
        """Execute raw HTTP call to Serper.dev /search or specified endpoint."""
        url = f"{self.base_url}/{search_type}"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        body: Dict[str, Any] = {
            "q": query,
            "num": max(1, min(num, 50))
        }
        if location:
            body["gl"] = location.lower() if len(location) == 2 else "us"
            body["location"] = location
        if language:
            body["hl"] = language

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    async def search(
        self,
        query: str,
        location: Optional[str] = None,
        language: Optional[str] = "en",
        num: int = 10,
        search_type: str = "search",
        auto_fallback: bool = True
    ) -> Dict[str, Any]:
        """Primary search call returning structured organic, PAA, answerBox, knowledgeGraph, relatedSearches.

        Fallback order: Serper.dev -> Tavily -> Crawlee scrape. When every source
        fails this returns EMPTY organic results with a structured error â€”
        fabricated SERP rows are never generated.
        """
        _CONNECTOR_STATE["total_calls"] += 1
        payload = {"q": query, "location": location, "language": language, "num": num, "type": search_type}

        # Step 1: Serper.dev Primary
        if self.is_configured() and self.is_enabled():
            try:
                data = await self._call_serper_search_api(
                    query=query, location=location, language=language, num=num, search_type=search_type
                )
                _CONNECTOR_STATE["successful_calls"] += 1
                _CONNECTOR_STATE["last_successful_call"] = datetime.utcnow().isoformat()
                _CONNECTOR_STATE["last_error"] = None

                # Normalize response keys
                return {
                    "source": "serper.dev",
                    "query": query,
                    "organic": data.get("organic", []),
                    "peopleAlsoAsk": data.get("peopleAlsoAsk", []),
                    "knowledgeGraph": data.get("knowledgeGraph", {}),
                    "answerBox": data.get("answerBox", {}),
                    "relatedSearches": data.get("relatedSearches", []),
                    "credits_used": 1,
                    "raw": data
                }
            except Exception as e:
                error_msg = f"Serper search failed for '{query}': {str(e)}"
                logger.warning(error_msg)
                _CONNECTOR_STATE["failed_calls"] += 1
                _CONNECTOR_STATE["last_error"] = error_msg
                self._log_failure_to_supabase("search", payload, str(e))
                if not auto_fallback:
                    raise

        # Step 2: Fallback to Tavily
        if auto_fallback and self.tavily_key:
            try:
                logger.info(f"[SerperFallback] Trying Tavily for query '{query}'")
                tavily_res = await self._fallback_tavily_search(query, num=num)
                if tavily_res and tavily_res.get("organic"):
                    return tavily_res
            except Exception as e:
                logger.warning(f"Tavily fallback also failed: {e}")

        # Step 3: Fallback to Crawlee SERP scrape
        if auto_fallback:
            try:
                logger.info(f"[SerperFallback] Trying Crawlee SERP scrape for '{query}'")
                crawlee_res = await self._fallback_crawlee_search(query)
                if crawlee_res and crawlee_res.get("organic"):
                    return crawlee_res
            except Exception as e:
                logger.warning(f"Crawlee fallback also failed: {e}")

        # All sources unavailable â€” honest empty result. Callers must treat an
        # empty organic list as 'no live SERP data', never invent competitors.
        error_detail = _CONNECTOR_STATE.get("last_error") or (
            "No search source available: configure SERPER_API_KEY in Connectors "
            "or ensure the Crawlee scraper is functional."
        )
        return {
            "source": "unavailable",
            "query": query,
            "organic": [],
            "peopleAlsoAsk": [],
            "knowledgeGraph": {},
            "answerBox": {},
            "relatedSearches": [],
            "credits_used": 0,
            "error": error_detail[:300],
        }

    # ---------------------------------------------------------
    # 2. News Search Method with Tenacity Retry
    # ---------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    async def _call_serper_news_api(
        self,
        query: str,
        location: Optional[str] = None,
        language: Optional[str] = "en",
        num: int = 10
    ) -> Dict[str, Any]:
        """Execute raw HTTP call to Serper.dev /news endpoint."""
        url = f"{self.base_url}/news"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        body: Dict[str, Any] = {
            "q": query,
            "num": max(1, min(num, 50))
        }
        if location:
            body["gl"] = location.lower() if len(location) == 2 else "us"
        if language:
            body["hl"] = language

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    async def news(
        self,
        query: str,
        location: Optional[str] = None,
        language: Optional[str] = "en",
        num: int = 10,
        auto_fallback: bool = True
    ) -> Dict[str, Any]:
        """Query Serper.dev /news for trend detection and competitor content monitoring."""
        _CONNECTOR_STATE["total_calls"] += 1
        payload = {"q": query, "location": location, "language": language, "num": num, "endpoint": "news"}

        if self.is_configured() and self.is_enabled():
            try:
                data = await self._call_serper_news_api(
                    query=query, location=location, language=language, num=num
                )
                _CONNECTOR_STATE["successful_calls"] += 1
                _CONNECTOR_STATE["last_successful_call"] = datetime.utcnow().isoformat()
                _CONNECTOR_STATE["last_error"] = None

                news_items = data.get("news", [])
                return {
                    "source": "serper.dev_news",
                    "query": query,
                    "news": news_items,
                    "total_results": len(news_items),
                    "raw": data
                }
            except Exception as e:
                error_msg = f"Serper news failed for '{query}': {str(e)}"
                logger.warning(error_msg)
                _CONNECTOR_STATE["failed_calls"] += 1
                _CONNECTOR_STATE["last_error"] = error_msg
                self._log_failure_to_supabase("news", payload, str(e))
                if not auto_fallback:
                    raise

        # Fallback to general search if news endpoint fails
        if auto_fallback:
            search_res = await self.search(f"{query} news", location=location, language=language, num=num)
            organic = search_res.get("organic") or []
            if not organic:
                return {"source": "unavailable", "query": query, "news": [],
                        "total_results": 0, "error": search_res.get("error")}
            # Derive news-shaped items strictly from real organic results
            derived_news = [
                {
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                    "date": item.get("date"),
                    "source": (
                        item.get("link", "").split("/")[2]
                        if "//" in (item.get("link") or "") else "Web"
                    ),
                }
                for item in organic[:num]
            ]
            return {
                "source": "search_derived_news",
                "query": query,
                "news": derived_news,
                "total_results": len(derived_news)
            }

        return {"source": "empty", "query": query, "news": [], "total_results": 0}

    # ---------------------------------------------------------
    # 3. Connector Health & Credits Probing
    # ---------------------------------------------------------
    async def check_status(self) -> Dict[str, Any]:
        """Ping Serper.dev with a lightweight test query to verify key validity and health."""
        if not self.api_key:
            return {
                "connected": False,
                "status": "not_configured",
                "enabled": self.is_enabled(),
                "api_key_valid": False,
                "api_key_masked": None,
                "credits_remaining": 0,
                "last_successful_call": _CONNECTOR_STATE.get("last_successful_call"),
                "last_error": "SERPER_API_KEY environment variable is not configured",
                "message": "Serper API key not configured. Add SERPER_API_KEY in .env or Connectors dashboard."
            }

        masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "***"

        try:
            url = f"{self.base_url}/search"
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }
            body = {"q": "rankforge ping test", "num": 1}

            start_t = time.time()
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(url, headers=headers, json=body)
                elapsed_ms = int((time.time() - start_t) * 1000)

            if response.status_code == 200:
                _CONNECTOR_STATE["last_successful_call"] = datetime.utcnow().isoformat()
                _CONNECTOR_STATE["last_error"] = None
                return {
                    "connected": True,
                    "status": "active",
                    "enabled": self.is_enabled(),
                    "api_key_valid": True,
                    "api_key_masked": masked_key,
                    "latency_ms": elapsed_ms,
                    "credits_remaining": _CONNECTOR_STATE.get("credits_remaining"),
                    "last_successful_call": _CONNECTOR_STATE["last_successful_call"],
                    "total_calls": _CONNECTOR_STATE["total_calls"],
                    "successful_calls": _CONNECTOR_STATE["successful_calls"],
                    "failed_calls": _CONNECTOR_STATE["failed_calls"],
                    "message": f"Serper.dev live & healthy (Response time: {elapsed_ms}ms) âœ…"
                }
            elif response.status_code in (401, 403):
                _CONNECTOR_STATE["last_error"] = f"Invalid API Key (HTTP {response.status_code})"
                return {
                    "connected": False,
                    "status": "unauthorized",
                    "enabled": self.is_enabled(),
                    "api_key_valid": False,
                    "api_key_masked": masked_key,
                    "credits_remaining": 0,
                    "last_successful_call": _CONNECTOR_STATE.get("last_successful_call"),
                    "last_error": _CONNECTOR_STATE["last_error"],
                    "message": "Serper API key rejected. Please check your key at serper.dev."
                }
            elif response.status_code == 429:
                _CONNECTOR_STATE["last_error"] = "Rate limit / Out of credits"
                return {
                    "connected": False,
                    "status": "rate_limited",
                    "enabled": self.is_enabled(),
                    "api_key_valid": True,
                    "api_key_masked": masked_key,
                    "credits_remaining": 0,
                    "last_successful_call": _CONNECTOR_STATE.get("last_successful_call"),
                    "last_error": "Serper credit limit reached (HTTP 429)",
                    "message": "Serper credits exhausted. Falling back to Tavily & Crawlee."
                }
            else:
                return {
                    "connected": False,
                    "status": "error",
                    "enabled": self.is_enabled(),
                    "api_key_valid": False,
                    "api_key_masked": masked_key,
                    "last_error": f"HTTP {response.status_code}: {response.text[:120]}",
                    "message": f"Serper returned status {response.status_code}"
                }
        except Exception as e:
            _CONNECTOR_STATE["last_error"] = str(e)
            return {
                "connected": False,
                "status": "unreachable",
                "enabled": self.is_enabled(),
                "api_key_valid": False,
                "api_key_masked": masked_key,
                "last_error": str(e),
                "message": f"Serper connection error: {str(e)}"
            }

    # ---------------------------------------------------------
    # 4. Fallback Helpers (Tavily & Crawlee)
    # ---------------------------------------------------------
    async def _fallback_tavily_search(self, query: str, num: int = 10) -> Optional[Dict[str, Any]]:
        """Secondary fallback using Tavily search."""
        if not self.tavily_key:
            return None
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.tavily_key,
            "query": query,
            "max_results": min(num, 10),
            "include_answer": True
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                organic = [
                    {
                        "title": r.get("title"),
                        "link": r.get("url"),
                        "snippet": r.get("content"),
                        "position": idx + 1
                    }
                    for idx, r in enumerate(data.get("results", []))
                ]
                return {
                    "source": "tavily_fallback",
                    "query": query,
                    "organic": organic,
                    "peopleAlsoAsk": [],
                    "answerBox": {"answer": data.get("answer")} if data.get("answer") else {},
                    "relatedSearches": [],
                    "credits_used": 1
                }
        return None

    async def _fallback_crawlee_search(self, query: str) -> Optional[Dict[str, Any]]:
        """Tertiary fallback using Crawlee SERP scraping."""
        try:
            from .crawlee_service import CrawleeService
            crawler = CrawleeService()
            landscape = await crawler.extract_serp_landscape(query)
            if landscape and landscape.get("top_pages"):
                organic = [
                    {
                        "title": p.get("title", f"Result {idx+1}"),
                        "link": p.get("url"),
                        "snippet": p.get("meta_description", ""),
                        "position": p.get("position", idx + 1)
                    }
                    for idx, p in enumerate(landscape.get("top_pages", []))
                ]
                return {
                    "source": "crawlee_fallback",
                    "query": query,
                    "organic": organic,
                    "peopleAlsoAsk": [{"question": q} for q in landscape.get("questions", [])],
                    "relatedSearches": [{"query": t} for t in landscape.get("trends", [])],
                    "credits_used": 0
                }
        except Exception as e:
            logger.debug(f"Crawlee SERP fallback failed: {e}")
        return None

    # ---------------------------------------------------------
    # 4. Specialized Serper.dev API Types (Upgrade 8)
    # ---------------------------------------------------------
    async def scholar(self, query: str, num: int = 5) -> Dict[str, Any]:
        """Academic search via Serper Scholar API for fact-checking statistical claims."""
        if not self.is_configured():
            return {"source": "unavailable", "organic": [],
                    "error": "Serper API key not configured â€” scholar search unavailable"}

        url = f"{self.base_url}/scholar"
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": max(1, min(num, 20))}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Serper Scholar HTTP {res.status_code}")
        except Exception as e:
            logger.warning(f"Serper Scholar error: {e}")

        # Fallback to search with scholar site restriction
        result = await self.search(f"{query} site:edu OR site:gov", num=num)
        if not result.get("organic"):
            return {"source": "unavailable", "organic": [], "error": "Scholar and fallback search unavailable"}
        return result

    async def images(self, query: str, num: int = 6) -> Dict[str, Any]:
        """Search relevant images via Serper Images API."""
        if not self.is_configured():
            return {"source": "unavailable", "images": [],
                    "error": "Serper API key not configured â€” image search unavailable"}

        url = f"{self.base_url}/images"
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": max(1, min(num, 20))}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()
        except Exception as e:
            logger.warning(f"Serper Images error: {e}")

        return {"source": "unavailable", "images": []}

    async def maps(self, query: str, location: Optional[str] = None) -> Dict[str, Any]:
        """Local search via Serper Places/Maps API for GEO visibility."""
        if not self.is_configured():
            return {"source": "unavailable", "places": [],
                    "error": "Serper API key not configured â€” places search unavailable"}

        url = f"{self.base_url}/places"
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query}
        if location:
            payload["location"] = location

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()
        except Exception as e:
            logger.warning(f"Serper Places error: {e}")

        return {"source": "unavailable", "places": []}

    async def autocomplete(self, query: str) -> Dict[str, Any]:
        """Google Autocomplete expansions for seed keyword expansion."""
        if not self.is_configured():
            return {"source": "unavailable", "suggestions": [],
                    "error": "Serper API key not configured â€” autocomplete unavailable"}

        url = f"{self.base_url}/autocomplete"
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    data.setdefault("source", "serper.dev")
                    return data
        except Exception as e:
            logger.warning(f"Serper Autocomplete error: {e}")

        return {"source": "unavailable", "suggestions": []}

    # ---------------------------------------------------------
    # 5. Key verification (Connectors page save flow)
    # ---------------------------------------------------------
    async def verify_key(self, api_key: str) -> bool:
        """Validate a Serper.dev key by issuing a real 1-result search."""
        if not api_key or len(api_key.strip()) < 8:
            return False
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self.base_url}/search",
                    headers={"X-API-KEY": api_key.strip(), "Content-Type": "application/json"},
                    json={"q": "test", "num": 1},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[SerperService] verify_key error: {e}")
            return False


# Global singleton instance
serper_service = SerperService()

