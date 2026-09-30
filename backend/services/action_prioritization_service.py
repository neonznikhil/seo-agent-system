"""Action Prioritization Service.
Replaces manual, unprioritized workflow buttons with an intelligent, impact-ranked
Top 10 Action List sorted strictly by estimated monthly traffic impact (+X clicks/mo).
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib

try:
    from backend.services.local_store import (
        get_local_website,
        list_local_audits,
        list_local_indexation_checks,
        list_local_keyword_research,
        list_local_keywords,
        save_local_guardrail_change,
    )
except ImportError:
    from services.local_store import (
        get_local_website,
        list_local_audits,
        list_local_indexation_checks,
        list_local_keyword_research,
        list_local_keywords,
        save_local_guardrail_change,
    )

logger = logging.getLogger("backend.services.action_prioritization_service")

# Fields the Preview Diff modal renders. The action builders below only author
# `before`/`after`, so they are derived centrally in `_enrich_preview_diff`
# rather than repeated in every literal.
_PREVIEW_RISK_LEVELS = {
    "APPLY_TITLE_TAG": ("LOW", "Modifies the page <title>, the primary CTR signal in search results."),
    "APPLY_META_DESCRIPTION": ("LOW", "Modifies the meta description; affects CTR, not ranking directly."),
    "APPLY_H1_TAG": ("LOW", "Adds a primary <h1>; affects on-page relevance and accessibility."),
    "APPLY_CANONICAL": ("MEDIUM", "Changes canonicalisation; a wrong target can de-index the page."),
    "RESOLVE_BROKEN_URL": ("MEDIUM", "Adds a redirect; a wrong target can create a redirect loop."),
    "REPAIR_ROBOTS_TXT": ("HIGH", "Edits robots.txt; a mistake can block crawlers site-wide."),
    "SUBMIT_XML_SITEMAP": ("LOW", "Registers a sitemap; no change to existing page content."),
    "APPLY_SECURITY_HEADERS": ("MEDIUM", "Adds HTTP security headers at the server/CDN layer."),
    "APPLY_TITLE_CTR_FIX": ("LOW", "Rewrites the <title> for CTR; no structural change."),
    "RUN_TECH_AUDIT": ("LOW", "Read-only crawl; makes no change to the live site."),
    "CONNECT_GSC": ("LOW", "Read-only Search Console access; no change to the live site."),
    "VERIFY_WP_CONNECTION": ("LOW", "Authentication check only; no change to the live site."),
}

# Actions that only read from the live site. They are executed for real (a crawl
# or an API probe), but there is nothing to write back, so they must not be
# reported as a CMS content update.
_READ_ONLY_ACTION_TYPES = {"RUN_TECH_AUDIT", "CONNECT_GSC", "VERIFY_WP_CONNECTION"}


def _enrich_preview_diff(action: Dict[str, Any]) -> Dict[str, Any]:
    """Fill the Preview Diff fields the UI renders but the builders omit.

    Without this the modal showed a blank "Impact Summary", "Risk Level: UNKNOWN"
    and an always-"PASSED" YMYL badge that never actually scanned anything.
    """
    try:
        from backend.services.change_guardrail_service import check_ymyl_risk
    except ImportError:
        from services.change_guardrail_service import check_ymyl_risk

    diff = dict(action.get("preview_diff") or {})
    before = diff.get("before") or ""
    after = diff.get("after") or ""

    ymyl = check_ymyl_risk(before, after)
    default_risk, default_summary = _PREVIEW_RISK_LEVELS.get(
        action.get("action_type", ""), ("MEDIUM", "Automated change applied under guardrail review.")
    )

    diff["before"] = before
    diff["after"] = after
    diff["summary"] = diff.get("summary") or default_summary
    diff["risk_level"] = ymyl["risk_level"] if ymyl["flagged_terms"] else default_risk
    diff["ymyl_compliant"] = ymyl["is_safe"]
    diff["flagged_terms"] = ymyl["flagged_terms"]
    diff["compliance_message"] = ymyl["compliance_message"]

    enriched = dict(action)
    enriched["preview_diff"] = diff
    return enriched


def _get_operational_onboarding_actions(website_id: str, domain: str) -> List[Dict[str, Any]]:
    """Concrete, high-leverage onboarding actions required to establish baseline telemetry."""
    site_prefix = website_id[:8] if website_id else "site"
    return [
        {
            "id": f"act-setup-crawl-{site_prefix}",
            "title": f"Run Initial Technical SEO Crawl on {domain}",
            "category": "TECHNICAL_CRAWL",
            "impact_clicks_per_month": None,
            "estimated_monthly_value": None,
            "effort": "LOW",
            "target_url": f"https://{domain}/",
            "target_query": f"{domain} site health",
            "rationale": "No baseline crawl has been completed for this domain yet. Executing a technical audit will identify broken links, missing meta tags, schema defects, and indexation barriers.",
            "action_type": "RUN_TECH_AUDIT",
            "preview_diff": {
                "before": "Status: Not crawled. Baseline site architecture, metadata, and indexability unknown.",
                "after": "Action: Run automated crawler to establish baseline health score and pinpoint critical SEO fixes.",
                "summary": "Execute initial technical crawl to discover baseline errors",
                "risk_level": "LOW",
                "ymyl_compliant": True,
            },
            "rank": 1,
        },
        {
            "id": f"act-setup-gsc-{site_prefix}",
            "title": f"Connect Google Search Console API for {domain}",
            "category": "SEARCH_CONSOLE",
            "impact_clicks_per_month": None,
            "estimated_monthly_value": None,
            "effort": "LOW",
            "target_url": f"https://{domain}/",
            "target_query": f"{domain} search performance",
            "rationale": "GSC API integration allows real-time monitoring of query impressions, clicks, average position, and indexation coverage directly from Google.",
            "action_type": "CONNECT_GSC",
            "preview_diff": {
                "before": "Google Search Console: Disconnected. Keyword performance and organic impression data unavailable.",
                "after": "Google Search Console: Connected. Automatic synchronization of daily queries, clicks, and CTR.",
                "summary": "Authenticate Google Search Console API integration",
                "risk_level": "LOW",
                "ymyl_compliant": True,
            },
            "rank": 2,
        },
        {
            "id": f"act-setup-wp-{site_prefix}",
            "title": f"Verify WordPress REST API Connection for {domain}",
            "category": "CMS_INTEGRATION",
            "impact_clicks_per_month": None,
            "estimated_monthly_value": None,
            "effort": "LOW",
            "target_url": f"https://{domain}/wp-json/wp/v2",
            "target_query": f"{domain} automated publishing",
            "rationale": "Validating WordPress Application Password authentication allows 1-click publishing of title tag, meta description, and schema fixes with instantaneous rollback protection.",
            "action_type": "VERIFY_WP_CONNECTION",
            "preview_diff": {
                "before": "CMS REST API: Inactive. Requires manual copy-pasting of code fixes into WordPress admin.",
                "after": "CMS REST API: Authenticated. Enables automated 1-click deployment with guardrail verification.",
                "summary": "Validate WordPress CMS REST API application password",
                "risk_level": "LOW",
                "ymyl_compliant": True,
            },
            "rank": 3,
        },
    ]


def _generate_curated_actions_for_site(website: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Synthesizes high-leverage prioritized actions tailored to the site domain and SEO state.
    
    If un-audited, surfaces concrete operational onboarding actions.
    If audited, dynamically constructs actions directly from real crawl issues and keyword research.
    """
    domain = website.get("domain", "example.com")
    site_id = website.get("id") or website.get("website_id", "default")
    cms = website.get("cms_type") or "WordPress"

    # Query real audit history and keyword research for this site
    audits = list_local_audits(site_id, limit=3)
    kw_research = list_local_keyword_research(site_id, limit=20)
    keywords = list_local_keywords(site_id, limit=50)

    latest_audit = audits[0] if audits else {}
    audit_issues = latest_audit.get("issues", []) if isinstance(latest_audit, dict) else []

    # If un-audited and no keyword research, return concrete operational onboarding actions
    if not audits or (not audit_issues and not kw_research and not keywords):
        return _get_operational_onboarding_actions(site_id, domain)

    candidates: List[Dict[str, Any]] = []
    seen_keys = set()

    # 1. Parse authentic audit issues into concrete actions
    for idx, issue in enumerate(audit_issues):
        issue_type = str(issue.get("type", "")).lower()
        desc = str(issue.get("description") or issue.get("issue") or issue.get("title") or issue.get("message") or "")
        desc_lower = desc.lower()
        fix_sugg = str(issue.get("fix_suggestion") or issue.get("recommendation") or "")

        # Extract target url from issue
        target_url = issue.get("url") or (issue.get("affected_urls")[0] if issue.get("affected_urls") else None)
        if not target_url and " on " in desc:
            target_url = desc.split(" on ")[-1].strip()
        elif not target_url and "http" in desc:
            import re
            match = re.search(r'https?://[^\s,\'\"\)]+', desc)
            if match:
                target_url = match.group(0)
        if not target_url:
            target_url = f"https://{domain}/"

        action_dict: Optional[Dict[str, Any]] = None

        if "title" in issue_type or "title" in desc_lower:
            action_key = f"title-{target_url}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-title-{hashlib.md5(f'{site_id}-{target_url}'.encode()).hexdigest()[:8]}",
                    "title": f"Implement Missing Title Tag on {target_url}",
                    "category": "CTR_OPTIMIZATION",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": target_url,
                    "target_query": f"{domain} services",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "APPLY_TITLE_TAG",
                    "preview_diff": {
                        "before": f"<!-- Missing <title> tag on {target_url} -->",
                        "after": f"<title>{domain.title()} | Expert Solutions & Services (2026)</title>",
                    },
                }

        elif "meta description" in issue_type or "meta description" in desc_lower or "meta desc" in desc_lower:
            action_key = f"meta-{target_url}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-meta-{hashlib.md5(f'{site_id}-{target_url}'.encode()).hexdigest()[:8]}",
                    "title": f"Add High-CTR Meta Description to {target_url}",
                    "category": "CTR_OPTIMIZATION",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": target_url,
                    "target_query": f"{domain} guide",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "APPLY_META_DESCRIPTION",
                    "preview_diff": {
                        "before": f"<!-- Missing meta description on {target_url} -->",
                        "after": f"<meta name=\"description\" content=\"Discover verified {domain} services. Transparent pricing, expert guidance, and proven results for your business.\">",
                    },
                }

        elif "h1" in issue_type or "h1" in desc_lower or "heading" in issue_type:
            action_key = f"h1-{target_url}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-h1-{hashlib.md5(f'{site_id}-{target_url}'.encode()).hexdigest()[:8]}",
                    "title": f"Define Primary <h1> Heading for {target_url}",
                    "category": "TECHNICAL_FIX",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": target_url,
                    "target_query": f"{domain} primary offering",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "APPLY_H1_TAG",
                    "preview_diff": {
                        "before": f"<!-- Missing primary <h1> tag on {target_url} -->",
                        "after": f"<h1>{domain.title()} - Comprehensive Solutions & Overview</h1>",
                    },
                }

        elif "canonical" in issue_type or "canonical" in desc_lower:
            action_key = f"canon-{target_url}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-canon-{hashlib.md5(f'{site_id}-{target_url}'.encode()).hexdigest()[:8]}",
                    "title": f"Apply Canonical Tag on {target_url}",
                    "category": "TECHNICAL_FIX",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": target_url,
                    "target_query": f"{domain} canonical URL",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "APPLY_CANONICAL",
                    "preview_diff": {
                        "before": f"<!-- Missing canonical link on {target_url} -->",
                        "after": f"<link rel=\"canonical\" href=\"{target_url}\" />",
                    },
                }

        elif "broken" in issue_type or "broken" in desc_lower or "404" in desc_lower or "status" in issue_type:
            action_key = f"broken-{target_url}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-broken-{hashlib.md5(f'{site_id}-{target_url}'.encode()).hexdigest()[:8]}",
                    "title": f"Resolve Broken Internal Route on {target_url}",
                    "category": "TECHNICAL_FIX",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": target_url,
                    "target_query": f"{domain} internal link",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "RESOLVE_BROKEN_URL",
                    "preview_diff": {
                        "before": f"{target_url} -> HTTP 404/500 (Broken internal route)",
                        "after": f"Rewrite / Redirect {target_url} -> HTTP 301 Permanent Redirect to valid target",
                    },
                }

        elif "robots" in issue_type or "robots" in desc_lower:
            action_key = f"robots-{domain}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-robots-{hashlib.md5(f'{site_id}-robots'.encode()).hexdigest()[:8]}",
                    "title": f"Deploy Valid robots.txt Directives for {domain}",
                    "category": "INDEXATION_REPAIR",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": f"https://{domain}/robots.txt",
                    "target_query": f"{domain} crawl budget",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "REPAIR_ROBOTS_TXT",
                    "preview_diff": {
                        "before": "robots.txt is missing or unreachable.",
                        "after": f"User-agent: *\nAllow: /\nSitemap: https://{domain}/sitemap.xml",
                    },
                }

        elif "sitemap" in issue_type or "sitemap" in desc_lower:
            action_key = f"sitemap-{domain}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-sitemap-{hashlib.md5(f'{site_id}-sitemap'.encode()).hexdigest()[:8]}",
                    "title": f"Submit and Verify XML Sitemap for {domain}",
                    "category": "INDEXATION_REPAIR",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": f"https://{domain}/sitemap.xml",
                    "target_query": f"{domain} sitemap",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "SUBMIT_XML_SITEMAP",
                    "preview_diff": {
                        "before": "<!-- XML sitemap not found at standard root endpoints -->",
                        "after": f"<!-- Generated XML sitemap with all active canonical URLs -> https://{domain}/sitemap.xml -->",
                    },
                }

        elif "security" in issue_type or "ssl" in desc_lower or "hsts" in desc_lower:
            action_key = f"sec-{domain}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                action_dict = {
                    "id": f"act-audit-sec-{hashlib.md5(f'{site_id}-sec'.encode()).hexdigest()[:8]}",
                    "title": f"Harden HTTPS & Security Headers on {domain}",
                    "category": "SECURITY_FIX",
                    "impact_clicks_per_month": None,
                    "estimated_monthly_value": None,
                    "effort": "LOW",
                    "target_url": f"https://{domain}/",
                    "target_query": f"{domain} security",
                    "rationale": f"{desc} {fix_sugg}".strip(),
                    "action_type": "APPLY_SECURITY_HEADERS",
                    "preview_diff": {
                        "before": "Strict-Transport-Security: (missing)",
                        "after": "Strict-Transport-Security: max-age=31536000; includeSubDomains",
                    },
                }

        if action_dict:
            candidates.append(action_dict)

    # 2. Parse striking-distance keywords (positions 4 to 20)
    for kw in keywords:
        pos = kw.get("position") or kw.get("rank") or 0
        query = kw.get("keyword") or kw.get("query")
        if 4 <= pos <= 20 and query:
            action_key = f"kw-{query}"
            if action_key not in seen_keys:
                seen_keys.add(action_key)
                vol = kw.get("search_volume") or kw.get("volume")
                # Only project clicks when a real search volume was measured.
                # Without volume there is no defensible traffic estimate.
                if vol:
                    potential_clicks = max(120, int(vol * 0.18))
                    estimated_value = round(potential_clicks * 3.5, 2)
                    volume_note = f"with {vol} monthly searches"
                else:
                    potential_clicks = None
                    estimated_value = None
                    volume_note = "search volume not yet measured"
                candidates.append({
                    "id": f"act-kw-{hashlib.md5(f'{site_id}-{query}'.encode()).hexdigest()[:8]}",
                    "title": f"Capture Striking-Distance Rank for '{query}' (Position #{pos})",
                    "category": "STRIKING_DISTANCE",
                    "impact_clicks_per_month": potential_clicks,
                    "estimated_monthly_value": estimated_value,
                    "effort": "LOW",
                    "target_url": kw.get("url") or f"https://{domain}/",
                    "target_query": query,
                    "rationale": f"Currently ranking at position #{pos} {volume_note}. Title hook optimization and schema enrichment can push this onto page 1.",
                    "action_type": "APPLY_TITLE_CTR_FIX",
                    "preview_diff": {
                        "before": f"<title>{domain.title()} - {query.title()}</title>",
                        "after": f"<title>{query.title()} (2026 Guide) | {domain.title()}</title>",
                    },
                })

    # If all issues/keywords produced fewer than 1, add baseline crawl/refresh action
    if not candidates:
        return _get_operational_onboarding_actions(site_id, domain)

    # Sort by measured monthly traffic impact descending; actions with no
    # measured impact rank after those that have one.
    candidates.sort(key=lambda a: a.get("impact_clicks_per_month") or 0, reverse=True)
    for idx, act in enumerate(candidates, 1):
        act["rank"] = idx
        if "preview_diff" in act:
            act["preview_diff"].setdefault("risk_level", "LOW")
            act["preview_diff"].setdefault("ymyl_compliant", True)
            if "summary" not in act["preview_diff"]:
                act["preview_diff"]["summary"] = act.get("title", "Action Diff Preview")

    return candidates


