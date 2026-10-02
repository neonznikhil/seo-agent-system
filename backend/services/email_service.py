import json
import logging
import aiohttp
import os
from datetime import datetime

logger = logging.getLogger("backend.services.email_service")

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000")

# aiohttp's default total timeout is 300s, which parks the calling task for five
# minutes on a hung provider. 15s is the bound used elsewhere in this repo.
RESEND_TIMEOUT_SECONDS = 15.0

# Delivery statuses. `not_configured` (no provider credentials) is deliberately
# distinct from `rejected` (provider present but refused the key) — collapsing
# both into False made the API tell users their working setup was "not
# configured" whenever Resend answered 401/500.
STATUS_SENT = "sent"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"


async def send_email_alert_detailed(to_email: str, alert: dict) -> dict:
    """Send a critical alert and report WHY it did or did not go out.

    Returns ``{"sent": bool, "status": str, "provider": str|None,
    "http_status": int|None, "error": str|None}``.
    """
    try:
        if os.getenv("RESEND_API_KEY"):
            return await _send_resend_email(to_email, alert)
        logger.warning("No email provider configured - alert logged only")
        return {
            "sent": False,
            "status": STATUS_NOT_CONFIGURED,
            "provider": None,
            "http_status": None,
            "error": "No email provider configured (RESEND_API_KEY is not set).",
        }
    except Exception as e:
        logger.error(f"Email alert failed: {e}")
        return {
            "sent": False,
            "status": STATUS_FAILED,
            "provider": "resend",
            "http_status": None,
            "error": str(e)[:200],
        }


async def send_email_alert(to_email: str, alert: dict) -> bool:
    """Send critical alert via Resend. Backwards-compatible boolean wrapper."""
    result = await send_email_alert_detailed(to_email, alert)
    return bool(result.get("sent"))


async def _send_resend_email(to_email: str, alert: dict) -> dict:
    """Send email via Resend API. Returns the detailed delivery result."""
    try:
        subject = f"[SEO ALERT] {alert.get('title', 'Alert')} - {alert.get('severity', 'info').upper()}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px;">
            <div style="background: {'#E01E5A' if alert.get('severity') == 'critical' else '#FF9500' if alert.get('severity') == 'high' else '#FFA500'}; padding: 20px; color: white;">
                <h2>{alert.get('title', 'Alert')}</h2>
                <p>Severity: {alert.get('severity', 'info').upper()}</p>
            </div>
            <div style="padding: 20px;">
                <p><strong>Source:</strong> {alert.get('source_monitor', 'Unknown')}</p>
                <p><strong>Description:</strong></p>
                <p>{alert.get('description', 'No description')}</p>
                <p><strong>Data:</strong></p>
                <pre style="background: #f5f5f5; padding: 10px; overflow-x: auto;">{str(alert.get('data', {}))}</pre>
                <p style="margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee;">
                    <a href="{DASHBOARD_URL}/monitoring?alert_id={alert.get('id')}">View Alert in Dashboard</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=RESEND_TIMEOUT_SECONDS)
        ) as session:
            resp = await session.post(
                "https://api.resend.com/emails",
                json={
                    "from": "SEO Monitor <alerts@yourdomain.com>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                    "headers": {"X-Priority": "1"} if alert.get("severity") == "critical" else {}
                },
                headers={
                    "Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}",
                    "Content-Type": "application/json"
                }
            )

            if resp.status == 201:
                logger.info(f"Email alert sent successfully: alert_id={alert.get('id')}")
                return {
                    "sent": True,
                    "status": STATUS_SENT,
                    "provider": "resend",
                    "http_status": resp.status,
                    "error": None,
                }

            data = await resp.text()
            logger.error(f"Resend API failed: {resp.status} {data}")
            # 401/403 means the provider IS configured and refused the key — not
            # "no provider configured". Keep the two apart so the caller can say
            # something actionable.
            status = STATUS_REJECTED if resp.status in (401, 403) else STATUS_FAILED
            return {
                "sent": False,
                "status": status,
                "provider": "resend",
                "http_status": resp.status,
                "error": f"Resend returned HTTP {resp.status}: {data[:180]}",
            }
    except Exception as e:
        logger.error(f"Resend email failed: {e}")
        return {
            "sent": False,
            "status": STATUS_FAILED,
            "provider": "resend",
            "http_status": None,
            "error": str(e)[:200],
        }