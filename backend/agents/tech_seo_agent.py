import json
import logging
from datetime import datetime
import httpx

from .tools.crawlee_tool import CrawleeTool
from ..database import get_supabase, call_nim_llm

logger = logging.getLogger("backend.agents.tech_seo_agent")


class TechSEOAgent:
    def __init__(self):
        pass

    async def check_sitemap(self, url: str) -> dict:
        url = url.rstrip("/")
        # Try multiple sitemap URLs
        sitemap_urls = [
            f"{url}/wp-sitemap.xml",
            f"{url}/sitemap.xml",
            f"{url}/sitemap_index.xml",
            f"{url}/sitemap-index.xml"
        ]
        
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True
        ) as client:
            for sitemap_url in sitemap_urls:
                try:
                    response = await client.get(sitemap_url)
                    if response.status_code == 200:
                        return {
                            "found": True,
                            "url": sitemap_url,
                            "status": "ok"
                        }
                except:
                    continue
        
        return {
            "found": False,
            "url": None,
            "status": "missing",
            "note": "No sitemap found at standard locations"
        }

    async def run_audit(self, website_id: str) -> dict:
        from ..routers.tech_seo import execute_tech_audit
        return await execute_tech_audit(website_id)


async def run_tech_seo_agent(website_id: str, base_url: str) -> dict:
    agent = TechSEOAgent()
    return await agent.run_audit(website_id)

