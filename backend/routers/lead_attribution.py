"""Router for Keyword Lead Attribution and Cost Per Lead (CPL).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
try:
    from backend.services.lead_attribution_service import (
        get_keyword_lead_attribution,
        update_lead_settings,
    )
except ImportError:
    from services.lead_attribution_service import (
        get_keyword_lead_attribution,
        update_lead_settings,
    )

router = APIRouter(prefix="/api/leads", tags=["Lead Attribution & CPL"])


class LeadSettingsRequest(BaseModel):
    monthly_seo_spend: Optional[float] = 2500.0
    target_cpl: Optional[float] = 75.0
    lead_value: Optional[float] = 350.0
    conversion_goals: Optional[List[str]] = None


@router.get("/{website_id}/keyword-performance")
def keyword_performance(website_id: str):
    """Get keyword-level conversion attribution, CVR, and Cost Per Lead."""
    return get_keyword_lead_attribution(website_id)


@router.get("/{website_id}/summary")
def lead_summary(website_id: str):
    """Get topline organic leads, average CPL, and pipeline value."""
    data = get_keyword_lead_attribution(website_id)
    return data.get("summary", {})


@router.post("/{website_id}/settings")
def save_settings(website_id: str, payload: LeadSettingsRequest):
    """Save target lead parameters and monthly budget."""
    settings_dict = payload.dict(exclude_unset=True)
    return update_lead_settings(website_id, settings_dict)
