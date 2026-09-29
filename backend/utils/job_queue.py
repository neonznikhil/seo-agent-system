"""Durable background-job helpers.

Two problems this module solves for every background job in the backend:

1. Fire-and-forget tasks vanish. A bare ``asyncio.create_task(coro)`` drops its
   only reference, so CPython may garbage-collect the task mid-flight, and any
   exception it raises is never observed. ``spawn_background`` keeps a strong
   reference for the task's lifetime and logs the real exception (instead of
   silently swallowing it).

2. Jobs did not survive a restart. APScheduler uses its default in-memory
   jobstore, so a crash or redeploy silently dropped scheduled work. Jobs that
   must outlive the process are recorded in a small JSON-backed queue
   (``data/background_jobs.json``) and can be re-dispatched on startup.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("backend.utils.job_queue")

# Keep strong references to in-flight tasks so they are not garbage-collected
# before completion (the documented asyncio.create_task footgun).
_INFLIGHT: set = set()

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(_DATA_DIR, exist_ok=True)
_JOBS_FILE = os.path.join(_DATA_DIR, "background_jobs.json")


def spawn_background(
    coro: Awaitable[Any],
    *,
    name: str = "background-task",
    on_error: Optional[Callable[[BaseException], None]] = None,
) -> Optional[asyncio.Task]:
    """Run ``coro`` as a detached task without losing it.

    Returns the task (or ``None`` if there is no running loop). Unlike a bare
    ``create_task``, the task is retained until it finishes and any exception is
    logged with its traceback rather than being swallowed.
    """
    try:
        task = asyncio.ensure_future(coro)
    except RuntimeError as exc:
        logger.error(f"[job_queue] no running event loop for '{name}': {exc}")
        return None

    _INFLIGHT.add(task)

    def _finalize(t: asyncio.Task) -> None:
        _INFLIGHT.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error(f"[job_queue] background task '{name}' failed: {exc!r}", exc_info=exc)
            if on_error is not None:
                try:
                    on_error(exc)
                except Exception as hook_exc:  # never let the hook mask the failure
                    logger.error(f"[job_queue] on_error hook for '{name}' failed: {hook_exc}")

    task.add_done_callback(_finalize)
    return task


def inflight_count() -> int:
    return len(_INFLIGHT)


# ---------------------------------------------------------------------------
# Durable job queue
# ---------------------------------------------------------------------------

def _load_jobs() -> List[Dict[str, Any]]:
    if not os.path.exists(_JOBS_FILE):
        return []
    try:
        with open(_JOBS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning(f"[job_queue] could not read job queue: {exc}")
        return []


def _save_jobs(jobs: List[Dict[str, Any]]) -> None:
    try:
        tmp = f"{_JOBS_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(jobs, fh, indent=2, default=str)
        os.replace(tmp, _JOBS_FILE)
    except Exception as exc:
        logger.error(f"[job_queue] could not persist job queue: {exc}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_job(
    kind: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    job_id: Optional[str] = None,
    account_id: Optional[str] = None,
    website_id: Optional[str] = None,
) -> str:
    """Record a durable job as ``pending`` and return its id.

    Upserts by ``job_id`` so re-dispatching the same logical job does not pile
    up duplicates. Use a deterministic id (e.g. ``first_setup:<website>``) to
    make dispatch idempotent.
    """
    jid = job_id or uuid.uuid4().hex
    jobs = _load_jobs()
    existing = next((j for j in jobs if j.get("job_id") == jid), None)
    if existing is not None:
        existing.update({
            "kind": kind,
            "payload": payload or {},
            "status": "pending",
            "updated_at": _now(),
            "attempts": int(existing.get("attempts", 0)) + 1,
        })
        existing.pop("error", None)
    else:
        jobs.append({
            "job_id": jid,
            "kind": kind,
            "payload": payload or {},
            "account_id": account_id,
            "website_id": website_id,
            "status": "pending",
            "attempts": 1,
            "created_at": _now(),
            "updated_at": _now(),
        })
    _save_jobs(jobs)
    return jid


def mark_running(job_id: str) -> None:
    _update(job_id, status="running")


def mark_done(job_id: str) -> None:
    _update(job_id, status="done")


def mark_failed(job_id: str, error: str) -> None:
    _update(job_id, status="failed", error=str(error)[:500])


def _update(job_id: str, **fields: Any) -> None:
    jobs = _load_jobs()
    changed = False
    for job in jobs:
        if job.get("job_id") == job_id:
            job.update(fields)
            job["updated_at"] = _now()
            changed = True
            break
    if changed:
        _save_jobs(jobs)


def list_jobs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    jobs = _load_jobs()
    if status is None:
        return jobs
    return [j for j in jobs if j.get("status") == status]


def get_stats() -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for job in _load_jobs():
        key = str(job.get("status", "unknown"))
        stats[key] = stats.get(key, 0) + 1
    return stats
