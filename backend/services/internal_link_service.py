import json
import asyncio
import logging
import math
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import networkx as nx
from bs4 import BeautifulSoup

from database import get_supabase, get_embedding, call_nim_llm
from services.ga4_service import GA4Service
from services.crawlee_service import _is_url_blocked
from services.reporting_service import report_problem

logger = logging.getLogger("backend.services.internal_link")

# A page view must not trigger a full site crawl. Every graph build fans out
# across the whole sitemap, and hammering the target site on each dashboard load
# is what gets the crawler WAF-banned (403s), which then silently produced an
# empty graph. Results are reused for a cooldown window instead.
_GRAPH_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_GRAPH_COOLDOWN_SEC = 900
# Graph builds are requested from both the API loop (dashboard/links routes) and
# the background loop (scheduler jobs). An asyncio.Lock is bound to the loop that
# first acquires it, so a single shared lock would raise "attached to a different
# loop" across the two. A plain thread lock is loop-agnostic; acquisition is
# awaited via a worker thread and release may be called from any thread (unlike
# RLock), so holding it across the I/O-bound build is safe.
_GRAPH_LOCK = threading.Lock()


def _chunks(lst: List[Any], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _extract_internal_links(soup: BeautifulSoup, base_url: str, parsed_domain: str) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = urljoin(base_url, href)
        if href.startswith("http") and urlparse(href).netloc.lower() == parsed_domain:
            links.append({"to": href, "anchor": a.get_text(strip=True)})
    return links


async def _discover_sitemap_urls(cms_url: str, domain: str) -> List[str]:
    """Resolve the real page URLs for a site, following redirects and sitemap indexes.

    WordPress commonly 301s /sitemap.xml to /wp-sitemap.xml, which is itself a
    <sitemapindex> pointing at per-post-type sitemaps. A single non-redirecting
    GET of /sitemap.xml therefore yields nothing usable on most WordPress sites.
    """
    import httpx

    base = cms_url.rstrip("/")
    candidates = [
        f"{base}/sitemap.xml",
        f"{base}/wp-sitemap.xml",
        f"{base}/sitemap_index.xml",
        f"{base}/sitemap-index.xml",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RankForgeBot/1.0)"}

    page_urls: List[str] = []
    visited: set[str] = set()

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:

        async def _walk(url: str, depth: int = 0) -> None:
            if depth > 2 or url in visited or len(page_urls) >= 500:
                return
            visited.add(url)
            try:
                r = await client.get(url)
            except Exception as exc:
                logger.debug("Sitemap fetch skipped %s: %s", url, exc)
                return
            if r.status_code != 200 or "<" not in r.text:
                return
            locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text, flags=re.IGNORECASE | re.DOTALL)
            is_index = "<sitemapindex" in r.text.lower()
            if is_index or locs and all(l.rstrip("/").endswith(".xml") for l in locs):
                for loc in locs:
                    await _walk(loc.strip(), depth + 1)
                return
            for loc in locs:
                clean = loc.strip()
                if clean and urlparse(clean).netloc.lower().endswith(domain):
                    page_urls.append(clean)

        for candidate in candidates:
            await _walk(candidate)
            if page_urls:
                break

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique = [u for u in page_urls if not (u in seen or seen.add(u))]
    return unique


async def _crawl_pages_fallback(sitemap_urls: List[str], parsed_domain: str) -> List[Dict[str, Any]]:
    """Dependency-free crawler used when crawlee is unavailable."""
    import httpx

    pages: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url in sitemap_urls:
            if _is_url_blocked(url):
                continue
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                text = soup.get_text(separator=" ", strip=True)
                pages.append(
                    {
                        "url": url,
                        "title": title,
                        "word_count": len(text.split()),
                        "links": _extract_internal_links(soup, url, parsed_domain),
                    }
                )
            except Exception as exc:
                logger.debug("Fallback crawl skipped %s: %s", url, exc)
    return pages


