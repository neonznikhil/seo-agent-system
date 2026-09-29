import asyncio
import ipaddress
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from urllib.parse import urlparse, urljoin

logger = logging.getLogger("backend.services.crawlee_service")

# crawlee/playwright are optional. When they are absent the service used to raise
# ImportError from _ensure_initialized, which broke every crawler-backed feature
# (decay detection, competitor monitoring, SERP analysis, the writer agent). We
# now fall back to an httpx/BeautifulSoup fetch and a Serper-backed SERP.
try:
    from crawlee.crawlers import BeautifulSoupCrawler, PlaywrightCrawler

    CRAWLEE_AVAILABLE = True
except ImportError:
    BeautifulSoupCrawler = None  # type: ignore[assignment]
    PlaywrightCrawler = None  # type: ignore[assignment]
    CRAWLEE_AVAILABLE = False
    logger.info("crawlee not installed — using httpx fallback crawler")

try:
    import playwright  # noqa: F401

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - bs4 is a hard dependency
    BeautifulSoup = None  # type: ignore[assignment]

_USER_AGENT = "Mozilla/5.0 (compatible; RankForgeBot/1.0; +https://rankforge.ai/bot)"

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
        # crawlee is optional; when it is missing we degrade to the httpx
        # fallback rather than raising, so callers keep working.
        self._initialized = True

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

    @staticmethod
    def _parse_page(html: str, url: str, source: str = "httpx_fallback") -> Dict[str, Any]:
        """Extract the same page shape the crawlee handler produces."""
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if (href.startswith("/") or href.startswith("http")) and not _is_url_blocked(href):
                links.append(href)
        schemas = []
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                schema_data = json.loads(s.string) if s.string else None
                if schema_data:
                    schemas.append(schema_data)
            except (json.JSONDecodeError, TypeError):
                pass
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        canonical_tag = soup.find("link", rel="canonical")
        text_content = soup.get_text(separator=" ", strip=True)
        return {
            "url": url,
            "title": title,
            "h1s": [h.get_text(strip=True) for h in soup.find_all("h1")],
            "h2s": [h.get_text(strip=True) for h in soup.find_all("h2")],
            "h3s": [h.get_text(strip=True) for h in soup.find_all("h3")],
            "word_count": len(text_content.split()),
            "links": links[:100],
            "schemas": schemas,
            "meta_description": meta_desc_tag["content"] if meta_desc_tag else None,
            "canonical": canonical_tag["href"] if canonical_tag else None,
            "crawled_at": datetime.utcnow().isoformat(),
            "source": source,
        }

    async def _fetch_page(self, client, url: str) -> Optional[Dict[str, Any]]:
        try:
            resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
            if resp.status_code != 200:
                return None
            return self._parse_page(resp.text, url)
        except Exception as exc:
            logger.debug("Fallback fetch skipped %s: %s", url, exc)
            return None

    async def _crawl_site_structure_fallback(self, start_urls: List[str], max_requests: int) -> List[Dict]:
        """httpx/BeautifulSoup crawler used when crawlee is unavailable."""
        import httpx

        results: List[Dict] = []
        seen: set = set()
        queue = list(start_urls)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            while queue and len(results) < max_requests:
                url = queue.pop(0)
                if url in seen or _is_url_blocked(url):
                    continue
                seen.add(url)
                page = await self._fetch_page(client, url)
                if page is None:
                    continue
                results.append(page)
                for link in page["links"]:
                    if link.startswith("/"):
                        link = urljoin(url, link)
                    if link not in seen and len(seen) + len(queue) < max_requests * 4:
                        queue.append(link)
        return results

    async def _crawl_pages_for_serp_fallback(self, pages: List[Dict]) -> None:
        """Populate SERP page detail (h1/h2/word_count/schema) without playwright."""
        import httpx

        targets = [p["url"] for p in pages if p.get("url") and not _is_url_blocked(p["url"])][:5]
        if not targets:
            return
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for page in pages:
                if page.get("url") not in targets:
                    continue
                fetched = await self._fetch_page(client, page["url"])
                if not fetched:
                    continue
                page["h1"] = fetched["h1s"]
                page["h2s"] = fetched["h2s"][:10]
                page["word_count"] = fetched["word_count"]
                page["has_table"] = bool(fetched.get("schemas")) or False
                page["has_faq"] = any(
                    isinstance(s, dict) and s.get("@type") == "FAQPage" for s in fetched.get("schemas", [])
                )
                page["schemas"] = [
                    s.get("@type", "Unknown")
                    for s in fetched.get("schemas", [])
                    if isinstance(s, dict)
                ]

    async def _serp_fallback(self, keyword: str, count: int) -> Optional[List[Dict]]:
        """Build the SERP result set from Serper when playwright is unavailable.

        Returns None when no live search provider is configured, so the caller
        can report an honest degraded result instead of inventing competitors.
        """
        try:
            from services.serper_service import serper_service

            if not serper_service.is_configured():
                return None
            res = await serper_service.search(keyword, num=count)
            organic = res.get("organic", []) if isinstance(res, dict) else []
            if not organic:
                return None
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "h1": None,
                    "h2s": [],
                    "word_count": 0,
                    "has_table": False,
                    "has_faq": False,
                    "schemas": [],
                }
                for item in organic[:count]
                if item.get("link") and not _is_url_blocked(item["link"])
            ]
        except Exception as exc:
            logger.warning("Serper SERP fallback failed: %s", exc)
            return None

    async def crawl_site_structure(self, start_urls: List[str], max_requests: int = 50) -> List[Dict]:
        """Crawl site structure and extract real data from pages."""
        await self._ensure_initialized()

        start_urls = self._sanitize_start_urls(start_urls)
        if not start_urls:
            return []

        if not CRAWLEE_AVAILABLE:
            return await self._crawl_site_structure_fallback(start_urls, max_requests)

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

        if not CRAWLEE_AVAILABLE or not PLAYWRIGHT_AVAILABLE:
            return await self._extract_serp_landscape_fallback(keyword, count)

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
            fallback = await self._extract_serp_landscape_fallback(keyword, count)
            if fallback.get("top_pages"):
                return fallback
            return {
                'keyword': keyword,
                'error': str(e),
                'top_pages': [],
                'winning_patterns': {},
                'source': 'crawlee_serp'
            }

        if not serp_data['top_pages']:
            # Google returned nothing (blocked/CAPTCHA) — try the live Serper
            # provider rather than reporting an empty landscape.
            fallback = await self._extract_serp_landscape_fallback(keyword, count)
            if fallback.get("top_pages"):
                return fallback

        return serp_data
    
    async def _extract_serp_landscape_fallback(self, keyword: str, count: int) -> Dict:
        """SERP landscape without crawlee/playwright.

        Uses Serper (a real live provider) when configured, otherwise returns an
        explicit degraded result — never fabricated competitor data.
        """
        base = {
            "keyword": keyword,
            "top_pages": [],
            "winning_patterns": {
                "avg_word_count": 0,
                "common_h2s": [],
                "has_table": False,
                "has_faq": False,
                "schema_types": [],
            },
            "source": "serper_fallback",
        }
        top_pages = await self._serp_fallback(keyword, count)
        if not top_pages:
            base["source"] = "unavailable"
            base["error"] = "No live SERP provider configured (crawlee/playwright and Serper both unavailable)."
            return base

        await self._crawl_pages_for_serp_fallback(top_pages)
        base["top_pages"] = top_pages
        base["winning_patterns"] = self._calculate_winning_patterns(top_pages)
        return base

    async def _deep_crawl_serp_pages(self, pages: List[Dict]) -> None:
        """Deep crawl SERP result pages for detailed analysis."""
        await self._ensure_initialized()

        if not CRAWLEE_AVAILABLE:
            await self._crawl_pages_for_serp_fallback(pages)
            return

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