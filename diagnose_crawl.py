"""
Knowledge Base Crawl Diagnostic Script
=======================================
Tests the new crawl_and_index_website function against a real website.
Creates a test website, runs crawl, and verifies results.

Usage: python diagnose_crawl.py
"""
import asyncio
import sys
import os
import uuid
import json
import re
from datetime import datetime

# Setup: load env
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

os.environ.setdefault('SUPABASE_URL', 'https://evpgxcuvcpihpasptcjk.supabase.co')

import httpx
from supabase import create_client

URL = os.environ['SUPABASE_URL']
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
client = create_client(URL, KEY)

TEST_SITE_URL = "https://accident.innovatcs.com"
TEST_WEBSITE_ID = str(uuid.uuid4())


async def check_nim():
    """Verify NVIDIA NIM is reachable for embeddings."""
    api_key = os.environ.get('NVIDIA_API_KEY', '')
    if not api_key:
        print("[WARN] NVIDIA_API_KEY not set")
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(
                "https://integrate.api.nvidia.com/v1/embeddings",
                json={"model": "nvidia/nemotron-3-embed-1b", "input": ["test"], "input_type": "query", "encoding_format": "float"},
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                dims = len(data.get("data", [{}])[0].get("embedding", []))
                print(f"[OK] NIM embedding works — {dims} dims")
                return True
            else:
                print(f"[WARN] NIM returned HTTP {resp.status_code}: {resp.text[:100]}")
                return False
    except Exception as e:
        print(f"[WARN] NIM embedding failed: {e}")
        return False


async def create_test_website():
    """Create a test website entry in the database. Returns website ID to use."""
    print(f"\n[STEP] Creating test website: {TEST_WEBSITE_ID}")
    try:
        result = client.table("websites").insert({
            "id": TEST_WEBSITE_ID,
            "domain": "accident.innovatcs.com",
            "url": TEST_SITE_URL,
            "cms_url": TEST_SITE_URL,
            "wordpress_url": TEST_SITE_URL,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
        if result.data:
            print(f"[OK] Website created: {result.data[0]['id']}")
            return TEST_WEBSITE_ID
        else:
            print(f"[FAIL] Insert returned no data")
            return None
    except Exception as e:
        err_str = str(e)
        if "duplicate" in err_str.lower() or "23505" in err_str:
            # Website already exists — fetch its ID
            print(f"[INFO] Website already exists, fetching existing ID...")
            try:
                existing = client.table("websites").select("id").eq("domain", "accident.innovatcs.com").limit(1).execute()
                if existing.data:
                    wid = existing.data[0]["id"]
                    print(f"[OK] Using existing website: {wid}")
                    return wid
            except Exception as fetch_err:
                print(f"[FAIL] Could not fetch existing website: {fetch_err}")
                return None
        print(f"[FAIL] Could not create website: {e}")
        return None


async def generate_embedding(text):
    """Generate embedding via NVIDIA NIM."""
    api_key = os.environ.get('NVIDIA_API_KEY', '')
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.post(
                "https://integrate.api.nvidia.com/v1/embeddings",
                json={"model": "nvidia/nemotron-3-embed-1b", "input": [text[:3500]], "input_type": "query", "encoding_format": "float"},
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                embedding = data.get("data", [{}])[0].get("embedding")
                # Truncate to 1024 dims to match DB column
                if embedding and len(embedding) > 1024:
                    embedding = embedding[:1024]
                return embedding
    except Exception as e:
        print(f"  [WARN] Embedding failed: {e}")
    return None


async def run_crawl():
    """Run the crawl logic directly (same as crawl_and_index_website)."""
    from bs4 import BeautifulSoup

    site_url = TEST_SITE_URL
    website_id = TEST_WEBSITE_ID

    results = {
        "website_id": website_id,
        "site_url": site_url,
        "pages_found": 0,
        "pages_crawled": 0,
        "chunks_created": 0,
        "chunks_saved": 0,
        "errors": []
    }

    print(f"\n[STEP] Starting crawl for {site_url}")

    # Update status
    try:
        client.table("websites").update({
            "status": "crawling",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", website_id).execute()
    except Exception as e:
        print(f"  [WARN] Status update failed: {e}")

    # Discover pages
    pages = []
    sitemap_urls = [
        f"{site_url.rstrip('/')}/sitemap.xml",
        f"{site_url.rstrip('/')}/wp-sitemap.xml",
        f"{site_url.rstrip('/')}/sitemap_index.xml",
        f"{site_url.rstrip('/')}/page-sitemap.xml",
        f"{site_url.rstrip('/')}/post-sitemap.xml",
    ]

    # Better headers to avoid 403
    crawl_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=crawl_headers) as http:
        # Helper: parse sitemap (handles both sitemap index and urlset)
        async def fetch_sitemap_urls(s_url: str) -> list:
            page_urls = []
            try:
                r = await http.get(s_url)
                if r.status_code != 200:
                    return page_urls
                soup = BeautifulSoup(r.text, 'xml')
                sitemap_locs = [sm.find('loc').text.strip() for sm in soup.find_all('sitemap') if sm.find('loc')]
                if sitemap_locs:
                    for sub_url in sitemap_locs:
                        sub_urls = await fetch_sitemap_urls(sub_url)
                        page_urls.extend(sub_urls)
                else:
                    for loc in soup.find_all('loc'):
                        txt = loc.text.strip() if loc.text else ""
                        if txt and not txt.endswith('.xml'):
                            page_urls.append(txt)
            except Exception as e:
                print(f"  [CRAWL] Sitemap parse error {s_url}: {e}")
            return page_urls

        # Try each sitemap
        for sitemap_url in sitemap_urls:
            found = await fetch_sitemap_urls(sitemap_url)
            if found:
                domain = site_url.rstrip('/')
                pages = [u for u in found
                         if u.startswith(domain)
                         and not any(skip in u.lower() for skip in
                                   ['wp-content', 'wp-includes', '.jpg', '.png', '.pdf',
                                    'attachment', 'feed', 'tag/', 'author/', 'page/2', 'page/3'])]
                print(f"  [OK] Found {len(pages)} pages in {sitemap_url}")
                break

        # Fallback: homepage links
        if not pages:
            print("  [INFO] No sitemap. Crawling homepage for links...")
            try:
                r = await http.get(site_url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    links = soup.find_all('a', href=True)
                    domain = site_url.rstrip('/')
                    seen = set()
                    pages = [site_url]
                    for link in links:
                        href = link['href']
                        if href.startswith('/'):
                            href = domain + href
                        if href.startswith(domain) and href not in seen:
                            if not any(skip in href.lower() for skip in
                                      ['.jpg', '.png', '.pdf', '.gif', 'wp-admin', 'wp-login', '#', 'mailto:', 'tel:']):
                                seen.add(href)
                                pages.append(href)
                    pages = list(set(pages))[:30]
                    print(f"  [OK] Found {len(pages)} pages from homepage links")
                else:
                    print(f"  [WARN] Homepage returned HTTP {r.status_code}")
            except Exception as e:
                results["errors"].append(f"Homepage crawl failed: {e}")
                print(f"  [FAIL] Homepage crawl: {e}")

        results["pages_found"] = len(pages)
        if not pages:
            pages = [site_url]
            print("  [INFO] Using homepage only")

        # Crawl pages
        all_chunks = []
        for page_url in pages[:50]:
            try:
                r = await http.get(page_url)
                if r.status_code != 200:
                    print(f"  [SKIP] {page_url} — HTTP {r.status_code}")
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')
                for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'noscript', 'iframe', 'svg', 'button']):
                    tag.decompose()

                main_content = (
                    soup.find('main') or
                    soup.find('article') or
                    soup.find(class_=re.compile(r'content|post|entry|article|main', re.I)) or
                    soup.find('body')
                )
                if not main_content:
                    continue

                title = ""
                title_tag = soup.find('h1') or soup.find('title')
                if title_tag:
                    title = title_tag.get_text().strip()[:200]

                text = main_content.get_text(separator=' ')
                text = re.sub(r'\s+', ' ', text).strip()

                if len(text) < 200:
                    print(f"  [SKIP] {page_url} — too little content ({len(text)} chars)")
                    continue

                results["pages_crawled"] += 1
                print(f"  [OK] Crawled {page_url} — {len(text)} chars")

                # Chunk
                chunk_size = 1500
                overlap = 200
                chunks = []
                start = 0
                while start < len(text):
                    end = start + chunk_size
                    if end < len(text):
                        last_period = text.rfind('.', start, end)
                        if last_period > start + (chunk_size // 2):
                            end = last_period + 1
                    chunk_text = text[start:end].strip()
                    if len(chunk_text) > 100:
                        titled_chunk = f"Page: {title}\n\n{chunk_text}" if title else chunk_text
                        chunks.append({
                            "fact": titled_chunk,
                            "source_url": page_url,
                            "fact_type": "company_info"
                        })
                    start = end - overlap

                all_chunks.extend(chunks)
                results["chunks_created"] += len(chunks)
                print(f"  [OK] Created {len(chunks)} chunks from {page_url}")

            except Exception as e:
                results["errors"].append(f"Failed to crawl {page_url}: {e}")
                print(f"  [FAIL] {page_url}: {e}")

        print(f"\n  [INFO] Total chunks created: {len(all_chunks)}")

        if not all_chunks:
            client.table("websites").update({
                "status": "error",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", website_id).execute()
            results["errors"].append("No content extracted")
            return results

        # Save to database with embeddings
        for i, chunk in enumerate(all_chunks):
            embedding = await generate_embedding(chunk["fact"])
            row = {
                "website_id": website_id,
                "fact": chunk["fact"],
                "fact_type": chunk["fact_type"],
                "source_url": chunk["source_url"]
            }
            if embedding:
                row["embedding"] = embedding

            try:
                insert_result = client.table("knowledge_base").insert(row).execute()
                if insert_result.data:
                    results["chunks_saved"] += 1
                else:
                    print(f"  [WARN] Insert returned no data for chunk {i}")
            except Exception as e:
                results["errors"].append(f"DB insert failed: {e}")
                print(f"  [FAIL] DB insert chunk {i}: {e}")

            if (i + 1) % 5 == 0:
                print(f"  [PROGRESS] Saved {results['chunks_saved']}/{len(all_chunks)} chunks")

    # Final status
    final_status = "active" if results["chunks_saved"] >= 3 else "error"
    try:
        client.table("websites").update({
            "status": final_status,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", website_id).execute()
    except Exception as e:
        print(f"  [WARN] Final status update failed: {e}")

    print(f"\n  [DONE] Status: {final_status}. Saved {results['chunks_saved']} chunks.")
    return results


async def verify_results():
    """Verify what ended up in the database."""
    print(f"\n[STEP] Verifying database results...")

    try:
        kb = client.table("knowledge_base").select("*").eq("website_id", TEST_WEBSITE_ID).execute()
        rows = kb.data or []
        print(f"\n  knowledge_base rows for this website: {len(rows)}")

        if rows:
            with_emb = sum(1 for r in rows if r.get("embedding"))
            without_emb = len(rows) - with_emb
            print(f"    With embeddings: {with_emb}")
            print(f"    Without embeddings: {without_emb}")

            urls = set(r.get("source_url") for r in rows if r.get("source_url"))
            print(f"    Unique source URLs: {len(urls)}")
            for u in list(urls)[:5]:
                print(f"      - {u}")

            print(f"\n    Sample chunk:")
            sample = rows[0]
            content = sample.get("fact", "")
            print(f"      {content[:200]}...")
        else:
            print("    *** NO ROWS IN KNOWLEDGE_BASE ***")
    except Exception as e:
        print(f"  [ERROR] Could not query knowledge_base: {e}")

    try:
        web = client.table("websites").select("*").eq("id", TEST_WEBSITE_ID).execute()
        if web.data:
            w = web.data[0]
            print(f"\n  Website status: {w.get('status')}")
    except Exception as e:
        print(f"  [ERROR] Could not query websites: {e}")


async def cleanup():
    """Remove test data."""
    print(f"\n[STEP] Cleaning up test data...")
    try:
        client.table("knowledge_base").delete().eq("website_id", TEST_WEBSITE_ID).execute()
        print("  Deleted knowledge_base rows")
    except Exception as e:
        print(f"  [WARN] Could not delete kb rows: {e}")
    try:
        client.table("websites").delete().eq("id", TEST_WEBSITE_ID).execute()
        print("  Deleted test website")
    except Exception as e:
        print(f"  [WARN] Could not delete website: {e}")


async def main():
    print("=" * 60)
    print("KNOWLEDGE BASE CRAWL DIAGNOSTIC")
    print("=" * 60)
    print(f"Target: {TEST_SITE_URL}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print(f"Key type: {'SERVICE_ROLE' if os.environ.get('SUPABASE_SERVICE_ROLE_KEY') else 'ANON'}")

    # Pre-check: NIM
    await check_nim()

    # Create test website
    website_id = await create_test_website()
    if not website_id:
        print("\n[FATAL] Cannot proceed without a website record.")
        print("  Check RLS policies — need service role key")
        return

    # Override the module-level ID for crawl and verify functions
    global TEST_WEBSITE_ID
    TEST_WEBSITE_ID = website_id

    # Run crawl
    results = await run_crawl()

    # Print results
    print("\n" + "=" * 60)
    print("CRAWL RESULTS")
    print("=" * 60)
    for k, v in results.items():
        if k == "errors":
            print(f"  {k}: {len(v)} errors")
            for err in v[:5]:
                print(f"    - {err}")
        else:
            print(f"  {k}: {v}")

    # Verify DB
    await verify_results()

    # Cleanup
    print("\n" + "=" * 60)
    cleanup_input = input("Delete test data? (y/n): ").strip().lower()
    if cleanup_input == 'y':
        await cleanup()
    else:
        print(f"Test data preserved. Website ID: {TEST_WEBSITE_ID}")

    print("\n[DONE]")


if __name__ == "__main__":
    asyncio.run(main())
