import logging
from typing import Optional
import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase

logger = logging.getLogger("backend.tools.crawlee")


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
    url: str = Field(description="URL to crawl with Crawlee")


class CrawleeTool(BaseTool):
    name: str = "crawlee"
    description: str = "Crawls a page using Crawlee Python and returns extracted content"
    args_schema: type[BaseModel] = CrawleeInput
    _website_id: Optional[str] = None
    _agent_name: str = "unknown"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, url: str) -> str:
        if not url:
            return "# Error: No URL provided"
        
        if not url.startswith(('http://', 'https://')):
            _log_proof(self._website_id or "", self._agent_name, "crawlee", "blocked", "ssrf_protection")
            return f"# Error: Invalid URL scheme for {url}"
        
        if 'localhost' in url or '127.0.0.1' in url or '0.0.0.0' in url:
            _log_proof(self._website_id or "", self._agent_name, "crawlee", "blocked", "ssrf_protection")
            return f"# Error: Blocked internal URL for {url}"
        
        try:
            import asyncio
            from ...services.crawlee_service import CrawleeService
            
            service = CrawleeService()
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(service.crawl_site_structure([url], max_requests=1))
            
            if result:
                page = result[0]
                content_parts = []
                if page.get('title'):
                    content_parts.append(f"# {page['title']}")
                if page.get('h1s'):
                    content_parts.extend([f"## {h1}" for h1 in page['h1s']])
                if page.get('h2s'):
                    content_parts.extend([f"### {h2}" for h2 in page['h2s'][:10]])
                content_parts.append(f"\n\n**Word count:** {page.get('word_count', 0)}")
                content_parts.append(f"\n**Links found:** {len(page.get('links', []))}")
                
                _log_proof(self._website_id or "", self._agent_name, "crawlee", "crawlee", "scrape")
                return "\n".join(content_parts)
            else:
                _log_proof(self._website_id or "", self._agent_name, "crawlee", "error", "no_data")
                return f"# Error: No content extracted from {url}"
            
        except ImportError:
            logger.error("Crawlee not installed - cannot fetch real data")
            _log_proof(self._website_id or "", self._agent_name, "crawlee", "error", "not_installed")
            return f"# Error: Crawlee service not available for {url}"
        except Exception as e:
            logger.error("Crawlee failed for %s: %s", url, e)
            _log_proof(self._website_id or "", self._agent_name, "crawlee", "error", str(e))
            return f"# Error: Crawl failed for {url}: {str(e)[:100]}"
