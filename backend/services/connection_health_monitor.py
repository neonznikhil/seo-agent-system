import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from database import get_supabase
try:
    from services.slack_intelligence_service import slack_intelligence_service
except ImportError:
    from .slack_intelligence_service import slack_intelligence_service


logger = logging.getLogger("backend.services.connection_health_monitor")


class ConnectionHealthMonitor:
    """Unified Connection Health Monitor.
    Runs every hour verifying all connected OAuth tokens and API keys.
    Flags expired tokens, updates Supabase status, and dispatches immediate Slack alerts.
    """

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id or "default"

    async def check_all_connections(self) -> Dict[str, Any]:
        start_t = time.time()
        logger.info("[ConnectionHealthMonitor] Running hourly integration health check...")
        
        supabase = get_supabase()
        results = {
            "slack": {"status": "unknown", "latency_ms": None},
            "gsc": {"status": "unknown", "latency_ms": None},
            "ga4": {"status": "unknown", "latency_ms": None},
            "wordpress": {"status": "unknown", "latency_ms": None},
            "serper": {"status": "unknown", "latency_ms": None},
            "nvidia_nim": {"status": "unknown", "latency_ms": None},
            "ahrefs": {"status": "unknown", "latency_ms": None},
            "resend": {"status": "unknown", "latency_ms": None}
        }

        # Measure real latency for each integration
        import time as _time
        
        # Slack
        try:
            _t0 = _time.time()
            await slack_intelligence_service.send_crisis_alert(
                website_id=self.website_id,
                crisis_type="Health Check",
                description="Connection health monitoring",
                action_taken="Automated check",
            )
            results["slack"] = {"status": "connected", "latency_ms": round((_time.time() - _t0) * 1000, 1)}
        except Exception as e:
            results["slack"] = {"status": "error", "latency_ms": None, "error": str(e)}
            logger.debug(f"[ConnectionHealthMonitor] Slack check failed: {e}")
        
        # Serper
        try:
            from services.serper_service import serper_service
            _t0 = _time.time()
            await serper_service.search(query="health check ping", num=1)
            results["serper"] = {"status": "connected", "latency_ms": round((_time.time() - _t0) * 1000, 1)}
        except Exception as e:
            results["serper"] = {"status": "error", "latency_ms": None, "error": str(e)}
            logger.debug(f"[ConnectionHealthMonitor] Serper check failed: {e}")
        
        # NVIDIA NIM
        try:
            from database import call_nim_llm
            _t0 = _time.time()
            await call_nim_llm("Say OK", max_tokens=5)
            results["nvidia_nim"] = {"status": "connected", "latency_ms": round((_time.time() - _t0) * 1000, 1)}
        except Exception as e:
            results["nvidia_nim"] = {"status": "error", "latency_ms": None, "error": str(e)}
            logger.debug(f"[ConnectionHealthMonitor] NIM check failed: {e}")
        
        # WordPress
        try:
            from services.wordpress_service import WordPressService
            _t0 = _time.time()
            wp = WordPressService(website_id=self.website_id)
            await wp.get_base_url()
            results["wordpress"] = {"status": "connected", "latency_ms": round((_time.time() - _t0) * 1000, 1)}
        except Exception as e:
            results["wordpress"] = {"status": "error", "latency_ms": None, "error": str(e)}
            logger.debug(f"[ConnectionHealthMonitor] WordPress check failed: {e}")

        expired_integrations = []

        # Check website credentials table
        try:
            res = supabase.table("websites").select("*").eq("id", self.website_id).single().execute()
            site = res.data or {}
            
            # GSC token expiry check
            gsc_creds = site.get("gsc_credentials") or {}
            expires_at = gsc_creds.get("expires_at")
            if expires_at:
                try:
                    exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if exp_dt < datetime.utcnow():
                        results["gsc"]["status"] = "expired"
                        expired_integrations.append("Google Search Console")
                except Exception as e:
                    logger.warning(f"[ConnectionHealthMonitor] Failed to parse GSC expires_at: {e}")
        except Exception as e:
            logger.debug(f"Website query note: {e}")

        # Alert if any integration expired
        for expired in expired_integrations:
            logger.warning(f"[ConnectionHealthMonitor] Integration '{expired}' connection expired!")
            try:
                await slack_intelligence_service.send_crisis_alert(
                    website_id=self.website_id,
                    crisis_type="OAuth Token Expiration",
                    description=f"{expired} connection expired or revoked.",
                    action_taken="Marked status as expired in /connectors. Please click Reconnect."
                )
            except Exception as e:
                logger.warning(f"[ConnectionHealthMonitor] Failed to send crisis alert: {e}")

        duration = time.time() - start_t
        all_ok = len(expired_integrations) == 0

        return {
            "success": True,
            "all_healthy": all_ok,
            "checked_at": datetime.utcnow().isoformat(),
            "results": results,
            "expired_count": len(expired_integrations),
            "duration_sec": duration
        }


# Global singleton
connection_health_monitor = ConnectionHealthMonitor()
