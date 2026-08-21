from typing import Optional, List, Dict, Any
import aiohttp
import os
from ...database import get_supabase


class SERPMonitor:
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
        """Get position for specific market type."""
        if os.getenv("SERPAPI_KEY"):
            async with aiohttp.ClientSession() as session:
                params = {
                    "api_key": os.getenv("SERPAPI_KEY"),
                    "q": keyword,
                    "location": self._get_location(market),
                    "device": "mobile" if market == "mobile" else "desktop",
                    "num": 20
                }
                async with session.get("https://serpapi.com/search", params=params) as resp:
                    data = await resp.json()
                    for result in data.get("organic_results", []):
                        rank = result.get("position")
                        if rank and rank <= 20:
                            return rank
        return None
    
    def _get_location(self, market: str) -> str:
        try:
            website = self.supabase.table("websites").select("local_target").eq("id", self.website_id).single().execute().data
            city = website.get("local_target", "Delhi") if website else "Delhi"
            if market == "local":
                return f"{city},India"
            elif market == "mobile":
                return f"{city},India"
            return "India"
        except:
            return "India"