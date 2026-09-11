import sys
import os
import asyncio

import pytest

sys.path.insert(0, r"c:\Users\nikhil\Desktop\seo-agent-system")

from backend.services.seo_quality_gate import (
    run_qa_gate,
    _check_anchor_quality,
    _check_required_disclaimer,
    _check_untraced_facts_and_figures,
)
from backend.services.workflow_service import get_workflows_status, run_workflow

def test_qa_anchor_quality():
    bad_html = '<p>To learn more, <a href="https://example.com">click here</a>.</p>'
    res = _check_anchor_quality(bad_html)
    assert res["status"] == "FAIL", "Should fail on generic 'click here' anchor"
    assert "generic anchor" in res["detail"].lower()

    good_html = '<p>Review our <a href="https://example.com">personal injury statute guide</a>.</p>'
    res_good = _check_anchor_quality(good_html)
    assert res_good["status"] == "PASS", "Should pass descriptive anchor"
    print("PASS: test_qa_anchor_quality")

def test_qa_disclaimer():
    bad_html = '<p>Legal advice on Texas injury claims.</p>'
    res = _check_required_disclaimer(bad_html)
    assert res["status"] == "FAIL", "Should fail when legal/medical disclaimer is missing"

    good_html = '<p>Texas claims overview.</p><p class="disclaimer">Disclaimer: This article is for informational purposes only and does not constitute formal legal advice.</p>'
    res_good = _check_required_disclaimer(good_html)
    assert res_good["status"] == "PASS", "Should pass when disclaimer is included"
    print("PASS: test_qa_disclaimer")

def test_qa_untraced_facts():
    # Statutory claim without verification
    bad_html = '<p>Under Tex. Civ. Prac. & Rem. Code § 16.003, the statute of limitations is 2 years.</p>'
    res = _check_untraced_facts_and_figures(bad_html, verified_facts=[])
    assert res["status"] == "FAIL", "Should fail on untraced statutory reference § 16.003"
    assert ("statutory" in res["detail"].lower() or "§" in res["detail"])

    # Verified
    res_verified = _check_untraced_facts_and_figures(bad_html, verified_facts=["§ 16.003", "2 years"])
    assert res_verified["status"] == "PASS", "Should pass when facts are verified"
    print("PASS: test_qa_untraced_facts")

def test_full_run_qa_gate():
    bad_article = """
    <html>
    <body>
    <title>Short</title>
    <h1>Title One</h1>
    <h1>Title Two</h1>
    <p>Check out our site by clicking <a href="#">click here</a>.</p>
    <p>Under § 16.003, statute of limitations is 2 years.</p>
    </body>
    </html>
    """
    qa = run_qa_gate(bad_article, keyword="injury attorney")
    assert qa["gate"] == "HARD_FAIL"
    assert "anchor_quality" in qa["hard_fails"]
    assert "required_disclaimer" in qa["hard_fails"]
    assert "statutes_and_figures" in qa["hard_fails"]
    print("PASS: test_full_run_qa_gate (correctly hard-failed violations)")

@pytest.mark.asyncio
async def test_workflow_status_envelope():
    """Status envelope: 9 workflows, honest statuses, pace UNKNOWN when unmeasured."""
    status = await get_workflows_status("test-site")
    assert len(status["workflows"]) == 9, f"Expected 9 workflows, got {len(status['workflows'])}"
    assert status["publishing_pace"]["status"] in ("NORMAL", "PAUSED_INDEXATION_GATE", "UNKNOWN")
    for wf in status["workflows"]:
        assert wf["status"] in ("never_run", "running", "completed", "failed", "degraded")
        # No green without a check: unmeasured workflows say so explicitly.
        if wf["status"] == "never_run":
            assert wf["summary"] == "No run completed yet."
    print("PASS: test_workflow_service status envelope (all 9 workflows returned)")


if __name__ == "__main__":
    test_qa_anchor_quality()
    test_qa_disclaimer()
    test_qa_untraced_facts()
    test_full_run_qa_gate()
    asyncio.run(test_workflow_status_envelope())
    print("\nALL BACKEND & QA GATE TESTS PASSED COMPLETELY!")
