"""Test full-site crawl discovers all subpages, not just single page."""
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

# Mock responses for a fake site https://example.com
SITEMAP_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/services</loc></url>
  <url><loc>https://example.com/blog</loc></url>
</urlset>"""

SITEMAP_INDEX_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>"""

HOMEPAGE_HTML = """
<html><head><title>Example Home</title></head>
<body>
<h1>Welcome to Example</h1>
<p>We provide services across Texas with expert team. This is a substantial paragraph with more than eighty characters to pass thin content filter and be indexed correctly for knowledge base chunks generation testing purpose.</p>
<nav>
<a href=\"/about\">About Us</a>
<a href=\"/services\">Our Services</a>
<a href=\"/contact\">Contact</a>
<a href=\"https://example.com/blog\">Blog</a>
</nav>
</body></html>
"""

ABOUT_HTML = """
<html><body><h1>About Us</h1><p>About page with sufficient content length exceeding eighty characters to be considered valid for indexing in knowledge base and chunk generation workflow testing.</p>
<a href=\"/team\">Team</a>
<a href=\"/\">Home</a>
</body></html>
"""
SERVICES_HTML = """
<html><body><h1>Services</h1><p>Services page content with detailed description exceeding eighty characters minimum length requirement for knowledge extraction and embedding indexing.</p>
<a href=\"/pricing\">Pricing</a>
</body></html>
"""
BLOG_HTML = """<html><body><h1>Blog</h1><p>Blog overview with enough text padding to pass length threshold for crawling and indexing via BFS discovery mechanism.</p></body></html>"""
CONTACT_HTML = """<html><body><h1>Contact</h1><p>Contact us with sufficient length content for indexing purposes, ensuring page is not skipped as thin content in crawl logic.</p></body></html>"""
TEAM_HTML = """<html><body><h1>Team</h1><p>Team page content filler text that is long enough to satisfy the eighty character minimum for extraction and chunk creation in knowledge service.</p></body></html>"""
PRICING_HTML = """<html><body><h1>Pricing</h1><p>Pricing details page filler content with enough length to be valid for indexing and ensure BFS depth traversal works correctly.</p></body></html>"""

RESP_MAP = {
    "https://example.com/sitemap.xml": (200, SITEMAP_XML, "application/xml"),
    "https://example.com/robots.txt": (200, "User-agent: *\nSitemap: https://example.com/sitemap.xml", "text/plain"),
    "https://example.com/wp-sitemap.xml": (404, "", "text/html"),
    "https://example.com/sitemap_index.xml": (404, "", "text/html"),
    "https://example.com/sitemap-index.xml": (404, "", "text/html"),
    "https://example.com/sitemap/sitemap.xml": (404, "", "text/html"),
    "https://example.com/post-sitemap.xml": (404, "", "text/html"),
    "https://example.com/page-sitemap.xml": (404, "", "text/html"),
    "https://example.com/sitemap-pages.xml": (200, SITEMAP_XML, "application/xml"),
    # Pages
    "https://example.com": (200, HOMEPAGE_HTML, "text/html"),
    "https://example.com/": (200, HOMEPAGE_HTML, "text/html"),
    "https://example.com/about": (200, ABOUT_HTML, "text/html"),
    "https://example.com/services": (200, SERVICES_HTML, "text/html"),
    "https://example.com/blog": (200, BLOG_HTML, "text/html"),
    "https://example.com/contact": (200, CONTACT_HTML, "text/html"),
    "https://example.com/about-us": (404, "", "text/html"),
    "https://example.com/our-services": (404, "", "text/html"),
    "https://example.com/team": (200, TEAM_HTML, "text/html"),
    "https://example.com/pricing": (200, PRICING_HTML, "text/html"),
    "https://example.com/practice-areas": (404, "", "text/html"),
    "https://example.com/news": (404, "", "text/html"),
    "https://example.com/faq": (404, "", "text/html"),
    "https://example.com/contact-us": (404, "", "text/html"),
}

