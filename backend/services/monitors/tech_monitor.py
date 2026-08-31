import logging
import json
from typing import Dict, Optional, List, Any
import aiohttp
import os
from datetime import datetime
from ...database import get_supabase


class TechMonitor:
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
        self.pagespeed_api_key = os.getenv("PAGESPEED_API_KEY")
    
    async def get_top_pages(self, limit: int = 5) -> List[str]:
        """Get top performing pages from GSC."""
        try:
            result = self.supabase.table("gsc_keywords").select("url").eq("website_id", self.website_id).order("clicks", desc=True).limit(limit).execute()
            urls = list(set(row.get("url") for row in (result.data or []) if row.get("url")))
            if not urls:
                website = self.supabase.table("websites").select("url").eq("id", self.website_id).single().execute().data
                if website:
                    urls = [website.get("url")]
            return urls[:5]
        except Exception:
            return []

    async def check_all_pages(self) -> Dict[str, Any]:
        """Check all top pages for technical issues."""
        pages = await self.get_top_pages(limit=5)
        page_results = {}
        for page in pages:
            if page:
                page_results[page] = await self.check_page(page)
        return {
            "website_id": self.website_id,
            "pages_checked": len(page_results),
            "results": page_results
        }

    async def check_page(self, url: str) -> Dict:
        """Run full technical check on a page."""
        result = {
            "broken_links": [],
            "speed_degraded": False,
            "mobile_issues": "",
            "old_lcp": None,
            "new_lcp": None,
            "lcp_change": 0
        }
        
        try:
            result["broken_links"] = await self._check_broken_links(url)
        except:
            pass
        
        try:
            speed_result = await self._check_page_speed(url)
            result.update(speed_result)
        except:
            pass
        
        try:
            result["mobile_issues"] = await self._check_mobile_usability(url)
        except:
            pass
        
        return result
    
    async def _check_broken_links(self, url: str) -> List[Dict]:
        """Check for broken links on page."""
        links = []
        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                if resp.status != 200:
                    return []
                html = await resp.text()
                
                import re
                found_links = re.findall(r'href=["\']([^"\']+)["\']', html)
                found_links += re.findall(r'src=["\']([^"\']+)["\']', html)
                
                for link in found_links[:50]:
                    if not link.startswith(('http://', 'https://', '/', '#', 'mailto:', 'tel:', 'javascript:')):
                        continue
                    
                    if link.startswith('/'):
                        link = url.rstrip('/') + link
                    elif not link.startswith('http'):
                        link = url + link
                    
                    try:
                        async with session.head(link, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as lresp:
                            if lresp.status in (404, 500, 502, 503):
                                links.append({"url": link, "status": lresp.status})
                    except:
                        pass
            except Exception:
                pass
        return links
    
    async def _check_page_speed(self, url: str) -> Dict:
        """Check PageSpeed and compare with previous metrics."""
        result = {
            "speed_degraded": False,
            "old_lcp": None,
            "new_lcp": None,
            "lcp_change": 0
        }
        
        if not self.pagespeed_api_key:
            return result
        
        try:
            api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile&key={self.pagespeed_api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    data = await resp.json()
            
            lcp = float(data.get("lighthouseResult", {}).get("audits", {}).get("largest-contentful-paint", {}).get("numericValue", 0)) / 1000
            
            last_audit = self.supabase.table("technical_audits").select("metrics").eq("website_id", self.website_id).eq("page_url", url).order("created_at", desc=True).limit(1).execute().data
            
            if last_audit and last_audit[0].get("metrics"):
                old_lcp = last_audit[0]["metrics"].get("lcp", 0)
                result["old_lcp"] = old_lcp
                result["new_lcp"] = lcp
                result["lcp_change"] = lcp - old_lcp
                
                if result["lcp_change"] > 0.5 or (old_lcp and lcp / old_lcp > 1.5):
                    result["speed_degraded"] = True
            
            self.supabase.table("technical_audits").insert({
                "website_id": self.website_id,
                "page_url": url,
                "audit_type": "pagespeed",
                "metrics": {"lcp": lcp, "score": data.get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score", 0)},
                "created_at": datetime.utcnow()
            }).execute()
        except Exception:
            pass
        
        return result
    
    async def _check_mobile_usability(self, url: str) -> str:
        """Check mobile usability issues."""
        if not self.pagespeed_api_key:
            return ""
        
        issues = []
        try:
            api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile&key={self.pagespeed_api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    data = await resp.json()
            
            form_factors = data.get("lighthouseResult", {}).get("audits", {}).get(" viewport", {}).get("details", {}).get("issues", [])
            issues.extend(form_factors)
            
            tap_targets = data.get("lighthouseResult", {}).get("audits", {}).get("tap-targets", {}).get("details", {}).get("issues", [])
            issues.extend(tap_targets)
            
            font_size = data.get("lighthouseResult", {}).get("audits", {}).get("font-size", {}).get("details", {}).get("issues", [])
            issues.extend(font_size)
            
            if self.supabase.table("technical_audits").select("audit_type").eq("website_id", self.website_id).eq("page_url", url).eq("audit_type", "mobile_usability").execute().data:
                pass
            else:
                self.supabase.table("technical_audits").insert({
                    "website_id": self.website_id,
                    "page_url": url,
                    "audit_type": "mobile_usability",
                    "issues": issues,
                    "created_at": datetime.utcnow()
                }).execute()
        except Exception:
            pass
        
        return "; ".join(issues[:3]) if issues else ""