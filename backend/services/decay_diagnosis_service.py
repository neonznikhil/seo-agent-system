import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

logger = logging.getLogger("backend.services.decay_diagnosis")


class DecayDiagnosisService:
    """Diagnose WHY content decayed using live Crawlee SERP data."""
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id
    
    async def diagnose(self, decay_log_id: str) -> Dict[str, Any]:
        """Full diagnosis of decay with Crawlee live SERP comparison."""
        from ..database import get_supabase
        supabase = get_supabase()
        
        decay = supabase.table("content_decay_logs").select("*").eq("id", decay_log_id).eq("website_id", self.website_id).single().execute().data
        
        if not decay:
            return {"error": "Decay log not found", "status": "error"}
        
        page_url = decay.get("page_url")
        primary_keyword = decay.get("primary_keyword", "")
        website_id = self.website_id
        
        diagnosis_result = {
            "decay_log_id": decay_log_id,
            "page_url": page_url,
            "primary_keyword": primary_keyword,
            "status": "processed",
            "diagnosis": {},
            "recommendations": [],
            "generated_at": datetime.utcnow().isoformat()
        }
        
        diagnosis = await self._run_full_diagnosis(page_url, primary_keyword, website_id)
        
        supabase.table("content_decay_logs").update({
            "status": "diagnosing",
            "diagnosis": diagnosis,
            "diagnosed_at": datetime.utcnow()
        }).eq("id", decay_log_id).eq("website_id", website_id).execute()
        
        diagnosis_result["diagnosis"] = diagnosis
        diagnosis_result["recommendations"] = self._generate_recommendations(diagnosis)
        
        return diagnosis_result
    
    async def _run_full_diagnosis(self, page_url: str, primary_keyword: str, website_id: str) -> Dict:
        """Run comprehensive diagnosis using Crawlee."""
        diagnosis = {
            "primary_keyword": primary_keyword,
            "our_page": {},
            "competitor_pages": [],
            "gaps": {
                "missing_h2s": [],
                "word_count_gap": 0,
                "missing_table": False,
                "missing_faq": False,
                "new_competitors": []
            },
            "winning_patterns": {},
            "competitor_analysis": {}
        }
        
        from .crawlee_service import CrawleeService
        from .gsc_service import GSCService
        from ..database import get_supabase
        
        supabase = get_supabase()
        crawler = CrawleeService()
        
        our_page_data = await crawler.crawl_site_structure([page_url], max_requests=1)
        if our_page_data:
            diagnosis["our_page"] = our_page_data[0]
        
        serp_data = await crawler.extract_serp_landscape(primary_keyword)
        top_pages = serp_data.get("top_pages", [])[:5]
        diagnosis["competitor_pages"] = top_pages
        diagnosis["winning_patterns"] = serp_data.get("winning_patterns", {})
        
        if top_pages and our_page_data:
            our_word_count = our_page_data[0].get("word_count", 0)
            avg_word_count = sum(p.get("word_count", 0) for p in top_pages) / len(top_pages)
            diagnosis["gaps"]["word_count_gap"] = max(0, avg_word_count - our_word_count)
            
            our_h2s = set(our_page_data[0].get("h2s", []))
            top_h2s = []
            for p in top_pages:
                top_h2s.extend(p.get("h2s", []))
            
            from collections import Counter
            h2_counts = Counter(top_h2s)
            common_h2s = [h for h, c in h2_counts.most_common(5) if c >= 2]
            diagnosis["gaps"]["missing_h2s"] = [h for h in common_h2s if h not in our_h2s]
            
            diagnosis["gaps"]["missing_table"] = serp_data.get("winning_patterns", {}).get("pages_with_table", 0) >= 3
            diagnosis["gaps"]["missing_faq"] = serp_data.get("winning_patterns", {}).get("pages_with_faq", 0) >= 3
            
            diagnosis["gaps"]["new_competitors"] = [p.get("url") for p in top_pages if "competitor" in p.get("url", "").lower() or p.get("url", "").startswith("https://")][:3]
        
        gsc_service = GSCService()
        if gsc_service.is_connected():
            gsc_data = await gsc_service.get_keyword_performance()
            diagnosis["gsc_data"] = {
                "total_keywords": len(gsc_data.get("keywords", [])),
                "total_impressions": gsc_data.get("total_impressions", 0),
                "total_clicks": gsc_data.get("total_clicks", 0)
            }
        
        return diagnosis
    
    def _generate_recommendations(self, diagnosis: Dict) -> List[str]:
        """Generate actionable recommendations based on diagnosis."""
        recommendations = []
        
        gaps = diagnosis.get("gaps", {})
        
        if gaps.get("word_count_gap", 0) > 300:
            recommendations.append(f"Expand content by {int(gaps['word_count_gap'])} words to match top competitors")
        
        if gaps.get("missing_h2s"):
            recommendations.append(f"Add H2 sections: {', '.join(gaps['missing_h2s'][:3])}")
        
        if gaps.get("missing_table"):
            recommendations.append("Add comparison table with real data")
        
        if gaps.get("missing_faq"):
            recommendations.append("Add FAQ section with 4-5 questions using People Also Ask")
        
        winning = diagnosis.get("winning_patterns", {})
        if winning.get("has_table"):
            recommendations.append("Include HTML comparison table for featured snippet")
        
        if winning.get("has_faq"):
            recommendations.append("Add FAQPage schema and Q&A structure")
        
        if diagnosis.get("gaps", {}).get("new_competitors"):
            recommendations.append("Competitive analysis: top new entrants have gained ground")
        
        return recommendations


async def diagnose_decay(decay_log_id: str, website_id: str) -> Dict:
    """Standalone function."""
    service = DecayDiagnosisService(website_id)
    return await service.diagnose(decay_log_id)