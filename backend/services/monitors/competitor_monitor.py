import logging
import os
import asyncio
from typing import Dict, Optional, List
import aiohttp
import hashlib
import json
from datetime import datetime

from ...database import get_supabase
from ..serper_service import serper_service

logger = logging.getLogger("backend.services.monitors.competitor_monitor")


class CompetitorMonitor:
    """Competitor Monitor watching pricing changes, sitemap pages, and real-time news via Serper.dev."""

    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
    
    async def check_competitor(self, competitor: Dict) -> Dict:
        """Check competitor for pricing, content, and Serper news changes."""
        result = {
            "pricing_changed": False,
            "new_content": False,
            "new_pages": 0,
            "new_urls": [],
            "news_updates": []
        }
        
        pricing_url = competitor.get("pricing_page_url")
        homepage_url = competitor.get("homepage_url")
        domain = competitor.get("competitor_domain")
        
        if pricing_url:
            result.update(await self._check_pricing(pricing_url, domain))
        
        if homepage_url:
            result.update(await self._check_content(homepage_url, domain))

        if domain:
            news_res = await self._check_competitor_news(domain)
            result.update(news_res)
        
        return result
    
    async def _check_competitor_news(self, domain: str) -> Dict:
        """Check latest competitor news and content releases via Serper.dev news endpoint."""
        try:
            news_data = await serper_service.news(f"{domain} legal news 2026", num=5)
            news_items = news_data.get("news", [])
            if news_items:
                return {
                    "new_content": True if len(news_items) > 0 else False,
                    "new_pages": len(news_items),
                    "new_urls": [n.get("link") for n in news_items if n.get("link")],
                    "news_updates": news_items
                }
        except Exception as e:
            logger.debug(f"Competitor news check note for {domain}: {e}")
        return {}

    async def _check_pricing(self, pricing_url: str, domain: str) -> Dict:
        """Check pricing page for changes using Crawlee."""
        try:
            last_snapshot = self.supabase.table("competitor_snapshots").select("*").eq("competitor_domain", domain).eq("snapshot_type", "pricing").order("created_at", desc=True).limit(1).execute().data
            old_hash = last_snapshot[0]["content_hash"] if last_snapshot else None
            
            content = await self._scrape_page(pricing_url)
            new_hash = hashlib.md5(content.encode()).hexdigest()
            
            if old_hash != new_hash:
                pricing_data = await self._extract_pricing(content)
                
                old_data = json.dumps(last_snapshot[0].get("pricing_data", {})) if last_snapshot else "{}"
                old_parsed = json.loads(old_data) if old_data else {}
                
                if pricing_data != old_parsed:
                    self.supabase.table("competitor_snapshots").insert({
                        "competitor_domain": domain,
                        "snapshot_type": "pricing",
                        "content_hash": new_hash,
                        "pricing_data": pricing_data,
                        "url": pricing_url,
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()
                    
                    return {
                        "pricing_changed": True,
                        "old_price": old_parsed.get("plans", [{}])[0].get("price") if old_parsed.get("plans") else "unknown",
                        "new_price": pricing_data.get("plans", [{}])[0].get("price") if pricing_data.get("plans") else "unknown"
                    }
            return {}
        except Exception as e:
            self.supabase.table("tasks").insert({
                "agent_name": "competitor_monitor",
                "action": "pricing_check",
                "status": "error",
                "payload": {"error": str(e)},
                "real_api_called": "crawlee"
            }).execute()
        return {}
    
    async def _check_content(self, homepage_url: str, domain: str) -> Dict:
        """Check for new content/pages."""
        try:
            last_snapshot = self.supabase.table("competitor_snapshots").select("*").eq("competitor_domain", domain).eq("snapshot_type", "homepage").order("created_at", desc=True).limit(1).execute().data
            
            content = await self._scrape_page(homepage_url)
            new_hash = hashlib.md5(content.encode()).hexdigest()
            
            sitemap_urls = await self._get_sitemap_urls(domain)
            current_count = len(sitemap_urls)
            
            old_count = last_snapshot[0].get("sitemap_count", 0) if last_snapshot else 0
            
            if current_count > old_count:
                self.supabase.table("competitor_snapshots").insert({
                    "competitor_domain": domain,
                    "snapshot_type": "homepage",
                    "content_hash": new_hash,
                    "sitemap_count": current_count,
                    "url": homepage_url,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                
                return {
                    "new_content": True,
                    "new_pages": current_count - old_count,
                    "new_urls": sitemap_urls[old_count:] if old_count < len(sitemap_urls) else []
                }
            return {}
        except Exception:
            pass
        return {}
    
    async def _scrape_page(self, url: str) -> str:
        """Scrape page content using Crawlee service."""
        try:
            from ..crawlee_service import CrawleeService
            crawler = CrawleeService()
            result = await crawler.crawl_site_structure([url], max_requests=1)
            
            if result:
                page = result[0]
                return f"Title: {page.get('title', '')}\nH1s: {page.get('h1s', [])}\nH2s: {page.get('h2s', [])}\nWord Count: {page.get('word_count', 0)}\nContent: {page.get('meta_description', '')}"
            return ""
        except Exception as e:
            logger.warning(f"Crawlee scrape failed: {e}")
            return ""
    
    async def _extract_pricing(self, content: str) -> Dict:
        """Extract pricing using NVIDIA NIM."""
        from ...database import call_nim_llm
        prompt = f"""Extract pricing plan data from this webpage content. Return JSON:
{{"plans": [{{"name": string, "price": number, "features": [string]}}]}}

Content: {content[:3000]}"""
        try:
            result = await call_nim_llm(prompt)
            return json.loads(result)
        except Exception:
            return {"plans": []}
    
    async def _get_sitemap_urls(self, domain: str) -> list:
        """Get sitemap URLs."""
        for scheme in ["https", "http"]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{scheme}://{domain}/sitemap.xml", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            import re
                            urls = re.findall(r'<loc>(.*?)</loc>', text)
                            return urls[:100]
            except Exception:
                pass
        return []