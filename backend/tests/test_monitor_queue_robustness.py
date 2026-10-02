"""Regression tests for monitor bookkeeping and durable-queue robustness.

Bugs covered, all verified by reading the call sites:

  * ``geo_monitor_loop`` never assigned ``last_website_id`` inside its website
    loop, so it called ``log_monitoring(website_id=None, ...)``.
    ``reporting_service.log_monitoring`` runs ``uuid.UUID(str(website_id))``
    inside a try and silently returns when it raises, so *every* GEO run wrote
    zero ``monitoring_logs`` rows and the dashboard showed GEO as never-run.
  * Every monitor loop reset ``issues_found = 0`` inside the per-website loop,
    so a multi-tenant cycle recorded only the last website's issues — and a
    final website that raised produced a ``status="completed"`` row claiming
    zero issues.
  * ``start_all_monitors()`` set ``_MONITORS_STARTED = True`` *before* spawning.
    A failed spawn (returns ``None``) therefore blocked every later call for the
    life of the process while the log still claimed all six loops started, and
    the guard was never cleared on shutdown.
  * ``auto_publisher_service.generate_queued_pages`` marked a queue row
    ``writing`` and then called ``generate_content`` unguarded. One exception
    stranded the row in ``writing`` — a status the selector never re-picks — and
    silently skipped every remaining item.
  * ``_recover_interrupted_jobs`` re-dispatched every ``pending``/``running``
    job on every startup with no attempt cap, so a job that crashes mid-flight
    re-ran the KB crawl + research + NIM generation after every restart forever.
  * ``utils.job_queue`` did an unlocked load -> mutate -> save with a fixed
    ``background_jobs.json.tmp`` name, so two concurrent website connects lost
    one job record entirely (and on Windows the shared temp name raised
    ``PermissionError``, which was swallowed).
"""

import asyncio
import os
import threading
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import continuous_monitor as cm
from services import background_runtime as br


# --------------------------------------------------------------- helpers


class _StopLoop(Exception):
    """Sentinel used to break a monitor's ``while True`` after one cycle."""


class _SleepOnceThenStop:
    """Replace ``asyncio.sleep`` so the next loop iteration raises ``_StopLoop``."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise _StopLoop("one cycle is enough")
        await asyncio.sleep(0)


@pytest.fixture(autouse=True)
def _reset_monitor_guard():
    """Keep the module-level start guard out of other tests' way."""
    cm._MONITORS_STARTED = False
    cm._MONITOR_TASKS.clear()
    yield
    cm._MONITORS_STARTED = False
    cm._MONITOR_TASKS.clear()


def _uuid(i: int) -> str:
    return str(uuid.UUID(int=i, version=4))


def _websites_supabase(*ids: str):
    """A supabase stub whose only table is ``websites``."""
    rows = [{"id": wid, "domain": f"site-{i}.com"} for i, wid in enumerate(ids, start=1)]
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=rows)
    return supabase


class _FakeGeoMonitor:
    """Behaviour table keyed by website_id; an Exception value means 'raise'."""

    behaviours: dict = {}

    def __init__(self, website_id):
        self.website_id = website_id

    async def get_local_keywords(self, limit: int = 10):
        behaviour = self.behaviours.get(self.website_id, {"keywords": []})
        if isinstance(behaviour, Exception):
            raise behaviour
        return behaviour["keywords"]

    async def get_geo_rank(self, keyword, city=None):
        # > 20 with a 4.0+ GMB rating triggers one geo_opportunity per keyword
        return 25

    async def get_gmb_signal(self, keyword):
        return {"rating": 4.5}


async def _run_geo_cycle(ids, behaviours):
    """Run exactly one ``geo_monitor_loop`` cycle; return the log_monitoring calls."""
    _FakeGeoMonitor.behaviours = behaviours
    log_calls = []
    sleeper = _SleepOnceThenStop()

    with patch.object(cm, "get_supabase", return_value=_websites_supabase(*ids)), \
         patch("services.monitors.geo_monitor.GEOMonitor", _FakeGeoMonitor), \
         patch("services.reporting_service.log_monitoring",
               new=AsyncMock(side_effect=lambda **kw: log_calls.append(kw))), \
         patch("services.reporting_service.report_problem", new=AsyncMock()), \
         patch.object(asyncio, "sleep", new=sleeper):
        with pytest.raises(_StopLoop):
            await cm.geo_monitor_loop()

    return log_calls


# --------------------------------------------------------------- Task 1 + 2


