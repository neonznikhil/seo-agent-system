"""Honesty-gate regression tests: every number real, every gate closed.

Covers the P0/P1 fixes:
- deterministic QA gate HARD_FAILs unverifiable claims (CHECK 6)
- striking distance has one definition everywhere (CHECK 7)
- run diffs classify Fixed/New/Still-open/Regressed (CHECK 5)
- indexation gate blocks below threshold, passes above, warns unknown (CHECK 4)
- publishing without a verified human identity is denied (CHECK 2)
- GSC-unconfigured endpoints say so explicitly (CHECK 3)
"""
import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# QA gate: invented statute must HARD_FAIL (CHECK 6)
# ---------------------------------------------------------------------------

def _good_article_html() -> str:
    words = " ".join(["clear"] * 1900)
    return (
        "<h1>Houston Car Accident Claims Guide for Injured Drivers</h1>"
        "<p>TL;DR — call 911, document the scene, see a doctor within 24 hours.</p>"
        f"<p>{words}</p>"
        "<h2>What compensation can Houston drivers claim?</h2>"
        "<p>Texas drivers may recover medical costs and lost wages.</p>"
        "<h2>Frequently Asked Questions</h2>"
        "<h3>How long do I have?</h3><p>Talk to counsel promptly.</p>"
        '<p>See our <a href="/services">services</a> and '
        '<a href="/contact">contact</a> pages.</p>'
        "<p><em>Disclaimer: this article is for informational purposes only and "
        "is not legal advice. Consult a licensed attorney about your situation.</em></p>"
        "<p>Meta Description: Houston car accident claims guide for injured Texas drivers.</p>"
    )


def test_qa_gate_hard_fails_unverified_statute():
    from backend.services.seo_quality_gate import run_qa_gate
    html = _good_article_html().replace(
        "Texas drivers may recover",
        "Texas Code \u00a7 99.999 guarantees triple damages, so Texas drivers may recover",
    )
    fact_result = {
        "performed": True,
        "critical_failures": 1,
        "claims_checked": 1,
        "unverified_claims": ["Texas Code \u00a7 99.999 guarantees triple damages"],
    }
    out = run_qa_gate(html, keyword="Houston car accident claims",
                      fact_result=fact_result)
    assert out["gate"] == "HARD_FAIL"
    assert "fact_check" in out["hard_fails"]


def test_qa_gate_passes_clean_article():
    from backend.services.seo_quality_gate import run_qa_gate
    fact_result = {"performed": True, "critical_failures": 0, "claims_checked": 2,
                   "unverified_claims": []}
    out = run_qa_gate(_good_article_html(), keyword="Houston car accident claims",
                      fact_result=fact_result)
    assert out["gate"] == "PASS", out


def test_qa_gate_blocks_when_fact_check_never_ran():
    from backend.services.seo_quality_gate import run_qa_gate
    out = run_qa_gate(_good_article_html(), keyword="Houston car accident claims",
                      fact_result={"performed": False, "critical_failures": 0})
    assert out["gate"] == "HARD_FAIL"
    assert "fact_check" in out["hard_fails"]


# ---------------------------------------------------------------------------
# Striking distance: one definition (CHECK 7)
# ---------------------------------------------------------------------------

def test_writer_statute_verifier_runs_without_nameerror():
    """Regression: writer_agent uses re.* 40+ times; a missing import once
    made every fact verifier crash. Runs the real verifier with a stubbed
    search backend (no network)."""
    from backend.agents.writer_agent import WriterPipeline

    async def _fake_verify(self, claim: str, num_results: int = 3) -> bool:
        return False

    async def _go():
        pipe = WriterPipeline.__new__(WriterPipeline)
        pipe.website_id = "wid-1"
        pipe.supabase = None
        pipe.content_id = None
        orig = WriterPipeline._serper_verify_claim
        WriterPipeline._serper_verify_claim = _fake_verify
        try:
            return await pipe._verify_statutes_and_deadlines(
                "<p>Under Texas Code section 99.999, file within 27 years.</p>")
        finally:
            WriterPipeline._serper_verify_claim = orig

    import asyncio
    res = asyncio.run(_go())
    assert res["performed"] is True
    assert res["critical_failures"] >= 1
    assert res["claims_checked"] >= 1


