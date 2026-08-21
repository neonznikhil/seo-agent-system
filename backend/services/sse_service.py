import logging
import asyncio
import json
from typing import Dict
from datetime import datetime

logger = logging.getLogger("backend.services.sse_service")

_connections: Dict[str, list] = {}


async def push_sse_alert(website_id: str, data: str) -> bool:
    """Push alert data to all connected SSE clients for website."""
    if website_id not in _connections:
        return False
    
    success = 0
    for websocket in _connections[website_id][:]:
        try:
            await websocket.send_text(data)
            success += 1
        except Exception as e:
            logger.warning(f"SSE push failed: {e}")
            _connections[website_id].remove(websocket)
    
    return success > 0


def register_connection(website_id: str, websocket) -> None:
    """Register a new SSE connection."""
    if website_id not in _connections:
        _connections[website_id] = []
    _connections[website_id].append(websocket)


def unregister_connection(website_id: str, websocket) -> None:
    """Remove an SSE connection."""
    if website_id in _connections and websocket in _connections[website_id]:
        _connections[website_id].remove(websocket)


async def push_to_dashboard(website_id: str, alert: dict) -> None:
    """Push alert to all dashboard channels - SSE + Slack + Email."""
    from .reporting_service import report_problem
    
    await report_problem(
        website_id=website_id,
        alert_type=alert.get("alert_type", "info"),
        severity=alert.get("severity", "info"),
        title=alert.get("title", "Alert"),
        description=alert.get("description", ""),
        data=alert.get("data", {}),
        source_monitor=alert.get("source_monitor", "dashboard")
    )