@pytest.mark.asyncio
async def test_geo_monitor_records_a_row_with_a_real_website_id():
    """Task 1: website_id was never assigned, so log_monitoring silently dropped it."""
    a, b = _uuid(1), _uuid(2)
    calls = await _run_geo_cycle(
        (a, b),
        {a: {"keywords": [{"keyword": "houston car accident lawyer", "city": "Houston"}]},
         b: {"keywords": [{"keyword": "truck accident attorney houston", "city": "Houston"}]}},
    )

    assert len(calls) == 1, "one monitoring record per cycle"
    record = calls[0]
    assert record["monitor_type"] == "geo_monitor"
    assert record["status"] == "completed"
    # A real UUID, never None: log_monitoring() drops the row on an invalid id.
    assert record["website_id"] == b
    assert uuid.UUID(record["website_id"])
    assert record["issues_found"] > 0


@pytest.mark.asyncio
async def test_monitor_issues_are_summed_across_websites():
    """Task 2: the per-website reset meant only the last site's issues were counted."""
    a, b = _uuid(11), _uuid(12)
    calls = await _run_geo_cycle(
        (a, b),
        {
            a: {"keywords": [
                {"keyword": "houston car accident lawyer", "city": "Houston"},
                {"keyword": "houston slip and fall lawyer", "city": "Houston",
                 "NAP_inconsistent": True},
            ]},
            b: {"keywords": [{"keyword": "truck accident attorney houston", "city": "Houston"}]},
        },
    )

    record = calls[0]
    # A: kw1 -> 1 geo_opportunity, kw2 -> 1 geo_opportunity + 1 nap_issue = 3.
    # B: kw1 -> 1 geo_opportunity. Total 4, not 1.
    assert record["issues_found"] == 4, (
        "cycle total must accumulate across websites, not reset per website"
    )
    assert record["checked_urls"] == 20  # 2 websites * 10


@pytest.mark.asyncio
async def test_raising_website_does_not_zero_the_recorded_issue_count():
    """Task 2: a site that raised used to leave a 'completed' row with issues_found=0."""
    a, b = _uuid(21), _uuid(22)
    calls = await _run_geo_cycle(
        (a, b),
        {
            a: {"keywords": [
                {"keyword": "houston car accident lawyer", "city": "Houston"},
                {"keyword": "houston slip and fall lawyer", "city": "Houston",
                 "NAP_inconsistent": True},
            ]},
            b: RuntimeError("SERPER circuit open"),
        },
    )

    record = calls[0]
    assert record["status"] == "completed"
    assert record["issues_found"] == 3, "issues found before the failure must survive"


# --------------------------------------------------------------- Task 3


def test_start_all_monitors_does_not_set_the_guard_when_a_spawn_fails():
    """The guard was set before spawning, so one failure disabled monitoring forever."""

    def _fake_spawn(coro, *, name="background-task", on_error=None):
        coro.close()  # nothing will await it; keep pytest clean
        return None

    with patch("utils.job_queue.spawn_background", new=_fake_spawn):
        cm.start_all_monitors()

    assert cm._MONITORS_STARTED is False, (
        "a failed spawn must leave the guard clear so a later call can retry"
    )
    assert cm._MONITOR_TASKS == []


def test_start_all_monitors_sets_the_guard_only_after_all_six_spawn():
    tasks = []
    names = []

    def _fake_spawn(coro, *, name="background-task", on_error=None):
        coro.close()
        names.append(name)
        task = MagicMock()
        tasks.append(task)
        return task

    with patch("utils.job_queue.spawn_background", new=_fake_spawn):
        cm.start_all_monitors()
        assert cm._MONITORS_STARTED is True
        assert len(names) == 6
        # Idempotency guard still holds (no double registration of 12 loops).
        cm.start_all_monitors()

    assert len(names) == 6, "a second call must not register another six loops"
    assert cm._MONITOR_TASKS == tasks


def test_stop_all_monitors_cancels_and_clears_the_guard():
    task = MagicMock()
    cm._MONITOR_TASKS.append(task)
    cm._MONITORS_STARTED = True

    cm.stop_all_monitors()

    task.cancel.assert_called_once()
    assert cm._MONITORS_STARTED is False
    assert cm._MONITOR_TASKS == []


# --------------------------------------------------------------- Task 4