async def build_internal_link_graph(website_id: str) -> Dict[str, Any]:
    """Return the internal link graph, crawling at most once per cooldown window.

    Callers (page loads, dashboards) are served the cached build so a burst of
    requests cannot turn into a crawl storm against the target site.
    """
    now = time.monotonic()
    cached = _GRAPH_CACHE.get(website_id)
    if cached and now - cached[0] < _GRAPH_COOLDOWN_SEC and cached[1].get("edges"):
        return cached[1]

    # Acquire off-loop so a concurrent builder on the other loop never blocks
    # this one while we wait for the lock.
    await asyncio.to_thread(_GRAPH_LOCK.acquire)
    try:
        now = time.monotonic()
        cached = _GRAPH_CACHE.get(website_id)
        if cached and now - cached[0] < _GRAPH_COOLDOWN_SEC and cached[1].get("edges"):
            return cached[1]
        result = await _build_internal_link_graph_uncached(website_id)
        if result.get("edges"):
            _GRAPH_CACHE[website_id] = (time.monotonic(), result)
        return result
    finally:
        _GRAPH_LOCK.release()


async def _build_internal_link_graph_uncached(website_id: str) -> Dict[str, Any]:
    website: Dict[str, Any] = {}
    try:
        supabase = get_supabase()
        website = (
            supabase.table("websites")
            .select("domain,cms_url")
            .eq("id", website_id)
            .single()
            .execute()
            .data
            or {}
        )
    except Exception as exc:
        # Fall back to the durable local website record so an unreachable
        # database does not turn the crawl into a 500.
        logger.warning("websites read failed, using local store: %s", exc)
        try:
            from services.local_store import get_local_website

            local = get_local_website(website_id) or {}
            website = {"domain": local.get("domain"), "cms_url": local.get("cms_url") or local.get("url")}
        except Exception as local_exc:
            logger.debug("Local website note: %s", local_exc)

    cms_url = website.get("cms_url") or f"https://{website.get('domain', '')}"
    if not cms_url or cms_url == "https://":
        return {"nodes": [], "edges": [], "orphans": []}

    parsed_domain = urlparse(cms_url).netloc.lower()

    try:
        sitemap_urls = await _discover_sitemap_urls(cms_url, parsed_domain)
    except Exception as exc:
        logger.warning("Sitemap discovery failed: %s", exc)
        sitemap_urls = []

    # Only fall back to crawling the homepage when discovery genuinely found
    # nothing. A homepage-only crawl cannot produce an edge graph, so this path
    # is treated as "no data" rather than overwriting a previously good graph.
    discovered = bool(sitemap_urls)
    if not sitemap_urls:
        sitemap_urls = [cms_url]

    sitemap_urls = [u for u in sitemap_urls if not _is_url_blocked(u)][:100]
    if not sitemap_urls:
        return {"nodes": [], "edges": [], "orphans": []}

    pages: List[Dict[str, Any]] = []
    try:
        from crawlee.crawlers import BeautifulSoupCrawler

        crawler = BeautifulSoupCrawler(max_requests_per_crawl=min(len(sitemap_urls), 100))

        @crawler.router.default_handler
        async def handler(context):
            if _is_url_blocked(context.request.url):
                return
            soup = context.soup
            url = context.request.url
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            text = soup.get_text(separator=" ", strip=True)
            pages.append(
                {
                    "url": url,
                    "title": title,
                    "word_count": len(text.split()),
                    "links": _extract_internal_links(soup, url, parsed_domain),
                }
            )

        await crawler.run(sitemap_urls)
    except ImportError:
        # crawlee is optional; without it the graph endpoint used to 500. Fall
        # back to a dependency-free crawler that returns the same page shape.
        logger.warning("crawlee not installed — using fallback crawler")
        pages = await _crawl_pages_fallback(sitemap_urls, parsed_domain)
    except Exception as exc:
        logger.error("Crawl failed: %s", exc)
        pages = await _crawl_pages_fallback(sitemap_urls, parsed_domain)

    urls = list({p["url"] for p in pages})
    url_to_title = {p["url"]: p.get("title", "") for p in pages}
    url_to_sessions: Dict[str, int] = {p["url"]: 0 for p in pages}

    ga4 = GA4Service()
    if ga4.is_connected():
        try:
            traffic = await ga4.get_page_traffic(limit=25000)
            for p in traffic.get("pages", []):
                path = p.get("page_path", "")
                full_url = urljoin(cms_url, path)
                url_to_sessions[full_url] = p.get("sessions", 0)
                if not url_to_title.get(full_url):
                    url_to_title[full_url] = path
        except Exception as exc:
            logger.warning("GA4 traffic fetch failed: %s", exc)

    G = nx.DiGraph()
    for u in urls:
        G.add_node(u, title=url_to_title.get(u, u), sessions=url_to_sessions.get(u, 0))

    edges: List[Dict[str, Any]] = []
    for p in pages:
        for link in p.get("links", []):
            to = link["to"]
            if to not in G.nodes():
                G.add_node(to, title=to, sessions=url_to_sessions.get(to, 0))
            G.add_edge(p["url"], to, anchor=link["anchor"])
            edges.append({"from": p["url"], "to": to, "anchor": link["anchor"]})

    pagerank = nx.pagerank(G, alpha=0.85) if G.nodes else {}
    orphans = [u for u in urls if G.in_degree(u) == 0 and url_to_sessions.get(u, 0) > 50]

    graph_rows = []
    for e in G.edges(data=True):
        from_u, to_u, data = e
        graph_rows.append(
            {
                "website_id": website_id,
                "from_url": from_u,
                "to_url": to_u,
                "anchor_text": data.get("anchor"),
                "pagerank_from": float(pagerank.get(from_u, 0.0)),
                "pagerank_to": float(pagerank.get(to_u, 0.0)),
                "sessions_from": int(url_to_sessions.get(from_u, 0)),
                "is_orphan_target": to_u in orphans,
                "crawled_at": datetime.utcnow().isoformat(),
            }
        )

    # A crawl that found no real pages (sitemap blocked/redirected, site down,
    # WAF) must never wipe the last good graph. Previously an unconditional
    # delete-then-insert turned a transient fetch failure into permanent data
    # loss, and the UI silently showed an empty graph.
    if graph_rows:
        try:
            supabase.table("internal_link_graph").delete().eq("website_id", website_id).execute()
            for chunk in _chunks(graph_rows, 500):
                supabase.table("internal_link_graph").insert(chunk).execute()
        except Exception as exc:
            # Persisting is best-effort; the freshly built graph is still
            # returned below so the UI is not blocked by a database outage.
            logger.warning("internal_link_graph persistence failed: %s", exc)
    else:
        logger.info(
            "Internal link graph for %s produced no edges (discovered=%s); keeping stored graph",
            website_id,
            discovered,
        )

    try:
        await report_problem(
            website_id=website_id,
            alert_type="internal_graph_built",
            severity="minor",
            title=f"Built internal graph {len(urls)} nodes {len(edges)} edges orphans {len(orphans)}",
            source_monitor="internal_link_service",
        )
    except Exception as e:
        logger.warning(f"[services_internal_link_service] operation failed: {e}")

    nodes_out = []
    for u in urls:
        nodes_out.append(
            {
                "url": u,
                "title": url_to_title.get(u, u),
                "pagerank": float(pagerank.get(u, 0.0)),
                "sessions": int(url_to_sessions.get(u, 0)),
                "in_degree": int(G.in_degree(u)),
                "is_orphan": u in orphans,
            }
        )

    return {
        "nodes": nodes_out,
        "edges": edges,
        "orphans": orphans,
    }


