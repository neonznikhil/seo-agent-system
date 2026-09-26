"""Tests for authentic, real-world task execution across Network, Action Prioritization, and Guardrails."""

import os
import inspect
import pytest
from unittest.mock import patch

try:
    from backend.services.network_service import get_network_overview
    from backend.services.action_prioritization_service import (
        get_top_10_actions,
        execute_prioritized_action,
    )
    from backend.services.change_guardrail_service import (
        list_changelog,
        rollback_change,
    )
    from backend.services.local_store import (
        save_local_website,
        save_local_audit,
        save_local_guardrail_change,
        get_local_guardrail_change,
    )
except ImportError:
    from services.network_service import get_network_overview
    from services.action_prioritization_service import (
        get_top_10_actions,
        execute_prioritized_action,
    )
    from services.change_guardrail_service import (
        list_changelog,
        rollback_change,
    )
    from services.local_store import (
        save_local_website,
        save_local_audit,
        save_local_guardrail_change,
        get_local_guardrail_change,
    )


def test_network_service_zero_character_hash():
    """Verify that network_service has zero character-code hash formulas."""
    import backend.services.network_service as ns
    source_code = inspect.getsource(ns)
    assert "ord(" not in source_code, "network_service.py must not contain any ord() character hashing formulas"


def test_unaudited_site_reports_pending_audit_and_zero_health():
    """Verify un-audited sites report health_score=0 and status=PENDING_AUDIT."""
    site_id = "test-unaudited-site-999"
    save_local_website({
        "id": site_id,
        "domain": "unaudited-site.com",
        "name": "Unaudited Site",
    })

    overview = get_network_overview()
    site_row = next((s for s in overview["sites"] if s["id"] == site_id), None)
    assert site_row is not None, f"Site {site_id} should be present in network overview"
    assert site_row["health_score"] == 0, "Un-audited site must report 0 health score"
    assert site_row["status"] == "PENDING_AUDIT", "Un-audited site must have status PENDING_AUDIT"
    assert site_row["open_issues_count"] == 0
    assert site_row["indexation_rate"] == 0.0
    assert site_row["trend"] == "N/A"


def test_audited_site_reports_genuine_audit_metrics():
    """Verify audited site reports genuine scores and issue breakdowns."""
    site_id = "test-audited-site-101"
    save_local_website({
        "id": site_id,
        "domain": "audited-site.com",
        "name": "Audited Site",
    })
    save_local_audit({
        "website_id": site_id,
        "score": 78,
        "issues": [
            {"severity": "critical", "issue": "Missing Title Tag on /services"},
            {"severity": "critical", "issue": "Broken 404 URL on /legacy"},
            {"severity": "warning", "issue": "Missing Meta Description on /contact"},
            {"severity": "info", "issue": "Missing H1 on /about"},
        ],
    })

    overview = get_network_overview()
    site_row = next((s for s in overview["sites"] if s["id"] == site_id), None)
    assert site_row is not None, f"Site {site_id} should be present in network overview"
    assert site_row["health_score"] == 78, "Health score must match the genuine audit score"
    assert site_row["open_issues_count"] == 4
    assert site_row["critical_issues"] == 2
    assert site_row["warning_issues"] == 1
    assert site_row["info_issues"] == 1


def test_unaudited_site_returns_concrete_onboarding_actions():
    """Verify un-audited sites return the 3 concrete operational onboarding actions."""
    site_id = "test-fresh-onboarding-site"
    save_local_website({
        "id": site_id,
        "domain": "freshsite.com",
        "name": "Fresh Site",
    })

    res = get_top_10_actions(site_id)
    actions = res["actions"]
    assert len(actions) == 3, "Un-audited site must return exactly 3 onboarding actions"
    action_types = [a["action_type"] for a in actions]
    assert "RUN_TECH_AUDIT" in action_types
    assert "CONNECT_GSC" in action_types
    assert "VERIFY_WP_CONNECTION" in action_types

    # Ensure actions have clear titles and target URLs
    titles = [a["title"] for a in actions]
    assert any("Run Initial Technical SEO Crawl" in t for t in titles)
    assert any("Connect Google Search Console API" in t for t in titles)
    assert any("Verify WordPress REST API Connection" in t for t in titles)


