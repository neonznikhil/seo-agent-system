"""Conversion intelligence: correlate organic traffic with GA4 conversions.

Identifies 'Leaky Stars' (lots of sessions, few conversions) and 'Hidden Gems'
(few sessions, high conversion rate). Every figure is computed from stored GA4
conversion rows. When no conversion data has been imported the report says so
and returns empty lists - it never invents example content or revenue.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from services import intelligence_store as store

logger = logging.getLogger("backend.services.conversion_intelligence_service")

# A page needs enough traffic before its conversion rate means anything.
MIN_SESSIONS_FOR_RATE = 50
LEAKY_MAX_RATE = 0.005      # <= 0.5% with real traffic is a CRO candidate
HIDDEN_GEM_MIN_RATE = 0.04  # >= 4% with low traffic deserves more links
REPORT_DAYS = 30


class ConversionIntelligenceService:
    """Upgrade 8: Conversion Intelligence Layer."""

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id or "default"

    async def run_conversion_analysis(self) -> Dict[str, Any]:
        start_t = time.time()
        logger.info("[ConversionIntelligence] Correlating traffic with GA4 goals for %s",
                    self.website_id)

        rows = store.select("conversions", {"website_id": self.website_id})
        if not rows:
            return {
                "success": True,
                "configured": False,
                "total_monthly_goal_completions": None,
                "attributed_revenue": None,
                "top_converting_articles": [],
                "leaky_stars_identified": [],
                "hidden_gems_identified": [],
                "duration_sec": round(time.time() - start_t, 3),
                "note": (
                    "No GA4 conversion data stored for this site. "
                    "Import conversions to populate this report."
                ),
            }

        pages: Dict[str, Dict[str, float]] = {}
        for row in rows:
            page = str(row.get("landing_page") or "")
            if not page:
                continue
            bucket = pages.setdefault(page, {"leads": 0.0, "revenue": 0.0})
            bucket["leads"] += float(row.get("conversion_count") or 0)
            bucket["revenue"] += float(row.get("conversion_value") or 0)

        # Sessions are not in the conversion rows; they come from GA4 sessions
        # if available. Without them a conversion rate cannot be stated, so the
        # page is reported for leads only.
        sessions_by_page = self._sessions_by_page()

        articles: List[Dict[str, Any]] = []
        for page, agg in pages.items():
            sessions = sessions_by_page.get(page)
            rate = (agg["leads"] / sessions) if sessions else None
            articles.append({
                "url": page,
                "title": page,
                "sessions": sessions,
                "goal_completions": int(agg["leads"]),
                "conv_rate": f"{rate * 100:.2f}%" if rate is not None else None,
                "revenue": f"${agg['revenue']:,.0f}",
                "revenue_value": round(agg["revenue"], 2),
            })

        top_converting = sorted(
            articles, key=lambda a: a["revenue_value"], reverse=True
        )[:5]

        leaky_stars = [
            a for a in articles
            if a["sessions"] and a["sessions"] >= MIN_SESSIONS_FOR_RATE
            and (a["goal_completions"] / a["sessions"]) <= LEAKY_MAX_RATE
        ]
        hidden_gems = [
            a for a in articles
            if a["sessions"] and a["sessions"] < MIN_SESSIONS_FOR_RATE
            and (a["goal_completions"] / a["sessions"]) >= HIDDEN_GEM_MIN_RATE
        ]

        queued = self._queue_cro_revisions(leaky_stars)
        total_leads = sum(a["goal_completions"] for a in articles)
        total_revenue = sum(a["revenue_value"] for a in articles)

        return {
            "success": True,
            "configured": True,
            "period_days": REPORT_DAYS,
            "pages_analysed": len(articles),
            "total_monthly_goal_completions": total_leads,
            "attributed_revenue": f"${total_revenue:,.0f}",
            "attributed_revenue_value": round(total_revenue, 2),
            "top_converting_articles": top_converting,
            "leaky_stars_identified": leaky_stars,
            "hidden_gems_identified": hidden_gems,
            "cro_revisions_queued": queued,
            "sessions_note": (
                "Conversion rate is only reported for pages with GA4 session "
                "counts. Pages without sessions show leads and revenue only."
                if not sessions_by_page else ""
            ),
            "thresholds": {
                "min_sessions_for_rate": MIN_SESSIONS_FOR_RATE,
                "leaky_max_rate": LEAKY_MAX_RATE,
                "hidden_gem_min_rate": HIDDEN_GEM_MIN_RATE,
            },
            "duration_sec": round(time.time() - start_t, 3),
        }

    def _sessions_by_page(self) -> Dict[str, int]:
        """Best-effort GA4 session counts, if a sessions table is populated."""
        try:
            rows = store.select("site_metrics_daily", {"website_id": self.website_id})
        except Exception:  # noqa: BLE001
            return {}
        sessions: Dict[str, int] = {}
        for row in rows:
            page = row.get("landing_page")
            if page and row.get("clicks") is not None:
                sessions[str(page)] = int(row.get("clicks") or 0)
        return sessions

    def _queue_cro_revisions(self, leaky_stars: List[Dict[str, Any]]) -> int:
        """Queue a CRO action for each real leaky page. Returns count queued."""
        from services import intelligence_service as intel

        queued = 0
        for page in leaky_stars:
            try:
                intel.create_action(
                    website_id=self.website_id,
                    title=f"CRO revision: {page['url']}",
                    category="cro",
                    target_url=page["url"],
                    severity="high",
                    effort_minutes=60,
                    source="conversion_intelligence",
                )
                queued += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ConversionIntelligence] could not queue CRO for %s: %s",
                               page.get("url"), exc)
        return queued