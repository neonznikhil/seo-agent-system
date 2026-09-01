import logging
from typing import List, Dict, Any, Optional
import aiohttp
import hashlib
import json
from datetime import datetime
from database import get_supabase


class StructureMonitor:
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
    
    async def analyze_structure(self) -> List[Dict]:
        """Analyze site structure for issues."""
        issues = []
        
        try:
            issues.extend(await self._check_orphan_pages())
        except Exception as e:
            pass
        
        try:
            issues.extend(await self._check_redirects())
        except Exception as e:
            pass
        
        try:
            issues.extend(await self._check_duplicate_titles())
        except Exception as e:
            pass
        
        try:
            issues.extend(await self._check_noindex_pages())
        except Exception as e:
            pass
        
        return issues
    
    async def _check_orphan_pages(self) -> List[Dict]:
        """Check for orphan pages with no internal links."""
        issues = []
        
        try:
            pages = self.supabase.table("website_pages").select("*").eq("website_id", self.website_id).execute().data or []
            linked_pages = set()
            
            for page in pages:
                internal_links = page.get("_internal_links", [])
                linked_pages.update(internal_links)
            
            for page in pages:
                if page.get("url") not in linked_pages and page.get("clicks", 0) > 100:
                    issues.append({
                        "title": "Orphan page detected",
                        "description": f"Page {page.get('url')} has no internal links",
                        "severity": "medium",
                        "data": {"page_url": page.get("url"), "clicks": page.get("clicks")},
                        "audit_type": "orphan_pages"
                    })
        except Exception:
            pass
        
        return issues
    
    async def _check_redirects(self) -> List[Dict]:
        """Check for redirect chains."""
        issues = []
        
        try:
            redirects = self.supabase.table("redirects").select("*").eq("website_id", self.website_id).execute().data or []
            
            for redirect in redirects:
                chain_length = redirect.get("redirect_chain_count", 1)
                if chain_length > 2:
                    issues.append({
                        "title": "Long redirect chain",
                        "description": f"Redirect from {redirect.get('source')} to {redirect.get('target')} has {chain_length} hops",
                        "severity": "medium",
                        "data": {
                            "source": redirect.get("source"),
                            "target": redirect.get("target"),
                            "chain_length": chain_length
                        },
                        "audit_type": "redirect_chains"
                    })
        except Exception:
            pass
        
        return issues
    
    async def _check_duplicate_titles(self) -> List[Dict]:
        """Check for duplicate titles using similarity check."""
        issues = []
        
        try:
            pages = self.supabase.table("website_pages").select("url", "title").eq("website_id", self.website_id).execute().data or []
            
            for i, page1 in enumerate(pages):
                for page2 in pages[i+1:]:
                    if page1.get("title") and page2.get("title"):
                        sim = self._string_similarity(page1["title"], page2["title"])
                        if sim > 0.90:
                            issues.append({
                                "title": "Duplicate titles detected",
                                "description": f"Similar titles: '{page1.get('title')}' and '{page2.get('title')}'",
                                "severity": "low",
                                "data": {
                                    "title": page1.get("title"),
                                    "page1_url": page1.get("url"),
                                    "page2_url": page2.get("url"),
                                    "similarity": sim
                                },
                                "audit_type": "duplicate_titles"
                            })
        except Exception:
            pass
        
        if issues:
            for issue in issues:
                try:
                    self.supabase.table("technical_audits").insert({
                        "website_id": self.website_id,
                        "page_url": issue["data"].get("page1_url"),
                        "audit_type": "duplicate_titles",
                        "issues": [issue],
                        "created_at": datetime.utcnow()
                    }).execute()
                except:
                    pass
        return issues
    
    async def _check_noindex_pages(self) -> List[Dict]:
        """Check for important pages blocked by noindex."""
        issues = []
        
        try:
            gsc_data = self.supabase.table("gsc_keywords").select("url, impressions").eq("website_id", self.website_id).gte("impressions", 500).execute().data or []
            
            for kw in gsc_data:
                page = self.supabase.table("website_pages").select("meta_robots").eq("url", kw.get("url")).eq("website_id", self.website_id).single().execute().data
                
                if page and page.get("meta_robots") == "noindex":
                    issues.append({
                        "title": "Important page is noindex",
                        "description": f"Page with {kw.get('impressions')} impressions is blocked by noindex",
                        "severity": "critical",
                        "data": {
                            "page_url": kw.get("url"),
                            "impressions": kw.get("impressions"),
                            "meta_robots": "noindex"
                        },
                        "audit_type": "noindex_pages"
                    })
        except Exception:
            pass
        
        return issues
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity ratio."""
        if not s1 or not s2:
            return 0.0
        
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()