class _FakeQuery:
    """Minimal PostgREST-ish query builder over an in-memory table."""

    def __init__(self, store: dict, table: str):
        self._store = store
        self._table = table
        self._op = "select"
        self._payload = None
        self._filters = []
        self._limit = None
        self._single = False

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = dict(payload)
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def in_(self, col, vals):
        self._filters.append((col, tuple(vals)))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        self._single = True
        return self

    def _match(self, row):
        for col, val in self._filters:
            if isinstance(val, tuple):
                if row.get(col) not in val:
                    return False
            elif row.get(col) != val:
                return False
        return True

    def execute(self):
        rows = self._store.setdefault(self._table, [])
        if self._op == "update":
            matched = [r for r in rows if self._match(r)]
            for r in matched:
                r.update(self._payload)
            self._store.setdefault("updates", []).append({
                "table": self._table,
                "filters": list(self._filters),
                "payload": dict(self._payload),
                "matched": len(matched),
            })
            return MagicMock(data=matched)
        matched = [r for r in rows if self._match(r)]
        if self._limit:
            matched = matched[: self._limit]
        if self._single:
            return MagicMock(data=(matched[0] if matched else None))
        return MagicMock(data=matched)


class _FakeSupabase:
    def __init__(self, store: dict):
        self._store = store

    def table(self, name):
        return _FakeQuery(self._store, name)


def _queue_store():
    return {
        "brain_auto_pages_queue": [
            {"id": "row-1", "website_id": "wid", "primary_keyword": "houston accident lawyer",
             "suggested_topic": "Houston accident guide", "status": "queued_for_writing",
             "priority_score": 90},
            {"id": "row-2", "website_id": "wid", "primary_keyword": "houston truck lawyer",
             "suggested_topic": "Houston truck guide", "status": "queued_for_writing",
             "priority_score": 50},
        ],
        "content_log": [],
    }


@pytest.mark.asyncio
async def test_crashing_generation_does_not_strand_a_row_in_writing():
    """Task 4: 'writing' is never re-selected, so a crash dropped the keyword forever."""
    from services.auto_publisher_service import generate_queued_pages

    store = _queue_store()
    supabase = _FakeSupabase(store)

    async def _boom(**_kwargs):
        raise RuntimeError("NIM cold-start timeout")

    with patch("database.get_supabase", return_value=supabase), \
         patch("routers.settings.get_global_setting", return_value="on"), \
         patch("agents.writer_agent.generate_content", new=AsyncMock(side_effect=_boom)), \
         patch("agents.seo_agent.SEOAgent", MagicMock()), \
         patch("services.seo_quality_gate.validate_content", new=AsyncMock()), \
         patch("services.brain_service.BrainService", MagicMock()):
        result = await generate_queued_pages("wid", limit=2)

    assert result["processed"] == 2, "the batch must continue past a failing item"
    assert result["failed"] == 2, "each crash must be counted, not swallowed"

    for row in store["brain_auto_pages_queue"]:
        assert row["status"] != "writing", (
            f"row {row['id']} stranded in 'writing': never re-selected, never retried"
        )
        assert row["status"] == "failed"
        assert "NIM cold-start timeout" in row.get("reason", "")


@pytest.mark.asyncio
async def test_finally_releases_a_row_left_in_writing_when_the_failure_write_itself_raises():
    """A failure while recording the failure must still leave the row re-runnable."""
    from services.auto_publisher_service import generate_queued_pages

    store = _queue_store()
    supabase = _FakeSupabase(store)
    real_table = supabase.table

    def _table(name):
        q = real_table(name)
        if name != "brain_auto_pages_queue":
            return q
        real_execute = q.execute

        def _execute():
            # The 'failed' write explodes (Supabase outage); the release must not.
            if q._op == "update" and q._payload and q._payload.get("status") == "failed":
                raise RuntimeError("supabase write failed")
            return real_execute()

        q.execute = _execute
        return q

    async def _boom(**_kwargs):
        raise RuntimeError("writer exploded")

    supabase.table = _table

    with patch("database.get_supabase", return_value=supabase), \
         patch("routers.settings.get_global_setting", return_value="on"), \
         patch("agents.writer_agent.generate_content", new=AsyncMock(side_effect=_boom)), \
         patch("agents.seo_agent.SEOAgent", MagicMock()), \
         patch("services.seo_quality_gate.validate_content", new=AsyncMock()), \
         patch("services.brain_service.BrainService", MagicMock()):
        result = await generate_queued_pages("wid", limit=2)

    assert result["failed"] == 2
    statuses = {r["id"]: r["status"] for r in store["brain_auto_pages_queue"]}
    assert set(statuses.values()) == {"queued_for_writing"}, (
        f"rows must be released back to a re-runnable status, got {statuses}"
    )


