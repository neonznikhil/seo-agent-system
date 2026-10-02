import os
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

import httpx
from config import SLACK_BOT_TOKEN, SLACK_WEBHOOK_URL
from database import get_supabase
from security import decrypt_secret

logger = logging.getLogger("backend.services.slack_app_service")

# Default target channels (auto-created by the OAuth flow)
SLACK_CHANNELS = {
    "daily": "#rankforge-daily",
    "backlinks": "#rankforge-backlinks",
    "weekly": "#rankforge-weekly",
    "alerts": "#rankforge-alerts",
}

SLACK_API = "https://slack.com/api"


class SlackAppService:
    """Slack App integration using the REAL Web API (chat.postMessage).

    Token resolution order:
      1. Per-website Fernet-encrypted token from the durable connector settings store
      2. Environment SLACK_BOT_TOKEN
    Delivery is never mocked: if no token/webhook is configured the call
    returns False with an explicit reason.
    """

    def __init__(self, bot_token: Optional[str] = None):
        # An explicit constructor argument is an override; everything else is
        # resolved from the environment at CALL time. Capturing the env at
        # import time (the module-level singleton is built then) meant a token
        # saved later updated `.env`/`os.environ` but the service kept using the
        # captured empty string, so dispatch reported "not_configured" while
        # `is_connected_config()` said connected.
        self._bot_token_override = bot_token

    # ------------------------------------------------------------------
    # Credential resolution (call-time, never import-time)
    # ------------------------------------------------------------------
    @property
    def bot_token(self) -> str:
        return self._bot_token_override or os.getenv("SLACK_BOT_TOKEN", "") or SLACK_BOT_TOKEN or ""

    @bot_token.setter
    def bot_token(self, value: Optional[str]) -> None:
        self._bot_token_override = value or None

    @property
    def webhook_url(self) -> str:
        return os.getenv("SLACK_WEBHOOK_URL", "") or SLACK_WEBHOOK_URL or ""

    @webhook_url.setter
    def webhook_url(self, value: Optional[str]) -> None:
        if value:
            os.environ["SLACK_WEBHOOK_URL"] = value

    # ------------------------------------------------------------------
    # Token resolution
    # ------------------------------------------------------------------
    async def _resolve_token(self, website_id: Optional[str] = None) -> str:
        if website_id and website_id not in ("default", "all", "", None):
            try:
                from services.local_store import get_local_connector_settings
                creds = get_local_connector_settings() or {}
                # The connector settings store keys the encrypted token per
                # website so multiple connected sites never share a bot token.
                token_encrypted = (
                    creds.get(f"slack_token_encrypted_{website_id}")
                    or creds.get("slack_token_encrypted")
                )
                if token_encrypted:
                    token = decrypt_secret(token_encrypted)
                    if token:
                        return token
            except Exception as e:
                logger.debug(f"[SlackApp] Website token lookup failed: {e}")
        return self.bot_token or ""

    @staticmethod
    def is_connected_config() -> bool:
        return bool(os.getenv("SLACK_BOT_TOKEN") or SLACK_BOT_TOKEN)

    # ------------------------------------------------------------------
    # Channel management via real Slack API
    # ------------------------------------------------------------------
    async def initialize_channels(self, website_id: str = "default") -> Dict[str, Any]:
        """Create the 4 RankForge channels if missing; store real IDs on the website."""
        token = await self._resolve_token(website_id)
        if not token:
            return {"success": False, "error": "No Slack bot token available"}

        created: Dict[str, str] = {}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for key, name in SLACK_CHANNELS.items():
                # 1. Try lookup first (conversations.list paginated shallowly)
                channel_id = None
                cursor = None
                for _ in range(4):
                    params = {"limit": 200, "types": "public_channel,private_channel"}
                    if cursor:
                        params["cursor"] = cursor
                    resp = await client.get(f"{SLACK_API}/conversations.list", headers=headers, params=params)
                    data = resp.json()
                    if not data.get("ok"):
                        break
                    for ch in data.get("channels", []):
                        if ch.get("name") == name.lstrip("#"):
                            channel_id = ch.get("id")
                            break
                    if channel_id or not data.get("response_metadata", {}).get("next_cursor"):
                        break
                    cursor = data["response_metadata"]["next_cursor"]

                # 2. Create when absent
                if not channel_id:
                    resp = await client.post(
                        f"{SLACK_API}/conversations.create",
                        headers=headers,
                        json={"name": name.lstrip("#")},
                    )
                    cdata = resp.json()
                    if cdata.get("ok"):
                        channel_id = cdata.get("channel", {}).get("id")
                    elif cdata.get("error") == "name_taken":
                        logger.info(f"[SlackApp] Channel {name} already exists")
                    else:
                        logger.warning(f"[SlackApp] Could not create {name}: {cdata.get('error')}")
                if channel_id:
                    created[key] = channel_id

        if created:
            try:
                from services.local_store import set_local_connector_settings
                set_local_connector_settings({
                    f"slack_channels_{website_id}": created,
                })
            except Exception as e:
                logger.debug(f"[SlackApp] Channel map update note: {e}")

        return {"success": bool(created), "channels": created}

    # ------------------------------------------------------------------
    # Message dispatch via real Slack API
    # ------------------------------------------------------------------
    async def post_block_message(
        self,
        channel: str,
        blocks: List[Dict[str, Any]],
        text_fallback: str,
        report_type: str = "report",
        website_id: str = "default"
    ) -> bool:
        """Send rich Block Kit message through the real Slack Web API."""
        token = await self._resolve_token(website_id)
        sent = False
        delivery_status = "failed"

        if token:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
            payload = {"channel": channel, "text": text_fallback, "blocks": blocks}
            # Resolve channel name -> ID when necessary
            if channel.startswith("#"):
                channel_id = await self._lookup_channel_id(token, channel)
                if channel_id:
                    payload["channel"] = channel_id
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(f"{SLACK_API}/chat.postMessage", headers=headers, json=payload)
                    data = resp.json()
                    if data.get("ok"):
                        sent = True
                        delivery_status = "sent"
                    else:
                        delivery_status = f"slack_error:{data.get('error')}"
                        logger.warning(f"[SlackApp] chat.postMessage failed: {data.get('error')}")
            except Exception as e:
                delivery_status = f"http_error:{str(e)[:80]}"
                logger.warning(f"[SlackApp] Dispatch error: {e}")
        elif self.webhook_url.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(self.webhook_url, json={"text": text_fallback, "blocks": blocks})
                    if resp.status_code == 200:
                        sent = True
                        delivery_status = "sent_via_webhook"
            except Exception as e:
                logger.warning(f"[SlackApp] Webhook dispatch warning: {e}")
        else:
            delivery_status = "not_configured"
            logger.info("[SlackApp] Slack not connected — skipping dispatch silently")

        # Log every attempt for observability
        summary = text_fallback[:120] if text_fallback else f"Slack {report_type} dispatched."
        entry = {
            "website_id": website_id,
            "report_type": report_type,
            "channel": channel,
            "sent_at": datetime.utcnow().isoformat(),
            "message_summary": summary,
            "delivery_status": delivery_status,
            "payload": {"blocks": blocks, "fallback": text_fallback},
        }
        try:
            get_supabase().table("slack_message_log").insert(entry).execute()
        except Exception as e:
            # The table may not exist on the connected project. Fall back to the
            # durable local store instead of silently dropping the dispatch log.
            logger.debug(f"[SlackApp] Log note: {e}")
            try:
                from services.local_store import save_local_slack_message_log
            except (ImportError, ValueError):
                from backend.services.local_store import save_local_slack_message_log
            save_local_slack_message_log(entry)

        return sent

    @staticmethod
    async def _lookup_channel_id(token: str, channel_name: str) -> Optional[str]:
        headers = {"Authorization": f"Bearer {token}"}
        cursor = None
        target = channel_name.lstrip("#")
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(4):
                params = {"limit": 200, "types": "public_channel,private_channel"}
                if cursor:
                    params["cursor"] = cursor
                resp = await client.get(f"{SLACK_API}/conversations.list", headers=headers, params=params)
                data = resp.json()
                if not data.get("ok"):
                    return None
                for ch in data.get("channels", []):
                    if ch.get("name") == target:
                        return ch.get("id")
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
        return None


# Global Singleton
slack_app_service = SlackAppService()
