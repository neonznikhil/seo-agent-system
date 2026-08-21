import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger("backend.services.real_data_service")


class RealDataService:
    """SINGLE SOURCE OF TRUTH - NO HALLUCINATIONS.
    
    All metrics must come from live APIs:
    - GSC: impressions, clicks, ctr, position, search_volume
    - GA4: sessions, users, time on page, bounce rate
    - Crawlee: actual page content, SERP landscape
    - PageSpeed: LCP, CLS, INP
    
    If data source not connected -> return error, not fake numbers.
    """
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id
        self._gsc_service = None
        self._ga4_service = None
        self._crawlee_service = None
    
    async def get_keyword_data(self, keyword: str, 
                                gsc_connected: bool = True,
                                ga4_connected: bool = True) -> Dict[str, Any]:
        """Get REAL keyword metrics from GSC and GA4."""
        result = {
            'keyword': keyword,
            'source': 'combined_real_data',
            'connected': gsc_connected,
            'data': {}
        }
        
        if gsc_connected:
            try:
                from .gsc_service import GSCService
                gsc = GSCService()
                gsc_data = await gsc.get_keyword_performance()
                
                matching_kw = None
                for kw in gsc_data.get('keywords', []):
                    if kw.get('keyword', '').lower() == keyword.lower():
                        matching_kw = kw
                        break
                
                if matching_kw:
                    result['data']['gsc'] = {
                        'impressions': matching_kw.get('impressions', 0),
                        'clicks': matching_kw.get('clicks', 0),
                        'ctr': matching_kw.get('ctr', 0),
                        'position': matching_kw.get('position', 0),
                    }
                    result['connected'] = True
                else:
                    result['data']['gsc'] = {'note': 'Keyword not in GSC data'}
            except Exception as e:
                result['error'] = f"GSC error: {e}"
                result['connected'] = False
        
        if ga4_connected:
            try:
                from .ga4_service import GA4Service
                ga4 = GA4Service()
                ga4_data = await ga4.get_page_traffic()
                result['data']['ga4'] = {
                    'total_sessions': ga4_data.get('total_sessions', 0),
                    'total_users': ga4_data.get('total_users', 0),
                    'top_pages': ga4_data.get('pages', [])[:5]
                }
            except Exception as e:
                result['data']['ga4'] = {'note': 'GA4 connection error'}
        
        return result
    
    async def get_serp_data(self, keyword: str) -> Dict[str, Any]:
        """Get REAL SERP data via Crawlee - no LLM guesses."""
        try:
            from .crawlee_service import CrawleeService
            crawler = CrawleeService()
            
            serp_landscape = await crawler.extract_serp_landscape(keyword)
            
            return {
                'keyword': keyword,
                'source': 'crawlee_serp',
                'top_pages': serp_landscape.get('top_pages', []),
                'winning_patterns': serp_landscape.get('winning_patterns', {}),
                'extracted_at': datetime.utcnow().isoformat(),
                'no_hallucination': True
            }
        
        except ImportError:
            return {
                'keyword': keyword,
                'error': 'Crawlee not installed - pip install crawlee[all]',
                'source': 'crawlee_serp',
                'no_hallucination': True
            }
        except Exception as e:
            return {
                'keyword': keyword,
                'error': str(e),
                'source': 'crawlee_serp',
                'no_hallucination': True
            }
    
    async def get_page_data(self, url: str) -> Dict[str, Any]:
        """Get REAL page content via Crawlee."""
        try:
            from .crawlee_service import CrawleeService
            crawler = CrawleeService()
            
            pages = await crawler.crawl_site_structure([url], max_requests=1)
            
            if pages:
                return {
                    'url': url,
                    'source': 'crawlee',
                    'title': pages[0].get('title'),
                    'h1s': pages[0].get('h1s', []),
                    'h2s': pages[0].get('h2s', []),
                    'word_count': pages[0].get('word_count'),
                    'links': pages[0].get('links', []),
                    'schemas': pages[0].get('schemas', []),
                    'meta_description': pages[0].get('meta_description'),
                    'crawled_at': pages[0].get('crawled_at'),
                    'no_hallucination': True
                }
            
            return {'url': url, 'error': 'Page not crawled', 'source': 'crawlee'}
        
        except Exception as e:
            return {
                'url': url,
                'error': str(e),
                'source': 'crawlee',
                'no_hallucination': True
            }
    
    async def get_keyword_opportunity(self, seed_keyword: str) -> Dict[str, Any]:
        """Get REAL keyword opportunities from GSC data."""
        try:
            from .gsc_service import GSCService
            gsc = GSCService()
            
            gsc_data = await gsc.get_keyword_performance(
                dimensions=['query', 'page'],
                row_limit=1000
            )
            
            all_keywords = gsc_data.get('keywords', [])
            
            target_keywords = [
                kw for kw in all_keywords 
                if seed_keyword.lower() in kw.get('keyword', '').lower()
            ]
            
            striking_distance = [
                kw for kw in all_keywords
                if 10 < kw.get('position', 0) <= 20 and kw.get('impressions', 0) > 100
            ]
            
            competitors = [
                kw for kw in all_keywords
                if kw.get('position', 0) > 20 and kw.get('clicks', 0) > 10
            ][:50]
            
            return {
                'seed_keyword': seed_keyword,
                'source': 'gsc_real',
                'target_keywords': target_keywords,
                'striking_distance': striking_distance,
                'competitor_opportunities': competitors,
                'total_keywords_analyzed': len(all_keywords),
                'no_hallucination': True
            }
        
        except Exception as e:
            return {
                'seed_keyword': seed_keyword,
                'error': str(e),
                'source': 'gsc_real',
                'no_hallucination': True
            }
    
    async def verify_no_index_pages(self) -> Dict[str, Any]:
        """Find pages with high impressions but noindex."""
        try:
            from .gsc_service import GSCService
            gsc = GSCService()
            
            high_impression = await gsc.get_keyword_performance(
                dimensions=['query', 'page'],
                row_limit=5000
            )
            
            high_imp_pages = [
                kw for kw in high_impression.get('keywords', [])
                if kw.get('impressions', 0) > 500
            ]
            
            critical_issues = []
            for page_kw in high_imp_pages:
                page_url = page_kw.get('page', '')
                if not page_url:
                    continue
                
                page_data = await self.get_page_data(page_url)
                
                if 'noindex' in str(page_data).lower():
                    critical_issues.append({
                        'url': page_url,
                        'keyword': page_kw.get('keyword'),
                        'impressions': page_kw.get('impressions'),
                        'issue': 'High-traffic page has noindex tag',
                        'severity': 'critical',
                        'source': 'verified_real_data'
                    })
            
            return {
                'checked_pages': len(high_imp_pages),
                'critical_issues': critical_issues,
                'source': 'gsc_verified',
                'no_hallucination': True
            }
        
        except Exception as e:
            return {
                'error': str(e),
                'source': 'gsc_verified',
                'no_hallucination': True
            }


async def get_keyword_data(keyword: str) -> Dict:
    """Standalone function."""
    service = RealDataService()
    return await service.get_keyword_data(keyword)


async def get_serp_data(keyword: str) -> Dict:
    """Standalone function."""
    service = RealDataService()
    return await service.get_serp_data(keyword)


async def get_page_data(url: str) -> Dict:
    """Standalone function."""
    service = RealDataService()
    return await service.get_page_data(url)


async def get_keyword_opportunity(seed: str) -> Dict:
    """Standalone function."""
    service = RealDataService()
    return await service.get_keyword_opportunity(seed)