def test_striking_distance_single_definition():
    from backend.seo_constants import (
        STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX, is_striking_distance,
        get_site_striking_range,
    )
    assert (STRIKING_DISTANCE_MIN, STRIKING_DISTANCE_MAX) == (11, 20)
    assert is_striking_distance(11) and is_striking_distance(20)
    assert not is_striking_distance(10) and not is_striking_distance(21)
    assert not is_striking_distance(None)
    # Per-site override respected
    assert get_site_striking_range({"striking_min": 4, "striking_max": 20}) == (4, 20)
    assert get_site_striking_range({}) == (11, 20)


def test_all_striking_usages_share_constants():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    for rel in ["services/daily_search_service.py", "services/real_data_service.py",
                "services/rank_tracker.py"]:
        content = (root / rel).read_text(encoding="utf-8")
        assert "seo_constants" in content, f"{rel} must import shared striking definition"
    # No hardcoded 11..20 / 10<..<=20 ranges left in those classifiers
    assert "11 <= (k.get(\"position\")" not in (root / "services/daily_search_service.py").read_text()
    assert "10 < kw.get('position'" not in (root / "services/real_data_service.py").read_text()


# ---------------------------------------------------------------------------
# Run diffs (CHECK 5)
# ---------------------------------------------------------------------------

def test_compute_diff_classifies_all_four_states():
    from backend.services.run_service import compute_diff, build_summary
    prev = {"issue_ids": ["a", "b", "c"], "health_score": 90.0}
    curr = {"issue_ids": ["b", "c", "d"], "health_score": 70.0}
    changes = compute_diff(curr, prev)
    assert changes["fixed"] == ["a"]
    assert changes["new"] == ["d"]
    assert changes["still_open"] == ["b", "c"]
    assert len(changes["regressed"]) == 1 and "health_score" in changes["regressed"][0]
    summary = build_summary(changes, "tech_seo_audit")
    assert "1 issue(s) fixed" in summary and "regressed" in summary


def test_compute_diff_no_previous_run_is_empty():
    from backend.services.run_service import compute_diff, build_summary
    changes = compute_diff({"issue_ids": ["a"]}, None)
    assert changes == {"fixed": [], "new": [], "still_open": [], "regressed": []}
    assert "No changes" in build_summary(changes)


# ---------------------------------------------------------------------------
# Indexation gate (CHECK 4)
# ---------------------------------------------------------------------------

def _fake_supabase_indexation(rate):
    """Fake supabase chain for indexation_checks + pending_fixes + settings."""
    mock_sb = MagicMock()

    check_row = {"id": "chk-1", "website_id": "wid-1",
                 "indexation_rate": rate, "threshold": 0.80,
                 "checked_at": "2026-09-11T00:00:00+00:00"}

    def _chain(data):
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.order.return_value = m
        m.limit.return_value = m
        m.execute.return_value = MagicMock(data=data)
        m.update.return_value = m
        m.insert.return_value = m
        m.single.return_value = m
        return m

    def _table(name):
        if name == "indexation_checks":
            return _chain([] if rate == "none" else [check_row])
        if name == "autonomous_settings":
            return _chain([])
        return _chain([])

    mock_sb.table.side_effect = _table
    return mock_sb


@pytest.mark.asyncio
async def test_indexation_gate_blocked_below_threshold(monkeypatch):
    import backend.services.indexation_service as svc
    monkeypatch.setattr(svc, "get_supabase", lambda: _fake_supabase_indexation(0.72))
    gate = await svc.indexation_gate_check("wid-1")
    assert gate["gate"] == "blocked"
    assert gate["indexation_rate"] == 0.72
    assert "0.80" in gate["reason"] or "80%" in gate["reason"]


@pytest.mark.asyncio
async def test_indexation_gate_passes_above_threshold(monkeypatch):
    import backend.services.indexation_service as svc
    monkeypatch.setattr(svc, "get_supabase", lambda: _fake_supabase_indexation(0.85))
    gate = await svc.indexation_gate_check("wid-1")
    assert gate["gate"] == "pass"


