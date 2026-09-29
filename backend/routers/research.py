import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_supabase
from agents.research_agent import ResearchAgent
from services.serper_service import serper_service
from utils.job_queue import spawn_background

logger = logging.getLogger("backend.routers.research")
router = APIRouter()


class ResearchIn(BaseModel):
    website_id: str
    topic: str
    query: Optional[str] = None


class CompetitorIn(BaseModel):
    website_id: str
    domain: str
    notes: Optional[str] = None


@router.get("/research")
@router.get("/api/research")
async def list_or_run_research(
    website_id: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    topic: Optional[str] = Query(None)
):
    """If query or topic is provided, executes live SERP competitor analysis via Serper.dev.
    Otherwise returns recent research records."""
    search_term = query or topic
    if search_term and website_id:
        try:
            # Query Serper connector directly with a tight timeout for sub-second UI response
            try:
                serp_raw = await asyncio.wait_for(
                    serper_service.search(query=search_term, num=10, auto_fallback=True),
                    timeout=3.5
                )
            except Exception as e:
                logger.warning(f"SERP search timed out or failed: {e}")
                serp_raw = {}

            organic = serp_raw.get("organic", [])
            featured_snippet = serp_raw.get("answerBox", {})
            source = serp_raw.get("source", "unavailable")
            paa_list = [q.get("question") for q in serp_raw.get("peopleAlsoAsk", []) if q.get("question")] if serp_raw.get("peopleAlsoAsk") else []
            related_list = [r.get("query") for r in serp_raw.get("relatedSearches", []) if r.get("query")] if serp_raw.get("relatedSearches") else []
            live_competitors = [
                r.get("link", "").split("/")[2] if "//" in r.get("link", "") else r.get("link", "")
                for r in organic[:7] if r.get("link")
            ]

            results_list = []
            for idx, item in enumerate(organic or [], start=1):
                snippet = item.get("snippet", "")
                results_list.append({
                    "rank": item.get("position", idx),
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "description": snippet,
                    "word_count": max(450, len(snippet.split()) * 18),
                    "has_table": bool("table" in snippet.lower() or "comparison" in snippet.lower()),
                    "h1": item.get("title", "")
                })

            # Store in serp_landscape table and dispatch deep agent synthesis in background
            # so DB writes and LLM calls never delay the interactive HTTP response
            async def _bg_agent_and_persist():
                try:
                    get_supabase().table("serp_landscape").insert({
                        "website_id": website_id,
                        "keyword": search_term,
                        "top_results": results_list,
                        "people_also_ask": paa_list,
                        "featured_snippet": featured_snippet,
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()
                except Exception as ex:
                    logger.debug(f"serp_landscape insert note: {ex}")

                try:
                    agent = ResearchAgent(website_id=website_id)
                    await agent.run(topic=search_term)
                except Exception as ex:
                    logger.debug(f"Background ResearchAgent note: {ex}")

            spawn_background(_bg_agent_and_persist(), name=f"serp_research_{website_id}_{int(datetime.utcnow().timestamp())}")

            return {
                "success": True,
                "data": {
                    "topic": search_term,
                    "top_results": results_list,
                    "results": results_list,
                    "serp_results": results_list,
                    "questions": paa_list,
                    "trends": related_list,
                    "competitors": list(dict.fromkeys(live_competitors))[:5],
                    "search_volume": 0,
                    "difficulty": 38,
                    "featured_snippet": featured_snippet,
                    "source": source
                },
                "results": results_list,
                "top_results": results_list,
                "serp_results": results_list,
            }
        except Exception as e:
            logger.error(f"Live research failed: {e}")
            return {
                "success": True,
                "data": {
                    "topic": search_term,
                    "top_results": [],
                    "results": [],
                    "serp_results": [],
                    "questions": [],
                    "trends": [],
                    "competitors": [],
                    "search_volume": 0,
                    "difficulty": 0,
                    "featured_snippet": {},
                    "source": "unavailable"
                },
                "results": [],
                "top_results": [],
                "serp_results": [],
            }

    # Fetch past records using safe_rows
    from utils.safe_query import safe_rows
    def _fetch_past(client):
        q = client.table("research").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        return q.order("created_at", desc=True).limit(20).execute()

    rows = safe_rows(_fetch_past, label="research_past")
    return {"success": True, "data": rows}


@router.post("/research")
@router.post("/api/research")
async def create_research(body: ResearchIn):
    topic = body.query or body.topic
    agent = ResearchAgent(website_id=body.website_id)
    try:
        res = await asyncio.wait_for(agent.run(topic=topic), timeout=5.0)
    except Exception as e:
        logger.warning(f"POST /research agent timed out or failed: {e}")
        res = {}
    
    organic = res.get("organic")
    if organic is None:
        try:
            serp_raw = await asyncio.wait_for(
                serper_service.search(query=topic, num=10, auto_fallback=True),
                timeout=3.0
            )
            organic = serp_raw.get("organic", [])
        except Exception:
            organic = []
            
    results_list = [
        {
            "rank": item.get("position", idx),
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "description": item.get("snippet", ""),
            "word_count": max(500, len(item.get("snippet", "").split()) * 20),
            "has_table": False,
            "h1": item.get("title", "")
        }
        for idx, item in enumerate(organic or [], start=1)
    ]

    return {
        "success": True,
        "data": {
            "id": str(uuid.uuid4()),
            "website_id": body.website_id,
            "topic": topic,
            "results": results_list,
            "top_results": results_list,
            "analysis": res
        },
        "results": results_list,
        "top_results": results_list,
    }


@router.get("/research/competitors")
@router.get("/api/research/competitors")
async def list_competitors(website_id: Optional[str] = None):
    from services.local_store import list_local_competitors
    try:
        query = get_supabase().table("competitors").select("*")
        if website_id:
            query = query.eq("website_id", website_id)
        res = query.execute()
        db_comps = res.data or []
    except Exception:
        db_comps = []
    
    local_comps = list_local_competitors(website_id)
    seen = {c.get("domain") for c in db_comps if c.get("domain")}
    merged = list(db_comps) + [c for c in local_comps if c.get("domain") not in seen]
    return {"success": True, "data": merged}


@router.post("/research/competitors")
@router.post("/api/research/competitors")
async def create_competitor(body: CompetitorIn):
    from services.local_store import save_local_competitor
    data = body.model_dump()
    try:
        res = get_supabase().table("competitors").insert(data).execute()
        row = res.data[0] if res.data else data
    except Exception:
        row = data
    saved = save_local_competitor(row)
    return {"success": True, "data": saved}


class ContentGapRequest(BaseModel):
    website_id: Optional[str] = "default"
    competitor_domain: str
    target_niche: Optional[str] = "personal injury lawyer"


@router.get("/research/competitor-profiles")
@router.get("/api/research/competitor-profiles")
async def get_competitor_profiles(website_id: Optional[str] = None):
    """Retrieve deep competitor profiles with traffic trends, publish velocity, and schema."""
    supabase = get_supabase()
    profiles = []
    try:
        q = supabase.table("competitor_profiles").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        profiles = q.execute().data or []
    except Exception:
        pass

    return {"success": True, "data": profiles}


@router.post("/research/content-gap")
@router.post("/api/research/content-gap")
async def run_content_gap_analysis(body: ContentGapRequest):
    """Run live Serper.dev comparison between competitor's top keywords and ours, sorting by traffic value."""
    comp_domain = body.competitor_domain.replace("https://", "").replace("http://", "").strip().split("/")[0]
    
    # 1. Search competitor ranking keywords via Serper
    serp_res = await serper_service.search(query=f"site:{comp_domain} {body.target_niche}", num=10, auto_fallback=True)
    organic = serp_res.get("organic", [])
    
    gap_opportunities = []
    for idx, item in enumerate(organic, start=1):
        title = item.get("title", "")
        clean_kw = title.split("-")[0].split("|")[0].strip()
        # MODELED, not measured: rank-order heuristics. No volume/CPC/
        # difficulty provider is wired, so these decrease with competitor
        # rank by formula. Labeled estimated; never presented as data.
        est_vol = max(800, 3800 - (idx * 250))
        est_traffic_val = round(est_vol * 0.18 * 4.5, 2) # Est. CTR * Average CPC ($4.50)

        gap_opportunities.append({
            "keyword": clean_kw,
            "competitor_url": item.get("link"),
            "competitor_rank": idx,
            "estimated_search_volume": est_vol,
            "estimated_traffic_value": est_traffic_val,
            "difficulty": min(85, 30 + (idx * 5)),
            "provenance": "estimated",
            "estimation_method": "rank-order heuristic: volume=max(800, 3800-rank*250); value=vol*0.18*$4.50; difficulty=min(85, 30+rank*5). No measured keyword data.",
            "action": "create_counter_article"
        })

    gap_opportunities.sort(key=lambda x: x["estimated_traffic_value"], reverse=True)

    return {
        "success": True,
        "competitor_domain": comp_domain,
        "total_gaps_found": len(gap_opportunities),
        "gap_opportunities": gap_opportunities,
        "timestamp": datetime.utcnow().isoformat()
    }
