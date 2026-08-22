"""GEO Monitor — monitors local/geo SEO signals.

Stub implementation so continuous_monitor.py doesn't crash on import.
"""

import logging

logger = logging.getLogger(__name__)


class GEOMonitor:
    """Monitor geographic/local SEO ranking signals."""

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self):
        """Run geo monitoring check. Returns status dict."""
        logger.info("[GEOMonitor] Running geo check for %s (stub)", self.website_id)
        return {
            "status": "ok",
            "website_id": self.website_id,
            "issues": [],
            "local_rankings": [],
            "geo_signals": {},
        }
