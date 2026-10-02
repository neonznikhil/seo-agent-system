import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query, HTTPException

from database import get_supabase, call_nim_llm, execute_db

logger = logging.getLogger("backend.routers.gsc")
router = APIRouter()


@router.get("/gsc/{website_id}/keywords")
@router.get("/gsc/keywords/{website_id}")
@router.get("/api/gsc/{website_id}/keywords")
@router.get("/api/gsc/keywords/{website_id}")
async def get_keywords(website_id: str):
    """Get keywords — from live GSC if connected, or fallback to SERP keyword opportunities.

    Always reports WHY the result looks the way it does via the
    `connected` flag. `connected` is ONLY True if Google Search Console
    credentials are validly configured and connected.
    """
    supabase = get_supabase()

    # 1. Try live GSC via real GSCService API.
    #
    # The property MUST be resolvable before any live query. GSCService has no
    # fallback property, so an unresolved site is reported as "unconfigured"
    # rather than silently querying whatever site happened to be in the env.
    site_url = None
    site_lookup_error: Optional[str] = None
    try:
        from services.gsc_service import GSCService

        try:
            site_row = await execute_db(
                supabase.table("websites").select("url, domain").eq("id", website_id).limit(1)
            )
            rows = (getattr(site_row, "data", None) or [])
            if rows:
                site_url = rows[0].get("url") or rows[0].get("domain")
        except Exception as e:
            # Previously swallowed with a bare `except: site_url = None`, which
            # hid a real DB outage behind a clean-looking response.
            site_lookup_error = str(e)[:200]
            logger.warning(f"[GSC] website row lookup failed for {website_id}: {site_lookup_error}")

        gsc = GSCService(website_url=site_url)
        if not gsc.has_property():
            logger.info(
                "[GSC] no property resolved (website row empty%s) — skipping live query",
                " and DB read failed" if site_lookup_error else "",
            )
        elif not gsc.is_connected():
            logger.info("[GSC] credentials not configured — skipping live query")
        else:
            perf = await gsc.get_keyword_performance()
            if perf.get("error") and not perf.get("keywords"):
                logger.warning(f"[GSC] live query failed: {perf.get('error')}")
            else:
                keywords = perf.get("keywords", [])
                return {
                    "success": True,
                    "connected": True,
                    "source": "gsc",
                    "data_available": True,
                    "keywords": keywords,
                    "data": keywords,
                    "message": "Live Google Search Console data retrieved." if keywords else "GSC connected but returned no keyword rows for this date range."
                }
    except Exception as e:
        logger.warning(f"[GSC] live service check note: {e}")

    # 2. GSC not connected: check if keyword_opportunities exist in Supabase (from SERP research)
    try:
        result = (
            supabase.table("keyword_opportunities")
            .select("*")
            .eq("website_id", website_id)
            .order("opportunity_score", desc=True)
            .limit(20)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return {
                "success": True,
                "connected": False,
                "source": "keyword_opportunities",
                "keywords": result.data,
                "data": result.data,
                "message": "Google Search Console is not connected. Showing keyword opportunities discovered from SERP research."
            }
    except Exception:
        pass

    # 3. Honest empty: GSC unavailable and no keyword opportunities found
    return {
        "success": True,
        "connected": False,
        "source": "unconfigured",
        "data_available": False,
        "keywords": [],
        "data": [],
        "message": "Google Search Console is not connected. Connect GSC credentials in Settings / Connectors to view real search performance.",
        **({"error": site_lookup_error} if site_lookup_error else {}),
    }


@router.get("/gsc/{website_id}/performance")
@router.get("/gsc/roi/{website_id}")
@router.get("/api/gsc/{website_id}/performance")
@router.get("/api/gsc/roi/{website_id}")
async def get_performance(website_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get performance metrics for the website.

    Never synthesizes fake GSC impressions or clicks from keyword search volume.
    If GSC is not connected, returns 0 clicks / impressions with connected=False.
    """
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

    data = await get_keywords(website_id)
    keywords = data.get("keywords", []) if isinstance(data, dict) else data
    connected = bool(data.get("connected")) if isinstance(data, dict) else False
    source = data.get("source") if isinstance(data, dict) else ""
    data_lookup_error = (data.get("error") if isinstance(data, dict) else None)

    # Real top pages from site_pages table if measured
    top_pages = []
    top_pages_available = True
    top_pages_error: Optional[str] = None
    try:
        supabase = get_supabase()
        pages = (await execute_db(
            supabase.table("site_pages").select("url, title, clicks, impressions, ctr").eq("website_id", website_id).limit(5)
        )).data or []
        for p in pages:
            if p.get("clicks") is None and p.get("impressions") is None:
                continue
            top_pages.append({
                "page": p.get("url"),
                "title": p.get("title"),
                "clicks": p.get("clicks"),
                "impressions": p.get("impressions"),
                "ctr": p.get("ctr"),
            })
    except Exception as e:
        # A failed read must not look like "measured, and there are zero pages".
        top_pages_available = False
        top_pages_error = str(e)[:200]
        logger.warning(f"[GSC] site_pages lookup failed for {website_id}: {top_pages_error}")

    if not connected or source != "gsc":
        # HONEST: When GSC is not connected, clicks and impressions are 0.
        # Never convert keyword search_volume into GSC impressions!
        return {
            "success": True,
            "connected": False,
            "website_id": website_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_clicks": 0,
            "total_impressions": 0,
            "average_ctr": 0.0,
            "average_position": 0.0,
            "keywords": keywords,
            "opportunities": [],
            "top_pages": top_pages,
            "top_pages_available": top_pages_available,
            "source": source or "unconfigured",
            # Not-connected is a genuine measured zero *for GSC only*. Callers must
            # not render "traffic collapsed to 0" when the read itself failed.
            "data_available": top_pages_available and not data_lookup_error,
            "message": data.get("message", "Google Search Console is not connected.") if isinstance(data, dict) else "Google Search Console is not connected.",
            **({"error": data_lookup_error or top_pages_error} if (data_lookup_error or top_pages_error) else {}),
        }

    total_clicks = sum(k.get("clicks", 0) for k in keywords)
    total_impressions = sum(k.get("impressions", 0) for k in keywords)
    avg_ctr = round((total_clicks / max(1, total_impressions)) * 100, 2) if total_impressions > 0 else 0.0
    avg_position = round(sum(k.get("position", 0.0) for k in keywords) / max(1, len(keywords)), 1) if keywords else 0.0

    # Keyword opportunities from real GSC queries (high impressions, CTR < 3%)
    opportunities = [
        k for k in keywords
        if float(k.get("ctr", 0.0)) < 0.030 and int(k.get("impressions", 0)) > 1000
    ]

    return {
        "success": True,
        "connected": True,
        "website_id": website_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "average_ctr": avg_ctr,
        "average_position": avg_position,
        "keywords": keywords,
        "opportunities": opportunities,
        "top_pages": top_pages,
        "top_pages_available": top_pages_available,
        "source": source or "gsc",
        "data_available": top_pages_available,
        **({"top_pages_error": top_pages_error} if top_pages_error else {}),
    }
