import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("backend.middleware.circuit_breaker")

# In-memory circuit breaker registry (mirrored in Redis when available)
_CIRCUITS: Dict[str, Dict[str, Any]] = {
    "nvidia_nim": {"state": "closed", "failure_count": 0, "last_failure": None, "reset_timeout": 300},
    "serper": {"state": "closed", "failure_count": 0, "last_failure": None, "reset_timeout": 300},
    "wordpress": {"state": "closed", "failure_count": 0, "last_failure": None, "reset_timeout": 300},
    "gsc": {"state": "closed", "failure_count": 0, "last_failure": None, "reset_timeout": 300},
    "ga4": {"state": "closed", "failure_count": 0, "last_failure": None, "reset_timeout": 300},
    "ahrefs": {"state": "closed", "failure_count": 0, "last_failure": None, "reset_timeout": 300},
}


class CircuitBreaker:
    """Enterprise Circuit Breaker protecting external APIs."""

    @classmethod
    def can_execute(cls, service_name: str) -> bool:
        circuit = _CIRCUITS.get(service_name)
        if not circuit:
            return True

        state = circuit["state"]
        if state == "closed":
            return True

        if state == "open":
            last_fail = circuit.get("last_failure")
            timeout = circuit.get("reset_timeout", 300)
            if last_fail and (time.time() - last_fail) > timeout:
                circuit["state"] = "half-open"
                logger.info(f"[CircuitBreaker] {service_name} transitioned from OPEN to HALF-OPEN (testing recovery)")
                return True
            return False

        if state == "half-open":
            return True

        return True

    @classmethod
    def record_success(cls, service_name: str):
        if service_name in _CIRCUITS:
            _CIRCUITS[service_name]["state"] = "closed"
            _CIRCUITS[service_name]["failure_count"] = 0
            _CIRCUITS[service_name]["last_failure"] = None

    @classmethod
    def record_failure(cls, service_name: str, error_msg: str = ""):
        if service_name not in _CIRCUITS:
            _CIRCUITS[service_name] = {"state": "closed", "failure_count": 0, "last_failure": None, "reset_timeout": 300}

        circuit = _CIRCUITS[service_name]
        circuit["failure_count"] += 1
        circuit["last_failure"] = time.time()

        if circuit["failure_count"] >= 3:
            circuit["state"] = "open"
            logger.critical(f"[CircuitBreaker] Tripped {service_name} circuit to OPEN after 3 consecutive failures. Pausing requests for 5 minutes. Error: {error_msg}")
            
            # Post alert
            try:
                from ..database import get_supabase
                get_supabase().table("realtime_alerts").insert({
                    "alert_type": "circuit_open",
                    "severity": "critical",
                    "title": f"Circuit Breaker Tripped: {service_name}",
                    "description": f"External API {service_name} failed 3 times. Circuit opened for 5 minutes.",
                    "status": "unread",
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            except Exception:
                pass

    @classmethod
    def get_all_states(cls) -> Dict[str, Any]:
        """Return live status of all external API circuits."""
        res = {}
        now = time.time()
        for name, data in _CIRCUITS.items():
            last_f = data.get("last_failure")
            timeout = data.get("reset_timeout", 300)
            remaining_seconds = max(0, int(timeout - (now - last_f))) if (data["state"] == "open" and last_f) else 0
            res[name] = {
                "state": data["state"],
                "failure_count": data["failure_count"],
                "remaining_seconds": remaining_seconds,
                "healthy": data["state"] == "closed"
            }
        return res
