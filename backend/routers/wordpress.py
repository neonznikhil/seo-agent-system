import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

logger = logging.getLogger("backend.routers.wordpress")

router = APIRouter()


class OAuthAuthorizeResponse(BaseModel):
    authorization_url: str


class OAuthCallbackResponse(BaseModel):
    status: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    scope: Optional[str] = None


class OAuthStatusResponse(BaseModel):
    oauth_enabled: bool
    connected: bool
    provider: str
    expires_at: Optional[str] = None
    scope: Optional[str] = None
    site_url: Optional[str] = None


@router.get("/wordpress/{website_id}/info")
async def wordpress_info(website_id: str):
    """Verify the WordPress connection and return site info (real data)."""
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    info = await ws.get_site_info()
    if info is None:
        raise HTTPException(404, "WordPress not configured or unreachable for this website")
    return {"status": "connected", "site": info}


@router.get("/wordpress/{website_id}/posts")
async def wordpress_posts(
    website_id: str,
    per_page: int = 10,
    page: int = 1,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    """Fetch real posts from the connected WordPress site."""
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    posts = await ws.get_posts(per_page=per_page, page=page, status=status, search=search)
    return {"count": len(posts), "posts": posts}


@router.get("/wordpress/{website_id}/pages")
async def wordpress_pages(
    website_id: str,
    per_page: int = 10,
    page: int = 1,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    """Fetch real pages from the connected WordPress site."""
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    pages = await ws.get_pages(per_page=per_page, page=page, status=status, search=search)
    return {"count": len(pages), "pages": pages}


@router.get("/wordpress/{website_id}/posts/{post_id}")
async def wordpress_post(website_id: str, post_id: str):
    """Fetch a single real post by id from WordPress."""
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    post = await ws.get_post(post_id)
    if post is None:
        raise HTTPException(404, "Post not found on WordPress")
    return post


@router.post("/wordpress/{website_id}/sync")
async def wordpress_sync(website_id: str, per_page: int = 20):
    """Pull real published content from WordPress into the local content_log so agents can act on it."""
    from ..database import get_supabase
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    posts = await ws.get_posts(per_page=per_page, status="publish")
    if not posts:
        return {"status": "no_data", "synced": 0}

    supabase = get_supabase()
    synced = 0
    for p in posts:
        title = (p.get("title") or {}).get("rendered", "") if isinstance(p.get("title"), dict) else p.get("title", "")
        excerpt = (p.get("excerpt") or {}).get("rendered", "") if isinstance(p.get("excerpt"), dict) else p.get("excerpt", "")
        row = {
            "website_id": website_id,
            "title": title,
            "url": p.get("link", ""),
            "content": excerpt,
            "status": "synced",
            "agent": "wordpress_sync",
            "wp_post_id": p.get("id"),
        }
        try:
            supabase.table("content_log").insert(row).execute()
            synced += 1
        except Exception as e:
            logger.warning(f"WP sync insert failed for post {p.get('id')}: {e}")

    return {"status": "synced", "fetched": len(posts), "synced": synced}


# ==================== WordPress OAuth Endpoints ====================


@router.get("/wordpress/{website_id}/oauth/authorize", response_model=OAuthAuthorizeResponse)
async def oauth_authorize(
    website_id: str,
    redirect_uri: Optional[str] = Query(None),
    scope: Optional[str] = Query("basic"),
    state: Optional[str] = Query(None),
):
    """
    Get WordPress OAuth authorization URL.
    Requires an OAuth server plugin on the WordPress site (e.g., OAuth Server for WordPress).
    """
    from ..database import get_supabase

    website = get_supabase().table("websites").select("cms_url, domain").eq("id", website_id).single().execute().data
    if not website:
        raise HTTPException(404, "Website not found")

    cms_url = website.get("cms_url", "").rstrip("/")
    if not cms_url:
        raise HTTPException(400, "WordPress CMS URL not configured")

    # Standard WordPress OAuth endpoints (requires OAuth server plugin)
    auth_url = f"{cms_url}/oauth/authorize"
    
    params = {
        "client_id": website_id,
        "redirect_uri": redirect_uri or f"{cms_url}/oauth/callback",
        "scope": scope,
        "response_type": "code",
    }
    if state:
        params["state"] = state

    from urllib.parse import urlencode
    full_url = f"{auth_url}?{urlencode(params)}"
    
    return {"authorization_url": full_url}


@router.get("/wordpress/{website_id}/oauth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    website_id: str,
    code: str = Query(...),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Handle OAuth callback from WordPress and exchange code for tokens."""
    if error:
        raise HTTPException(400, f"OAuth error: {error}")

    from ..database import get_supabase

    website = get_supabase().table("websites").select("cms_url, domain").eq("id", website_id).single().execute().data
    if not website:
        raise HTTPException(404, "Website not found")

    cms_url = website.get("cms_url", "").rstrip("/")
    if not cms_url:
        raise HTTPException(400, "WordPress CMS URL not configured")

    token_url = f"{cms_url}/oauth/token"
    redirect_uri = f"{cms_url}/oauth/callback"
    
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": website_id,
        "client_secret": "",  # Should be stored per-website in production
        "redirect_uri": redirect_uri,
    }

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise HTTPException(400, f"Token exchange failed: {resp.status} - {error_text}")
                data = await resp.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.utcnow().timestamp() + expires_in

        token_row = {
            "website_id": website_id,
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "token_type": data.get("token_type", "Bearer"),
            "expires_at": datetime.fromtimestamp(expires_at).isoformat(),
            "scope": data.get("scope"),
            "provider": "wordpress",
            "updated_at": datetime.utcnow().isoformat(),
        }

        get_supabase().table("wordpress_oauth_tokens").upsert(token_row, on_conflict="website_id,provider").execute()

        # Mark website as OAuth enabled
        get_supabase().table("websites").update({"oauth_enabled": True}).eq("id", website_id).execute()

        return {
            "status": "connected",
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "expires_in": expires_in,
            "scope": data.get("scope"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(500, f"OAuth callback failed: {str(e)}")


@router.post("/wordpress/{website_id}/oauth/refresh")
async def oauth_refresh(website_id: str):
    """Refresh OAuth access token using stored refresh token."""
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    token_data = ws._get_oauth_token()
    if not token_data or not token_data.get("refresh_token"):
        raise HTTPException(400, "No refresh token available")

    new_token = ws._refresh_oauth_token(token_data)
    if not new_token:
        raise HTTPException(500, "Failed to refresh token")

    return {
        "status": "refreshed",
        "access_token": new_token.get("access_token"),
        "expires_at": new_token.get("expires_at"),
    }


@router.delete("/wordpress/{website_id}/oauth")
async def oauth_disconnect(website_id: str):
    """Disconnect WordPress OAuth and remove stored tokens."""
    from ..database import get_supabase

    try:
        get_supabase().table("wordpress_oauth_tokens").delete().eq("website_id", website_id).eq("provider", "wordpress").execute()
        get_supabase().table("websites").update({"oauth_enabled": False}).eq("id", website_id).execute()
        return {"status": "disconnected"}
    except Exception as e:
        logger.error(f"OAuth disconnect error: {e}")
        raise HTTPException(500, f"Failed to disconnect: {str(e)}")


@router.get("/wordpress/{website_id}/oauth/status", response_model=OAuthStatusResponse)
async def oauth_status(website_id: str):
    """Check WordPress OAuth connection status."""
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    token_data = ws._get_oauth_token()
    
    site_info = await ws.get_site_info()
    
    if not token_data:
        return {
            "oauth_enabled": bool(ws.site.get("oauth_enabled")),
            "connected": False,
            "provider": "wordpress",
            "site_url": site_info.get("url") if site_info else None,
        }

    return {
        "oauth_enabled": True,
        "connected": True,
        "provider": "wordpress",
        "expires_at": token_data.get("expires_at"),
        "scope": token_data.get("scope"),
        "site_url": site_info.get("url") if site_info else None,
    }

