import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.agents.autonomous_decision_engine import AutonomousDecisionEngine


@pytest.mark.asyncio
async def test_scheduler_status():
    """Test GET /api/scheduler/status returns scheduled jobs and timezone."""
    from backend.agents.scheduler import start_scheduler
    start_scheduler()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/scheduler/status")
        assert res.status_code == 200
        data = res.json()
        assert data["timezone"] == "Asia/Kolkata"
        assert len(data.get("jobs", [])) >= 7


@pytest.mark.asyncio
async def test_decision_engine_should_run():
    """Test Decision Engine evaluation logic returns empirical status and rationale."""
    engine = AutonomousDecisionEngine()
    
    # Routine jobs
    res_search = await engine.should_run("daily_search")
    assert "should_run" in res_search
    assert "reason" in res_search

    res_seo = await engine.should_run("seo_report_aeo_tracking")
    assert res_seo["should_run"] is True


@pytest.mark.asyncio
async def test_quality_gate_enforcement():
    """Test Quality Gate rejects draft when SEO score or validation is substandard."""
    engine = AutonomousDecisionEngine()
    
    # Case 1: Low SEO score (< 85)
    gate_fail = await engine.check_quality_gate(
        blog_content="Draft content for car accidents",
        seo_score=78.0,
        validation_score=0.95,
        knowledge_similarity_avg=0.88
    )
    assert gate_fail["passed"] is False
    assert "SEO score" in gate_fail["reason"]

    # Case 2: Optimal scores (All passed)
    gate_pass = await engine.check_quality_gate(
        blog_content="In Texas, personal injury claims under Section 16.003 have a 2-year statute of limitations.",
        seo_score=92.0,
        validation_score=0.95,
        knowledge_similarity_avg=0.88
    )
    assert gate_pass["passed"] is True
    assert gate_pass["checks"]["seo_score_passed"] is True


@pytest.mark.asyncio
async def test_autonomous_settings_toggle():
    """Test updating and reading autonomous publishing settings."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Toggle auto_publish ON
        res_post = await client.post("/api/autonomous/settings", json={
            "auto_publish": True,
            "auto_generate": True,
            "auto_refresh": True
        })
        assert res_post.status_code == 200

        # Read back settings
        res_get = await client.get("/api/autonomous/settings")
        assert res_get.status_code == 200
        settings = res_get.json()
        assert settings["auto_publish"] is True


@pytest.mark.asyncio
async def test_cost_tracking_and_retry_queue():
    """Test tracking tokens in daily_costs and local retry queue."""
    engine = AutonomousDecisionEngine()
    
    # Cost tracking
    await engine.track_cost(agent_name="TestWriter", tokens=10000)
    
    # Retry queue
    engine.queue_job_for_retry(job_name="test_job", payload={"test": True}, error="Simulated Network Timeout")
    queue = engine.get_retry_queue()
    assert isinstance(queue, list)
    assert any(q.get("job_name") == "test_job" for q in queue)
