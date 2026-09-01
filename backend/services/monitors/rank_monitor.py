import logging
import json
from typing import Optional, List, Dict, Any
import aiohttp
import os
from datetime import datetime
from database import get_supabase


class RankMonitor:
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
    
    async def get_gsc_keywords(self, limit: int = 20) -> List[Dict]:
        """Get top keywords from GSC based on impressions."""
        try:
            result = self.supabase.table("gsc_keywords").select("*").eq("website_id", self.website_id).eq("is_active", True).order("impressions", desc=True).limit(limit).execute()
            return result.data or []
        except Exception:
            return []
    
    async def get_current_position(self, keyword: str, market: str = "global") -> Optional[int]:
        """Get current SERP position for keyword."""
        try:
            url = f"https://www.googleapis.com/webmasters/v3/sites/{website.url}/searchAnalytics/query"
            params = {
                "startDate": (datetime.utcnow() - __import__('datetime').timedelta(days=7)).strftime("%Y-%m-%d"),
                "endDate": datetime.utcnow().strftime("%Y-%m-%d"),
                "dimensions": ["query", "page"],
                "rowLimit": 1000
            }
            
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            creds = Credentials(token=os.getenv("GSC_ACCESS_TOKEN"))
            service = build("webmasters", "v3", credentials=creds)
            
            request = service.searchanalytics().query(siteUrl=os.getenv("GSC_SITE_URL"), body=params)
            response = request.execute()
            
            for row in response.get("rows", []):
                if row.get("keys", [""])[0] == keyword:
                    return int(row.get("position", 0))
            
            return None
        except Exception:
            pass
        
        if os.getenv("SERPAPI_KEY"):
            async with aiohttp.ClientSession() as session:
                params = {
                    "api_key": os.getenv("SERPAPI_KEY"),
                    "q": keyword,
                    "location": "Delhi,India" if market == "local" else "India",
                    "device": "mobile" if market == "mobile" else "desktop",
                    "num": 20
                }
                async with session.get("https://serpapi.com/search", params=params) as resp:
                    data = await resp.json()
                    for result in data.get("organic_results", []):
                        if keyword.lower() in result.get("title", "").lower() or keyword.lower() in result.get("snippet", "").lower():
                            return result.get("position")
        return None