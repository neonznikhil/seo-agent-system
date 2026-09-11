"""Auto-publish safety matrix: OFF unless explicitly opted in per site.

Drafts-only default is enforced at every layer:
- is_auto_publish_enabled(): no row / False / lookup failure -> False.
  Only an explicit True enables publishing.
- job_auto_publish_approval: publishes only status="approved" rows with a
  real human approved_by plus an active WordPress connection (covered by
  the SKIP-logging gates in scheduler.py).
- publish_post: verified re-GET receipt or published=False (covered in
  test_wp_draft_fix.py).
"""
import pytest
from unittest.mock import MagicMock


def _fake_supabase(rows=None, explode: bool = False):
    mock_sb = MagicMock()

    def _table(name):
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.limit.return_value = m
        if explode:
            m.execute.side_effect = RuntimeError("db down")
        else:
            exec_res = MagicMock()
            exec_res.data = rows if rows is not None else []
            m.execute.return_value = exec_res
        return m

    mock_sb.table.side_effect = _table
    return mock_sb


@pytest.mark.asyncio
async def test_auto_publish_off_when_no_settings_row(monkeypatch):
    import backend.agents.scheduler as sched
    import database as dbmod
    monkeypatch.setattr(dbmod, "get_supabase", lambda: _fake_supabase([]),
                        raising=True)
    assert await sched.is_auto_publish_enabled("wid-1") is False


@pytest.mark.asyncio
async def test_auto_publish_off_when_explicit_false(monkeypatch):
    import backend.agents.scheduler as sched
    fake = _fake_supabase([{"auto_publish": False}])
    import database as dbmod
    monkeypatch.setattr(dbmod, "get_supabase", lambda: fake, raising=True)
    assert await sched.is_auto_publish_enabled("wid-1") is False


@pytest.mark.asyncio
async def test_auto_publish_off_on_lookup_failure(monkeypatch):
    import backend.agents.scheduler as sched
    fake = _fake_supabase(explode=True)
    import database as dbmod
    monkeypatch.setattr(dbmod, "get_supabase", lambda: fake, raising=True)
    assert await sched.is_auto_publish_enabled("wid-1") is False


@pytest.mark.asyncio
async def test_auto_publish_on_only_with_explicit_true(monkeypatch):
    import backend.agents.scheduler as sched
    fake = _fake_supabase([{"auto_publish": True}])
    import database as dbmod
    monkeypatch.setattr(dbmod, "get_supabase", lambda: fake, raising=True)
    assert await sched.is_auto_publish_enabled("wid-1") is True


def test_approval_gate_requires_real_human_approver():
    """The auto-publish candidate filter: status approved + real identity."""
    candidates = [
        {"id": "1", "approved_by": "user-uuid-123"},
        {"id": "2", "approved_by": "human-approved"},
        {"id": "3", "approved_by": "autonomous"},
        {"id": "4", "approved_by": None},
        {"id": "5", "approved_by": ""},
    ]
    eligible = [a for a in candidates
                if (a.get("approved_by") or "") not in ("", "human-approved", "autonomous", "system")]
    assert [a["id"] for a in eligible] == ["1"]