def test_audited_site_generates_dynamic_actions_from_real_issues():
    """Verify audited sites generate real dynamic actions with exact URLs and unified diffs."""
    site_id = "test-dynamic-actions-site"
    save_local_website({
        "id": site_id,
        "domain": "acmedental.com",
        "name": "Acme Dental",
    })
    save_local_audit({
        "website_id": site_id,
        "score": 65,
        "issues": [
            {"severity": "critical", "issue": "Missing Title Tag on https://acmedental.com/implants"},
            {"severity": "warning", "issue": "Missing Meta Description on https://acmedental.com/contact"},
            {"severity": "critical", "issue": "Broken 404 URL: https://acmedental.com/old-page"},
        ],
    })

    res = get_top_10_actions(site_id)
    actions = res["actions"]
    assert len(actions) >= 3, "Must generate actions corresponding to genuine issues"

    urls = [a.get("target_url") for a in actions]
    assert any("/implants" in u for u in urls if u), "Missing Title on /implants must generate an action"
    assert any("/contact" in u for u in urls if u), "Missing Meta Description on /contact must generate an action"
    assert any("/old-page" in u for u in urls if u), "Broken URL on /old-page must generate an action"

    title_action = next(a for a in actions if a.get("action_type") == "APPLY_TITLE_TAG")
    assert "<title>" in title_action.get("preview_diff", {}).get("after", "")
    assert title_action.get("effort") == "LOW"


def test_changelog_has_no_fake_seed_data():
    """Verify list_changelog returns only authentic recorded changes and no fabricated seed entries."""
    site_id = "test-empty-changelog-site"
    save_local_website({
        "id": site_id,
        "domain": "emptychangelog.com",
        "name": "Empty Changelog Site",
    })

    changelog = list_changelog(site_id)
    assert changelog == [], "Changelog for site without changes must be empty, not contain fake seed entries"


def test_execute_action_and_rollback_record_authentic_cms_status():
    """Verify execute_prioritized_action and rollback_change record genuine cms_sync_status."""
    site_id = "test-execution-sync-site"
    save_local_website({
        "id": site_id,
        "domain": "syncsite.com",
        "name": "Sync Site",
    })

    # Grab the top actions for this site
    res = get_top_10_actions(site_id)
    first_action = res["actions"][0]
    action_id = first_action["id"]

    # Test 1: Site with no CMS credentials records appropriate cms_sync_status
    result = execute_prioritized_action(site_id, action_id, author="Test Operator")
    assert result["status"] == "success"
    # For onboarding actions, RUN_TECH_AUDIT maps to AUDIT_COMPLETED or SAVED_LOCALLY_NO_CMS_CONFIGURED
    assert result["cms_sync_status"] in ("AUDIT_COMPLETED", "SAVED_LOCALLY_NO_CMS_CONFIGURED", "WP_CREDENTIALS_MISSING")

    change_id = result["guardrail_change_id"]
    saved_change = get_local_guardrail_change(change_id)
    assert saved_change is not None
    assert saved_change["cms_sync_status"] == result["cms_sync_status"]

    # Test 2: Rollback with no CMS configured
    rb_result = rollback_change(change_id, author="Test Operator")
    assert rb_result["status"] == "success"
    assert rb_result["cms_sync_status"] == "REVERTED_LOCALLY_NO_CMS_CONFIGURED"
    assert rb_result["live_cms_reverted"] is False

    # Test 3: Rollback when CMS credentials are configured
    change_seed = {
        "website_id": site_id,
        "title": "Live Title Patch",
        "target_url": "https://syncsite.com/live",
        "category": "TECHNICAL_SEO",
        "author": "Autonomous Agent",
        "impact_clicks": 50,
        "before_state": "<title>Old</title>",
        "after_state": "<title>New</title>",
        "status": "APPLIED",
    }
    change_with_cms = save_local_guardrail_change(change_seed)

    with patch("backend.routers.websites.get_decrypted_wordpress_credentials", return_value=("https://syncsite.com", "wp_admin", "app_pass_123")):
        rb_cms_result = rollback_change(change_with_cms["id"], author="Test Operator")
        assert rb_cms_result["status"] == "success"
        assert rb_cms_result["cms_sync_status"] == "LIVE_CMS_REVERTED"
        assert rb_cms_result["live_cms_reverted"] is True
