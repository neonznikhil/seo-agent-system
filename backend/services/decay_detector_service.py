import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import uuid

logger = logging.getLogger("backend.services.decay_detector")


class DecayDetectorService:
    """Detect content decay using real GSC data - NO HALLUCINATIONS."""
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id
        self.supabase = None
    
    def _get_supabase(self):
        if not self.supabase:
            from database import get_supabase
            self.supabase = get_supabase()
        return self.supabase
    
    async def detect_decay(self, website_id: str = None, auto_alert: bool = True) -> Dict[str, Any]:
        """Detect content decay by comparing GSC data 28 days ago vs 28 days ago before that."""
        if website_id:
            self.website_id = website_id
        
        if not self.website_id:
            return {"error": "website_id required", "status": "error"}
        
        supabase = self._get_supabase()
        
        try:
            recent_data = await self._get_gsc_period(
                end_date=datetime.utcnow().strftime("%Y-%m-%d"),
                days_back=28
            )
            
            previous_data = await self._get_gsc_period(
                end_date=(datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d"),
                days_back=28
            )
        except Exception as e:
            logger.error(f"GSC data fetch error: {e}")
            return {"error": f"GSC API error: {e}", "status": "error", "message": "Connect GSC to enable decay detection"}
        
        if not recent_data.get("connected"):
            return {"error": "GSC not connected", "status": "error", "message": "Connect GSC credentials"}
        
        decayed_pages = []
        
        recent_pages = {page["url"]: page for page in recent_data.get("pages", [])}
        previous_pages = {page["url"]: page for page in previous_data.get("pages", [])}
        
        for url, recent in recent_pages.items():
            if url not in previous_pages:
                continue
            
            previous = previous_pages[url]
            
            decay_percent = self._calculate_decay(recent, previous)
            
            if decay_percent and decay_percent > 15:
                diagnosis = await self._diagnose_decay(url, recent.get("primary_keyword", ""), website_id)
                
                decay_id = str(uuid.uuid4())
                decay_log = {
                    "id": decay_id,
                    "website_id": website_id,
                    "page_url": url,
                    "page_title": recent.get("title", ""),
                    "primary_keyword": recent.get("primary_keyword", ""),
                    "previous_position": previous.get("position", 0),
                    "current_position": recent.get("position", 0),
                    "previous_clicks": previous.get("clicks", 0),
                    "current_clicks": recent.get("clicks", 0),
                    "decay_percent": decay_percent,
                    "decay_reason": diagnosis,
                    "status": "detected",
                    "detected_at": datetime.utcnow()
                }
                
                supabase.table("content_decay_logs").insert(decay_log).execute()
                
                decayed_pages.append({
                    "url": url,
                    "decay_percent": decay_percent,
                    "position_change": f"{previous.get('position', 0)} -> {recent.get('position', 0)}",
                    "clicks_change": f"{previous.get('clicks', 0)} -> {recent.get('clicks', 0)}"
                })
                
                if auto_alert:
                    from .reporting_service import report_problem
                    await report_problem(
                        website_id=website_id,
                        alert_type="content_decay",
                        severity="warning" if decay_percent < 30 else "major",
                        title=f"Content decay detected: {url}",
                        description=f"Position dropped {previous.get('position', 0)} -> {recent.get('position', 0)}, clicks -{decay_percent}%",
                        data={"decay_log_id": decay_id, "decay_percent": decay_percent, "page_url": url},
                        source_monitor="decay_detector"
                    )
        
        return {
            "status": "success",
            "decayed_pages": decayed_pages,
            "total_decayed": len(decayed_pages),
            "source": "gsc_real"
        }
    
    async def _get_gsc_period(self, end_date: str, days_back: int = 28) -> Dict:
        """Get GSC data for a specific period using real GSC API."""
        from .gsc_service import GSCService

        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days_back)).strftime("%Y-%m-%d")

        supabase = self._get_supabase()

        website = supabase.table("websites").select("domain,gsc_property").eq("id", self.website_id).single().execute().data or {}
        website_url = website.get("gsc_property") or website.get("domain")

        if not website_url:
            return {"connected": False, "pages": [], "error": "No GSC property or domain configured"}

        service = GSCService(website_url=website_url)
        if not service.is_connected():
            return {"connected": False, "pages": [], "error": "GSC not connected"}

        result = await service.get_keyword_performance(
            start_date=start_date,
            end_date=end_date,
            dimensions=["query", "page", "device", "country"],
            row_limit=5000,
        )

        keywords = result.get("keywords", [])
        page_stats = {}
        for kw in keywords:
            page_url = kw.get("page")
            if not page_url:
                continue

            if page_url not in page_stats:
                page_stats[page_url] = {
                    "url": page_url,
                    "title": page_url[:60],
                    "primary_keyword": kw.get("keyword", ""),
                    "impressions": 0,
                    "clicks": 0,
                    "position": 0,
                }

            page_stats[page_url]["impressions"] += kw.get("impressions", 0)
            page_stats[page_url]["clicks"] += kw.get("clicks", 0)
            page_stats[page_url]["position"] = kw.get("position", 0)

        return {
            "connected": True,
            "pages": list(page_stats.values()),
        }
    
    def _calculate_decay(self, recent: Dict, previous: Dict) -> float:
        """Calculate decay percentage based on position and clicks."""
        recent_pos = recent.get("position", 0)
        prev_pos = previous.get("position", 0)
        
        if prev_pos > 0 and recent_pos > prev_pos:
            position_decay = ((recent_pos - prev_pos) / prev_pos) * 100
        else:
            position_decay = 0
        
        prev_clicks = previous.get("clicks", 0)
        recent_clicks = recent.get("clicks", 0)
        
        if prev_clicks > 0:
            click_decay = ((prev_clicks - recent_clicks) / prev_clicks) * 100
        else:
            click_decay = 0
        
        return max(position_decay, click_decay)
    
    async def _diagnose_decay(self, page_url: str, primary_keyword: str, website_id: str) -> Dict:
        """Diagnose why page decayed using real crawls."""
        diagnosis = {
            "primary_keyword": primary_keyword,
            "missing_h2s": [],
            "word_count_gap": 0,
            "missing_table": False,
            "missing_faq": False,
            "new_competitors": [],
            "freshness_issue": False,
            "winning_patterns": {},
            "checked_at": datetime.utcnow().isoformat()
        }
        
        from .crawlee_service import CrawleeService
        
        try:
            crawler = CrawleeService()
            
            page_data = await crawler.crawl_site_structure([page_url], max_requests=1)
            
            if page_data:
                our_page = page_data[0]
                diagnosis["our_word_count"] = our_page.get("word_count", 0)
                diagnosis["our_has_table"] = len(our_page.get("schemas", [])) > 0
                diagnosis["our_h2_count"] = len(our_page.get("h2s", []))
            
            serp_data = await crawler.extract_serp_landscape(primary_keyword)
            top_pages = serp_data.get("top_pages", [])
            
            if top_pages:
                avg_word_count = sum(p.get("word_count", 0) for p in top_pages) / len(top_pages)
                diagnosis["avg_top_word_count"] = avg_word_count
                diagnosis["word_count_gap"] = max(0, avg_word_count - (our_page.get("word_count", 0) if page_data else 0))
                diagnosis["winning_patterns"] = serp_data.get("winning_patterns", {})
                
                our_h2s = set(our_page.get("h2s", []) if page_data else [])
                top_h2s = []
                for p in top_pages:
                    top_h2s.extend(p.get("h2s", []))
                
                from collections import Counter
                top_h2_counts = Counter(top_h2s)
                common_top_h2s = [h for h, c in top_h2_counts.most_common(5) if c >= 2]
                diagnosis["missing_h2s"] = [h for h in common_top_h2s if h not in our_h2s]
                
                diagnosis["missing_table"] = serp_data.get("winning_patterns", {}).get("pages_with_table", 0) >= 3 and not diagnosis.get("our_has_table", False)
                diagnosis["missing_faq"] = serp_data.get("winning_patterns", {}).get("pages_with_faq", 0) >= 3
                
                diagnosis["new_competitors"] = [p.get("url") for p in top_pages if "competitor" in p.get("url", "").lower()][:3]
                
                year_ago = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
                from database import get_supabase
                supabase = get_supabase()
                old_ranks = supabase.table("rank_tracking").select("created_at").eq("page_url", page_url).gte("created_at", year_ago).execute().data or []
                diagnosis["freshness_issue"] = len(old_ranks) == 0
        
        except Exception as e:
            logger.warning(f"Diagnosis failed for {page_url}: {e}")
            diagnosis["diagnosis_error"] = str(e)
        
        return diagnosis


async def detect_decay(website_id: str) -> Dict:
    """Standalone function."""
    service = DecayDetectorService(website_id)
    return await service.detect_decay(website_id)