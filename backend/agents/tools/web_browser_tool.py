import logging
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio
import json
import re
from datetime import datetime

logger = logging.getLogger("backend.tools.web_browser_tool")


class WebBrowserInput(BaseModel):
    url: str = Field(description="URL to browse")
    wait_time: int = Field(default=5, description="Wait time in seconds for page load")
    extract: str = Field(default="content", description="What to extract: content, links, images, tables")


class WebBrowserTool(BaseTool):
    name: str = "web_browser"
    description: str = "Browse websites and extract real-time data. Can render JavaScript, extract links, images, tables, and structured content. For SEO research, competitor analysis, and data collection."
    args_schema: type[BaseModel] = WebBrowserInput
    _website_id: Optional[str] = None
    _agent_name: str = "web_browser"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, url: str, wait_time: int = 5, extract: str = "content") -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})
        
        try:
            from playwright.sync_api import sync_playwright
            from bs4 import BeautifulSoup
            import httpx
            
            result = {
                "url": url,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {}
            }
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                
                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(wait_time * 1000)
                    
                    if extract == "content":
                        content = page.inner_text("body")
                        result["data"]["content"] = content[:50000]
                    elif extract == "links":
                        links = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText, href: a.href}))")
                        result["data"]["links"] = links[:100]
                    elif extract == "images":
                        images = page.evaluate("Array.from(document.querySelectorAll('img')).map(img => ({alt: img.alt, src: img.src, width: img.width, height: img.height}))")
                        result["data"]["images"] = images[:50]
                    elif extract == "tables":
                        html = page.content()
                        soup = BeautifulSoup(html, 'lxml')
                        tables = []
                        for i, table in enumerate(soup.find_all('table')):
                            rows = []
                            for row in table.find_all('tr'):
                                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                                rows.append(cells)
                            if rows:
                                tables.append({"table_id": i, "rows": rows})
                        result["data"]["tables"] = tables[:10]
                    elif extract == "seo_data":
                        title = page.title()
                        meta_description = page.evaluate("document.querySelector('meta[name=\"description\"]').content || ''")
                        h1 = page.evaluate("document.querySelector('h1').innerText || ''")
                        canonical = page.evaluate("document.querySelector('link[rel=\"canonical\"]').href || ''")
                        result["data"]["seo"] = {
                            "title": title,
                            "meta_description": meta_description,
                            "h1": h1,
                            "canonical": canonical
                        }
                    
                    result["success"] = True
                    
                except Exception as e:
                    result["status"] = "error"
                    result["error"] = str(e)
                finally:
                    browser.close()
            
            _log_proof(self._website_id, self._agent_name, "web_browser", "playwright", f"url={url}")
            logger.info(f"Web browse completed for {url}")
            
        except Exception as e:
            logger.error(f"Web browser failed: {e}")
            result = {
                "url": url,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return json.dumps(result)


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        from ...database import get_supabase
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "result": json.dumps({"real_api_called": real_api}),
            "real_api_called": real_api,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass
