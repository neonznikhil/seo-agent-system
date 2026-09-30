"""Regression tests for durable content persistence.

Bugs covered:
  * save_local_content appended unconditionally, so a placeholder row plus the
    finished article produced two rows for one blog id (one empty "generating",
    one filled), and status lookups could return the empty one.
  * A run killed mid-flight left /crew/status reporting "generating" forever
    because nothing was written until the very end of generation.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from services.local_store import get_local_content, save_local_content


def test_save_local_content_upserts_by_id(tmp_path, monkeypatch):
    import services.local_store as ls

    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    blog_id = "dup-check-id"

    ls.save_local_content({"id": blog_id, "status": "generating", "content": ""})
    ls.save_local_content({"id": blog_id, "status": "draft", "content": "final body"})

    rows = [r for r in ls._load_json("content_log.json") if r.get("id") == blog_id]
    assert len(rows) == 1, "placeholder and final write must collapse into one row"
    assert rows[0]["status"] == "draft"
    assert rows[0]["content"] == "final body"


@pytest.mark.asyncio
async def test_stale_generating_row_reports_failed(tmp_path, monkeypatch):
    import services.local_store as ls

    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    blog_id = "stale-run-id"
    old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    ls.save_local_content({"id": blog_id, "status": "generating", "content": "", "created_at": old})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/crew/status/{blog_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["blog"] is not None
    assert data["blog"]["status"] == "failed"
    assert data["blog"]["pipeline_status"] == "stalled"


@pytest.mark.asyncio
async def test_live_slow_run_is_not_reported_failed(tmp_path, monkeypatch):
    """A genuinely running slow generation must stay "generating".

    Regression: the stale check used age alone, so a ~46-minute NIM run was
    flipped to failed/stalled while it was still producing content. Liveness must
    override age for a run this process is actively executing.
    """
    import services.local_store as ls

    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    blog_id = "live-slow-run-id"
    old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    ls.save_local_content({"id": blog_id, "status": "generating", "content": "", "created_at": old})
    ls.mark_run_active(blog_id)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/crew/status/{blog_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["blog"] is not None
        assert data["blog"]["status"] == "generating", "a live run must not be failed by age alone"
    finally:
        ls.mark_run_finished(blog_id)


@pytest.mark.asyncio
async def test_failed_generation_is_persisted_as_failed(tmp_path, monkeypatch):
    """A generation that raises must be written to storage as failed.

    Regression: the background runner only published a failure event; the row
    stayed "generating/running" in content_log.json forever, so listings kept
    advertising a dead run and only the status endpoint's age check masked it.
    """
    import services.local_store as ls

    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    blog_id = "fail-persist-id"
    ls.save_local_content({"id": blog_id, "status": "generating",
                           "pipeline_status": "running", "content": ""})

    class _Payload:
        blog_id = "fail-persist-id"
        topic = "x"  # too short -> the pipeline raises ValueError
        website_id = ""
        user_id = "tester"
        tone = "professional"
        word_count = 1000

    from routers.crew_writer import _run_generation
    await _run_generation(_Payload())

    row = ls.get_local_content(blog_id)
    assert row is not None
    assert row["status"] == "failed", "a raised generation must persist as failed"
    assert row["pipeline_status"] == "failed"
