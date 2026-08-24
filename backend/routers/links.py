import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from ..database import get_supabase
from ..services.link_graph_engine import LinkGraphEngine

logger = logging.getLogger("backend.routers.links")

router = APIRouter(prefix="/links", tags=["Internal Links & PageRank Graph"])


@router.get("/{website_id}/graph")
async def get_link_graph(website_id: str = Path(..., description="Website ID")):
    """Compute and return internal link graph, PageRank scores, and cluster connectivity."""
    engine = LinkGraphEngine(website_id=website_id)
    try:
        graph_data = await engine.build_internal_link_graph()
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
    engine = LinkGraphEngine(website_id=website_id)
    try:
        suggestions = await engine.suggest_internal_links(target_slug=target_slug)
        return {"success": True, "website_id": website_id, "suggestions": suggestions}
    except Exception as e:
        logger.warning(f"Error generating link suggestions: {e}")
        return {"success": True, "website_id": website_id, "suggestions": []}
