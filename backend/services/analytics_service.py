import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

import httpx

from database import get_supabase

logger = logging.getLogger("backend.services.analytics_service")


class AnalyticsService:
    """Real GA4 + Google Search Console Analytics & Content Gap Engine."""

    @staticmethod
    async def sync_gsc_data(website_id: Optional[str] = None) -> Dict[str, Any]:
        """Pull live keyword rows from GSC API and persist into analytics_data.

        Real rows only. Without GSC credentials returns not_configured with 0.
        Accepts either a service-account file path or the pasted JSON content,
        matching how the Connectors UI saves credentials.
        """
        website_url = None
        supabase = get_supabase()
        try:
            site = supabase.table("websites").select("url, cms_url, wordpress_url, domain").eq("id", website_id).single().execute().data or {}
            website_url = site.get("url") or site.get("cms_url") or site.get("wordpress_url") or site.get("domain")
        except Exception as e:
            logger.warning(f"GSC sync website lookup failed: {e}")

        try:
            from services.gsc_service import GSCService
        except (ImportError, ValueError):
            from backend.services.gsc_service import GSCService

        svc = GSCService(website_url=website_url)
        if not svc.is_connected():
            return {
                "success": False,
                "source": "not_configured",
                "records_synced": 0,
                "message": "GSC credentials not configured — connect via Google OAuth or add service JSON in /connectors",
                "timestamp": datetime.utcnow().isoformat(),
            }

        try:
            perf = await svc.get_keyword_performance()
            keywords = perf.get("keywords", []) if isinstance(perf, dict) else []
        except Exception as e:
            logger.warning(f"GSC API error: {e}")
            return {"success": False, "source": "gsc", "records_synced": 0, "error": str(e)[:200], "timestamp": datetime.utcnow().isoformat()}

        records_saved = 0
        today = datetime.utcnow().date().isoformat()
        for kw in keywords:
            try:
                supabase.table("analytics_data").insert({
                    "website_id": website_id,
                    "keyword": kw.get("keyword"),
                    "clicks": int(kw.get("clicks", 0) or 0),
                    "impressions": int(kw.get("impressions", 0) or 0),
                    "position": float(kw.get("position", 0) or 0),
                    "source": "gsc",
                    "date": today,
                }).execute()
                records_saved += 1
            except Exception as e:
                logger.debug(f"GSC row persist note: {e}")
                continue

        return {
            "success": True,
            "source": "gsc",
            "records_synced": records_saved,
            "message": f"Synced {records_saved} keyword rows from GSC" if records_saved else "GSC returned 0 rows for this property/date range",
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def get_content_gaps(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Identify high-impression, low-CTR queries ranking in positions 5-15 needing new content or refresh.

        Real DB query only — returns [] when no analytics_data.
        """
        supabase = get_supabase()
        try:
            q = supabase.table("analytics_data").select("keyword, clicks, impressions, position, created_at")
            if website_id:
                q = q.eq("website_id", website_id)
            rows = q.gte("position", 5).lte("position", 15).order("impressions", desc=True).limit(20).execute().data or []
            # Filter high-impression low-CTR
            gaps = []
            for r in rows:
                # analytics_data has no ctr column; derive it from real clicks/impressions.
                try:
                    imp = float(r.get("impressions", 0) or 0)
                    ctr_val = (float(r.get("clicks", 0) or 0) / imp * 100) if imp else 0.0
                except Exception:
                    ctr_val = 0
                if (r.get("impressions", 0) or 0) > 1000 and ctr_val < 3.0:
                    gaps.append({
                        "keyword": r.get("keyword"),
                        "impressions": r.get("impressions"),
                        "clicks": r.get("clicks"),
                        "ctr": round(ctr_val, 2),
                        "position": r.get("position"),
                        "opportunity": f"High-impression low-CTR query ranking at position {r.get('position')}",
                        "action": "create_new_article" if float(r.get("position", 0)) > 8 else "refresh_existing",
                    })
            # Fallback to gsc_keywords table if analytics_data empty
            if not gaps:
                try:
                    gq = supabase.table("gsc_keywords").select("keyword, clicks, impressions, ctr, position")
                    if website_id:
                        gq = gq.eq("website_id", website_id)
                    grows = gq.gte("position", 5).lte("position", 15).order("impressions", desc=True).limit(20).execute().data or []
                    for r in grows:
                        try:
                            ctr_val = float(str(r.get("ctr", "0")).replace("%", "")) if isinstance(r.get("ctr"), str) else float(r.get("ctr", 0))
                        except Exception:
                            ctr_val = 0
                        if (r.get("impressions", 0) or 0) > 1000 and ctr_val < 3.0:
                            gaps.append({
                                "keyword": r.get("keyword"),
                                "impressions": r.get("impressions"),
                                "clicks": r.get("clicks"),
                                "ctr": r.get("ctr"),
                                "position": r.get("position"),
                                "opportunity": f"GSC gap at position {r.get('position')}",
                                "action": "create_new_article",
                            })
                except Exception:
                    pass
            return gaps[:10]
        except Exception as e:
            logger.debug(f"get_content_gaps note: {e}")
            return []

    @staticmethod
    async def get_decaying_content(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find blog posts where views dropped > 30% over the last 7 days vs previous 7 days.

        Real DB only — returns [] when no decaying rows (empty state).
        """
        supabase = get_supabase()
        try:
            # First try decay_logs table (real decay detector output)
            try:
                cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
                decay_rows = supabase.table("decay_logs").select("id, blog_id, title, primary_keyword, view_drop_percentage, previous_week_views, current_week_views, reason, recommended_action").gte("created_at", cutoff)
                if website_id:
                    decay_rows = decay_rows.eq("website_id", website_id)
                d_data = decay_rows.order("view_drop_percentage").limit(10).execute().data or []
                if d_data:
                    return [
                        {
                            "blog_id": r.get("blog_id") or r.get("id"),
                            "title": r.get("title"),
                            "primary_keyword": r.get("primary_keyword"),
                            "view_drop_percentage": r.get("view_drop_percentage"),
                            "previous_week_views": r.get("previous_week_views"),
                            "current_week_views": r.get("current_week_views"),
                            "reason": r.get("reason"),
                            "recommended_action": r.get("recommended_action"),
                        }
                        for r in d_data
                    ]
            except Exception:
                pass

            # Fallback: compute from analytics_data vs content_log comparison
            blogs = supabase.table("content_log").select("id, title, keyword, created_at").eq("website_id", website_id).limit(20).execute().data or [] if website_id else []
            if not blogs:
                # No content yet -> empty
                return []

            # If blogs exist but no decay_logs, try analytics_data join logic
            decaying = []
            for b in blogs[:5]:
                try:
                    # Check 7d vs previous 7d views from analytics_data
                    now = datetime.utcnow()
                    week_ago = (now - timedelta(days=7)).isoformat()
                    two_weeks_ago = (now - timedelta(days=14)).isoformat()
                    cur_q = supabase.table("analytics_data").select("views").eq("website_id", website_id).gte("created_at", week_ago).execute().data or []
                    prev_q = supabase.table("analytics_data").select("views").eq("website_id", website_id).gte("created_at", two_weeks_ago).lt("created_at", week_ago).execute().data or []
                    cur_views = sum(r.get("views", 0) for r in cur_q)
                    prev_views = sum(r.get("views", 0) for r in prev_q)
                    if prev_views > 0:
                        drop = ((cur_views - prev_views) / prev_views) * 100
                        if drop < -30:
                            decaying.append({
                                "blog_id": b["id"],
                                "title": b.get("title"),
                                "primary_keyword": b.get("keyword"),
                                "view_drop_percentage": round(drop, 1),
                                "previous_week_views": prev_views,
                                "current_week_views": cur_views,
                                "reason": "Views dropped >30% week-over-week",
                                "recommended_action": "Refresh with updated content",
                            })
                except Exception:
                    continue
            return decaying
        except Exception as e:
            logger.debug(f"get_decaying_content note: {e}")
            return []

    @staticmethod
    async def get_analytics_summary(website_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate high level metrics for the dashboard Analytics tab — real DB only."""
        supabase = get_supabase()
        gaps = await AnalyticsService.get_content_gaps(website_id)
        decaying = await AnalyticsService.get_decaying_content(website_id)

        total_impressions_7d = 0
        total_clicks_7d = 0
        avg_ctr = "0%"
        avg_position = 0.0
        try:
            cutoff_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
            q = supabase.table("analytics_data").select("clicks, impressions, position").gte("created_at", cutoff_7d)
            if website_id:
                q = q.eq("website_id", website_id)
            rows = q.execute().data or []
            if rows:
                total_impressions_7d = sum(r.get("impressions", 0) or 0 for r in rows)
                total_clicks_7d = sum(r.get("clicks", 0) or 0 for r in rows)
                if total_impressions_7d:
                    avg_ctr = f"{round(total_clicks_7d / total_impressions_7d * 100, 2)}%"
                pos_vals = [float(r.get("position", 0)) for r in rows if r.get("position")]
                if pos_vals:
                    avg_position = round(sum(pos_vals)/len(pos_vals), 1)
        except Exception as e:
            logger.debug(f"analytics_summary aggregation note: {e}")

        website_url = None
        if website_id:
            try:
                site = supabase.table("websites").select("url, cms_url, wordpress_url, domain").eq("id", website_id).single().execute().data or {}
                website_url = site.get("url") or site.get("cms_url") or site.get("wordpress_url") or site.get("domain")
            except Exception:
                pass

        gsc_conn = False
        try:
            try:
                from services.gsc_service import GSCService
            except (ImportError, ValueError):
                from backend.services.gsc_service import GSCService
            gsc_svc = GSCService(website_url=website_url)
            gsc_conn = gsc_svc.is_connected()
            if gsc_conn and not rows:
                try:
                    start_7d = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
                    end_today = datetime.utcnow().strftime('%Y-%m-%d')
                    perf = await gsc_svc.get_keyword_performance(start_date=start_7d, end_date=end_today, row_limit=500)
                    if perf and perf.get("total_impressions"):
                        total_impressions_7d = perf.get("total_impressions", 0)
                        total_clicks_7d = perf.get("total_clicks", 0)
                        if total_impressions_7d > 0:
                            avg_ctr = f"{round((total_clicks_7d / total_impressions_7d) * 100, 2)}%"
                        avg_position = round(perf.get("avg_position", 0.0), 1)
                except Exception as ex:
                    logger.debug(f"Live GSC fallback query in summary: {ex}")
        except Exception:
            pass

        ga4_conn = False
        try:
            try:
                from services.ga4_service import ga4_service
            except (ImportError, ValueError):
                from backend.services.ga4_service import ga4_service
            ga4_conn = ga4_service.is_connected()
        except Exception:
            pass

        return {
            "gsc_connected": gsc_conn,
            "ga4_connected": ga4_conn,
            "data_source": "Google Search Console Live" if gsc_conn else "analytics_data",
            "total_impressions_7d": total_impressions_7d,
            "total_clicks_7d": total_clicks_7d,
            "average_ctr": avg_ctr,
            "average_position": avg_position,
            "content_gaps": gaps,
            "decaying_content": decaying,
            "timestamp": datetime.utcnow().isoformat()
        }


analytics_service = AnalyticsService()


async def sync_gsc_data(website_id: Optional[str] = None) -> Dict[str, Any]:
    """Module-level wrapper so callers can `from services.analytics_service import sync_gsc_data`."""
    return await AnalyticsService.sync_gsc_data(website_id=website_id)
