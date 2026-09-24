"""Router for Competitor Tracking, Share of Voice, New Pages, and Outranking Matrix."""

import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

try:
    from backend.services.competitor_intelligence_service import (
        get_competitors,
        add_competitor,
        remove_competitor,
        calculate_share_of_voice,
        get_competitor_new_pages,
        get_outranking_gap_matrix,
    )
except ImportError:
    from services.competitor_intelligence_service import (
        get_competitors,
        add_competitor,
        remove_competitor,
        calculate_share_of_voice,
        get_competitor_new_pages,
        get_outranking_gap_matrix,
    )

logger = logging.getLogger("backend.routers.competitors")

router = APIRouter(prefix="/api/competitors", tags=["Competitor Intelligence"])


class AddCompetitorRequest(BaseModel):
    domain: str
    label: Optional[str] = None


@router.get("/{website_id}")
async def list_site_competitors(website_id: str):
    """List all tracked competitors for a website."""
    try:
        competitors = get_competitors(website_id)
        return {"website_id": website_id, "competitors": competitors, "count": len(competitors)}
    except Exception as e:
        logger.error(f"Error fetching competitors for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{website_id}")
async def add_site_competitor(website_id: str, payload: AddCompetitorRequest):
    """Add a new competitor domain to monitor."""
    if not payload.domain or not payload.domain.strip():
        raise HTTPException(status_code=400, detail="Competitor domain is required.")
    try:
        comp = add_competitor(website_id, payload.domain, payload.label)
        return {"status": "success", "competitor": comp}
    except Exception as e:
        logger.error(f"Error adding competitor {payload.domain} for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{website_id}/{competitor_id}")
async def delete_site_competitor(website_id: str, competitor_id: str):
    """Delete a competitor domain from monitoring."""
    success = remove_competitor(website_id, competitor_id)
    if not success:
        raise HTTPException(status_code=404, detail="Competitor not found.")
    return {"status": "success", "message": "Competitor domain removed."}


@router.get("/{website_id}/share-of-voice")
@router.get("/{website_id}/sov")
async def get_site_share_of_voice(website_id: str):
    """Calculate organic search Share of Voice (SOV) against competitors."""
    try:
        return calculate_share_of_voice(website_id)
    except Exception as e:
        logger.error(f"Error calculating share of voice for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{website_id}/new-pages")
async def get_site_competitor_new_pages(website_id: str):
    """Get feed of recently published competitor pages and content counter-strategies."""
    try:
        pages = get_competitor_new_pages(website_id)
        return {"website_id": website_id, "new_pages": pages, "count": len(pages)}
    except Exception as e:
        logger.error(f"Error fetching competitor new pages for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{website_id}/outranking-matrix")
@router.get("/{website_id}/outranked")
async def get_site_outranking_matrix(website_id: str):
    """Get head-to-head outranking gap matrix showing where competitors outrank you and traffic loss."""
    try:
        matrix = get_outranking_gap_matrix(website_id)
        return {"website_id": website_id, "outranked_queries": matrix, "count": len(matrix)}
    except Exception as e:
        logger.error(f"Error fetching outranking matrix for website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
