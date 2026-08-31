import asyncio
import ipaddress
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from urllib.parse import urlparse

logger = logging.getLogger("backend.services.crawlee_service")

BLOCKED_SCHEMES = {"file", "ftp", "gopher", "telnet", "ldap", "rlogin", "rsh", "ssh"}
INTERNAL_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_url_blocked(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in BLOCKED_SCHEMES:
        return True
    hostname = parsed.hostname
    if not hostname:
        return True
    if hostname in ("localhost", "metadata.google.internal"):
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        for network in INTERNAL_NETWORKS:
            if addr in network:
                return True
    except ValueError:
        pass
    return False


class CrawleeService:
    """Real-data web crawling using Crawlee."""
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id
        self._initialized = False
    
    async def _ensure_initialized(self):
        if self._initialized:
            return
        try:
            from crawlee.crawlers import BeautifulSoupCrawler, PlaywrightCrawler
            self._initialized = True
        except ImportError as e:
            logger.error(f"Crawlee not installed: {e}")
            raise

    async def _cleanup_storage(self, crawler) -> None:
        try:
            if hasattr(crawler, "storage") and crawler.storage:
                await crawler.storage.purge()
            if hasattr(crawler, "request_manager") and crawler.request_manager:
                await crawler.request_manager.reset()
        except Exception as e:
            logger.warning(f"Crawlee storage cleanup failed: {e}")

    def _sanitize_start_urls(self, start_urls: List[str]) -> List[str]:
        sanitized = []
        for url in start_urls:
            if _is_url_blocked(url):
                logger.warning(f"Blocked potentially unsafe URL during crawl: {url}")
                continue
            sanitized.append(url)
        return sanitized
    
    async def crawl_site_structure(self, start_urls: List[str], max_requests: int = 50) -> List[Dict]:
        """Crawl site structure and extract real data from pages."""
        await self._ensure_initialized()

        from crawlee.crawlers import BeautifulSoupCrawler

        start_urls = self._sanitize_start_urls(start_urls)
        if not start_urls:
            return []

        results = []
        crawler = BeautifulSoupCrawler(max_requests_per_crawl=max_requests)

        @crawler.router.default_handler
        async def handler(context):
            soup = context.soup
            url = context.request.url

            if _is_url_blocked(url):
                logger.warning(f"Blocked SSRF attempt during crawl: {url}")
                return

            title = soup.title.string.strip() if soup.title and soup.title.string else None
            h1s = [h.get_text(strip=True) for h in soup.find_all('h1')]
            h2s = [h.get_text(strip=True) for h in soup.find_all('h2')]
            h3s = [h.get_text(strip=True) for h in soup.find_all('h3')]

            text_content = soup.get_text(separator=' ', strip=True)
            word_count = len(text_content.split())

            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/') or href.startswith('http'):
                    if not _is_url_blocked(href):
                        links.append(href)

            schema_scripts = soup.find_all('script', type='application/ld+json')
            schemas = []
            for s in schema_scripts:
                try:
                    schema_data = json.loads(s.string) if s.string else None
                    if schema_data:
                        schemas.append(schema_data)
                except (json.JSONDecodeError, TypeError):
                    pass

            meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
            meta_desc = meta_desc_tag['content'] if meta_desc_tag else None

            canonical_tag = soup.find('link', rel='canonical')
            canonical = canonical_tag['href'] if canonical_tag else None

            data = {
                'url': url,
                'title': title,
                'h1s': h1s,
                'h2s': h2s,
                'h3s': h3s,
                'word_count': word_count,
                'links': links[:100],
                'schemas': schemas,
                'meta_description': meta_desc,
                'canonical': canonical,
                'crawled_at': datetime.utcnow().isoformat(),
                'source': 'crawlee'
            }

            await context.push_data(data)
            results.append(data)

            if len(results) < max_requests:
                await context.enqueue_links()

        try:
            await crawler.run(start_urls)
        except Exception as e:
            logger.error(f"Crawling failed: {e}")
        finally:
            await self._cleanup_storage(crawler)

        return results
    
    async def extract_serp_landscape(self, keyword: str, location: str = "India", count: int = 10) -> Dict:
        """Extract real SERP data for keyword analysis."""
        await self._ensure_initialized()

        import urllib.parse
        from crawlee.crawlers import PlaywrightCrawler

        serp_url = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}&num={count}&gl=IN&hl=en"

        if _is_url_blocked(serp_url):
            return {
                'keyword': keyword,
                'error': 'Blocked unsafe SERP URL',
                'top_pages': [],
                'winning_patterns': {},
                'source': 'crawlee_serp'
            }

        crawler = PlaywrightCrawler(max_requests_per_crawl=count, headless=True)
        serp_data = {
            'keyword': keyword,
            'top_pages': [],
            'winning_patterns': {
                'avg_word_count': 0,
                'common_h2s': [],
                'has_table': False,
                'has_faq': False,
                'schema_types': []
            },
            'source': 'crawlee_serp'
        }

        @crawler.router.default_handler
        async def handler(context):
            page = context.page
            url = context.request.url
            if _is_url_blocked(url):
                logger.warning(f"Blocked SSRF attempt during SERP extraction: {url}")
                return

            try:
                titles = await page.locator('h3').all_inner_texts()
                urls = await page.locator('.yuRUBF a').evaluate_all('els => els.map(a => a.href)')

                if not urls:
                    urls = await page.locator('a').evaluate_all('els => els.map(a => a.href)')

                for title, url in zip(titles[:count], urls[:count]):
                    if not _is_url_blocked(url):
                        serp_data['top_pages'].append({
                            'title': title,
                            'url': url,
                            'h1': None,
                            'h2s': [],
                            'word_count': 0,
                            'has_table': False,
                            'has_faq': False,
                            'schemas': []
                        })
            except Exception as e:
                logger.warning(f"SERP extraction failed: {e}")

        try:
            await crawler.run([serp_url])
            await self._cleanup_storage(crawler)

            top_pages = serp_data['top_pages'][:count]
            if top_pages:
                await self._deep_crawl_serp_pages(top_pages)
                serp_data['winning_patterns'] = self._calculate_winning_patterns(top_pages)
                serp_data['top_pages'] = top_pages

        except Exception as e:
            logger.error(f"SERP landscape extraction failed: {e}")
            return {
                'keyword': keyword,
                'error': str(e),
                'top_pages': [],
                'winning_patterns': {},
                'source': 'crawlee_serp'
            }

        return serp_data
    
    async def _deep_crawl_serp_pages(self, pages: List[Dict]) -> None:
        """Deep crawl SERP result pages for detailed analysis."""
        await self._ensure_initialized()

        from crawlee.crawlers import BeautifulSoupCrawler

        urls = [p['url'] for p in pages if p.get('url') and not _is_url_blocked(p.get('url', ''))][:5]
        if not urls:
            return

        crawler = BeautifulSoupCrawler(max_requests_per_crawl=5)

        @crawler.router.default_handler
        async def handler(context):
            soup = context.soup
            url = context.request.url
            if _is_url_blocked(url):
                logger.warning(f"Blocked SSRF attempt during deep crawl: {url}")
                return

            for page in pages:
                if page.get('url') == url:
                    page['h1'] = [h.get_text(strip=True) for h in soup.find_all('h1')]
                    page['h2s'] = [h.get_text(strip=True) for h in soup.find_all('h2')][:10]

                    text = soup.get_text(separator=' ', strip=True)
                    page['word_count'] = len(text.split())

                    tables = soup.find_all('table')
                    page['has_table'] = len(tables) > 0

                    faq_items = soup.find_all('div', class_='faq')
                    page['has_faq'] = len(faq_items) > 0 or bool(soup.find_all('script', type='application/ld+json'))

                    schema_scripts = soup.find_all('script', type='application/ld+json')
                    for s in schema_scripts:
                        try:
                            schema = json.loads(s.string) if s.string else None
                            if schema and isinstance(schema, dict):
                                page.setdefault('schemas', []).append(schema.get('@type', 'Unknown'))
                            elif schema and isinstance(schema, list):
                                page.setdefault('schemas', []).extend([s.get('@type', 'Unknown') for s in schema if isinstance(s, dict)])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    break

            await context.enqueue_links()

        try:
            await crawler.run(urls)
        except Exception as e:
            logger.warning(f"Deep crawl failed: {e}")
        finally:
            await self._cleanup_storage(crawler)
    
    def _calculate_winning_patterns(self, pages: List[Dict]) -> Dict:
        """Calculate what Google is rewarding RIGHT NOW in SERP."""
        if not pages:
            return {'avg_word_count': 0, 'common_h2s': [], 'has_table': False, 'has_faq': False, 'schema_types': []}
        
        word_counts = [p.get('word_count', 0) for p in pages if p.get('word_count')]
        avg_word_count = sum(word_counts) / len(word_counts) if word_counts else 0
        
        all_h2s = []
        for p in pages:
            all_h2s.extend(p.get('h2s', []))
        
        from collections import Counter
        h2_counts = Counter(all_h2s)
        common_h2s = [h for h, c in h2_counts.most_common(5) if c >= 2]
        
        has_table = any(p.get('has_table', False) for p in pages)
        has_faq = any(p.get('has_faq', False) for p in pages)
        
        schema_types = []
        for p in pages:
            schema_types.extend(p.get('schemas', []))
        
        schema_counts = Counter(schema_types)
        common_schema = [s for s, c in schema_counts.most_common(3)]
        
        return {
            'avg_word_count': round(avg_word_count, 0),
            'common_h2s': common_h2s,
            'has_table': has_table,
            'has_faq': has_faq,
            'schema_types': common_schema,
            'pages_with_table': sum(1 for p in pages if p.get('has_table')),
            'pages_with_faq': sum(1 for p in pages if p.get('has_faq'))
        }
    
    async def competitor_intelligence(self, competitor_domains: List[str], our_keywords: List[str]) -> Dict:
        """Analyze competitors for keyword gaps and opportunities."""
        await self._ensure_initialized()
        
        results = {
            'competitors': [],
            'keyword_gaps': [],
            'content_gaps': [],
            'source': 'crawlee',
        }
        
        for domain in competitor_domains[:5]:
            sitemap_urls = await self._get_sitemap_urls(domain)
            
            page_data = await self.crawl_site_structure(sitemap_urls[:10], max_requests=10)
            
            competitor_keywords = set()
            for page in page_data:
                if page.get('title'):
                    competitor_keywords.add(page['title'])
                if page.get('h1s'):
                    for h1 in page['h1s']:
                        competitor_keywords.add(h1)
            
            our_kw_set = set(our_keywords)
            gaps = [kw for kw in competitor_keywords if kw.lower() not in {k.lower() for k in our_kw_set}]
            
            results['competitors'].append({
                'domain': domain,
                'pages_crawled': len(page_data),
                'keywords_found': list(competitor_keywords)[:50],
                'gap_keywords': gaps[:20]
            })
        
        results['keyword_gaps'] = [g for c in results['competitors'] for g in c.get('gap_keywords', [])]
        
        return results
    
    async def _get_sitemap_urls(self, domain: str) -> List[str]:
        """Extract URLs from sitemap.xml."""
        import httpx
        import re
        urls = []
        
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for protocol in ['https', 'http']:
                try:
                    resp = await client.get(f"{protocol}://{domain}/sitemap.xml")
                    if resp.status_code == 200:
                        urls = re.findall(r'<loc>(.*?)</loc>', resp.text)
                        return urls[:100]
                except Exception:
                    pass
        
        return urls


async def crawl_site_structure(start_urls: List[str], max_requests: int = 50) -> List[Dict]:
    """Standalone function for easier imports."""
    service = CrawleeService()
    return await service.crawl_site_structure(start_urls, max_requests)


async def extract_serp_landscape(keyword: str, location: str = "India") -> Dict:
    """Standalone function for easier imports."""
    service = CrawleeService()
    return await service.extract_serp_landscape(keyword, location)


async def competitor_intelligence(domains: List[str], kw: List[str]) -> Dict:
    """Standalone function for easier imports."""
    service = CrawleeService()
    return await service.competitor_intelligence(domains, kw)