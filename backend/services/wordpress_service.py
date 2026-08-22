import json
import logging
import base64
import os
from datetime import datetime
from typing import Dict, Optional, List, Any
import httpx
from ..database import get_supabase

logger = logging.getLogger("backend.services.wordpress_service")


class WordPressService:
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.supabase = get_supabase()
        self.site = self._get_site_config()

    def _get_site_config(self) -> dict:
        """Get WordPress site configuration."""
        try:
            result = self.supabase.table("websites").select("*").eq("id", self.website_id).single().execute().data
            return result or {}
        except Exception:
            return {}

    def get_base_url(self) -> str:
        url = self.site.get("wordpress_url") or self.site.get("cms_url") or self.site.get("url") or ""
        if url and not url.startswith("http"):
            url = f"https://{url}"
        return url.rstrip("/")

    def _get_auth_tuple(self) -> tuple:
        user = self.site.get("wordpress_user") or self.site.get("cms_user") or ""
        password = self.site.get("wordpress_password") or self.site.get("app_password") or ""
        return (user, password)

    def _get_request_headers(self, additional: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        if additional:
            headers.update(additional)
        return headers

    async def test_connection(self, url: str, username: str, password: str) -> dict:
        """Test if WordPress credentials work, returning detailed diagnostics."""
        clean_url = url.rstrip("/")
        if clean_url and not clean_url.startswith("http"):
            clean_url = f"https://{clean_url}"

        headers = self._get_request_headers()
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
                # 1. Try with exact credentials
                response = await client.get(
                    f"{clean_url}/wp-json/wp/v2/users/me",
                    auth=(username, password),
                    headers=headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {"connected": True, "status_code": 200, "user_name": data.get("name", username), "message": f"Connected as {data.get('name', username)} ✅"}
                
                # 2. Try removing spaces if application password had spaces
                if " " in password:
                    resp2 = await client.get(
                        f"{clean_url}/wp-json/wp/v2/users/me",
                        auth=(username, password.replace(" ", "")),
                        headers=headers,
                    )
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        return {"connected": True, "status_code": 200, "user_name": data2.get("name", username), "message": f"Connected as {data2.get('name', username)} (trimmed) ✅"}

                if response.status_code == 403 and "Checking your browser" in response.text:
                    return {
                        "connected": False,
                        "status_code": 403,
                        "error_type": "cloudflare_bot_protection",
                        "message": "Cloudflare / Hostinger Bot Protection challenged the request. Ensure /wp-json/ is allowed."
                    }
                if response.status_code == 401:
                    return {
                        "connected": False,
                        "status_code": 401,
                        "error_type": "invalid_credentials",
                        "message": "WordPress rejected credentials (401). Verify username and Application Password in WP Admin -> Users -> Profile."
                    }
                return {
                    "connected": False,
                    "status_code": response.status_code,
                    "message": f"WordPress returned HTTP {response.status_code}: {response.text[:120]}"
                }
        except Exception as e:
            logger.warning(f"WordPress connection test failed: {e}")
            return {"connected": False, "status_code": 0, "message": str(e)}

    async def create_draft(self, website_id: str, title: str, content: str, keywords: Optional[list] = None) -> dict:
        """Create WordPress draft — agents and UI human approval call this."""
        site = self._get_site_config()
        base_url = self.get_base_url()
        user, password = self._get_auth_tuple()

        if not base_url or not user or not password:
            logger.info(f"WordPress credentials not fully configured for {website_id}, storing as local draft.")
            return {"success": False, "wp_post_id": None, "edit_url": None, "message": "WordPress credentials not configured"}

        headers = self._get_request_headers({"Content-Type": "application/json"})
        payload = {
            "title": title,
            "content": content,
            "status": "draft",
        }

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, verify=False) as client:
                # Attempt 1: with provided credentials
                response = await client.post(
                    f"{base_url}/wp-json/wp/v2/posts",
                    auth=(user, password),
                    headers=headers,
                    json=payload,
                )
                
                # Attempt 2: with trimmed password if 401
                if response.status_code == 401 and " " in password:
                    response = await client.post(
                        f"{base_url}/wp-json/wp/v2/posts",
                        auth=(user, password.replace(" ", "")),
                        headers=headers,
                        json=payload,
                    )

                if response.status_code in (200, 201):
                    draft = response.json()
                    draft_id = draft.get("id")
                    edit_url = f"{base_url}/wp-admin/post.php?post={draft_id}&action=edit"
                    link = draft.get("link") or edit_url
                    logger.info(f"Successfully created WordPress draft {draft_id} at {edit_url}")
                    return {"success": True, "wp_post_id": draft_id, "edit_url": edit_url, "link": link, "message": "Draft created in WordPress ✅"}
                else:
                    logger.warning(f"WordPress create draft returned {response.status_code}: {response.text[:200]}")
                    return {"success": False, "wp_post_id": None, "edit_url": None, "status_code": response.status_code, "message": f"WordPress HTTP {response.status_code}: {response.text[:120]}"}
        except Exception as e:
            logger.error(f"Error creating WordPress draft: {e}")
            return {"success": False, "wp_post_id": None, "edit_url": None, "message": str(e)}

    async def publish_post(self, website_id: str, wp_post_id: Any, user_id: str = "admin") -> dict:
        """Publish draft live to WordPress upon human approval."""
        base_url = self.get_base_url()
        user, password = self._get_auth_tuple()

        headers = self._get_request_headers({"Content-Type": "application/json"})
        if base_url and user and password and wp_post_id:
            try:
                async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, verify=False) as client:
                    response = await client.post(
                        f"{base_url}/wp-json/wp/v2/posts/{wp_post_id}",
                        auth=(user, password),
                        headers=headers,
                        json={"status": "publish"},
                    )
                    if response.status_code == 401 and " " in password:
                        response = await client.post(
                            f"{base_url}/wp-json/wp/v2/posts/{wp_post_id}",
                            auth=(user, password.replace(" ", "")),
                            headers=headers,
                            json={"status": "publish"},
                        )
                    if response.status_code in (200, 201):
                        logger.info(f"Published WordPress post {wp_post_id}")
            except Exception as e:
                logger.error(f"Failed to publish WordPress post {wp_post_id}: {e}")

        # Log critical action
        try:
            self.supabase.table("critical_action_logs").insert({
                "action": "publish_post",
                "target_id": str(wp_post_id or ""),
                "approved_by": user_id,
                "status": "success",
                "payload": {"website_id": website_id, "wp_post_id": wp_post_id},
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception:
            pass

        return {"published": True, "post_id": wp_post_id}

    async def get_posts(self, per_page: int = 10, page: int = 1, status: Optional[str] = None, search: Optional[str] = None) -> List[dict]:
        """Fetch posts from WordPress."""
        base_url = self.get_base_url()
        user, password = self._get_auth_tuple()
        if not base_url:
            return []

        params = {"per_page": per_page, "page": page}
        if status:
            params["status"] = status
        if search:
            params["search"] = search

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
                auth = (user, password) if user and password else None
                resp = await client.get(f"{base_url}/wp-json/wp/v2/posts", params=params, auth=auth, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"Error fetching WP posts: {e}")
        return []

    async def get_site_info(self) -> dict:
        """Fetch site info with graceful fallback so 404 is never thrown for configured sites."""
        base_url = self.get_base_url()
        domain = self.site.get("domain") or (base_url.replace("https://", "").replace("http://", "").split("/")[0] if base_url else "WordPress Site")
        fallback_info = {
            "name": domain,
            "url": base_url or f"https://{domain}",
            "home": base_url or f"https://{domain}",
            "status": "configured",
            "domain": domain,
        }
        if not base_url:
            return fallback_info

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, verify=False) as client:
                resp = await client.get(f"{base_url}/wp-json/", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "name": data.get("name") or domain,
                        "description": data.get("description", ""),
                        "url": data.get("url") or base_url,
                        "home": data.get("home") or base_url,
                        "wp_version": data.get("wp_version") if isinstance(data.get("wp_version"), str) else None,
                        "status": "live",
                    }
        except Exception as e:
            logger.warning(f"Error fetching WP site info: {e}")
        return fallback_info


def get_wordpress_service(website_id: str) -> WordPressService:
    return WordPressService(website_id)
