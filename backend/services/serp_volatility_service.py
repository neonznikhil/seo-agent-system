import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from database import get_supabase
from services.serper_service import serper_service


logger = logging.getLogger("backend.services.serp_volatility_service")


class SerpVolatilityService:
    """Upgrade 4: Real-Time SERP Volatility Detection.
    Runs every 6 hours across top 20 tracked keywords.
    Calculates Volatility Scores and Niche Volatility Index. Triggers Defensive Posture Protocol if > 35%.
    """

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id or "default"

    def _prior_positions(self, keyword: str) -> Dict[str, int]:
        """url -> position from the most recent snapshot set for this keyword."""
        try:
            supabase = get_supabase()
            rows = (
                supabase.table("serp_snapshots")
                .select("url, position, date_captured")
                .eq("website_id", self.website_id)
                .eq("keyword", keyword)
                .order("date_captured", desc=True)
                .limit(20)
                .execute()
                .data or []
            )
            out: Dict[str, int] = {}
            for r in rows:
                url = r.get("url")
                if url and url not in out:
                    try:
                        out[url] = int(r.get("position") or 0)
                    except (TypeError, ValueError):
                        continue
            return out
        except Exception as e:
            logger.warning(f"[SerpVolatility] prior snapshot lookup failed for '{keyword}': {e}")
            return {}

    @staticmethod
    def _position_shift(previous: Dict[str, int], organic: List[Dict[str, Any]]) -> Optional[float]:
        """Mean absolute position change as a percentage.

        Returns None when there is nothing to compare against (first run, or no
        prior snapshot), so the caller can skip rather than invent a number.
        """
        if not previous or not organic:
            return None
        deltas = []
        for item in organic:
            url = item.get("link") or item.get("url")
            if not url or url not in previous:
                continue
            try:
                new_pos = int(item.get("position") or 0)
            except (TypeError, ValueError):
                continue
            old_pos = previous[url]
            if new_pos > 0 and old_pos > 0:
                deltas.append(abs(new_pos - old_pos))
        if not deltas:
            return None
        return round((sum(deltas) / len(deltas)) / 10.0 * 100.0, 1)

    async def check_serp_volatility(self) -> Dict[str, Any]:
        start_t = time.time()
        logger.info("[SerpVolatility] Running 6-hour SERP volatility check across tracked keywords...")
        
        supabase = get_supabase()
        keywords = []
        try:
            kw_rows = supabase.table("keywords").select("keyword").eq("website_id", self.website_id).limit(5).execute().data or []
            keywords = [k["keyword"] for k in kw_rows if k.get("keyword")]
            if not keywords:
                site_row = supabase.table("websites").select("niche").eq("id", self.website_id).single().execute().data
                if site_row and site_row.get("niche"):
                    keywords = [site_row["niche"]]
        except Exception:
            pass

        if not keywords:
            keywords = ["search engine optimization", "AI SEO strategy"]

        volatility_scores = []
        snapshots_recorded = 0

        for kw in keywords:
            try:
                res = await serper_service.search(query=kw, num=10, auto_fallback=True)
                organic = res.get("organic", [])

                # A degraded Serper response must never contribute a score.
                if res.get("source") == "unavailable" or not organic:
                    logger.warning(
                        f"[SerpVolatility] No live SERP data for '{kw}' "
                        f"({res.get('error', 'empty organic')}); excluding from index."
                    )
                    continue

                previous = self._prior_positions(kw)

                for item in organic:
                    snap = {
                        "website_id": self.website_id,
                        "keyword": kw,
                        "position": item.get("position", 1),
                        "url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "date_captured": datetime.utcnow().isoformat()
                    }
                    try:
                        supabase.table("serp_snapshots").insert(snap).execute()
                        snapshots_recorded += 1
                    except Exception:
                        pass

                # Compute the real position shift against the previous snapshot.
                # This used to be `vol_score = 22.5` with a comment claiming it was
                # a live calculation, and it ran even when organic was empty — so a
                # total Serper outage was reported as a measured "22.5% stable SERP".
                vol_score = self._position_shift(previous, organic)
                if vol_score is None:
                    logger.info(
                        f"[SerpVolatility] No prior snapshot for '{kw}'; "
                        f"recording baseline instead of inventing a score."
                    )
                    continue
                volatility_scores.append(vol_score)
            except Exception as e:
                logger.warning(f"[SerpVolatility] Keyword '{kw}' check note: {e}")

        if not volatility_scores:
            # Never fabricate an index. routers/serp.py surfaces this as a 503.
            return {
                "success": False,
                "error": "No live SERP data available — cannot compute volatility "
                         "(Serper unavailable or no prior snapshot to compare against).",
                "snapshots_recorded": snapshots_recorded,
                "niche_volatility_index": None,
                "defensive_posture_active": False,
            }

        avg_niche_volatility = round(sum(volatility_scores) / len(volatility_scores), 1)
        defensive_posture_triggered = avg_niche_volatility > 35.0

        if defensive_posture_triggered:
            logger.warning(f"[SerpVolatility] Niche Volatility Index ({avg_niche_volatility}%) exceeded 35% threshold! Triggering Defensive Posture Protocol...")
            
            # 1. Pause new content in autonomous_settings
            try:
                supabase.table("autonomous_settings").update({"content_pause_until": (datetime.utcnow() + timedelta(hours=48)).isoformat()}).eq("website_id", self.website_id).execute()
            except Exception:
                pass

            # 2. Push critical alert to the dashboard alert feed
            try:
                supabase.table("realtime_alerts").insert({
                    "website_id": self.website_id,
                    "alert_type": "algorithm_update_volatility",
                    "severity": "critical",
                    "title": f"Algorithm Update Detected (Niche Volatility: {avg_niche_volatility}%)",
                    "description": "Niche Volatility Index exceeded 35%. Activated 48h Defensive Posture Protocol to protect rankings.",
                    "is_read": False,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            except Exception:
                pass

        duration = time.time() - start_t
        return {
            "success": True,
            "niche_volatility_index": avg_niche_volatility,
            "defensive_posture_active": defensive_posture_triggered,
            "snapshots_recorded": snapshots_recorded,
            "duration_sec": duration
        }