@pytest.mark.asyncio
async def test_indexation_gate_unknown_without_checks(monkeypatch):
    import backend.services.indexation_service as svc
    monkeypatch.setattr(svc, "get_supabase", lambda: _fake_supabase_indexation("none"))
    gate = await svc.indexation_gate_check("wid-1")
    assert gate["gate"] == "unknown"


# ---------------------------------------------------------------------------
# Counter consistency: one shared counter module (CHECK: dashboard parity)
# ---------------------------------------------------------------------------

def test_both_dashboard_endpoints_share_counter_module():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    dash = (root / "routers" / "dashboard.py").read_text(encoding="utf-8")
    main = (root / "main.py").read_text(encoding="utf-8")
    assert "get_site_counts" in dash, "dashboard.py must use shared get_site_counts"
    assert "get_site_counts" in main, "main.py /api/stats must use shared get_site_counts"
    assert "backlink_opportunities\": opportunities_count = backlinks_count" not in dash
    assert "opportunities_count = backlinks_count" not in dash


@pytest.mark.asyncio
async def test_shared_counts_are_honest_and_unified():
    from backend.services.dashboard_metrics import get_site_counts

    def _chain(data):
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.order.return_value = m
        m.limit.return_value = m
        m.gte.return_value = m
        exec_res = MagicMock()
        exec_res.data = data
        exec_res.count = len(data)
        m.execute.return_value = exec_res
        return m

    mock_sb = MagicMock()
    tables = {
        "content_log": [{"id": "c1"}, {"id": "c2"}],
        "blog_approvals": [{"id": "a1"}],
        "realtime_alerts": [],
        "brain_memory": [{"id": "m1"}],
        "backlinks": [{"id": "b1"}],
        "backlink_opportunities": [{"id": "o1"}, {"id": "o2"}],
        "knowledge_base": [{"id": "k1"}],
        "technical_audits": [],
    }
    state = {"table": None}

    def _table(name):
        state["table"] = name
        base = _chain(tables.get(name, []))
        orig_eq = base.eq

        def _eq(k, v):
            # blog_approvals status filter narrows the single fixture row
            if name == "blog_approvals" and k == "status" and v == "published":
                return _chain([])
            return orig_eq(k, v)

        base.eq = MagicMock(side_effect=_eq)
        return base

    mock_sb.table.side_effect = _table
    out = await get_site_counts(mock_sb, "wid-1")
    assert out["total_articles"] == 2
    assert out["published_articles"] == 0
    assert out["pending_articles"] == 1
    assert out["monitored_alerts"] == 0  # no floor, empty is 0
    assert out["backlinks_count"] == 1
    assert out["backlink_opportunities"] == 2  # own table, not an alias
    assert out["health_score"] is None  # no audit -> null, never 94

@pytest.mark.asyncio
async def test_publish_without_identity_is_denied():
    from httpx import AsyncClient, ASGITransport
    try:
        from main import app
    except ImportError:
        from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/wordpress/publish",
                                json={"website_id": "x", "title": "t", "content": "c"})
        assert res.status_code == 403, res.text
        res2 = await client.post("/api/wordpress/publish",
                                 headers={"X-User-Id": "human-approved"},
                                 json={"website_id": "x", "title": "t", "content": "c"})
        assert res2.status_code == 403, res2.text


# ---------------------------------------------------------------------------
# GSC unconfigured says so (CHECK 3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gsc_keywords_honest_when_unconfigured(monkeypatch):
    from backend.routers import gsc as gsc_router

    class _DeadGSC:
        def __init__(self, website_url=None):
            pass

        def is_connected(self):
            return False

    # Patch every module path the router might import GSCService from.
    for mod_name in ("services.gsc_service", "backend.services.gsc_service"):
        try:
            mod = __import__(mod_name, fromlist=["GSCService"])
            monkeypatch.setattr(mod, "GSCService", _DeadGSC, raising=True)
        except ImportError:
            pass
    out = await gsc_router.get_keywords("wid-1")
    assert out["keywords"] == []
    assert out["connected"] is False
    assert "message" in out
