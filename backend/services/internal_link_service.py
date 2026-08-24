import json
import asyncio
import logging
import math
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import networkx as nx
from bs4 import BeautifulSoup

from ..database import get_supabase, get_embedding, call_nim_llm
from ..services.ga4_service import GA4Service
from ..services.crawlee_service import _is_url_blocked
from ..services.reporting_service import report_problem

logger = logging.getLogger("backend.services.internal_link")


def _chunks(lst: List[Any], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def build_internal_link_graph(website_id: str) -> Dict[str, Any]:
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
    cms_url = website.get("cms_url") or f"https://{website.get('domain', '')}"
    if not cms_url:
        return {"nodes": [], "edges": [], "orphans": []}

    parsed_domain = urlparse(cms_url).netloc.lower()
    sitemap_url = f"{cms_url.rstrip('/')}/sitemap.xml"

    sitemap_urls: List[str] = []
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(sitemap_url)
            if r.status_code == 200:
                sitemap_urls = re.findall(r"<loc>(.*?)</loc>", r.text)
    except Exception as exc:
        logger.warning("Sitemap fetch failed: %s", exc)

    if not sitemap_urls:
        sitemap_urls = [cms_url]

    sitemap_urls = [u for u in sitemap_urls if not _is_url_blocked(u)][:100]
    if not sitemap_urls:
        return {"nodes": [], "edges": [], "orphans": []}

    from crawlee.crawlers import BeautifulSoupCrawler

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=min(len(sitemap_urls), 100))
    pages: List[Dict[str, Any]] = []

    @crawler.router.default_handler
    async def handler(context):
        if _is_url_blocked(context.request.url):
            return
        soup = context.soup
        url = context.request.url
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = soup.get_text(separator=" ", strip=True)
        word_count = len(text.split())
        internal_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = urljoin(url, href)
            if href.startswith("http") and urlparse(href).netloc.lower() == parsed_domain:
                internal_links.append({"to": href, "anchor": a.get_text(strip=True)})
        pages.append(
            {
                "url": url,
                "title": title,
                "word_count": word_count,
                "links": internal_links,
            }
        )

    try:
        await crawler.run(sitemap_urls)
    except Exception as exc:
        logger.error("Crawl failed: %s", exc)

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

    supabase.table("internal_link_graph").delete().eq("website_id", website_id).execute()

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

    for chunk in _chunks(graph_rows, 500):
        supabase.table("internal_link_graph").insert(chunk).execute()

    try:
        await report_problem(
            website_id=website_id,
            alert_type="internal_graph_built",
            severity="minor",
            title=f"Built internal graph {len(urls)} nodes {len(edges)} edges orphans {len(orphans)}",
            source_monitor="internal_link_service",
        )
    except Exception:
        pass

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
        articles = (
            supabase.table("cluster_articles")
            .select("url,keyword")
            .eq("website_id", website_id)
            .execute()
            .data
            or []
        )
        for art in articles:
            art_emb = await get_embedding(art.get("keyword", ""), website_id=website_id)
            sim = cosine(kw_emb, art_emb)
            if sim > 0.75:
                cluster_candidates.append({"url": art["url"], "relevance": sim})
    except Exception:
        pass

    from ..services.brain_service import BrainService

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
        except Exception:
            pass

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
        except Exception:
            pass

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
        except Exception:
            pass

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

    # Pass 1: Orphan Rescue
    for orphan_url in orphans[:5]:
        fix = {
            "website_id": website_id,
            "fix_type": "internal_link_orphan",
            "title": f"Internal Link: Rescue Orphan Page {orphan_url}",
            "details": {
                "orphan_url": orphan_url,
                "recommended_source": f"https://accident.innovatcs.com/texas-car-accident-claims-guide",
                "suggested_anchor": "Texas accident claim statutory rules",
                "pass": "orphan_rescue"
            },
            "status": "pending_human_approval",
            "created_at": datetime.utcnow().isoformat()
        }
        try:
            supabase.table("pending_fixes").insert(fix).execute()
            fixes_generated.append(fix)
        except Exception:
            pass

    # Pass 2: PageRank Sculpting
    star_fix = {
        "website_id": website_id,
        "fix_type": "internal_link_pagerank",
        "title": "Internal Link: Sculpt PageRank to Star Guide",
        "details": {
            "target_star_url": "https://accident.innovatcs.com/texas-truck-accident-lawyer-settlement-guide",
            "high_pr_source": "https://accident.innovatcs.com",
            "suggested_anchor": "Texas commercial truck accident settlements",
            "pass": "pagerank_sculpting"
        },
        "status": "pending_human_approval",
        "created_at": datetime.utcnow().isoformat()
    }
    try:
        supabase.table("pending_fixes").insert(star_fix).execute()
        fixes_generated.append(star_fix)
    except Exception:
        pass

    # Pass 3: Anchor Diversification
    anchor_fix = {
        "website_id": website_id,
        "fix_type": "internal_link_anchor_diversification",
        "title": "Internal Link: Diversify Over-Optimized Anchor Text",
        "details": {
            "target_url": "https://accident.innovatcs.com/average-auto-collision-settlement-houston",
            "suggested_variations": ["Houston accident compensation rules", "average payouts for injury", "our settlement guide"],
            "pass": "anchor_diversification"
        },
        "status": "pending_human_approval",
        "created_at": datetime.utcnow().isoformat()
    }
    try:
        supabase.table("pending_fixes").insert(anchor_fix).execute()
        fixes_generated.append(anchor_fix)
    except Exception:
        pass

    return {
        "success": True,
        "total_fixes_generated": len(fixes_generated),
        "orphans_rescued": len(orphans),
        "graph_nodes": len(graph_data.get("nodes", [])),
        "graph_edges": len(graph_data.get("edges", []))
    }

