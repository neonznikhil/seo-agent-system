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
    website_id: Optional[str] = None
    monthly_seo_spend: Optional[float] = None
    monthly_budget: Optional[float] = None
    target_cpl: Optional[float] = None
    lead_value: Optional[float] = None
    conversion_goals: Optional[List[str]] = None


@router.get("/{website_id}/keyword-performance")
@router.get("/{website_id}/attribution")
def keyword_performance(website_id: str):
    """Get keyword-level conversion attribution, CVR, and Cost Per Lead."""
    return get_keyword_lead_attribution(website_id)


@router.get("/{website_id}/summary")
def lead_summary(website_id: str):
    """Get topline organic leads, average CPL, and pipeline value."""
    data = get_keyword_lead_attribution(website_id)
    return data.get("summary", {})


@router.get("/{website_id}/settings")
def get_settings(website_id: str):
    """Retrieve saved target lead parameters for a website."""
    data = get_keyword_lead_attribution(website_id)
    return data.get("settings", {})


@router.post("/{website_id}/settings")
@router.post("/settings")
def save_settings(payload: LeadSettingsRequest, website_id: Optional[str] = None):
    """Save target lead parameters and monthly budget."""
    effective_website_id = website_id or payload.website_id
    if not effective_website_id:
        raise HTTPException(status_code=400, detail="website_id is required either in path or body.")

    settings_dict = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    settings_dict.pop("website_id", None)
    if "monthly_budget" in settings_dict and "monthly_seo_spend" not in settings_dict:
        settings_dict["monthly_seo_spend"] = settings_dict["monthly_budget"]
    elif "monthly_seo_spend" in settings_dict and "monthly_budget" not in settings_dict:
        settings_dict["monthly_budget"] = settings_dict["monthly_seo_spend"]
    return update_lead_settings(effective_website_id, settings_dict)
