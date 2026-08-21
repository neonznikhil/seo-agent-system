import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..config import FRONTEND_URL
from ..services.wordpress_oauth_service import (
    get_authorize_url,
    exchange_code_for_token,
    get_oauth_status,
    publish_with_oauth,
    disconnect_oauth,
)

logger = logging.getLogger("backend.routers.wordpress_oauth")
router = APIRouter(prefix="/api/wordpress/oauth", tags=["wordpress-oauth"])


class AuthorizeResponse(BaseModel):
    authorize_url: str


class OAuthStatusResponse(BaseModel):
    connected: bool
    reason: Optional[str] = None
    needs_reconnect: Optional[bool] = None
    wp_site_url: Optional[str] = None
    wp_user_login: Optional[str] = None
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None


class PublishResponse(BaseModel):
    wp_post_id: int
    wp_url: str
    edit_url: str
    status: str


def _get_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-Id")
    if not user_id or user_id == "anonymous":
        raise HTTPException(status_code=403, detail="X-User-Id header required")
    return user_id


@router.get("/authorize", response_model=AuthorizeResponse)
async def authorize(request: Request, website_id: str = Query(...)):
    user_id = _get_user_id(request)

    from ..database import get_supabase

    website = get_supabase().table("websites").select("cms_url, domain").eq("id", website_id).single().execute().data
    if not website:
        raise HTTPException(404, "Website not found")

    wp_site_url = website.get("cms_url", "").rstrip("/")
    if not wp_site_url:
        raise HTTPException(400, "WordPress CMS URL not configured")

    client_id = WP_OAUTH_CLIENT_ID
    if not client_id:
        raise HTTPException(500, "WP_OAUTH_CLIENT_ID not configured on server")

    result = await get_authorize_url(website_id, user_id, wp_site_url, client_id)
    return {"authorize_url": result["authorize_url"]}


@router.get("/callback")
async def callback(code: str = Query(...), state: str = Query(...), error: Optional[str] = Query(None)):
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/settings?wp_error={error}")

    try:
        result = await exchange_code_for_token(code, state)
        return RedirectResponse(url=f"{FRONTEND_URL}/settings?wp_connected=1&wp_user={result['wp_user_login']}")
    except Exception as e:
        logger.error("OAuth callback failed: %s", e)
        return RedirectResponse(url=f"{FRONTEND_URL}/settings?wp_error={str(e)[:200]}")


@router.get("/status/{website_id}", response_model=OAuthStatusResponse)
async def status(request: Request, website_id: str):
    user_id = _get_user_id(request)
    result = await get_oauth_status(website_id, user_id)
    return result


@router.post("/disconnect/{website_id}")
async def disconnect(request: Request, website_id: str):
    user_id = _get_user_id(request)
    await disconnect_oauth(website_id, user_id)
    return {"disconnected": True}


@router.post("/publish/{website_id}", response_model=PublishResponse)
async def publish(request: Request, website_id: str, body: dict):
    user_id = _get_user_id(request)
    title = body.get("title", "")
    content_html = body.get("content_html", "")
    status = body.get("status", "draft")
    meta = body.get("meta")

    if not title or not content_html:
        raise HTTPException(400, "title and content_html are required")

    result = await publish_with_oauth(website_id, user_id, title, content_html, status, meta)
    return result
