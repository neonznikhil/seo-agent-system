"""Regression tests: background jobs must never report success for work they did not do.

Original bugs, all verified by reading the call sites:
  * run_first_time_setup_pipeline wrapped every phase in try/except and never
    raised, so the caller wrote status="done" even when all phases failed — and a
    "done" job is never retried, so the site was stranded permanently.
  * It read research_res["keywords"], a key ResearchAgent.run() never returns, so
    every site's first article was written about the literal "primary service
    guide".
  * _has_run_today returned False on a Supabase error, making all 8 daily jobs look
    un-run, so a restart during a DB blip re-ran full article generation.
  * retrieve_relevant_hybrid floored fallback similarity to 0.60, so every
    consumer's >=0.55 grounding gate passed by construction and the
    "not grounded, abort" guard was dead code on that path.
  * serp_volatility_service hardcoded vol_score = 22.5 and ran it even when Serper
    returned zero results, so a total outage read as a measured "22.5% stable SERP".
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.setup_pipeline import run_first_time_setup_pipeline, _extract_keywords
from agents.scheduler import _has_run_today
from services.serp_volatility_service import SerpVolatilityService
from services.knowledge_service import KnowledgeService


# ------------------------------------------------------- setup pipeline

def _patch_all_steps(**overrides):
    """Patch every phase so no network/DB work happens.

    The awaited method names must match what the pipeline actually calls —
    watch_business_website / run / generate / run_audit / run_prospecting_loop.
    """
    def _make(method, ret):
        inst = MagicMock()
        setattr(inst, method, AsyncMock(return_value=ret))
        return MagicMock(return_value=inst)

    crawl = _make("watch_business_website",
                  overrides.get("crawl", {"new_pages_ingested": 7}))
    research = _make("run", overrides.get(
        "research",
        {"relatedSearches": [{"query": "houston car accident lawyer"}]},
    ))
    generate = _make("generate", overrides.get(
        "generate",
        {"status": "completed", "title": "Houston Car Accident Guide",
         "word_count": 2400, "seo_score": 88},
    ))
    backlinks = _make("run_prospecting_loop",
                      overrides.get("backlinks", {"opportunities_found": 12}))
    # TechSEOAgent is instantiated then .run_audit(website_id) awaited.
    tech = _make("run_audit", overrides.get("audit", {"health_score": 74}))

    return [
        patch("agents.setup_pipeline.KnowledgeService", crawl),
        patch("agents.setup_pipeline.ResearchAgent", research),
        patch("agents.setup_pipeline.is_nim_available", AsyncMock(return_value=True)),
        patch("agents.setup_pipeline.WriterPipeline", generate),
        patch("agents.setup_pipeline.TechSEOAgent", tech),
        patch("agents.setup_pipeline.BacklinkAgent", backlinks),
        patch("agents.setup_pipeline.slack_intelligence_service.send_crisis_alert",
              AsyncMock(return_value=True)),
    ]


def test_extract_keywords_uses_fields_research_agent_actually_returns():
    """ResearchAgent.run() has no 'keywords' key — that was the whole bug."""
    res = {
        "relatedSearches": [{"query": "houston car accident lawyer"}],
        "questions": ["How much does a car accident claim pay?"],
        "organic": [{"title": "Best Houston Accident Attorneys"}],
    }
    kws = _extract_keywords(res)
    assert kws, "keywords must be derived from real SERP fields"
    assert "houston car accident lawyer" in kws
    # and must NOT need the missing key
    assert _extract_keywords({}) == []
    assert _extract_keywords(None) == []


def test_extract_keywords_dedupes_and_ignores_empty():
    # _add() requires len > 2, so single chars are dropped by design.
    res = {"relatedSearches": [{"query": "auto"}], "questions": ["auto", "", None, "truck"]}
    kws = _extract_keywords(res)
    assert kws.count("auto") == 1
    assert "truck" in kws
    assert "" not in kws


@pytest.mark.asyncio
async def test_pipeline_raises_when_writer_fails_so_mark_failed_runs():
    """The caller does mark_failed only on an exception. Swallowing = 'done' forever."""
    patches = _patch_all_steps(generate={"status": "failed", "error_message": "NIM down"})
    for p in patches:
        p.start()
    try:
        with pytest.raises(RuntimeError) as exc:
            await run_first_time_setup_pipeline("wid-1", "https://example.com")
        assert "incomplete" in str(exc.value).lower()
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_pipeline_raises_when_crawl_ingested_zero_pages():
    """0 pages means the crawler failed or the site is empty — never 'completed'."""
    patches = _patch_all_steps(crawl={"new_pages_ingested": 0})
    for p in patches:
        p.start()
    try:
        with pytest.raises(RuntimeError):
            await run_first_time_setup_pipeline("wid-2", "https://example.com")
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_pipeline_raises_when_research_returns_no_keywords():
    patches = _patch_all_steps(research={"relatedSearches": [], "questions": [], "organic": []})
    for p in patches:
        p.start()
    try:
        with pytest.raises(RuntimeError):
            await run_first_time_setup_pipeline("wid-3", "https://example.com")
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_pipeline_returns_results_and_uses_real_keyword_when_all_steps_pass():
    patches = _patch_all_steps()
    for p in patches:
        p.start()
    try:
        res = await run_first_time_setup_pipeline("wid-4", "https://example.com")
        assert res["complete"] is True
        assert res["steps"]["research"]["top_keyword"] == "houston car accident lawyer"
        assert res["steps"]["knowledge"]["status"] == "completed"
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_pipeline_does_not_announce_completion_on_slack_when_incomplete():
    """The old message said 'setup complete' with article_title='' and score None."""
    alert = AsyncMock(return_value=True)
    patches = _patch_all_steps(generate={"status": "failed", "error_message": "NIM down"})
    patches[-1] = patch("agents.setup_pipeline.slack_intelligence_service.send_crisis_alert", alert)
    for p in patches:
        p.start()
    try:
        with pytest.raises(RuntimeError):
            await run_first_time_setup_pipeline("wid-5", "https://example.com")
    finally:
        for p in patches:
            p.stop()

    if alert.await_count:
        details = alert.await_args.kwargs.get("details", "")
        assert "setup complete" not in details.lower()
        assert alert.await_args.kwargs.get("title") != "Setup Complete"


# ------------------------------------------------------- _has_run_today

def test_has_run_today_fails_closed(monkeypatch):
    """A DB outage must NOT look like 'never ran' — that re-ran all 8 daily jobs."""
    import agents.scheduler as sched

    boom = MagicMock()
    boom.table.return_value.select.return_value.eq.return_value.gte.return_value \
        .limit.return_value.execute.side_effect = RuntimeError("DNS failure")
    monkeypatch.setattr("database.get_supabase", lambda: boom)

    assert sched._has_run_today("job_daily_search") is True


def test_has_run_today_true_when_row_found(monkeypatch):
    import agents.scheduler as sched

    res = MagicMock()
    res.data = [{"id": "1"}]
    q = MagicMock()
    q.table.return_value.select.return_value.eq.return_value.gte.return_value \
        .limit.return_value.execute.return_value = res
    monkeypatch.setattr("database.get_supabase", lambda: q)

    assert sched._has_run_today("job_daily_search") is True


def test_has_run_today_false_when_no_row(monkeypatch):
    import agents.scheduler as sched

    res = MagicMock()
    res.data = []
    q = MagicMock()
    q.table.return_value.select.return_value.eq.return_value.gte.return_value \
        .limit.return_value.execute.return_value = res
    monkeypatch.setattr("database.get_supabase", lambda: q)

    assert sched._has_run_today("job_daily_search") is False


# ------------------------------------------------------- SERP volatility

def test_position_shift_returns_none_without_prior_snapshot():
    assert SerpVolatilityService._position_shift({}, [{"link": "a", "position": 1}]) is None
    assert SerpVolatilityService._position_shift({"a": 1}, []) is None


def test_position_shift_computes_real_delta():
    prev = {"https://a": 2, "https://b": 8}
    now = [{"link": "https://a", "position": 5}, {"link": "https://b", "position": 8}]
    score = SerpVolatilityService._position_shift(prev, now)
    assert score is not None
    # deltas: |5-2| = 3, |8-8| = 0 -> mean 1.5 -> /10 * 100 = 15.0
    assert score == 15.0


@pytest.mark.asyncio
async def test_no_fabricated_score_when_serper_is_down(monkeypatch):
    """A total Serper outage must not report a measured index."""
    monkeypatch.setattr(
        "services.serp_volatility_service.get_supabase",
        lambda: MagicMock(),
    )

    def _tbl(name):
        q = MagicMock()
        q.select.return_value.eq.return_value.limit.return_value.execute.return_value = \
            MagicMock(data=[{"keyword": "car accident lawyer"}])
        q.select.return_value.eq.return_value.eq.return_value.order.return_value \
            .limit.return_value.execute.return_value = MagicMock(data=[])
        return q

    sup = MagicMock()
    sup.table.side_effect = _tbl
    monkeypatch.setattr(
        "services.serp_volatility_service.get_supabase", lambda: sup
    )

    async def _dead(*_a, **_k):
        return {"source": "unavailable", "organic": [], "error": "circuit open"}

    monkeypatch.setattr(
        "services.serp_volatility_service.serper_service.search", _dead
    )

    out = await SerpVolatilityService(website_id="wid").check_serp_volatility()
    assert out["success"] is False
    assert out["niche_volatility_index"] is None


# ------------------------------------------------------- grounding gate

@pytest.mark.asyncio
async def test_kb_fallback_does_not_floor_similarity_to_pass_gate():
    """max(sim, 0.60) made every grounding gate pass by construction."""
    import inspect
    src = inspect.getsource(KnowledgeService.retrieve_relevant_hybrid)
    # Strip comments — the fix is explained in a comment that names the old code.
    code = "\n".join(
        line for line in src.splitlines() if not line.strip().startswith("#")
    )
    assert "max(sim, 0.60)" not in code, "similarity floor must stay removed"
    assert '"similarity"] = sim' in code

    # NULL columns must not raise TypeError mid-generation.
    assert 'float(doc.get("freshness_score") or 1.0)' in code
    assert 'int(doc.get("usage_count") or 0)' in code


# ------------------------------------------------------- auto-publish claim

def test_auto_publish_claims_atomically_before_publishing():
    import inspect
    import agents.scheduler as sched

    src = inspect.getsource(sched.job_auto_publish_approval)
    assert '"publishing"' in src, "must claim the row before publishing"
    # the claim must be conditional on still being 'approved'
    assert '.eq("status", "approved")' in src
    # and released on failure so the row is not stranded
    assert '.eq("status", "publishing")' in src


def test_auto_publish_reports_real_published_count():
    import inspect
    import agents.scheduler as sched

    src = inspect.getsource(sched.job_auto_publish_approval)
    assert "return totals" in src, "must return a real count, not a 'cycle ran' flag"
