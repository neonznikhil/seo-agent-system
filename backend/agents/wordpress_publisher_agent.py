from datetime import datetime
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("backend.agents.wordpress_publisher_agent")


class WordPressPublisherAgent:
    """
    WordPressPublisherAgent - publishes or drafts content to WordPress via saved OAuth
    or Basic Auth connections stored in wordpress_connections.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, title: str, content_html: str, status: str = "draft", meta: Dict[str, Any] = None) -> Dict[str, Any]:
        from ..services.wordpress_oauth_service import get_oauth_status, publish_with_oauth
        from ..services.wordpress_service import get_wordpress_service

        oauth_status = get_oauth_status(self.website_id, user_id="test-user")
        meta = meta or {}

        if oauth_status.get("connected"):
            try:
                result = await publish_with_oauth(
                    website_id=self.website_id,
                    user_id="test-user",
                    title=title,
                    content_html=content_html,
                    status=status,
                    meta=meta,
                )
                return {
                    "status": "success",
                    "connection": "oauth",
                    "wp_post_id": result.get("wp_post_id"),
                    "wp_url": result.get("wp_url"),
                    "edit_url": result.get("edit_url"),
                }
            except Exception as e:
                logger.error("OAuth publish failed: %s", e)
                return {"status": "error", "connection": "oauth", "error": str(e)}

        ws = get_wordpress_service(self.website_id)
        site = ws._get_site_config()
        if not site.get("cms_url"):
            return {
                "status": "skipped",
                "connection": "none",
                "reason": "No WordPress connection configured",
                "oauth_url": self._build_oauth_url(),
            }

        try:
            result = await ws.draft_post(title=title, content=content_html, seo_keyword=meta.get("seo_keyword", ""), meta=meta)
            if result:
                return {
                    "status": "success",
                    "connection": "basic_auth",
                    "wp_post_id": result.get("id"),
                    "wp_url": result.get("link"),
                }
        except Exception as e:
            logger.error("Basic auth publish failed: %s", e)

        return {
            "status": "skipped",
            "connection": "basic_auth",
            "reason": f"Publish failed: {site.get('cms_url')}",
            "oauth_url": self._build_oauth_url(),
        }

    def _build_oauth_url(self) -> str:
        from ..config import WP_OAUTH_AUTHORIZE_URL, WP_OAUTH_CLIENT_ID, REDIRECT_URI
        if not WP_OAUTH_AUTHORIZE_URL:
            return ""
        return (
            f"{WP_OAUTH_AUTHORIZE_URL}"
            f"?response_type=code&client_id={WP_OAUTH_CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}&scope=basic"
        )


def create_wordpress_publisher_agent(website_id: str) -> WordPressPublisherAgent:
    return WordPressPublisherAgent(website_id)