@pytest.mark.asyncio
async def test_successful_item_is_not_reverted_by_the_release_net():
    """The 'writing' release is conditional: a staged row must stay pending_approval."""
    from services.auto_publisher_service import generate_queued_pages

    store = _queue_store()
    store["content_log"] = [{"id": "c1", "title": "T", "content": "x" * 400}]
    supabase = _FakeSupabase(store)

    async def _gen(**_kwargs):
        return {"content_id": "c1", "status": "completed"}

    seo_agent = MagicMock(return_value=MagicMock(run=AsyncMock(return_value={
        "meta_description": "d", "seo_title": "t", "slug": "s",
    })))
    brain = MagicMock(return_value=MagicMock(remember=AsyncMock()))

    with patch("database.get_supabase", return_value=supabase), \
         patch("routers.settings.get_global_setting", return_value="on"), \
         patch("agents.writer_agent.generate_content", new=AsyncMock(side_effect=_gen)), \
         patch("agents.seo_agent.SEOAgent", seo_agent), \
         patch("services.seo_quality_gate.validate_content",
               new=AsyncMock(return_value={"passed": True, "score": 91, "issues": [],
                                           "threshold": 80})), \
         patch("services.auto_publisher_service._stage_for_approval", new=AsyncMock()), \
         patch("services.brain_service.BrainService", brain):
        result = await generate_queued_pages("wid", limit=2)

    assert result["staged_for_approval"] == 2
    statuses = {r["id"] for r in store["brain_auto_pages_queue"] if r["status"] == "pending_approval"}
    assert statuses == {"row-1", "row-2"}, "the release net must not undo a staged item"


# --------------------------------------------------------------- Task 6


@pytest.mark.asyncio
async def test_recovery_abandons_a_job_after_the_attempt_cap():
    """A job that crashes mid-flight used to re-run forever, once per restart."""
    job = {
        "job_id": "first_setup:wid-crash",
        "kind": "first_time_setup",
        "status": "running",
        "attempts": br.MAX_RECOVERY_ATTEMPTS,
        "payload": {"website_id": "wid-crash", "url": "https://x.com"},
    }

    with patch("utils.job_queue.list_jobs", return_value=[job]), \
         patch("utils.job_queue.mark_failed") as failed, \
         patch("agents.scheduler.dispatch_onboarding", new=AsyncMock()) as dispatched, \
         patch.object(asyncio, "sleep", new=AsyncMock()):
        await br._recover_interrupted_jobs()

    dispatched.assert_not_called()
    failed.assert_called_once()
    assert failed.call_args.args[0] == "first_setup:wid-crash"
    assert "dispatch attempt" in failed.call_args.args[1]


@pytest.mark.asyncio
async def test_recovery_still_dispatches_jobs_under_the_cap():
    job = {
        "job_id": "first_setup:wid-ok",
        "kind": "first_time_setup",
        "status": "pending",
        "attempts": 1,
        "payload": {"website_id": "wid-ok", "url": "https://ok.com", "account_id": "a1"},
    }

    with patch("utils.job_queue.list_jobs", return_value=[job]), \
         patch("utils.job_queue.mark_failed") as failed, \
         patch("agents.scheduler.dispatch_onboarding", new=AsyncMock()) as dispatched, \
         patch.object(asyncio, "sleep", new=AsyncMock()):
        await br._recover_interrupted_jobs()

    failed.assert_not_called()
    dispatched.assert_awaited_once()
    assert dispatched.await_args.args[0] == "wid-ok"


# --------------------------------------------------------------- Task 10


def _aeo_agent(monkeypatch, insert_side_effect=None):
    from agents.aeo_agent import AEOAgent

    inserted = []

    def _table(name):
        q = MagicMock()
        if name == "websites":
            q.select.return_value.eq.return_value.single.return_value.execute.return_value = \
                MagicMock(data={"domain": "example.com", "url": "https://example.com",
                                "niche": "legal"})
        elif name == "aeo_citations":
            def _insert(row):
                inserted.append(row)
                if insert_side_effect is not None:
                    raise insert_side_effect
                return MagicMock(execute=MagicMock())

            q.insert.side_effect = _insert
        return q

    supabase = MagicMock()
    supabase.table.side_effect = _table
    # aeo_agent binds these into its own module namespace at import time.
    monkeypatch.setattr("agents.aeo_agent.get_supabase", lambda: supabase)
    monkeypatch.setattr(
        "agents.aeo_agent.call_nim_llm",
        AsyncMock(return_value="Example Law Firm is the recommended provider."),
    )
    monkeypatch.setattr(
        "services.serper_service.serper_service.search",
        AsyncMock(return_value={"answerBox": {}, "peopleAlsoAsk": []}),
    )
    return AEOAgent(website_id="wid-aeo"), inserted


