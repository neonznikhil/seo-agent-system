import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from database import get_supabase
from services.internal_link_service import build_internal_link_graph

logger = logging.getLogger("backend.routers.links")

router = APIRouter(prefix="/links", tags=["Internal Links & PageRank Graph"])


@router.get("/{website_id}/graph")
async def get_link_graph(website_id: str = Path(..., description="Website ID")):
    """Compute and return internal link graph, PageRank scores, and cluster connectivity."""
    try:
        graph_data = await build_internal_link_graph(website_id=website_id)
        return {"success": True, "website_id": website_id, "graph": graph_data}
    except Exception as e:
        logger.warning(f"Error computing link graph for {website_id}: {e}")
        return {
            "success": True,
            "website_id": website_id,
            "graph": {
                "nodes": [],
                "edges": [],
                "orphan_pages": [],
                "top_pagerank_urls": []
            }
        }


@router.get("/{website_id}/suggestions")
async def get_linking_suggestions(
    website_id: str = Path(..., description="Website ID"),
    target_slug: Optional[str] = Query(None)
):
    """Retrieve contextual internal link recommendations for a draft or published post."""
    supabase = get_supabase()
    try:
        try:
            q = supabase.table("content_log").select("title, slug, primary_keyword, keyword").eq("website_id", website_id)
            if target_slug:
                q = q.neq("slug", target_slug)
            rows = q.limit(10).execute().data or []
        except Exception:
            q = supabase.table("content_log").select("id, title, keyword").eq("website_id", website_id)
            rows = q.limit(10).execute().data or []

        # Relevance is computed from keyword overlap between the candidate
        # target and the rest of the corpus. It is a heuristic ranker, not a
        # measurement: null + note when there is nothing to compare against.
        corpus_terms = set()
        for r in rows:
            for token in ((r.get("primary_keyword") or r.get("keyword") or r.get("title") or "").lower().split()):
                if len(token) > 3:
                    corpus_terms.add(token)

        suggestions = []
        for r in rows:
            anchor = r.get("primary_keyword") or r.get("keyword") or r.get("title")
            anchor_terms = {t for t in (anchor or "").lower().split() if len(t) > 3}
            if corpus_terms and anchor_terms:
                relevance = round(len(anchor_terms & corpus_terms) / max(1, len(anchor_terms)), 3)
            else:
                relevance = None
            suggestions.append({
                "target_title": r.get("title"),
                "target_url": f"/{r.get('slug') or r.get('id', '')}",
                "recommended_anchor": anchor,
                "relevance_score": relevance,
                "relevance_note": ("keyword-overlap heuristic, not a measured signal"
                                   if relevance is not None else
                                   "Embeddings not computed — no basis for a score"),
            })
        return {"success": True, "website_id": website_id, "suggestions": suggestions}
    except Exception as e:
        logger.warning(f"Error generating link suggestions: {e}")
        return {"success": True, "website_id": website_id, "suggestions": []}