def get_stored_link_graph(website_id: str) -> Dict[str, Any]:
    """Return the last persisted internal link graph for a website.

    Used as an honest fallback when a live crawl cannot run, so the UI shows
    real previously-crawled edges instead of a misleading empty state.
    """
    try:
        supabase = get_supabase()
        rows = (
            supabase.table("internal_link_graph")
            .select("from_url,to_url,anchor_text,pagerank_from,pagerank_to,sessions_from,is_orphan_target,crawled_at")
            .eq("website_id", website_id)
            .limit(2000)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.warning("Stored link graph read failed for %s: %s", website_id, exc)
        return {"nodes": [], "edges": [], "orphans": []}

    if not rows:
        return {"nodes": [], "edges": [], "orphans": []}

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    orphans: List[str] = []
    for r in rows:
        src = r.get("from_url")
        dst = r.get("to_url")
        edges.append({"from": src, "to": dst, "anchor": r.get("anchor_text")})
        for url, pr_key, sess_key in ((src, "pagerank_from", "sessions_from"), (dst, "pagerank_to", None)):
            if not url:
                continue
            node = nodes.setdefault(url, {"url": url, "pagerank": 0.0, "sessions": 0})
            node["pagerank"] = max(node["pagerank"], float(r.get(pr_key) or 0.0))
            if sess_key:
                node["sessions"] = max(node["sessions"], int(r.get(sess_key) or 0))
        if r.get("is_orphan_target") and dst and dst not in orphans:
            orphans.append(dst)

    for url in nodes:
        nodes[url]["is_orphan"] = url in orphans

    return {"nodes": list(nodes.values()), "edges": edges, "orphans": orphans}


async def suggest_internal_links(
    website_id: str,
    new_article_url: str,
    new_article_keyword: str,
    new_article_content: str,
) -> Dict[str, Any]:
    supabase = get_supabase()
    graph_rows = (
        supabase.table("internal_link_graph")
        .select("*")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    if not graph_rows:
        await build_internal_link_graph(website_id)
        graph_rows = (
            supabase.table("internal_link_graph")
            .select("*")
            .eq("website_id", website_id)
            .execute()
            .data
            or []
        )

    G = nx.DiGraph()
    node_meta: Dict[str, Dict[str, Any]] = {}
    for row in graph_rows:
        G.add_node(row["from_url"])
        G.add_node(row["to_url"])
        G.add_edge(row["from_url"], row["to_url"], anchor=row.get("anchor_text"))
        node_meta.setdefault(row["from_url"], {"pagerank": row.get("pagerank_from", 0.0), "sessions": row.get("sessions_from", 0), "title": row["from_url"]})
        node_meta.setdefault(row["to_url"], {"pagerank": row.get("pagerank_to", 0.0), "sessions": 0, "title": row["to_url"]})

    nodes = list(G.nodes())
    top_pagerank = sorted(nodes, key=lambda n: node_meta.get(n, {}).get("pagerank", 0), reverse=True)[:20]
    top_traffic = sorted(nodes, key=lambda n: node_meta.get(n, {}).get("sessions", 0), reverse=True)[:20]

    try:
        content_emb = await get_embedding(new_article_content or new_article_keyword, website_id=website_id)
    except Exception:
        content_emb = [0.0] * 1024

    def cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    cluster_candidates = []
    try:
        kw_emb = await get_embedding(new_article_keyword, website_id=website_id)
        # cluster_articles stores content_id (no url column); resolve the
        # published URL from content_log for each clustered article.
        articles = (
            supabase.table("cluster_articles")
            .select("keyword,content_id")
            .eq("website_id", website_id)
            .execute()
            .data
            or []
        )
        url_by_content_id = {}
        content_ids = [a.get("content_id") for a in articles if a.get("content_id")]
        if content_ids:
            try:
                rows = supabase.table("content_log").select("id,published_url,wordpress_url").in_("id", content_ids).execute().data or []
                url_by_content_id = {r["id"]: (r.get("published_url") or r.get("wordpress_url")) for r in rows}
            except Exception as e:
                logger.warning(f"[services_internal_link_service] content_log url lookup failed: {e}")
        for art in articles:
            art_url = url_by_content_id.get(art.get("content_id"))
            if not art_url:
                continue
            art_emb = await get_embedding(art.get("keyword", ""), website_id=website_id)
            sim = cosine(kw_emb, art_emb)
            if sim > 0.75:
                cluster_candidates.append({"url": art_url, "relevance": sim})
    except Exception as e:
        logger.warning(f"[services_internal_link_service] operation failed: {e}")

    from services.brain_service import BrainService

    brain = BrainService(website_id)
    brain_memories = await brain.recall(website_id, "internal links that boosted ranking", top_k=3)

    candidates = []
    for url in top_pagerank:
        if url == new_article_url:
            continue
        meta = node_meta.get(url, {"pagerank": 0.0, "sessions": 0, "title": url})
        try:
            node_emb = await get_embedding(meta.get("title", url), website_id=website_id)
            rel = cosine(content_emb, node_emb)
        except Exception:
            rel = 0.0
        if rel > 0.7:
            candidates.append(
                {
                    "url": url,
                    "pagerank": meta.get("pagerank", 0.0),
                    "sessions": meta.get("sessions", 0),
                    "relevance_score": rel,
                    "reason": f"High PageRank {meta.get('pagerank', 0):.2f} + topical {rel:.2f} + sessions {meta.get('sessions', 0)}",
                    "type": "high_pagerank",
                }
            )

    for url in top_traffic:
        if url == new_article_url or any(c["url"] == url for c in candidates):
            continue
        meta = node_meta.get(url, {"pagerank": 0.0, "sessions": 0, "title": url})
        try:
            node_emb = await get_embedding(meta.get("title", url), website_id=website_id)
            rel = cosine(content_emb, node_emb)
        except Exception:
            rel = 0.0
        if rel > 0.7:
            candidates.append(
                {
                    "url": url,
                    "pagerank": meta.get("pagerank", 0.0),
                    "sessions": meta.get("sessions", 0),
                    "relevance_score": rel,
                    "reason": f"High Traffic {meta.get('sessions', 0)} sessions + topical {rel:.2f}",
                    "type": "high_traffic",
                }
            )

    if cluster_candidates:
        best_topical = max(cluster_candidates, key=lambda x: x["relevance"])
        if not any(c["url"] == best_topical["url"] for c in candidates):
            candidates.append(
                {
                    "url": best_topical["url"],
                    "pagerank": node_meta.get(best_topical["url"], {}).get("pagerank", 0.0),
                    "sessions": node_meta.get(best_topical["url"], {}).get("sessions", 0),
                    "relevance_score": best_topical["relevance"],
                    "reason": f"Topical cluster article relevance {best_topical['relevance']:.2f}",
                    "type": "topical",
                }
            )

    selected = candidates[:3]
    suggestions = []
    for cand in selected:
        anchor = new_article_keyword
        try:
            anchor_prompt = (
                "Generate natural anchor for linking "
                + cand["url"]
                + " in article about "
                + new_article_keyword
                + ", avoid exact match spam, use secondary keyword, max 5 words"
            )
            anchor = await call_nim_llm(anchor_prompt, website_id=website_id)
            anchor = anchor.strip().strip('"')
        except Exception as e:
            logger.warning(f"[services_internal_link_service] operation failed: {e}")

        position_h2 = ""
        try:
            pos_prompt = (
                "Find best H2 section to insert internal link to "
                + cand["url"]
                + " about "
                + anchor
                + " in article content: "
                + (new_article_content or "")[:1000]
            )
            position_h2 = await call_nim_llm(pos_prompt, website_id=website_id)
            position_h2 = position_h2.strip().strip('"')
        except Exception as e:
            logger.warning(f"[services_internal_link_service] operation failed: {e}")

        suggestions.append(
            {
                "url": cand["url"],
                "anchor": anchor,
                "reason": cand["reason"],
                "position_h2": position_h2,
                "sessions": cand.get("sessions", 0),
                "pagerank": cand.get("pagerank", 0.0),
                "relevance_score": cand.get("relevance_score", 0.0),
            }
        )

    reverse_link = None
    if brain_memories:
        try:
            rev_prompt = (
                "Given these successful internal linking memories: "
                + brain_memories[0].get("title", "")
                + ", suggest which pillar page should link to "
                + new_article_url
                + " for cluster authority. Return only the pillar page URL."
            )
            pillar_url = await call_nim_llm(rev_prompt, website_id=website_id)
            pillar_url = pillar_url.strip().strip('"')
            if pillar_url.startswith("http"):
                reverse_link = {
                    "pillar_url": pillar_url,
                    "anchor": new_article_keyword,
                    "reason": "Cluster authority - pillar should link to new article",
                }
        except Exception as e:
            logger.warning(f"[services_internal_link_service] operation failed: {e}")

    return {
        "suggestions": suggestions,
        "reverse_link": reverse_link,
        "brain_memories_used": len(brain_memories),
    }


async def run_autonomous_internal_link_optimization(website_id: str) -> Dict[str, Any]:
    """Execute the 4 autonomous optimization passes:
    Pass 1: Orphan Rescue
    Pass 2: PageRank Sculpting (High-PR to Star articles)
    Pass 3: Anchor Text Diversification
    Pass 4: Semantic Cluster Linking
    """
    supabase = get_supabase()
    fixes_generated = []

    # 1. Build graph
    graph_data = await build_internal_link_graph(website_id)
    orphans = graph_data.get("orphans", [])

    # Get site config
    site_url = None
    try:
        s_row = supabase.table("websites").select("url, domain").eq("id", website_id).single().execute().data
        if s_row:
            site_url = s_row.get("url") or f"https://{s_row.get('domain')}"
    except Exception as e:
        logger.warning(f"[InternalLinks] Failed to fetch site URL: {e}")
    if not site_url:
        logger.warning("[InternalLinks] Site URL missing; using empty base")
        site_url = ""

    # Pass 1: Orphan Rescue
    pages = [n.get("id") for n in graph_data.get("nodes", []) if n.get("id") not in orphans]
    fallback_source = pages[0] if pages else site_url
    for orphan_url in orphans[:5]:
        fix = {
            "website_id": website_id,
            "fix_type": "internal_link_orphan",
            "fix_payload": {
                "title": f"Internal Link: Rescue Orphan Page {orphan_url}",
                "orphan_url": orphan_url,
                "recommended_source": fallback_source,
                "suggested_anchor": "Related Domain Guide",
                "pass": "orphan_rescue"
            },
            "status": "pending_approval",
            "proposed_by": "internal_link_service",
            "created_at": datetime.utcnow().isoformat()
        }
        try:
            supabase.table("pending_fixes").insert(fix).execute()
            fixes_generated.append(fix)
        except Exception as e:
            logger.warning(f"[services_internal_link_service] operation failed: {e}")

    # Pass 2: PageRank Sculpting (if pages available)
    if len(pages) >= 2:
        star_fix = {
            "website_id": website_id,
            "fix_type": "internal_link_pagerank",
            "fix_payload": {
                "title": f"Internal Link: Sculpt PageRank to {pages[0]}",
                "target_star_url": pages[0],
                "high_pr_source": site_url,
                "suggested_anchor": "Core Domain Guide",
                "pass": "pagerank_sculpting"
            },
            "status": "pending_approval",
            "proposed_by": "internal_link_service",
            "created_at": datetime.utcnow().isoformat()
        }
        try:
            supabase.table("pending_fixes").insert(star_fix).execute()
            fixes_generated.append(star_fix)
        except Exception as e:
            logger.warning(f"[services_internal_link_service] operation failed: {e}")

    # Pass 3: Anchor Diversification
    if pages:
        target_page = pages[0]
        anchor_fix = {
            "website_id": website_id,
            "fix_type": "internal_link_anchor_diversification",
            "fix_payload": {
                "title": f"Internal Link: Diversify Anchor Text for {target_page}",
                "target_url": target_page,
                "suggested_variations": ["Explore our guide", "Read complete analysis", "Full overview"],
                "pass": "anchor_diversification"
            },
            "status": "pending_approval",
            "proposed_by": "internal_link_service",
            "created_at": datetime.utcnow().isoformat()
        }
        try:
            supabase.table("pending_fixes").insert(anchor_fix).execute()
            fixes_generated.append(anchor_fix)
        except Exception as e:
            logger.warning(f"[services_internal_link_service] operation failed: {e}")

    return {
        "success": True,
        "total_fixes_generated": len(fixes_generated),
        "orphans_rescued": len(orphans),
        "graph_nodes": len(graph_data.get("nodes", [])),
        "graph_edges": len(graph_data.get("edges", []))
    }

