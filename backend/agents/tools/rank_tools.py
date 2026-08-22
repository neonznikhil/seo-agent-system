import logging
import re
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio
import json
from datetime import datetime

logger = logging.getLogger("backend.tools.rank_tools")


class GSCQueryRequest(BaseModel):
    website_id: str = Field(description="Website ID in Supabase")
    days: int = Field(default=30, description="Number of days to fetch")
    dimension: str = Field(default="query", description="GSC dimension: query, page, device, country")


class SERPPositionRequest(BaseModel):
    keyword: str = Field(description="Keyword to check position for")
    domain: str = Field(description="Domain to check ranking against")
    location: str = Field(default="India", description="Geographic location")


class RankTrackingInput(BaseModel):
    website_id: str = Field(description="Website ID")
    action: str = Field(description="Action: fetch_performance, get_position, calculate_visibility")


class RankTools(BaseTool):
    name: str = "rank_tracking_tools"
    description: str = "Fetch GSC performance data, check SERP positions, and calculate SEO visibility scores"
    args_schema: type[BaseModel] = RankTrackingInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def _run(self, action: str, website_id: str = None, **kwargs) -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})
        
        try:
            if action == "fetch_gsc_performance":
                result = self._fetch_gsc_performance(website_id, kwargs.get("days", 30))
            elif action == "get_position":
                result = self._get_serp_position(kwargs.get("keyword"), kwargs.get("domain"))
            elif action == "calculate_visibility":
                result = self._calculate_visibility_score(website_id)
            else:
                result = {"error": f"Unknown action: {action}"}
            
            return json.dumps({"status": "success", "data": result})
        except Exception as e:
            logger.error(f"Rank tools error: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    def _fetch_gsc_performance(self, website_id: str, days: int = 30) -> Dict:
        from ...database import get_supabase
        
        try:
            gsc_data = get_supabase().table("gsc_keywords").select("*").eq("website_id", website_id).gte("impressions", 100).execute().data or []
            
            results = []
            for keyword in gsc_data:
                results.append({
                    "keyword": keyword.get("query", ""),
                    "current_position": keyword.get("average_position", 0),
                    "impressions": keyword.get("impressions", 0),
                    "clicks": keyword.get("clicks", 0),
                    "ctr": keyword.get("ctr", 0),
                    "search_volume": keyword.get("search_volume", 0),
                    "tracked_at": datetime.utcnow().isoformat()
                })
            
            rank_table = get_supabase().table("rank_tracking")
            for r in results:
                rank_table.insert({
                    "website_id": website_id,
                    "keyword": r["keyword"],
                    "current_position": r["current_position"],
                    "impressions": r["impressions"],
                    "clicks": r["clicks"],
                    "ctr": r["ctr"],
                    "search_volume": r["search_volume"],
                    "tracked_at": datetime.utcnow()
                }).execute()
            
            return {"keywords_tracked": len(results), "data": results}
            
        except Exception as e:
            logger.error(f"GSC fetch error: {e}")
            raise

    def _get_serp_position(self, keyword: str, domain: str) -> Dict:
        from ...database import get_supabase
        
        position = get_supabase().table("rank_tracking").select("current_position").eq("keyword", keyword).eq("website_id", self._website_id).execute().data
        if position:
            return {"keyword": keyword, "domain": domain, "position": position[0]["current_position"]}
        
        return {"keyword": keyword, "domain": domain, "position": 100, "note": "Not tracked yet"}

    def _calculate_visibility_score(self, website_id: str) -> Dict:
        from ...database import get_supabase
        
        rankings = get_supabase().table("rank_tracking").select("impressions, current_position").eq("website_id", website_id).execute().data or []
        
        if not rankings:
            return {"visibility_score": 0, "total_keywords": 0, "avg_position": 0}
        
        total_impressions = sum(r.get("impressions", 0) for r in rankings)
        total_score = sum(r.get("impressions", 0) / max(r.get("current_position", 1), 1) for r in rankings)
        visibility = min(100, (total_score / max(total_impressions, 1)) * 100)
        avg_position = sum(r.get("current_position", 0) for r in rankings) / len(rankings)
        
        return {
            "visibility_score": round(visibility, 2),
            "total_keywords": len(rankings),
            "avg_position": round(avg_position, 2),
            "total_impressions": total_impressions
        }


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
