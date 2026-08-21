import logging
import aiohttp
import os
import base64
from datetime import datetime
from typing import Dict, Optional
from ..database import get_supabase

logger = logging.getLogger("backend.services.wordpress_service")

# DEPRECATED: Use wordpress_oauth_service.py for real OAuth2 flow.
# This module is kept only as a fallback for Basic Auth.


class WordPressService:
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
        self.site = self._get_site_config()
    
    def _get_site_config(self) -> dict:
        """Get WordPress site configuration."""
        result = self.supabase.table("websites").select("cms_url, cms_user, app_password, oauth_enabled").eq("id", self.website_id).single().execute().data
        return result or {}
    
    def get_base_url(self) -> str:
        return self.site.get("cms_url", "").rstrip("/")
    
    def _get_auth(self) -> str:
        """Get Basic Auth token."""
        user = self.site.get("cms_user", "")
        password = self.site.get("app_password", "")
        return base64.b64encode(f"{user}:{password}".encode()).decode()
    
    def _get_oauth_token(self) -> Optional[dict]:
        """Get valid OAuth token from database."""
        try:
            result = self.supabase.table("wordpress_oauth_tokens").select("*").eq("website_id", self.website_id).eq("provider", "wordpress").single().execute().data
            if not result:
                return None
            if result.get("expires_at") and datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00")) < datetime.utcnow():
                # Token expired, try to refresh
                if result.get("refresh_token"):
                    return self._refresh_oauth_token(result)
                return None
            return result
        except Exception as e:
            logger.warning(f"Failed to get OAuth token: {e}")
            return None
    
    def _refresh_oauth_token(self, token_data: dict) -> Optional[dict]:
        """Refresh OAuth access token."""
        try:
            cms_url = self.get_base_url()
            if not cms_url:
                return None
            
            token_url = f"{cms_url}/oauth/token"
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": token_data.get("refresh_token"),
                "client_id": token_data.get("client_id", ""),
                "client_secret": token_data.get("client_secret", ""),
            }
            
            async def _refresh():
                async with aiohttp.ClientSession() as session:
                    async with session.post(token_url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            expires_in = data.get("expires_in", 3600)
                            expires_at = (datetime.utcnow().timestamp() + expires_in)
                            new_token = {
                                "website_id": self.website_id,
                                "access_token": data.get("access_token"),
                                "refresh_token": data.get("refresh_token", token_data.get("refresh_token")),
                                "token_type": data.get("token_type", "Bearer"),
                                "expires_at": datetime.fromtimestamp(expires_at).isoformat(),
                                "scope": data.get("scope"),
                                "provider": "wordpress",
                                "updated_at": datetime.utcnow().isoformat(),
                            }
                            self.supabase.table("wordpress_oauth_tokens").upsert(new_token, on_conflict="website_id,provider").execute()
                            return new_token
                        logger.error(f"Token refresh failed: {resp.status}")
                        return None
            
            import asyncio
            return asyncio.run(_refresh())
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    
    def _get_oauth_auth_header(self) -> Optional[str]:
        """Get OAuth Bearer token header."""
        token_data = self._get_oauth_token()
        if not token_data:
            return None
        return f"Bearer {token_data['access_token']}"
    
    async def _oauth_request(self, method: str, endpoint: str, **kwargs) -> Optional[dict]:
        """Make authenticated OAuth request to WordPress."""
        auth_header = self._get_oauth_auth_header()
        if not auth_header:
            logger.error("No valid OAuth token available")
            return None
        
        url = f"{self.get_base_url()}/wp-json/wp/v2/{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = auth_header
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, **kwargs) as resp:
                    if resp.status in (200, 201):
                        return await resp.json()
                    if resp.status == 401:
                        logger.error("OAuth token expired or invalid")
                        # Clear invalid token
                        try:
                            self.supabase.table("wordpress_oauth_tokens").delete().eq("website_id", self.website_id).eq("provider", "wordpress").execute()
                        except Exception:
                            pass
                    logger.error(f"OAuth WP request failed: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"OAuth WP request error: {e}")
            return None
    
    async def draft_post(self, title: str, content: str, seo_keyword: str = "", meta: dict = None) -> Optional[dict]:
        """Create a draft post in WordPress - NEVER publishes live."""
        if not self.get_base_url():
            logger.error("WordPress URL not configured")
            return None
        
        # Try OAuth first
        if self.site.get("oauth_enabled"):
            result = await self._oauth_request("POST", "posts", json={
                "title": title,
                "content": content,
                "status": "draft",
                "meta": {
                    "generated_from_alert": True,
                    "seo_keyword": seo_keyword,
                    "human_review_needed": True,
                    **(meta or {})
                }
            })
            if result:
                logger.info(f"Draft created via OAuth: {result.get('id')}")
                return result
        
        # Fallback to Basic Auth
        try:
            headers = {"Authorization": f"Basic {self._get_auth()}"}
            post_data = {
                "title": title,
                "content": content,
                "status": "draft",
                "meta": {
                    "generated_from_alert": True,
                    "seo_keyword": seo_keyword,
                    "human_review_needed": True,
                    **(meta or {})
                }
            }
            url = f"{self.get_base_url()}/wp-json/wp/v2/posts"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=post_data, headers=headers) as resp:
                    if resp.status in (200, 201):
                        result = await resp.json()
                        logger.info(f"Draft created via Basic Auth: {result.get('id')}")
                        return result
                    logger.error(f"WP draft failed: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"WP draft error: {e}")
            return None
    
    async def publish_post(self, post_id: str, user_id: str) -> Optional[dict]:
        """Publish a post - REQUIRES X-User-Id approval."""
        if not user_id:
            raise PermissionError("Human approval required - X-User-Id missing")
        
        if not self.get_base_url():
            logger.error("WordPress URL not configured")
            return None
        
        # Try OAuth first
        if self.site.get("oauth_enabled"):
            result = await self._oauth_request("PUT", f"posts/{post_id}", json={"status": "publish"})
            if result:
                self._log_publish_success(post_id, user_id, result)
                return result
        
        # Fallback to Basic Auth
        try:
            headers = {"Authorization": f"Basic {self._get_auth()}"}
            url = f"{self.get_base_url()}/wp-json/wp/v2/posts/{post_id}"
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json={"status": "publish"}, headers=headers) as resp:
                    if resp.status in (200, 201):
                        result = await resp.json()
                        self._log_publish_success(post_id, user_id, result)
                        return result
                    logger.error(f"WP publish failed: {resp.status}")
                    return None
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"WP publish error: {e}")
            return None
    
    def _log_publish_success(self, post_id: str, user_id: str, result: dict):
        """Log successful publish to critical_action_logs."""
        try:
            self.supabase.table("critical_action_logs").insert({
                "action": "publish_post",
                "target_id": post_id,
                "approved_by": user_id,
                "status": "success",
                "payload": {"post_id": post_id, "title": result.get("title", {}).get("rendered", "") if isinstance(result.get("title"), dict) else result.get("title", "")},
                "created_at": datetime.utcnow()
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to log publish action: {e}")
    
    async def get_site_info(self) -> Optional[dict]:
        """Fetch public WordPress site info to verify the connection (no auth required)."""
        if not self.get_base_url():
            logger.error("WordPress URL not configured")
            return None
        try:
            url = f"{self.get_base_url()}/wp-json/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(f"WP site info failed: {resp.status}")
                        return None
                    data = await resp.json()
            return {
                "name": data.get("name"),
                "description": data.get("description"),
                "url": data.get("url"),
                "home": data.get("home"),
                "wp_version": (data.get("wp_version") if isinstance(data.get("wp_version"), str) else None),
            }
        except Exception as e:
            logger.error(f"WP site info error: {e}")
            return None
    
    async def get_posts(self, per_page: int = 10, page: int = 1, status: str = None,
                        search: str = None) -> list:
        """Fetch real posts from WordPress. Returns list of post dicts."""
        return await self._list("posts", per_page=per_page, page=page, status=status, search=search)
    
    async def get_pages(self, per_page: int = 10, page: int = 1, status: str = None,
                        search: str = None) -> list:
        """Fetch real pages from WordPress. Returns list of page dicts."""
        return await self._list("pages", per_page=per_page, page=page, status=status, search=search)
    
    async def get_post(self, post_id: str) -> Optional[dict]:
        """Fetch a single post/page by id from WordPress."""
        if not self.get_base_url():
            logger.error("WordPress URL not configured")
            return None
        try:
            # Try OAuth first
            if self.site.get("oauth_enabled"):
                result = await self._oauth_request("GET", f"posts/{post_id}")
                if result:
                    return result
            
            # Fallback to Basic Auth
            headers = {"Authorization": f"Basic {self._get_auth()}"}
            url = f"{self.get_base_url()}/wp-json/wp/v2/posts/{post_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"WP get_post failed: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"WP get_post error: {e}")
            return None
    
    async def _list(self, endpoint: str, per_page: int = 10, page: int = 1,
                    status: str = None, search: str = None) -> list:
        """Generic GET list for wp/v2/{endpoint}."""
        if not self.get_base_url():
            logger.error("WordPress URL not configured")
            return []
        try:
            # Try OAuth first
            if self.site.get("oauth_enabled"):
                params = {"per_page": per_page, "page": page,
                          "_fields": "id,date,modified,link,title,status,excerpt,author,featured_media"}
                if status:
                    params["status"] = status
                if search:
                    params["search"] = search
                result = await self._oauth_request("GET", endpoint, params=params)
                if result is not None:
                    return result if isinstance(result, list) else []
            
            # Fallback to Basic Auth
            headers = {"Authorization": f"Basic {self._get_auth()}"}
            params = {"per_page": per_page, "page": page,
                      "_fields": "id,date,modified,link,title,status,excerpt,author,featured_media"}
            if status:
                params["status"] = status
            if search:
                params["search"] = search
            url = f"{self.get_base_url()}/wp-json/wp/v2/{endpoint}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"WP list {endpoint} failed: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"WP list {endpoint} error: {e}")
            return []


def get_wordpress_service(website_id: str) -> WordPressService:
    """Factory function."""
    return WordPressService(website_id)