@pytest.mark.asyncio
async def test_aeo_does_not_count_or_report_a_citation_that_failed_to_persist(monkeypatch):
    """A failed insert must not inflate the citation list or the SoV numerator."""
    agent, inserted = _aeo_agent(monkeypatch, insert_side_effect=RuntimeError("PGRST403"))

    out = await agent.track_buyer_intent_queries(["best houston accident lawyer"])

    assert len(inserted) == 1, "the row was built and the insert attempted"
    assert out["citations"] == [], "a citation that never persisted must not be reported"
    assert out["citations_recorded"] == 0
    assert out["citations_failed"] == 1
    assert out["sov_percentage"] == 0.0, "SoV must come from persisted citations only"
    assert out["queries_tracked"] == 1, "the query was still evaluated and is reported"


@pytest.mark.asyncio
async def test_aeo_counts_and_reports_citations_that_did_persist(monkeypatch):
    agent, inserted = _aeo_agent(monkeypatch)

    out = await agent.track_buyer_intent_queries(
        ["best houston accident lawyer", "houston slip and fall lawyer"]
    )

    assert len(inserted) == 2
    assert out["citations_recorded"] == 2
    assert out["citations_failed"] == 0
    assert out["sov_percentage"] == 100.0


# --------------------------------------------------------------- Task 7


@pytest.fixture
def _jobs_file(tmp_path, monkeypatch):
    import utils.job_queue as jq

    path = str(tmp_path / "background_jobs.json")
    monkeypatch.setattr(jq, "_JOBS_FILE", path)
    return path


def test_concurrent_register_job_keeps_every_record(_jobs_file):
    """Two website connects used to race: the second save discarded the first job."""
    import utils.job_queue as jq

    threads = 12
    barrier = threading.Barrier(threads)
    errors = []

    def _register(i):
        try:
            barrier.wait(timeout=30)
            jq.register_job("first_time_setup", {"website_id": f"wid-{i}"},
                            job_id=f"first_setup:wid-{i}")
        except Exception as exc:  # pragma: no cover - only on a barrier timeout
            errors.append(exc)

    workers = [threading.Thread(target=_register, args=(i,)) for i in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=20)

    assert not errors, errors
    jobs = jq.list_jobs()
    ids = {j["job_id"] for j in jobs}
    assert ids == {f"first_setup:wid-{i}" for i in range(threads)}, (
        f"lost job records: {sorted(ids)}"
    )

    leftovers = [f for f in os.listdir(os.path.dirname(_jobs_file)) if f.endswith(".tmp")]
    assert leftovers == [], f"temp files left behind: {leftovers}"


def test_save_jobs_uses_a_unique_temp_name_per_writer():
    import inspect

    import utils.job_queue as jq

    src = inspect.getsource(jq._save_jobs)
    assert 'f"{_JOBS_FILE}.tmp"' not in src, "shared temp name must stay removed"
    assert "uuid.uuid4" in src


def test_save_jobs_cleans_up_its_temp_file_when_the_replace_fails():
    import utils.job_queue as jq

    seen = {}

    real_open = open

    def _spy(path, *args, **kwargs):
        seen["tmp"] = path
        return real_open(path, *args, **kwargs)

    with patch("builtins.open", new=_spy), \
         patch("os.replace", side_effect=PermissionError("file in use")):
        jq._save_jobs([{"job_id": "x"}])

    assert seen.get("tmp", "").endswith(".tmp")
    assert not os.path.exists(seen["tmp"]), "a failed write must not leave a stale temp file"


def test_update_and_register_share_the_same_lock(_jobs_file):
    """mark_done() must not clobber a concurrent register_job()'s record."""
    import utils.job_queue as jq

    jq.register_job("first_time_setup", {"website_id": "wid"}, job_id="j1")
    jq.mark_done("j1")

    barrier = threading.Barrier(2)
    errors = []

    def _mark():
        try:
            barrier.wait(timeout=30)
            jq.mark_running("j1")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    def _register():
        try:
            barrier.wait(timeout=30)
            jq.register_job("first_time_setup", {"website_id": "wid2"}, job_id="j2")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    t1 = threading.Thread(target=_mark)
    t2 = threading.Thread(target=_register)
    t1.start()
    t2.start()
    t1.join(timeout=20)
    t2.join(timeout=20)

    assert not errors, errors
    assert {j["job_id"] for j in jq.list_jobs()} == {"j1", "j2"}
