import json
import logging
import aiohttp
import os
from datetime import datetime

logger = logging.getLogger("backend.services.email_service")

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000")


async def send_email_alert(to_email: str, alert: dict) -> bool:
    """Send critical alert via Resend or SMTP."""
    try:
        if os.getenv("RESEND_API_KEY"):
            return await _send_resend_email(to_email, alert)
        else:
            logger.warning("No email provider configured - alert logged only")
            return False
    except Exception as e:
        logger.error(f"Email alert failed: {e}")
        return False


async def _send_resend_email(to_email: str, alert: dict) -> bool:
    """Send email via Resend API."""
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
        
        async with aiohttp.ClientSession() as session:
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
                return True
            else:
                data = await resp.text()
                logger.error(f"Resend API failed: {resp.status} {data}")
                return False
    except Exception as e:
        logger.error(f"Resend email failed: {e}")
        return False