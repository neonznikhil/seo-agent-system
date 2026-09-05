import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("backend.services.ai_visibility_monitor")


async def check_ai_visibility(
    website_id: str,
    website_domain: str,
    target_keywords: list
) -> dict:
    from services.serper_service import serper_search_safe, serper_service
    from database import get_supabase

    results = {
        "website_id": website_id,
        "domain": website_domain,
        "checked_at": datetime.utcnow().isoformat(),
        "keywords_checked": len(target_keywords),
        "ai_overview_appearances": 0,
        "cited_in_ai_results": 0,
        "keyword_results": []
    }

    for keyword in target_keywords[:10]:
        keyword_result = {
            "keyword": keyword,
            "ai_overview_found": False,
            "site_cited_in_ai": False,
            "site_in_organic": False,
            "organic_position": None
        }

        try:
            serp_data = await serper_search_safe(keyword, num_results=10)

            for i, result in enumerate(serp_data or []):
                if website_domain in result.get('link', ''):
                    keyword_result["site_in_organic"] = True
                    keyword_result["organic_position"] = i + 1

            raw_results = await serper_service.search(keyword, num=5)
            if raw_results:
                answer_box = raw_results.get('answerBox', {})
                if answer_box:
                    keyword_result["ai_overview_found"] = True
                    results["ai_overview_appearances"] += 1

                    if website_domain in str(answer_box):
                        keyword_result["site_cited_in_ai"] = True
                        results["cited_in_ai_results"] += 1
        except Exception as e:
            logger.warning(f"[AIVisibility] Check failed for '{keyword}': {e}")

        results["keyword_results"].append(keyword_result)

    try:
        get_supabase().table("ai_visibility").insert({
            "website_id": website_id,
            "domain": website_domain,
            "checked_at": results["checked_at"],
            "keywords_checked": results["keywords_checked"],
            "ai_overview_appearances": results["ai_overview_appearances"],
            "cited_count": results["cited_in_ai_results"],
            "keyword_results": results["keyword_results"]
        }).execute()
    except Exception as e:
        logger.debug(f"[AIVisibility] DB insert note: {e}")

    if results["cited_in_ai_results"] > 0:
        try:
            await create_system_alert(
                website_id=website_id,
                severity="info",
                message=(
                    f"AI Visibility: Your site appeared in "
                    f"{results['cited_in_ai_results']} AI-generated "
                    f"answers today."
                ),
                alert_type="ai_citation"
            )
        except Exception:
            pass

    return results


async def create_system_alert(website_id: str, severity: str, message: str, alert_type: str):
    try:
        from database import get_supabase
        get_supabase().table("realtime_alerts").insert({
            "website_id": website_id,
            "alert_type": alert_type,
            "severity": severity,
            "title": "AI Citation Detected",
            "description": message,
            "is_read": False,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        pass


async def run_ai_visibility_check_all_sites():
    try:
        from database import get_supabase
        from services.website_service import list_active_website_ids
        website_ids = list_active_website_ids()
        for wid in website_ids:
            try:
                site = get_supabase().table("websites").select("domain, target_keywords").eq("id", wid).maybe_single().execute().data
                if not site:
                    continue
                domain = site.get("domain", "")
                keywords = site.get("target_keywords") or []
                if not keywords:
                    blogs = get_supabase().table("content_log").select("target_keyword").eq("website_id", wid).order("created_at", desc=True).limit(10).execute().data or []
                    keywords = [b.get("target_keyword") for b in blogs if b.get("target_keyword")]
                if domain and keywords:
                    await check_ai_visibility(wid, domain, keywords[:10])
            except Exception as e:
                logger.warning(f"[AIVisibility] Site check failed for {wid}: {e}")
    except Exception as e:
        logger.warning(f"[AIVisibility] All-sites check failed: {e}")
