import logging
import json
from typing import Optional, List, Dict, Any
import aiohttp
import os
from datetime import datetime
from ...database import get_supabase


class GEOMonitor:
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()

    async def get_local_keywords(self, limit: int = 10) -> List[Dict]:
        """Get keywords with local intent for GEO monitoring."""
        try:
            result = (
                self.supabase.table("gsc_keywords")
                .select("*")
                .eq("website_id", self.website_id)
                .order("impressions", desc=True)
                .limit(limit)
                .execute()
            )
            keywords = result.data or []
            if not keywords:
                clusters = (
                    self.supabase.table("topic_clusters")
                    .select("pillar_keyword")
                    .eq("website_id", self.website_id)
                    .limit(limit)
                    .execute()
                    .data
                    or []
                )
                keywords = [{"keyword": c["pillar_keyword"]} for c in clusters if c.get("pillar_keyword")]
            return keywords
        except Exception:
            return []

    async def get_geo_rank(self, keyword: str, city: Optional[str] = None) -> Optional[int]:
        """Get local geo rank for keyword using SERPAPI."""
        if not os.getenv("SERPAPI_KEY"):
            return None

        location = city or "Delhi,India"
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "api_key": os.getenv("SERPAPI_KEY"),
                    "q": keyword,
                    "location": location,
                    "device": "mobile",
                    "num": 20,
                }
                async with session.get("https://serpapi.com/search", params=params) as resp:
                    data = await resp.json()
                    for result in data.get("local_results", []) + data.get("organic_results", []):
                        rank = result.get("position")
                        if rank and rank <= 20:
                            return rank
        except Exception:
            pass
        return None

    async def get_gmb_signal(self, keyword: str) -> Dict:
        """Get Google My Business signal for keyword (stub for production)."""
        return {
            "rating": 4.2,
            "review_count": 15,
            "is_verified": True,
            "NAP_consistent": True,
            "keyword": keyword,
        }
