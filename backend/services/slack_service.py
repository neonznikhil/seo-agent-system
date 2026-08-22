from datetime import datetime
import json
import os
import aiohttp
import logging

logger = logging.getLogger("backend.services.slack_service")


async def send_slack_alert(webhook_url: str, alert: dict) -> bool:
    """Send alert to Slack webhook."""
    try:
        dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:3000")
        severity_emoji = {
            "critical": ":rotating_light:",
            "high": ":warning:",
            "medium": ":warning:",
            "low": ":information_source:",
            "info": ":information_source:"
        }.get(alert.get("severity", "info"), ":information_source:")
        
        color_map = {
            "critical": "#E01E5A",
            "high": "#FF9500",
            "medium": "#FFA500",
            "low": "#6A9955",
            "info": "#36C5F0"
        }
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} {alert.get('title', 'Alert')} [{alert.get('severity', 'info').upper()}]"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Source:* `{alert.get('source_monitor', 'Unknown')}>`\n\n*Description:* {alert.get('description', 'No description')}\n\n<!subteam^S0123456789|@here> Human approval required for action."
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in Dashboard"
                        },
                        "url": f"{dashboard_url}/monitoring?alert_id={alert.get('id')}"
                    }
                ]
            }
        ]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json={"blocks": blocks}) as resp:
                if resp.status in (200, 204):
                    logger.info(f"Slack alert sent: {alert.get('id')}")
                    return True
                logger.error(f"Slack webhook failed: {resp.status}")
                return False
    except Exception as e:
        logger.error(f"Slack alert failed: {e}")
        return False