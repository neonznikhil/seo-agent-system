"""GEO Monitor — monitors local/geo SEO signals.

Stub implementation so continuous_monitor.py doesn't crash on import.
"""

import logging

logger = logging.getLogger(__name__)


class GEOMonitor:
    """Monitor geographic/local SEO ranking signals."""

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def get_local_keywords(self, limit: int = 10):
        return []

    async def get_geo_rank(self, keyword: str, city: str = None):
        return None

    async def get_gmb_signal(self, keyword: str):
        return None
