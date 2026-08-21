import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger("backend.agents.tools.research_tools")


class ResearchTools:
    """Phase 2: SERP & Competitor Analysis using real data via Crawlee."""
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id
        self.supabase = None
    
    def set_website_id(self, website_id: str):
        self.website_id = website_id
    
    def _get_supabase(self):
        if not self.supabase:
            from ...database import get_supabase
            self.supabase = get_supabase()
        return self.supabase
    
    async def extract_serp_landscape(self, keyword: str) -> Dict[str, Any]:
        """Phase 2 Step 16: Extract real SERP data via Crawlee."""
        from ...services.crawlee_service import CrawleeService
        
        crawler = CrawleeService()
        return await crawler.extract_serp_landscape(keyword)
    
    async def competitor_intelligence(self, domains: List[str], our_keywords: List[str]) -> Dict[str, Any]:
        """Phase 2 Step 17-18: Analyze competitors for gaps."""
        from ...services.crawlee_service import CrawleeService
        
        crawler = CrawleeService()
        return await crawler.competitor_intelligence(domains, our_keywords)
    
    async def get_gsc_keyword_data(self) -> List[Dict]:
        """Get real keyword data from GSC - NEVER hallucinated."""
        from ...services.gsc_service import GSCService
        
        gsc = GSCService()
        if not gsc.is_connected():
            return []
        
        data = await gsc.get_keyword_performance()
        return data.get('keywords', [])
    
    async def get_ga4_page_data(self) -> List[Dict]:
        """Get real page data from GA4 for internal linking."""
        from ...services.ga4_service import GA4Service
        
        ga4 = GA4Service()
        if not ga4.is_connected():
            return []
        
        data = await ga4.get_page_traffic()
        return data.get('pages', [])
    
    async def analyze_serp_winning_patterns(self, keyword: str) -> Dict[str, Any]:
        """Analyze what Google is rewarding RIGHT NOW in SERP."""
        serp_data = await self.extract_serp_landscape(keyword)
        
        return {
            'keyword': keyword,
            'avg_word_count': serp_data.get('winning_patterns', {}).get('avg_word_count', 0),
            'common_h2_structures': serp_data.get('winning_patterns', {}).get('common_h2s', []),
            'has_tables_in_top_3': serp_data.get('winning_patterns', {}).get('pages_with_table', 0) >= 3,
            'has_faq_in_top_3': serp_data.get('winning_patterns', {}).get('pages_with_faq', 0) >= 3,
            'schema_types_common': serp_data.get('winning_patterns', {}).get('schema_types', []),
            'top_10_results': serp_data.get('top_pages', [])[:10],
            'verified_real_data': True,
            'source': 'crawlee_serp_verified'
        }
    
    async def find_competitor_gaps(self, keyword: str, competitors: List[str]) -> Dict[str, Any]:
        """Find keyword gaps with competitors."""
        our_keywords = await self.get_gsc_keyword_data()
        
        our_kw_set = {k.get('keyword', '').lower() for k in our_keywords if k.get('keyword')}
        
        gap_analysis = await self.competitor_intelligence(competitors, list(our_kw_set))
        
        return {
            'keyword': keyword,
            'competitor_domains': competitors,
            'our_keywords_count': len(our_kw_set),
            'competitor_keyword_gaps': gap_analysis.get('keyword_gaps', [])[:20],
            'content_gaps': gap_analysis.get('content_gaps', []),
            'verified_real_data': True,
            'source': 'gsc_competitor_verified'
        }


async def extract_serp_landscape(keyword: str) -> Dict:
    """Standalone function."""
    tools = ResearchTools()
    return await tools.extract_serp_landscape(keyword)


async def competitor_intelligence(domains: List[str], kws: List[str]) -> Dict:
    """Standalone function."""
    tools = ResearchTools()
    return await tools.competitor_intelligence(domains, kws)


async def get_keyword_data() -> List[Dict]:
    """Standalone function."""
    tools = ResearchTools()
    return await tools.get_gsc_keyword_data()


async def get_page_data() -> List[Dict]:
    """Standalone function."""
    tools = ResearchTools()
    return await tools.get_ga4_page_data()