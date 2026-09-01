import logging
from typing import Optional, Dict, Any
import json
import httpx
from bs4 import BeautifulSoup
try:
    from crewai.tools import BaseTool
except ImportError:
    try:
        from crewai_tools import BaseTool  # type: ignore
    except ImportError:
        class BaseTool:  # fallback stub for py_compile without crewai
            name: str = ""
            description: str = ""
            def _run(self, *a, **kw):
                raise NotImplementedError("crewai not installed")
from pydantic import BaseModel, Field

from backend.database import get_supabase

logger = logging.getLogger("backend.tools.crawlee")

try:
    from crawlee.crawlers import BeautifulSoupCrawler
    CRAWLEE_AVAILABLE = True
except ImportError:
    CRAWLEE_AVAILABLE = False
    logger.info("crawlee not available — using httpx fallback crawler")


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "error": json.dumps({"real_api_called": real_api}),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


class CrawleeInput(BaseModel):
    url: str = Field(description="URL to crawl")


class CrawleeTool(BaseTool):
    name: str = "crawlee"
    description: str = "Crawls a page using Crawlee or httpx fallback and returns extracted content"
    args_schema: type[BaseModel] = CrawleeInput
    _website_id: Optional[str] = None
    _agent_name: str = "unknown"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    async def crawl(self, url: str) -> dict:
        return await self._crawl_with_httpx(url)

    async def _crawl_with_httpx(self, url: str) -> dict:
        """Fallback crawler using httpx + BeautifulSoup."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RankForge/2.0"}
            async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=12.0) as client:
                response = await client.get(url, headers=headers)
                
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else ""
            meta_desc_tag = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta_desc_tag.get("content", "") if meta_desc_tag else ""
            h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
            h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
            links = [a.get("href") for a in soup.find_all("a", href=True)]
            
            return {
                "url": url,
                "title": title,
                "meta_description": meta_desc,
                "h1": h1s,
                "h2": h2s,
                "content": " ".join(paragraphs[:25]),
                "links": links[:50],
                "status": "success",
            }
        except Exception as e:
            return {"url": url, "status": "error", "error": str(e)}

    async def _run(self, url: str) -> str:
        if not url:
            return "# Error: No URL provided"
        
        if not url.startswith(("http://", "https://")):
            _log_proof(self._website_id or "", self._agent_name, "crawlee", "blocked", "ssrf_protection")
            return f"# Error: Invalid URL scheme for {url}"
        
        if "localhost" in url or "127.0.0.1" in url or "0.0.0.0" in url:
            _log_proof(self._website_id or "", self._agent_name, "crawlee", "blocked", "ssrf_protection")
            return f"# Error: Blocked internal URL for {url}"
        
        res = await self._crawl_with_httpx(url)
        _log_proof(self._website_id or "", self._agent_name, "crawlee", "httpx_crawl", "crawl_page")
        return json.dumps(res, indent=2)
