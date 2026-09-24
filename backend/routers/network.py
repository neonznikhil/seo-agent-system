"""Network router for multi-site overview endpoints.
"""

from fastapi import APIRouter, Query
from typing import Optional
try:
    from backend.services.network_service import get_network_overview
except ImportError:
    from services.network_service import get_network_overview

router = APIRouter(prefix="/api/network", tags=["Network"])


@router.get("/overview")
def network_overview(account_id: Optional[str] = Query(None, description="Optional account ID filter")):
    """Get unified multi-site network health, indexation, clicks, and issues."""
    return get_network_overview(account_id)


@router.get("/summary-stats")
def network_summary(account_id: Optional[str] = Query(None)):
    """Get high-level summary KPIs across the network."""
    overview = get_network_overview(account_id)
    return overview.get("summary", {})