class MockResponse:
    def __init__(self, status_code, text, ctype):
        self.status_code = status_code
        self.text = text
        self.content = text.encode()
        self.headers = {"content-type": ctype}

async def mock_get(self, url, *args, **kwargs):
    # Normalize url for lookup
    url_str = str(url).split("#")[0].split("?")[0].rstrip("/")
    # Try exact then with trailing slash variants
    key = url_str
    if key in RESP_MAP:
        code, txt, ctype = RESP_MAP[key]
        return MockResponse(code, txt, ctype)
    # Try with slash
    if key + "/" in RESP_MAP:
        code, txt, ctype = RESP_MAP[key + "/"]
        return MockResponse(code, txt, ctype)
    # Default 404
    return MockResponse(404, "", "text/html")

async def test_full_crawl():
    # Patch supabase and local_store and embedding
    with patch("backend.services.knowledge_service.get_supabase") as mock_supabase, \
         patch("backend.services.knowledge_service.list_local_knowledge") as mock_list_local, \
         patch("backend.services.knowledge_service.save_local_knowledge") as mock_save, \
         patch.object(httpx.AsyncClient, "get", new=mock_get):

        mock_table = MagicMock()
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_supabase.return_value.table.return_value.insert.return_value.execute.return_value.data = [{"id": "1"}]
        mock_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
        mock_table.execute.return_value.data = []
        mock_list_local.return_value = []

        # Patch ingest to avoid embedding calls — mock create_embeddings_batch
        with patch("backend.services.knowledge_service.KnowledgeService.create_embeddings_batch", new_callable=AsyncMock) as mock_emb, \
             patch("backend.services.knowledge_service.KnowledgeService.extract_entities", new_callable=AsyncMock) as mock_ent:
            mock_emb.return_value = [[0.1]*1536]
            mock_ent.return_value = {"people": [], "orgs": [], "locations": [], "laws": [], "services": [], "keywords": []}

            # Also patch httpx.AsyncClient context manager to use our mock
            original_ac = httpx.AsyncClient
            # We already patched get, but need to ensure __aenter__ returns self
            # Our mock_get is instance method, patch covers it

            from backend.services.knowledge_service import KnowledgeService
            ks = KnowledgeService(website_id="test-wid")
            # Mock os.getenv
            with patch.dict("os.environ", {"WP_SITE_URL": ""}):
                res = await ks.watch_business_website(target_site="https://example.com", max_pages=10, max_depth=3)
                print("=== Crawl result ===")
                print(f"success: {res.get('success')}")
                print(f"site_checked: {res.get('site_checked')}")
                print(f"urls_scanned: {res.get('urls_scanned')}")
                print(f"urls_discovered: {res.get('urls_discovered')}")
                print(f"new_pages_ingested: {res.get('new_pages_ingested')}")
                print(f"updated_pages: {res.get('updated_pages')}")
                print(f"total_chunks_indexed: {res.get('total_chunks_indexed')}")
                print(f"sitemap_urls_found: {res.get('sitemap_urls_found')}")
                print(f"sitemaps_visited: {res.get('sitemaps_visited')}")
                # Assertions
                assert res["success"] == True, "Crawl should succeed"
                assert res["urls_scanned"] >= 4, f"Should crawl at least 4 subpages (sitemap has 4), got {res['urls_scanned']}"
                assert res["total_chunks_indexed"] >= 1, "Should index at least 1 chunk"
                # Should have crawled more than single page
                if res["urls_scanned"] <= 1:
                    print("FAIL: crawl still only single page!")
                    return False
                print("PASS: full-site crawl correctly crawled multiple subpages")
                return True

if __name__ == "__main__":
    ok = asyncio.run(test_full_crawl())
    if ok:
        print("TEST PASSED")
    else:
        print("TEST FAILED")
