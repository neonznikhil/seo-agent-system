"""Integration test suite for the 6 Enterprise Pillars:
1. Multi-Site Network Overview (/api/network)
2. Ranked Top 10 Prioritized Actions (/api/actions)
3. Keyword Lead Attribution & CPL (/api/leads)
4. Change Guardrails, Preview Diff & 1-Click Rollback (/api/guardrails)
5. Competitor Intelligence, SOV & Outranking Matrix (/api/competitors)
6. 28-Day Post-Fix ROI Proof Tracker (/api/roi-proof)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app

AUTH_HEADERS = {"X-User-Id": "a0000000-0000-0000-0000-000000000001"}
TEST_WEBSITE_ID = "44666e81-1d83-4801-be22-1cb72f39801a"


@pytest.fixture
def client_transport():
    return ASGITransport(app=app)


# ============================================================================
# PILLAR 1: MULTI-SITE NETWORK OVERVIEW (/api/network)
# ============================================================================

@pytest.mark.asyncio
async def test_pillar_1_network_overview(client_transport):
    async with AsyncClient(transport=client_transport, base_url="http://test") as client:
        # Test unified network overview
        res = await client.get("/api/network/overview", headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        assert "sites" in data
        assert isinstance(data["sites"], list)
        assert "summary" in data
        assert "total_sites" in data
        assert "network_health_avg" in data
        assert "network_indexation_avg" in data
        assert "network_clicks_28d" in data
        assert "total_open_issues" in data

        if data["sites"]:
            site = data["sites"][0]
            assert "site_name" in site
            assert "domain" in site
            assert "health_score" in site
            assert "indexed_pages" in site
            assert "submitted_pages" in site
            assert "clicks_28d" in site
            assert "impressions_28d" in site
            assert "open_issues_count" in site
            assert "critical_issues" in site
            assert "warning_issues" in site
            assert "info_issues" in site
            assert "last_audit_date" in site
            assert "trend" in site

        # Test high-level summary KPIs
        res_summary = await client.get("/api/network/summary-stats", headers=AUTH_HEADERS)
        assert res_summary.status_code == 200
        summary_data = res_summary.json()
        assert "total_sites" in summary_data or "average_health_score" in summary_data


# ============================================================================
# PILLAR 2: RANKED TOP 10 PRIORITIZED ACTIONS (/api/actions)
# ============================================================================

@pytest.mark.asyncio
async def test_pillar_2_prioritized_actions(client_transport):
    async with AsyncClient(transport=client_transport, base_url="http://test") as client:
        # Test GET /api/actions/{website_id}/top-10
        res1 = await client.get(f"/api/actions/{TEST_WEBSITE_ID}/top-10", headers=AUTH_HEADERS)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1.get("website_id") == TEST_WEBSITE_ID
        assert "actions" in data1
        assert len(data1["actions"]) <= 10
        assert data1["total_potential_clicks_per_month"] >= 0
        assert data1["total_potential_value_per_month"] >= 0

        # Verify alias GET /api/actions/{website_id}/top10
        res1_alias = await client.get(f"/api/actions/{TEST_WEBSITE_ID}/top10", headers=AUTH_HEADERS)
        assert res1_alias.status_code == 200
        assert res1_alias.json()["website_id"] == TEST_WEBSITE_ID

        # Verify action structure
        assert len(data1["actions"]) > 0
        action = data1["actions"][0]
        assert "id" in action
        assert "title" in action
        assert "category" in action
        assert "impact_clicks_per_month" in action
        assert "estimated_monthly_value" in action
        assert "effort" in action
        assert "preview_diff" in action

        action_id = action["id"]

        # Test POST /api/actions/{website_id}/{action_id}/execute
        res_exec = await client.post(
            f"/api/actions/{TEST_WEBSITE_ID}/{action_id}/execute",
            json={"author": "Test Suite Runner"},
            headers=AUTH_HEADERS,
        )
        assert res_exec.status_code == 200
        exec_data = res_exec.json()
        assert exec_data.get("status") == "success"
        assert "guardrail_change_id" in exec_data

        # Test POST execution on nonexistent action -> 404
        res_exec_bad = await client.post(
            f"/api/actions/{TEST_WEBSITE_ID}/act-nonexistent-9999/execute",
            json={"author": "Test Suite Runner"},
            headers=AUTH_HEADERS,
        )
        assert res_exec_bad.status_code == 404

        # Test POST /api/actions/{website_id}/{action_id}/dismiss
        res_dismiss = await client.post(
            f"/api/actions/{TEST_WEBSITE_ID}/{action_id}/dismiss",
            headers=AUTH_HEADERS,
        )
        assert res_dismiss.status_code == 200
        assert res_dismiss.json().get("status") == "success"


# ============================================================================
# PILLAR 3: KEYWORD LEAD ATTRIBUTION & CPL (/api/leads)
# ============================================================================

@pytest.mark.asyncio
async def test_pillar_3_lead_attribution(client_transport):
    async with AsyncClient(transport=client_transport, base_url="http://test") as client:
        # Test GET /api/leads/{website_id}/keyword-performance
        res_perf = await client.get(f"/api/leads/{TEST_WEBSITE_ID}/keyword-performance", headers=AUTH_HEADERS)
        assert res_perf.status_code == 200
        perf_data = res_perf.json()
        assert perf_data.get("website_id") == TEST_WEBSITE_ID
        assert "keywords" in perf_data
        assert "summary" in perf_data
        assert "settings" in perf_data

        # Verify alias GET /api/leads/{website_id}/attribution
        res_attr = await client.get(f"/api/leads/{TEST_WEBSITE_ID}/attribution", headers=AUTH_HEADERS)
        assert res_attr.status_code == 200
        assert res_attr.json()["website_id"] == TEST_WEBSITE_ID

        # Verify keyword metrics
        if perf_data["keywords"]:
            kw = perf_data["keywords"][0]
            assert "keyword" in kw
            assert "clicks" in kw
            assert "conversions" in kw
            assert "cvr" in kw
            assert "cpl" in kw
            assert "pipeline_value" in kw

        # Test GET /api/leads/{website_id}/summary
        res_sum = await client.get(f"/api/leads/{TEST_WEBSITE_ID}/summary", headers=AUTH_HEADERS)
        assert res_sum.status_code == 200
        sum_data = res_sum.json()
        assert "total_organic_leads" in sum_data
        assert "blended_cpl" in sum_data
        assert "total_pipeline_value" in sum_data

        # Test GET /api/leads/{website_id}/settings
        res_get_set = await client.get(f"/api/leads/{TEST_WEBSITE_ID}/settings", headers=AUTH_HEADERS)
        assert res_get_set.status_code == 200

        # Test POST /api/leads/{website_id}/settings (path-based)
        update_payload = {
            "monthly_budget": 4500.0,
            "target_cpl": 55.0,
            "lead_value": 300.0,
            "conversion_goals": ["Demo Request", "Contact Sales"],
        }
        res_save_path = await client.post(
            f"/api/leads/{TEST_WEBSITE_ID}/settings",
            json=update_payload,
            headers=AUTH_HEADERS,
        )
        assert res_save_path.status_code == 200
        saved_data = res_save_path.json()
        assert (
            saved_data.get("monthly_budget") == 4500.0
            or saved_data.get("monthly_seo_spend") == 4500.0
            or saved_data.get("settings", {}).get("monthly_budget") == 4500.0
            or saved_data.get("settings", {}).get("monthly_seo_spend") == 4500.0
        )
        assert (
            saved_data.get("target_cpl") == 55.0
            or saved_data.get("settings", {}).get("target_cpl") == 55.0
        )

        # Test POST /api/leads/settings (body-based website_id)
        res_save_body = await client.post(
            "/api/leads/settings",
            json={
                "website_id": TEST_WEBSITE_ID,
                "monthly_seo_spend": 5000.0,
                "target_cpl": 60.0,
                "lead_value": 350.0,
            },
            headers=AUTH_HEADERS,
        )
        assert res_save_body.status_code == 200
        saved_body_data = res_save_body.json()
        assert (
            saved_body_data.get("monthly_seo_spend") == 5000.0
            or saved_body_data.get("settings", {}).get("monthly_seo_spend") == 5000.0
        )
        assert (
            saved_body_data.get("target_cpl") == 60.0
            or saved_body_data.get("settings", {}).get("target_cpl") == 60.0
        )

        # Test POST /api/leads/settings without website_id -> 400
        res_bad_settings = await client.post(
            "/api/leads/settings",
            json={"target_cpl": 40.0},
            headers=AUTH_HEADERS,
        )
        assert res_bad_settings.status_code == 400


# ============================================================================
# PILLAR 4: CHANGE GUARDRAILS, PREVIEW DIFF & 1-CLICK ROLLBACK (/api/guardrails)
# ============================================================================

@pytest.mark.asyncio
async def test_pillar_4_guardrails_and_rollback(client_transport):
    async with AsyncClient(transport=client_transport, base_url="http://test") as client:
        # Test POST /api/guardrails/preview-diff
        before_text = "<title>Old Title</title>\n<p>General overview</p>"
        after_text = "<title>New Optimized Title</title>\n<p>Enhanced overview with proven pricing and clinical medical advice.</p>"
        res_diff = await client.post(
            "/api/guardrails/preview-diff",
            json={"before": before_text, "after": after_text},
            headers=AUTH_HEADERS,
        )
        assert res_diff.status_code == 200
        diff_data = res_diff.json()
        assert "diff" in diff_data
        diff_text = diff_data["diff"]["raw_diff"] if isinstance(diff_data["diff"], dict) else diff_data["diff"]
        assert "Old Title" in diff_text
        assert "New Optimized Title" in diff_text
        assert "ymyl_safety" in diff_data
        assert "is_safe" in diff_data["ymyl_safety"]
        assert "risk_level" in diff_data["ymyl_safety"]

        # Ensure at least one action is executed to guarantee a changelog entry
        act_res = await client.get(f"/api/actions/{TEST_WEBSITE_ID}/top-10", headers=AUTH_HEADERS)
        actions = act_res.json().get("actions", [])
        assert len(actions) > 0
        action_id = actions[0]["id"]
        exec_res = await client.post(
            f"/api/actions/{TEST_WEBSITE_ID}/{action_id}/execute",
            json={"author": "Guardrail Auditor"},
            headers=AUTH_HEADERS,
        )
        change_id = exec_res.json()["guardrail_change_id"]

        # Test GET /api/guardrails/{website_id}/changelog
        res_log = await client.get(f"/api/guardrails/{TEST_WEBSITE_ID}/changelog", headers=AUTH_HEADERS)
        assert res_log.status_code == 200
        log_data = res_log.json()
        assert log_data.get("website_id") == TEST_WEBSITE_ID
        assert "changes" in log_data
        assert log_data.get("count", 0) > 0

        # Test alias GET /api/guardrails/{website_id}/changes
        res_log_alias = await client.get(f"/api/guardrails/{TEST_WEBSITE_ID}/changes", headers=AUTH_HEADERS)
        assert res_log_alias.status_code == 200
        assert res_log_alias.json()["website_id"] == TEST_WEBSITE_ID

        # Test GET /api/guardrails/change/{change_id}
        res_change = await client.get(f"/api/guardrails/change/{change_id}", headers=AUTH_HEADERS)
        assert res_change.status_code == 200
        ch_data = res_change.json()
        assert ch_data.get("id") == change_id or ch_data.get("change_id") == change_id
        assert "visual_diff" in ch_data or "diff" in ch_data
        assert "ymyl_check" in ch_data or "ymyl_safety" in ch_data

        # Test GET /api/guardrails/change/nonexistent -> 404
        res_change_404 = await client.get("/api/guardrails/change/nonexistent-change-uuid", headers=AUTH_HEADERS)
        assert res_change_404.status_code == 404

        # Test POST /api/guardrails/change/{change_id}/rollback
        res_rb = await client.post(
            f"/api/guardrails/change/{change_id}/rollback",
            json={"author": "Rollback Officer"},
            headers=AUTH_HEADERS,
        )
        assert res_rb.status_code == 200
        rb_data = res_rb.json()
        assert rb_data.get("status") == "success"
        assert rb_data.get("rolled_back_change_id") == change_id or rb_data.get("change_id") == change_id

        # Verify rollback alias POST /api/guardrails/{website_id}/rollback/{change_id}
        # Execute another action to test alias rollback
        if len(actions) > 1:
            second_action_id = actions[1]["id"]
            second_exec = await client.post(
                f"/api/actions/{TEST_WEBSITE_ID}/{second_action_id}/execute",
                headers=AUTH_HEADERS,
            )
            second_change_id = second_exec.json()["guardrail_change_id"]
            res_rb_alias = await client.post(
                f"/api/guardrails/{TEST_WEBSITE_ID}/rollback/{second_change_id}",
                json={"author": "Rollback Officer Alias"},
                headers=AUTH_HEADERS,
            )
            assert res_rb_alias.status_code == 200
            assert res_rb_alias.json().get("status") == "success"


# ============================================================================
# PILLAR 5: COMPETITOR INTELLIGENCE, SOV & OUTRANKING MATRIX (/api/competitors)
# ============================================================================

@pytest.mark.asyncio
async def test_pillar_5_competitors(client_transport):
    async with AsyncClient(transport=client_transport, base_url="http://test") as client:
        # Test POST /api/competitors/{website_id} - Add competitor
        new_comp_domain = "apexrival.com"
        res_add = await client.post(
            f"/api/competitors/{TEST_WEBSITE_ID}",
            json={"domain": new_comp_domain, "label": "Apex Rival Corp"},
            headers=AUTH_HEADERS,
        )
        assert res_add.status_code == 200
        add_data = res_add.json()
        assert add_data.get("status") == "success"
        comp_obj = add_data.get("competitor", {})
        assert comp_obj.get("domain") == new_comp_domain
        comp_id = comp_obj.get("id")
        assert comp_id is not None

        # Test POST /api/competitors/{website_id} with empty domain -> 400
        res_bad_comp = await client.post(
            f"/api/competitors/{TEST_WEBSITE_ID}",
            json={"domain": "   "},
            headers=AUTH_HEADERS,
        )
        assert res_bad_comp.status_code == 400

        # Test GET /api/competitors/{website_id} - List competitors
        res_list = await client.get(f"/api/competitors/{TEST_WEBSITE_ID}", headers=AUTH_HEADERS)
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data.get("website_id") == TEST_WEBSITE_ID
        assert any(c.get("domain") == new_comp_domain for c in list_data.get("competitors", []))

        # Test GET /api/competitors/{website_id}/share-of-voice
        res_sov = await client.get(f"/api/competitors/{TEST_WEBSITE_ID}/share-of-voice", headers=AUTH_HEADERS)
        assert res_sov.status_code == 200
        sov_data = res_sov.json()
        assert "my_share_of_voice" in sov_data or "sov_data" in sov_data or "competitors" in sov_data

        # Verify alias GET /api/competitors/{website_id}/sov
        res_sov_alias = await client.get(f"/api/competitors/{TEST_WEBSITE_ID}/sov", headers=AUTH_HEADERS)
        assert res_sov_alias.status_code == 200

        # Test GET /api/competitors/{website_id}/new-pages
        res_np = await client.get(f"/api/competitors/{TEST_WEBSITE_ID}/new-pages", headers=AUTH_HEADERS)
        assert res_np.status_code == 200
        np_data = res_np.json()
        assert "new_pages" in np_data
        assert isinstance(np_data["new_pages"], list)

        # Test GET /api/competitors/{website_id}/outranking-matrix
        res_mat = await client.get(f"/api/competitors/{TEST_WEBSITE_ID}/outranking-matrix", headers=AUTH_HEADERS)
        assert res_mat.status_code == 200
        mat_data = res_mat.json()
        assert "outranked_queries" in mat_data
        assert isinstance(mat_data["outranked_queries"], list)

        # Verify alias GET /api/competitors/{website_id}/outranked
        res_mat_alias = await client.get(f"/api/competitors/{TEST_WEBSITE_ID}/outranked", headers=AUTH_HEADERS)
        assert res_mat_alias.status_code == 200

        # Test DELETE /api/competitors/{website_id}/{competitor_id}
        res_del = await client.delete(f"/api/competitors/{TEST_WEBSITE_ID}/{comp_id}", headers=AUTH_HEADERS)
        assert res_del.status_code == 200
        assert res_del.json().get("status") == "success"

        # Test DELETE on nonexistent competitor -> 404
        res_del_404 = await client.delete(f"/api/competitors/{TEST_WEBSITE_ID}/nonexistent-comp-id", headers=AUTH_HEADERS)
        assert res_del_404.status_code == 404


# ============================================================================
# PILLAR 6: 28-DAY POST-FIX ROI PROOF TRACKER (/api/roi-proof)
# ============================================================================

@pytest.mark.asyncio
async def test_pillar_6_roi_proof(client_transport):
    async with AsyncClient(transport=client_transport, base_url="http://test") as client:
        # Test POST /api/roi-proof/{website_id}/track - Register new fix
        track_payload = {
            "target_url": f"https://example.com/blog/legal-guide-{TEST_WEBSITE_ID[:6]}",
            "fix_title": "Optimized H1, Meta Tags, and Canonical URLs",
            "category": "ON_PAGE_TECHNICAL",
            "target_keyword": "accident lawyer consultation",
            "baseline_position": 8.5,
            "baseline_monthly_clicks": 350,
            "action_id": "act-test-001",
        }
        res_track = await client.post(
            f"/api/roi-proof/{TEST_WEBSITE_ID}/track",
            json=track_payload,
            headers=AUTH_HEADERS,
        )
        assert res_track.status_code == 200
        track_data = res_track.json()
        assert track_data.get("status") == "success"
        tracked_fix = track_data.get("tracked_fix", {})
        assert tracked_fix.get("fix_title") == track_payload["fix_title"]
        assert tracked_fix.get("baseline_position") == 8.5
        assert tracked_fix.get("baseline_monthly_clicks") == 350

        # Test GET /api/roi-proof/{website_id}/proof-list
        res_list = await client.get(f"/api/roi-proof/{TEST_WEBSITE_ID}/proof-list", headers=AUTH_HEADERS)
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data.get("website_id") == TEST_WEBSITE_ID
        assert "tracked_fixes" in list_data
        assert any(f.get("target_url") == track_payload["target_url"] for f in list_data.get("tracked_fixes", []))

        # Verify alias GET /api/roi-proof/{website_id}/fixes
        res_list_alias = await client.get(f"/api/roi-proof/{TEST_WEBSITE_ID}/fixes", headers=AUTH_HEADERS)
        assert res_list_alias.status_code == 200
        assert res_list_alias.json()["website_id"] == TEST_WEBSITE_ID

        # Test GET /api/roi-proof/{website_id}/summary
        res_sum = await client.get(f"/api/roi-proof/{TEST_WEBSITE_ID}/summary", headers=AUTH_HEADERS)
        assert res_sum.status_code == 200
        sum_data = res_sum.json()
        assert "roi_multiple" in sum_data
        assert "total_monthly_clicks_gained" in sum_data
        assert "total_pipeline_value_added" in sum_data
        assert "verified_fixes_count" in sum_data
        assert "total_fixes_tracked" in sum_data
        assert sum_data.get("total_fixes_tracked", 0) >= 1
