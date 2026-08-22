import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from ..database import get_supabase
from ..services.internal_link_service import build_internal_link_graph, suggest_internal_links
from ..services.backlink_prospect_service import find_backlink_prospects, monitor_backlinks
from ..services.outreach_draft_service import create_outreach_draft, mark_outreach_sent

logger = logging.getLogger("backend.routers.backlinks")
router = APIRouter()


def parse_links_from_html(html: str) -> list:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    return [l for l in links if l and l.startswith('http')]


async def crawl_for_prospects(url: str) -> list:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000)
            content = await page.content()
            await browser.close()
            return parse_links_from_html(content)
    except ImportError:
        # Fallback to httpx
        import httpx
        from bs4 import BeautifulSoup
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 RankForge/1.0'
                })
            soup = BeautifulSoup(r.text, 'html.parser')
            links = [a.get('href') for a in soup.find_all('a', href=True)]
            return [l for l in links if l and l.startswith('http')]
        except Exception as e:
            print(f"Crawl fallback failed: {e}")
            return []
    except Exception as e:
        print(f"Crawl error: {e}")
        return []



@router.get("/backlinks/{website_id}")
async def get_backlinks_dashboard(website_id: str):
    supabase = get_supabase()
    prospects = (
        supabase.table("backlink_prospects")
        .select("*")
        .eq("website_id", website_id)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
        .data
        or []
    )
    monitor = (
        supabase.table("backlink_monitor")
        .select("*")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    outreach = (
        supabase.table("outreach_drafts")
        .select("*")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    graph_rows = (
        supabase.table("internal_link_graph")
        .select("*")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    nodes = {}
    for r in graph_rows:
        nodes.setdefault(
            r["from_url"],
            {
                "url": r["from_url"],
                "pagerank": r.get("pagerank_from", 0),
                "sessions": r.get("sessions_from", 0),
                "in_degree": 0,
                "is_orphan": False,
            },
        )
        nodes.setdefault(
            r["to_url"],
            {
                "url": r["to_url"],
                "pagerank": r.get("pagerank_to", 0),
                "sessions": 0,
                "in_degree": 0,
                "is_orphan": r.get("is_orphan_target", False),
            },
        )
    for r in graph_rows:
        nodes[r["to_url"]]["in_degree"] = nodes[r["to_url"]].get("in_degree", 0) + 1
    orphans = [u for u, n in nodes.items() if n["in_degree"] == 0 and n["sessions"] > 50]
    for u in orphans:
        nodes[u]["is_orphan"] = True
    graph_data = {
        "nodes": list(nodes.values()),
        "edges": [
            {"from": r["from_url"], "to": r["to_url"], "anchor": r.get("anchor_text", "")}
            for r in graph_rows
        ],
        "orphans": orphans,
    }
    brain_memories = (
        supabase.table("brain_memory")
        .select("*")
        .eq("website_id", website_id)
        .eq("source_type", "backlink")
        .execute()
        .data
        or []
    )
    return {
        "prospects": prospects,
        "monitor": monitor,
        "outreach": outreach,
        "graph": graph_data,
        "brain_memories": brain_memories,
    }


@router.post("/backlinks/{website_id}/prospect")
async def post_prospect(website_id: str, body: Dict[str, Any]):
    keyword = body.get("primary_keyword")
    target_page_url = body.get("target_page_url")
    if not keyword:
        raise HTTPException(400, "primary_keyword required")
    try:
        prospects = await find_backlink_prospects(
            website_id, keyword, target_page_url=target_page_url
        )
        return {"prospects": prospects}
    except Exception as exc:
        logger.error("Prospect search failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.post("/backlinks/{website_id}/graph/rebuild")
async def rebuild_graph(website_id: str):
    try:
        result = await build_internal_link_graph(website_id)
        return result
    except Exception as exc:
        logger.error("Graph rebuild failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.post("/backlinks/{website_id}/check")
async def check_backlinks(website_id: str):
    try:
        result = await monitor_backlinks(website_id)
        return result
    except Exception as exc:
        logger.error("Monitor failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.post("/links/{website_id}/suggest")
async def suggest_links(website_id: str, body: Dict[str, Any]):
    url = body.get("url")
    keyword = body.get("keyword")
    if not url or not keyword:
        raise HTTPException(400, "url and keyword required")
    try:
        result = await suggest_internal_links(website_id, url, keyword, "")
        return result
    except Exception as exc:
        logger.error("Suggest failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/links/{website_id}/graph")
async def get_graph(website_id: str):
    supabase = get_supabase()
    rows = (
        supabase.table("internal_link_graph")
        .select("*")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    nodes: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        nodes.setdefault(
            r["from_url"],
            {
                "url": r["from_url"],
                "pagerank": r.get("pagerank_from", 0),
                "sessions": r.get("sessions_from", 0),
                "in_degree": 0,
                "is_orphan": False,
            },
        )
        nodes.setdefault(
            r["to_url"],
            {
                "url": r["to_url"],
                "pagerank": r.get("pagerank_to", 0),
                "sessions": 0,
                "in_degree": 0,
                "is_orphan": r.get("is_orphan_target", False),
            },
        )
    for r in rows:
        nodes[r["to_url"]]["in_degree"] = nodes[r["to_url"]].get("in_degree", 0) + 1

    orphans = [
        u for u, n in nodes.items() if n["in_degree"] == 0 and n["sessions"] > 50
    ]
    for u in orphans:
        nodes[u]["is_orphan"] = True

    return {
        "nodes": list(nodes.values()),
        "edges": [
            {"from": r["from_url"], "to": r["to_url"], "anchor": r.get("anchor_text", "")}
            for r in rows
        ],
        "orphans": orphans,
    }


@router.post("/backlinks/{website_id}/prospects/{prospect_id}/approve")
async def approve_prospect(website_id: str, prospect_id: str, request: Request):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(403, "Human approval required - provide X-User-Id header")
    try:
        draft_id = await create_outreach_draft(website_id, prospect_id, user_id)
        return {"draft_id": draft_id, "status": "draft_ready"}
    except Exception as exc:
        logger.error("Approve failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.post("/backlinks/{website_id}/outreach/{draft_id}/sent")
async def outreach_sent(website_id: str, draft_id: str, request: Request):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(403, "Human approval required - provide X-User-Id header")
    try:
        result = await mark_outreach_sent(website_id, draft_id, user_id)
        return result
    except Exception as exc:
        logger.error("Mark sent failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/backlinks/{website_id}/outreach")
async def get_outreach(website_id: str):
    supabase = get_supabase()
    rows = (
        supabase.table("outreach_drafts")
        .select("*")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    return rows
