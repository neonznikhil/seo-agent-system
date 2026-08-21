import logging
import re
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio

logger = logging.getLogger("backend.tools.competitor_tools")


class AddCompetitorInput(BaseModel):
    website_id: str = Field(description="Website ID")
    domain: str = Field(description="Competitor domain to add")
    pricing_page: Optional[str] = Field(None, description="Pricing page URL")


class ScanRequest(BaseModel):
    website_id: str = Field(description="Website ID")
    competitor_id: Optional[str] = Field(None, description="Specific competitor ID")


class CompetitorTools(BaseTool):
    name: str = "competitor_tools"
    description = "Monitor competitor websites, detect pricing changes, track market moves"
    args_schema: type[BaseModel] = ScanRequest
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def _run(self, website_id: str = None, competitor_id: Optional[str] = None, action: str = "scan") -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})
        
        try:
            from ...database import get_supabase
            
            result = {"status": "success", "timestamp": datetime.utcnow().isoformat()}
            
            if action == "add_competitor":
                result = self._add_competitor(website_id, competitor_id)
            elif action == "daily_scan":
                result = self._daily_scan(website_id)
            elif action == "detect_changes":
                result = self._detect_changes(website_id)
            elif action == "market_trend":
                result = self._market_trend(website_id)
            
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Competitor tools error: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    def _add_competitor(self, website_id: str, url: str = None) -> Dict:
        from ...database import get_supabase
        
        domain = url or f"https://{website_id}.com"
        
        result = {
            "competitor_id": "new-id",
            "domain": domain,
            "status": "added",
            "action_taken": "Added to competitor list"
        }
        
        get_supabase().table("competitors").insert({
            "website_id": website_id,
            "competitor_domain": domain,
            "competitor_name": domain.split("//")[-1].split("/")[0],
            "status": "active",
            "created_at": datetime.utcnow()
        }).execute()
        
        return result

    def _daily_scan(self, website_id: str) -> Dict:
        from ...database import get_supabase
        
        competitors = get_supabase().table("competitors").select("*").eq("website_id", website_id).eq("status", "active").execute().data or []
        scanned = 0
        
        for comp in competitors[:10]:
            pricing_page = comp.get("pricing_page_url") or f"https://{comp['competitor_domain']}/pricing"
            
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(pricing_page, wait_until="networkidle", timeout=30000)
                    content = page.inner_text("body")[:5000]
                    browser.close()
                    
                    content_hash = hash(content)
                    
                    existing = get_supabase().table("competitor_snapshots").select("content_hash").eq("competitor_id", comp["id"]).order("snapshot_at", desc=True).limit(1).execute().data
                    
                    if not existing or existing[0]["content_hash"] != str(content_hash):
                        get_supabase().table("competitor_snapshots").insert({
                            "competitor_id": comp["id"],
                            "page_url": pricing_page,
                            "content_hash": str(content_hash),
                            "title": page.title(),
                            "snapshot_at": datetime.utcnow()
                        }).execute()
                        scanned += 1
            except Exception as e:
                logger.warning(f"Scan failed for {pricing_page}: {e}")
        
        return {
            "scan_date": datetime.utcnow().isoformat(),
            "scanned": scanned,
            "total_competitors": len(competitors),
            "status": "completed"
        }

    def _detect_changes(self, website_id: str) -> Dict:
        from ...database import get_supabase
        
        snapshot = get_supabase().table("competitor_snapshots").select("*").order("snapshot_at", desc=True).limit(1).execute().data
        
        changes = []
        if snapshot:
            latest = snapshot[0]
            prev = get_supabase().table("competitor_snapshots").select("*").eq("competitor_id", latest["competitor_id"]).order("snapshot_at", desc=True).offset(1).limit(1).execute().data
            
            if prev and prev[0]["content_hash"] != latest["content_hash"]:
                changes.append({
                    "competitor_id": latest["competitor_id"],
                    "change_type": "content_update",
                    "new_value": latest["title"],
                    "detected_at": datetime.utcnow().isoformat()
                })
        
        return {"changes": changes, "status": "checked"}

    def _market_trend(self, website_id: str) -> Dict:
        from ...database import get_supabase
        
        changes = get_supabase().table("competitor_changes").select("*").eq("website_id", website_id).order("detected_at", desc=True).limit(20).execute().data or []
        
        summary = {}
        for change in changes:
            change_type = change.get("change_type", "unknown")
            summary[change_type] = summary.get(change_type, 0) + 1
        
        total_changes = len(changes)
        unread = len([c for c in changes if not c.get("is_read", False)])
        
        return {
            "summary": summary,
            "total_changes_last_30d": total_changes,
            "unread_alerts": unread,
            "trends": list(summary.keys())[:5],
            "status": "analyzed"
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
