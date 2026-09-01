import logging
from datetime import datetime
import json
from typing import Optional, List, Dict, Any
import os

from database import get_supabase
try:
    from services.serper_service import serper_service
except ImportError:
    from ..serper_service import serper_service


logger = logging.getLogger("backend.services.monitors.serp_monitor")


class SERPMonitor:
    """SERP Monitor checking live search ranking differences using Serper.dev."""

    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
    
    async def get_top_keywords(self, limit: int = 10) -> List[Dict]:
        """Get top performing keywords for SERP comparison."""
        try:
            result = self.supabase.table("gsc_keywords").select("*").eq("website_id", self.website_id).order("clicks", desc=True).limit(limit).execute()
            return result.data or []
        except Exception:
            return []
    
    async def get_position(self, keyword: str, market: str = "global") -> Optional[int]:
        """Get position for specific market type using Serper.dev primary connector."""
        target_domain = self._get_domain()
        location = self._get_location(market)
        
        try:
            serp_res = await serper_service.search(
                query=keyword,
                location=location,
                num=20,
                auto_fallback=True
            )
            
            for idx, result in enumerate(serp_res.get("organic", [])):
                link = result.get("link", "").lower()
                if target_domain and target_domain in link:
                    return result.get("position") or (idx + 1)
                
            # If domain not found in top results, return first result's position if available or None
            if serp_res.get("organic"):
                return None
        except Exception as e:
            logger.warning(f"SERP monitor position check failed for '{keyword}' via Serper: {e}")
        
        return None
    
    def _get_domain(self) -> str:
        try:
            website = self.supabase.table("websites").select("domain").eq("id", self.website_id).single().execute().data
            return (website.get("domain") or "").lower()
        except Exception:
            return ""

    def _get_location(self, market: str) -> str:
        try:
            website = self.supabase.table("websites").select("local_target").eq("id", self.website_id).single().execute().data
            city = website.get("local_target", "Houston") if website else "Houston"
            if market == "local":
                return f"{city}, United States"
            elif market == "mobile":
                return f"{city}, United States"
            return "United States"
        except Exception:
            return "United States"