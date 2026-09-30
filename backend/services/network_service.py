"""Network Service for Multi-Site Intelligence.
Aggregates health, indexation, clicks, and issue telemetry across all registered sites in the network.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from backend.services.local_store import (
        list_local_websites,
        list_local_audits,
        list_local_indexation_checks,
        list_local_keyword_research,
    )
except ImportError:
    from services.local_store import (
        list_local_websites,
        list_local_audits,
        list_local_indexation_checks,
        list_local_keyword_research,
    )

logger = logging.getLogger("backend.services.network_service")


def _gsc_credentials_configured() -> bool:
    try:
        try:
            from backend.services.google_credentials import has_service_account_credentials
        except ImportError:
            from services.google_credentials import has_service_account_credentials
        return has_service_account_credentials(
            json_env_keys=["GSC_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_JSON"],
            path_env_keys=["GSC_CREDENTIALS_PATH", "GSC_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS"],
        )
    except Exception:
        return False


def _fetch_site_search_totals(site_id: str) -> Optional[Dict[str, int]]:
    """Sum real GSC-synced rows from `analytics_data` for one site.

    Returns None when the table cannot be read, so a site with no synced data is
    distinguishable from "measured zero".
    """
    try:
        try:
            from backend.database import get_supabase
        except (ImportError, ValueError):
            from database import get_supabase
        supabase = get_supabase()
        rows = (
            supabase.table("analytics_data")
            .select("clicks, impressions")
            .eq("website_id", site_id)
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        return {
            "clicks": sum(int(float(r.get("clicks", 0) or 0)) for r in rows),
            "impressions": sum(int(float(r.get("impressions", 0) or 0)) for r in rows),
        }
    except Exception as e:
        logger.debug(f"[network] analytics_data note for {site_id}: {e}")
        return None


def get_network_overview(account_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve high-density network overview across all connected sites."""
    sites = list_local_websites(account_id)
    site_rows = []

    total_clicks = 0
    total_impressions = 0
    health_scores = []
    total_critical = 0
    total_warning = 0

    for site in sites:
        site_id = site.get("id")
        domain = site.get("domain", "unknown-domain.com")
        cms = site.get("cms_type") or site.get("platform") or "WordPress"
        status = site.get("status", "ACTIVE")

        # 1. Health Score calculation from authentic audits
        audits = list_local_audits(site_id, limit=3)
        has_audit = False
        health = 0
        trend = "N/A"
        last_audit = ""

        if audits:
            primary_audit = audits[0]
            score_val = primary_audit.get("health_score") if primary_audit.get("health_score") is not None else primary_audit.get("score")
            if score_val is not None:
                try:
                    health = int(float(score_val))
                    has_audit = True
                    health_scores.append(health)
                except (ValueError, TypeError):
                    health = 0
            
            last_audit = primary_audit.get("created_at") or primary_audit.get("last_run") or ""
            
            # Trend calculation between current and previous audit if available
            if len(audits) > 1 and has_audit:
                prev_score = audits[1].get("health_score") if audits[1].get("health_score") is not None else audits[1].get("score")
                if prev_score is not None:
                    try:
                        diff = health - int(float(prev_score))
                        trend = f"{diff:+d} pts" if diff != 0 else "+0 pts"
                    except (ValueError, TypeError):
                        trend = "Baseline"
                else:
                    trend = "Baseline"
            elif has_audit:
                trend = "Baseline"

        if not has_audit:
            status = "PENDING_AUDIT"
            last_audit = site.get("updated_at") or site.get("created_at") or ""

        # 2. Indexation stats from real checks or crawl telemetry
        checks = list_local_indexation_checks(site_id, limit=1)
        if checks:
            last_check = checks[0]
            try:
                indexed = int(float(last_check.get("indexed_pages", 0) or 0))
            except (ValueError, TypeError):
                indexed = 0
            try:
                total_pages = int(float(last_check.get("total_pages", 0) or 0))
            except (ValueError, TypeError):
                total_pages = 0
        elif has_audit and audits and audits[0].get("crawled_urls"):
            crawled = audits[0].get("crawled_urls", [])
            total_pages = len(crawled)
            indexed = len([u for u in crawled if u.get("status") == 200 or u.get("status_code") == 200])
        else:
            indexed = 0
            total_pages = 0

        indexation_rate = round((indexed / max(total_pages, 1)) * 100, 1) if total_pages > 0 else 0.0

        # 3. 28-day Clicks & Impressions. Prefer real GSC-synced rows in
        # `analytics_data`; fall back to local keyword research summaries.
        gsc_totals = _fetch_site_search_totals(site_id)
        if gsc_totals is not None:
            clicks = gsc_totals["clicks"]
            impressions = gsc_totals["impressions"]
            clicks_source = "gsc"
        else:
            kw_records = list_local_keyword_research(site_id, limit=5)
            if kw_records and isinstance(kw_records[0].get("summary"), dict):
                summary = kw_records[0].get("summary", {})
                try:
                    clicks = int(float(summary.get("total_clicks", 0) or 0))
                except (ValueError, TypeError):
                    clicks = 0
                try:
                    impressions = int(float(summary.get("total_impressions", 0) or 0))
                except (ValueError, TypeError):
                    impressions = 0
                clicks_source = "keyword_research"
            else:
                clicks = 0
                impressions = 0
                clicks_source = "unavailable"

        total_clicks += clicks
        total_impressions += impressions

        # 4. Open Issues Breakdown from actual audit issues
        crit = 0
        warn = 0
        info = 0
        if has_audit and audits:
            for iss in audits[0].get("issues", []) or []:
                sev = str(iss.get("severity", "")).lower()
                if sev in ("critical", "high", "error"):
                    crit += 1
                elif sev in ("warning", "warn", "medium"):
                    warn += 1
                else:
                    info += 1

        total_critical += crit
        total_warning += warn
        site_name = site.get("name") or site.get("site_name") or domain.split(".")[0].capitalize()

        site_rows.append({
            "id": site_id,
            "domain": domain,
            "site_name": site_name,
            "name": site_name,
            "cms_type": cms,
            "status": status,
            "health_score": health,
            "indexation_rate": indexation_rate,
            "indexed_pages": indexed,
            "submitted_pages": total_pages,
            "clicks_28d": clicks,
            "impressions_28d": impressions,
            "clicks_source": clicks_source,
            "open_issues_count": crit + warn + info,
            "critical_issues": crit,
            "warning_issues": warn,
            "info_issues": info,
            "last_audit_date": str(last_audit),
            "last_audit_at": str(last_audit),
            "trend": trend,
            "indexation": {
                "indexed_pages": indexed,
                "total_pages": total_pages,
                "indexation_rate": indexation_rate,
            },
            "performance_28d": {
                "clicks": clicks,
                "impressions": impressions,
                "source": clicks_source,
                "measured": clicks_source == "gsc",
                "ctr": round((clicks / max(impressions, 1)) * 100, 2) if impressions > 0 else 0.0,
            },
            "open_issues": {
                "critical": crit,
                "warning": warn,
                "info": info,
                "total": crit + warn + info,
            },
        })

    # Sort by health ascending (need attention first) or clicks descending
    site_rows.sort(key=lambda s: (s["open_issues"]["critical"], -s["performance_28d"]["clicks"]), reverse=True)

    audited_sites = [s for s in site_rows if s["health_score"] > 0]
    avg_health = round(sum(s["health_score"] for s in audited_sites) / max(len(audited_sites), 1), 1) if audited_sites else 0.0

    indexed_sites = [s for s in site_rows if s["submitted_pages"] > 0]
    avg_indexation = round(sum(s["indexation_rate"] for s in indexed_sites) / max(len(indexed_sites), 1), 1) if indexed_sites else 0.0

    total_issues = total_critical + total_warning
    gsc_configured = _gsc_credentials_configured()
    sites_with_gsc_data = len([s for s in site_rows if s.get("clicks_source") == "gsc"])

    if not gsc_configured:
        data_note = "Connect Google Search Console in Connectors to populate real clicks and impressions."
    elif sites_with_gsc_data == 0:
        data_note = "GSC is configured but no site has synced search data yet. Run a GSC sync in Connectors."
    else:
        data_note = f"Search performance sourced from GSC for {sites_with_gsc_data} of {len(site_rows)} site(s)."

    return {
        "success": True,
        "total_sites": len(site_rows),
        "network_health_avg": avg_health,
        "network_indexation_avg": avg_indexation,
        "network_clicks_28d": total_clicks,
        "total_open_issues": total_issues,
        "gsc_configured": gsc_configured,
        "data_note": data_note,
        "summary": {
            "total_sites": len(site_rows),
            "avg_health_score": avg_health,
            "total_clicks_28d": total_clicks,
            "total_impressions_28d": total_impressions,
            "critical_issues_total": total_critical,
            "warning_issues_total": total_warning,
            "healthy_sites_count": len([s for s in site_rows if s["health_score"] >= 85]),
            "needs_attention_count": len([s for s in site_rows if s["health_score"] < 75]),
            "sites_with_search_data": sites_with_gsc_data,
            "gsc_configured": gsc_configured,
        },
        "sites": site_rows,
        "generated_at": datetime.utcnow().isoformat(),
    }
