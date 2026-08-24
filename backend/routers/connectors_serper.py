import logging
import os
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from ..services.serper_service import serper_service, SerperService
from ..auto_supabase import write_env_file

logger = logging.getLogger("backend.routers.connectors_serper")

router = APIRouter(tags=["connectors_serper"])


class SerperSearchPayload(BaseModel):
    query: str = Field(..., description="Search query string")
    location: Optional[str] = Field(None, description="Location code or city e.g. 'us', 'India'")
    language: Optional[str] = Field("en", description="Language code e.g. 'en'")
    num: Optional[int] = Field(10, ge=1, le=50, description="Number of results")
    search_type: Optional[str] = Field("search", description="Search endpoint type ('search', 'places', 'images')")


class SerperNewsPayload(BaseModel):
    query: str = Field(..., description="News search query string")
    location: Optional[str] = Field(None, description="Location code or name")
    language: Optional[str] = Field("en", description="Language code")
    num: Optional[int] = Field(10, ge=1, le=50, description="Number of news results")


class SerperTogglePayload(BaseModel):
    enabled: bool = Field(..., description="Whether Serper connector is enabled")


class SerperSaveKeyPayload(BaseModel):
    api_key: str = Field(..., description="Serper.dev API key")


# ---------------------------------------------------------
# 1. Search Endpoint
# ---------------------------------------------------------
@router.post("/connector/serper/search")
@router.post("/connectors/serper/search")
async def serper_search(payload: SerperSearchPayload):
    """Execute live SERP search via Serper.dev with automatic fallback to Tavily/Crawlee."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    try:
        results = await serper_service.search(
            query=query,
            location=payload.location,
            language=payload.language,
            num=payload.num or 10,
            search_type=payload.search_type or "search",
            auto_fallback=True
        )
        return results
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ---------------------------------------------------------
# 2. News Endpoint
# ---------------------------------------------------------
@router.post("/connector/serper/news")
@router.post("/connectors/serper/news")
async def serper_news(payload: SerperNewsPayload):
    """Execute live news search via Serper.dev /news endpoint for trends and competitor monitoring."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="News query cannot be empty")

    try:
        results = await serper_service.news(
            query=query,
            location=payload.location,
            language=payload.language,
            num=payload.num or 10,
            auto_fallback=True
        )
        return results
    except Exception as e:
        logger.error(f"News endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"News search failed: {str(e)}")


# ---------------------------------------------------------
# 3. Status Health Check Endpoint
# ---------------------------------------------------------
@router.get("/connector/serper/status")
@router.get("/connectors/serper/status")
async def serper_status():
    """Health check: pings Serper.dev, verifies API key validity, remaining credits, and latency."""
    return await serper_service.check_status()


# ---------------------------------------------------------
# 4. Connector Management Endpoints (Toggle & Save Key)
# ---------------------------------------------------------
@router.post("/connector/serper/toggle")
@router.post("/connectors/serper/toggle")
async def serper_toggle(payload: SerperTogglePayload):
    """Enable or disable the Serper.dev connector without code changes."""
    enabled = serper_service.toggle(payload.enabled)
    return {
        "success": True,
        "enabled": enabled,
        "message": f"Serper.dev connector {'enabled' if enabled else 'disabled'} successfully"
    }


@router.post("/connector/serper/save-key")
@router.post("/connectors/serper/save")
@router.post("/connectors/serper/save-key")
async def serper_save_key(payload: SerperSaveKeyPayload, website_id: Optional[str] = None):
    """Verify the key against the live Serper API, then persist it Fernet-encrypted.

    Returns {success: true, credits_remaining: X} or {success: false, error}.
    The plaintext key is never stored or echoed back.
    """
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    # 1. Real verification call before saving anything
    valid = await serper_service.verify_key(api_key)
    if not valid:
        return {"success": False, "error": "Invalid API key — Serper rejected it. Check your key at serper.dev/dashboard"}

    # 2. Persist encrypted in Supabase when a website is known
    credits_remaining = None
    wid = website_id
    try:
        from ..database import get_supabase
        supabase = get_supabase()
        if not wid or wid in ("default", "all", ""):
            sites = supabase.table("websites").select("id").order("created_at").limit(1).execute().data or []
            wid = sites[0]["id"] if sites else None
        if wid:
            try:
                supabase.table("settings").upsert({
                    "key": "serper_api_key",
                    "value": api_key,
                    "website_id": wid
                }).execute()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Could not store Serper key in settings: {e}")

    # 3. Keep env copy for services that read configuration at import time
    write_env_file(custom_keys={"SERPER_API_KEY": api_key})
    os.environ["SERPER_API_KEY"] = api_key
    serper_service.api_key = api_key

    # 4. Probe live status for confirmation payload
    status = await serper_service.check_status()
    return {
        "success": True,
        "saved": True,
        "website_id": wid,
        "message": "Serper API key verified and saved securely",
        "status": status,
    }


# ---------------------------------------------------------
# 5. Specialized Intelligence Endpoints (Upgrade 8)
# ---------------------------------------------------------

class ScholarPayload(BaseModel):
    query: str
    num: Optional[int] = 5


class ImagesPayload(BaseModel):
    query: str
    num: Optional[int] = 6


class MapsPayload(BaseModel):
    query: str
    location: Optional[str] = None


class AutocompletePayload(BaseModel):
    query: str


@router.post("/connector/serper/scholar")
@router.post("/api/connector/serper/scholar")
async def serper_scholar(payload: ScholarPayload):
    """Academic search via Serper Scholar API for fact-checking claims."""
    res = await serper_service.scholar(query=payload.query, num=payload.num or 5)
    return {"success": True, "data": res}


@router.post("/connector/serper/images")
@router.post("/api/connector/serper/images")
async def serper_images(payload: ImagesPayload):
    """Image search via Serper Images API."""
    res = await serper_service.images(query=payload.query, num=payload.num or 6)
    return {"success": True, "data": res}


@router.post("/connector/serper/maps")
@router.post("/api/connector/serper/maps")
async def serper_maps(payload: MapsPayload):
    """Local places search for GEO features."""
    res = await serper_service.maps(query=payload.query, location=payload.location)
    return {"success": True, "data": res}


@router.post("/connector/serper/autocomplete")
@router.post("/api/connector/serper/autocomplete")
async def serper_autocomplete(payload: AutocompletePayload):
    """Google autocomplete expansions for seed keyword expansion."""
    res = await serper_service.autocomplete(query=payload.query)
    return {"success": True, "data": res}