def get_top_10_actions(website_id: str) -> Dict[str, Any]:
    """Retrieve the ranked Top 10 actions for the specified website."""
    site = get_local_website(website_id)
    if not site:
        site = {"id": website_id, "domain": "example.com", "cms_type": "WordPress"}

    actions = [_enrich_preview_diff(a) for a in _generate_curated_actions_for_site(site)]
    measured = [a for a in actions if a.get("impact_clicks_per_month") is not None]
    total_potential_clicks = sum(a["impact_clicks_per_month"] for a in measured) if measured else None
    total_potential_value = sum(a["estimated_monthly_value"] or 0 for a in measured) if measured else None

    return {
        "website_id": website_id,
        "domain": site.get("domain", "example.com"),
        "total_actions": len(actions),
        "total_potential_clicks_per_month": total_potential_clicks,
        "total_potential_value_per_month": total_potential_value,
        "impact_measured": bool(measured),
        "actions": actions[:10],
        "generated_at": datetime.utcnow().isoformat(),
    }


def execute_prioritized_action(website_id: str, action_id: str, author: str = "AI Agent") -> Dict[str, Any]:
    """Execute an action with automatic Guardrail change logging, WordPress sync check, and preview snapshotting."""
    actions_res = get_top_10_actions(website_id)
    matching_action = next((a for a in actions_res["actions"] if a["id"] == action_id), None)
    if not matching_action:
        return {"status": "error", "message": f"Action {action_id} not found."}

    action_type = matching_action.get("action_type", "")

    # Check for live WordPress credentials
    has_wp_creds = False
    try:
        try:
            from backend.routers.websites import get_decrypted_wordpress_credentials
        except ImportError:
            from routers.websites import get_decrypted_wordpress_credentials
        base_url, user, password = get_decrypted_wordpress_credentials(website_id)
        has_wp_creds = bool(base_url and user and password)
    except Exception as e:
        logger.debug(f"[action_prioritization] WP cred lookup note: {e}")

    # Be explicit about what actually happened. Having WordPress credentials is
    # not the same as having written to WordPress: nothing in this function
    # pushes the change to the CMS, so it must never report a live content
    # update. The change is recorded locally and staged for application.
    if action_type in _READ_ONLY_ACTION_TYPES:
        cms_sync_status = "READ_ONLY_NO_SITE_CHANGE"
        cms_synced = False
    elif has_wp_creds:
        cms_sync_status = "STAGED_FOR_CMS_PUSH"
        cms_synced = False
    else:
        cms_sync_status = "SAVED_LOCALLY_NO_CMS_CONFIGURED"
        cms_synced = False

    # Automatically record to Guardrail change log
    diff = matching_action.get("preview_diff", {})
    change_record = {
        "website_id": website_id,
        "action_id": action_id,
        "title": matching_action["title"],
        "target_url": matching_action["target_url"],
        "category": matching_action["category"],
        "impact_clicks": matching_action["impact_clicks_per_month"],
        "author": author,
        "before_state": diff.get("before", ""),
        "after_state": diff.get("after", ""),
        "status": "APPLIED",
        "cms_sync_status": cms_sync_status,
        "ymyl_flag": "LEGAL/YMYL SENSITIVE" if "law" in matching_action["target_url"] or "health" in matching_action["target_url"] or matching_action["category"] == "CONTENT_REFRESH" else "STANDARD",
    }
    saved_change = save_local_guardrail_change(change_record)

    # Register the fix for 28-day ROI tracking so "prove the work" has data to
    # show. Without this the ROI Proof section stays empty forever because the
    # only other way in is a manual POST to /api/roi-proof/{id}/track.
    roi_fix_id = None
    try:
        try:
            from backend.services.roi_proof_service import track_new_fix
        except ImportError:
            from services.roi_proof_service import track_new_fix
        roi_fix = track_new_fix(
            website_id=website_id,
            target_url=matching_action.get("target_url", ""),
            fix_title=matching_action.get("title", ""),
            category=matching_action.get("category", ""),
            target_keyword=matching_action.get("target_query", ""),
            action_id=action_id,
        )
        roi_fix_id = roi_fix.get("id") if isinstance(roi_fix, dict) else None
    except Exception as e:
        logger.debug(f"[action_prioritization] ROI tracking note: {e}")

    return {
        "status": "success",
        "message": f"Action '{matching_action['title']}' recorded with guardrail protection and queued for 28-day ROI tracking.",
        "action": matching_action,
        "guardrail_change_id": saved_change["id"],
        "roi_fix_id": roi_fix_id,
        "cms_sync_status": cms_sync_status,
        "cms_synced": cms_synced,
        "cms_sync_note": (
            "Read-only action: nothing was written to the live site."
            if action_type in _READ_ONLY_ACTION_TYPES
            else "Change recorded and staged. Push to WordPress from the Guardrails page to apply it live."
            if has_wp_creds
            else "Change recorded locally. Connect WordPress to apply it to the live site."
        ),
    }

