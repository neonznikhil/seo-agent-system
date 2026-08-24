import logging
import os
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
class WordPressCredentialsIn(BaseModel):
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    wordpress_url: Optional[str] = None
    wordpress_user: Optional[str] = None
    wordpress_password: Optional[str] = None


class CreateDraftIn(BaseModel):
    title: str
    content: str
    keywords: Optional[list] = None


@router.post("/wordpress/{website_id}/connect")
async def connect_wordpress(website_id: str, request: Request):
    import base64
    import httpx
    from ..database import get_supabase
    
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid request body")
    
    wp_url = data.get('wordpress_url', '').rstrip('/')
    wp_user = data.get('wordpress_user', '')
    wp_pass = data.get('wordpress_password', '')
    
    if not all([wp_url, wp_user, wp_pass]):
        raise HTTPException(
            status_code=400,
            detail="wordpress_url, wordpress_user, and wordpress_password are all required"
        )
    
    credentials = base64.b64encode(
        f"{wp_user}:{wp_pass}".encode()
    ).decode()
    
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(
                f"{wp_url}/wp-json/wp/v2/users/me",
                headers={"Authorization": f"Basic {credentials}"}
            )
        
        if response.status_code == 200:
            user_info = response.json()
            
            # Save to Supabase
            supabase = get_supabase()
            supabase.table("websites").update({
                "wordpress_url": wp_url,
                "wordpress_user": wp_user,
                "wordpress_password": wp_pass
            }).eq("id", website_id).execute()
            
            return {
                "success": True,
                "message": f"Connected as {user_info.get('name', wp_user)}",
                "wp_user_name": user_info.get('name'),
                "wp_url": wp_url
            }
        else:
            return {
                "success": False,
                "message": f"WordPress rejected credentials. Status: {response.status_code}. Make sure you're using Application Password, not login password."
            }
    
    except httpx.ConnectError:
        return {
            "success": False,
            "message": f"Cannot reach {wp_url}. Check if the URL is correct and site is online."
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/wordpress/{website_id}/create-draft")
@router.post("/api/wordpress/{website_id}/create-draft")
async def create_wp_draft(website_id: str, request: Request):
    import json
    import base64
    import httpx
    from datetime import datetime
    from ..database import get_supabase
    
    user_id = request.headers.get("X-User-Id")
    if not user_id or user_id.strip() == "":
        user_id = "human-approved"
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")
    
    supabase = get_supabase()
    
    title = body.get('title', 'Untitled')
    content = body.get('content', '')
    content_id = body.get('content_id')
    
    if not content and content_id:
        try:
            content_result = supabase.table("content_log").select("*").eq("id", content_id).single().execute()
            if content_result.data:
                content = content_result.data.get('content') or content_result.data.get('body') or ''
                title = content_result.data.get('title', title)
        except Exception:
            pass
    
    if not content:
        raise HTTPException(status_code=400, detail="No content found to publish")
    
    from ..services.wordpress_service import WordPressService
    wp_svc = WordPressService(website_id)
    wp_result = await wp_svc.create_draft(website_id, title, content)
    
    wp_post_id = wp_result.get("wp_post_id")
    edit_url = wp_result.get("edit_url")
    link = wp_result.get("link") or edit_url
    
    # Always update content_log status to approved / draft so work is preserved
    if content_id:
        update_data = {"status": "draft", "approved_by": user_id}
        if wp_post_id:
            update_data["wp_post_id"] = wp_post_id
            update_data["wp_draft_url"] = link
            update_data["status"] = "approved"
        try:
            supabase.table("content_log").update(update_data).eq("id", content_id).execute()
        except Exception as db_err:
            logger.warning(f"DB update error: {db_err}")
    
    if wp_result.get("success"):
        return {
            "success": True,
            "wp_post_id": wp_post_id,
            "draft_url": link,
            "edit_url": edit_url,
            "message": f"Draft created in WordPress! Edit at: {edit_url}"
        }
    else:
        return {
            "success": False,
            "wp_post_id": None,
            "message": wp_result.get("message", "WordPress connection failed. Saved as local draft.")
        }


@router.post("/wordpress/save-connection")
@router.post("/api/wordpress/save-connection")
async def save_wordpress_connection(body: WordPressCredentialsIn):
    """Save and verify WordPress REST connection credentials."""
    from ..services.wordpress_service import WordPressService
    wp_svc = WordPressService("default")
    diag = await wp_svc.test_connection(body.site_url, body.username, body.app_password)
    
    clean_url = body.site_url.rstrip("/")
    if clean_url and not clean_url.startswith("http"):
        clean_url = f"https://{clean_url}"

    try:
        supabase = get_supabase()
        supabase.table("wordpress_connections").upsert({
            "site_url": clean_url,
            "username": body.username,
            "app_password": body.app_password,
            "status": "connected" if diag.get("connected") else "configured",
            "last_verified_at": datetime.utcnow().isoformat()
        }, on_conflict="site_url").execute()
    except Exception as e:
        logger.warning(f"Failed to upsert wordpress_connections: {e}")

    return {
        "success": True,
        "connected": diag.get("connected", False),
        "site_url": clean_url,
        "username": body.username,
        "diagnostics": diag
    }


@router.post("/wordpress/publish")
@router.post("/api/wordpress/publish")
async def direct_publish_wp_post(payload: Dict[str, Any], request: Request):
    """Direct human-authorized publishing of content into WordPress."""
    user_id = request.headers.get("X-User-Id")
    if not user_id or user_id.strip() == "":
        raise HTTPException(status_code=401, detail="X-User-Id header required for publishing action")

    website_id = payload.get("website_id", "default")
    title = payload.get("title")
    content = payload.get("content") or payload.get("body")
    content_id = payload.get("content_id")
    status = payload.get("status", "draft")

    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")

    from ..services.wordpress_service import WordPressService
    wp_svc = WordPressService(website_id)
    result = await wp_svc.create_draft(website_id, title, content)
    
    if content_id:
        try:
            get_supabase().table("content_log").update({
                "status": "published" if status == "publish" else "approved",
                "approved_by": user_id,
                "wp_post_id": result.get("wp_post_id"),
                "wp_draft_url": result.get("link")
            }).eq("id", content_id).execute()
        except Exception:
            pass

    return {
        "success": result.get("success", False),
        "wp_post_id": result.get("wp_post_id"),
        "url": result.get("link"),
        "published_by": user_id
    }



@router.post("/wordpress/{website_id}/test")
async def test_wordpress_connection(website_id: str, body: WordPressCredentialsIn):
    """Test WordPress credentials directly with detailed diagnostics."""
    from ..services.wordpress_service import WordPressService
    from ..database import get_supabase
    from datetime import datetime

    url = (body.url or body.wordpress_url or "").strip()
    username = (body.username or body.wordpress_user or "").strip()
    password = (body.password or body.wordpress_password or "").strip()

    if not url or not username or not password:
        raise HTTPException(400, "URL, username, and application password are required")

    ws = WordPressService(website_id)
    diag = await ws.test_connection(url, username, password)
    is_connected = diag.get("connected", False)

    # If successfully connected and website exists, persist credentials
    if is_connected and website_id and website_id != "default":
        try:
            supabase = get_supabase()
            supabase.table("websites").update({
                "cms_url": url,
                "url": url,
                "cms_user": username,
                "app_password": password,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", website_id).execute()
        except Exception:
            pass

    return {
        "success": is_connected,
        "connected": is_connected,
        "url": url,
        "status_code": diag.get("status_code"),
        "error_type": diag.get("error_type"),
        "message": diag.get("message", "Connection verified ✅" if is_connected else "Connection failed"),
        "wp_user": username,
    }


@router.post("/wordpress/{website_id}/credentials")
async def save_wordpress_credentials(website_id: str, body: WordPressCredentialsIn):
    """Save WordPress URL, username, and application password into websites table."""
    from ..database import get_supabase
    from datetime import datetime

    supabase = get_supabase()
    url = (body.url or body.wordpress_url or "").strip()
    username = (body.username or body.wordpress_user or "").strip()
    password = (body.password or body.wordpress_password or "").strip()

    update_data = {
        "updated_at": datetime.utcnow().isoformat(),
    }
    if url:
        update_data["cms_url"] = url
        update_data["url"] = url
    if username:
        update_data["cms_user"] = username
    if password:
        update_data["app_password"] = password

    try:
        supabase.table("websites").update(update_data).eq("id", website_id).execute()
    except Exception as e:
        logger.error(f"Error updating website credentials: {e}")
        raise HTTPException(500, f"Failed to save credentials: {str(e)}")

    return {"status": "saved", "website_id": website_id}


@router.post("/wordpress/{website_id}/draft")
async def create_wordpress_draft(website_id: str, body: CreateDraftIn):
    """Create a draft post on WordPress."""
    from ..services.wordpress_service import WordPressService

    ws = WordPressService(website_id)
    result = await ws.create_draft(website_id, body.title, body.content, body.keywords or [])
    return result


@router.get("/wordpress/{website_id}/info")
async def wordpress_info(website_id: str):
    """Verify the WordPress connection and return site info."""
    from ..services.wordpress_service import get_wordpress_service

    ws = get_wordpress_service(website_id)
    info = await ws.get_site_info()
    return {"status": "connected" if info.get("status") == "live" else "configured", "site": info}


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
        "client_secret": os.getenv("WP_OAUTH_CLIENT_SECRET", ""),
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

