"""Dedicated event loop for background automation.

Every scheduled job (APScheduler), the autonomous health poller and the six
continuous monitoring loops used to run as tasks on the API's event loop. Those
jobs call the *synchronous* Supabase client inline, so each query blocked the
loop for the whole round trip and long jobs (the startup catch-up, knowledge
crawls, brain learning) starved request handling for tens of seconds. The
user-visible symptom: the moment a website was connected, the whole app — even
`GET /api/websites` and `/api/health` — appeared to hang.

Running automation on its own loop keeps the API loop free to serve requests.
The two loops share process state (the Supabase singleton, the local store), so
cross-loop primitives were made loop-agnostic first:

* ``services.event_bus`` routes delivery through each subscriber's loop.
* ``services.internal_link_service._GRAPH_LOCK`` is a thread lock, not an
  ``asyncio.Lock``.

The loops are isolated only for *scheduling*: request handlers still call the
same async services, they simply no longer contend with a job that is sitting on
a synchronous HTTP call.
"""

import asyncio
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger("backend.services.background_runtime")


def _spawn(coro, *, name: str):
    """Run a startup coroutine without losing it or swallowing its exception."""
    from utils.job_queue import spawn_background
    return spawn_background(coro, name=name)


def submit_background(coro, *, name: str) -> bool:
    """Schedule ``coro`` on the automation loop from any thread.

    FastAPI's ``BackgroundTasks`` run on the API loop *after* the response, so a
    post-connect onboarding/crawl used to re-block request handling the instant a
    website was created — the very moment the UI starts polling. Submitting here
    keeps that work off the API loop. Returns False when the runtime is disabled
    so the caller can fall back to its previous scheduling.
    """
    loop = _loop
    if loop is None or not loop.is_running():
        return False
    try:
        asyncio.run_coroutine_threadsafe(coro, loop)
        return True
    except Exception as e:
        logger.warning(f"[Background] submit '{name}' failed: {e}")
        return False

_thread: Optional[threading.Thread] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_ready = threading.Event()
_shutdown_requested = threading.Event()


def get_background_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Return the automation loop, or None when the runtime is not running."""
    return _loop


async def _run_migrations() -> None:
    from scripts.migrate import run_migrations

    def _work():
        try:
            run_migrations()
        except Exception as e:
            logger.warning(f"[Migrations] Startup migration warning: {e}")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _work)


MAX_RECOVERY_ATTEMPTS = 3


async def _recover_interrupted_jobs() -> None:
    try:
        await asyncio.sleep(5)
        from utils.job_queue import list_jobs, mark_failed
        from agents.scheduler import dispatch_onboarding

        interrupted = [j for j in list_jobs() if j.get("status") in ("pending", "running")]
        if not interrupted:
            return
        logger.info(f"[Startup] Recovering {len(interrupted)} interrupted background job(s)")
        for job in interrupted:
            job_id = job.get("job_id", "")
            kind = job.get("kind")
            payload = job.get("payload") or {}
            try:
                attempts = int(job.get("attempts") or 0)
            except (TypeError, ValueError):
                attempts = 0
            # A job that keeps crashing mid-flight used to re-run the KB crawl +
            # research + NIM generation after every single restart, forever.
            if attempts >= MAX_RECOVERY_ATTEMPTS:
                mark_failed(
                    job_id,
                    f"abandoned after {attempts} dispatch attempt(s); manual retry required",
                )
                logger.error(
                    f"[Startup] Job {job_id} ({kind}) exhausted {MAX_RECOVERY_ATTEMPTS} "
                    "dispatch attempts — marked failed, not retried"
                )
                continue
            if kind == "first_time_setup" and payload.get("website_id"):
                await dispatch_onboarding(
                    payload["website_id"],
                    payload.get("url") or "",
                    payload.get("account_id"),
                    bool(payload.get("has_wordpress")),
                )
            else:
                mark_failed(job_id, "unknown job kind after restart")
    except Exception as e:
        logger.warning(f"[Startup] Job recovery failed: {e}")


async def _recover_stale_crawls() -> None:
    try:
        await asyncio.sleep(8)
        from datetime import datetime, timedelta
        from services import local_store

        cutoff = datetime.utcnow() - timedelta(minutes=15)
        recovered = 0
        for site in local_store._load_json("websites.json"):
            if site.get("status") != "crawling":
                continue
            updated = site.get("updated_at") or site.get("created_at") or ""
            try:
                ts = datetime.fromisoformat(str(updated).replace("Z", "").split("+")[0])
            except Exception:
                ts = None
            if ts is None or ts < cutoff:
                local_store.save_local_website({
                    "id": site.get("id"),
                    "domain": site.get("domain"),
                    "status": "active",
                })
                recovered += 1
        if recovered:
            logger.info(f"[Startup] Cleared {recovered} stale 'crawling' website status(es)")
    except Exception as e:
        logger.warning(f"[Startup] Stale crawl recovery failed: {e}")


async def _restore_schedules() -> None:
    try:
        from database import get_supabase
        from agents.scheduler import scheduler, run_autonomous_blog_generation

        result = None
        try:
            result = get_supabase().table("autonomous_settings").select(
                "website_id, generation_interval_minutes, auto_generate_enabled, schedule_label, daily_blog_target, auto_generate"
            ).eq("auto_generate_enabled", True).execute()
        except Exception:
            try:
                result = get_supabase().table("autonomous_settings").select(
                    "website_id, generation_interval_minutes, schedule_label"
                ).limit(50).execute()
                if result.data:
                    result.data = [r for r in result.data if r.get("auto_generate_enabled") is not False]
            except Exception:
                result = None

        schedules = []
        if result and result.data:
            schedules = result.data
        else:
            import json as _json
            from pathlib import Path as _Path
            p = _Path(__file__).resolve().parent.parent / "local_data" / "blog_settings.json"
            if p.exists():
                try:
                    jdata = _json.loads(p.read_text(encoding="utf-8"))
                    for wid, vals in jdata.items():
                        schedules.append({
                            "website_id": wid,
                            "generation_interval_minutes": vals.get("generation_interval_minutes") or vals.get("interval_minutes") or 288,
                            "schedule_label": vals.get("schedule_label") or vals.get("label") or "default",
                            "auto_generate_enabled": vals.get("auto_generate_enabled", True),
                        })
                except Exception as e:
                    logger.warning("[Background] Schedule config parse failed: %s", e)

        for setting in (schedules or []):
            wid = setting.get("website_id")
            if not wid:
                continue
            interval = int(setting.get("generation_interval_minutes") or 288)
            label = setting.get("schedule_label") or f"every {interval} min"
            job_id = f"auto_blog_{wid}"
            try:
                scheduler.add_job(
                    func=run_autonomous_blog_generation,
                    trigger="interval",
                    minutes=interval,
                    id=job_id,
                    name=f"Auto Blog — {label} — {wid[:8]}",
                    replace_existing=True,
                    misfire_grace_time=120,
                )
                logger.info(f"[SCHEDULER] Restored: {job_id} every {interval} min ({label})")
            except Exception as e:
                logger.warning(f"[SCHEDULER] Failed to restore {job_id}: {e}")
    except Exception as e:
        logger.warning(f"[SCHEDULER] restore_schedules failed: {e}")


async def _bootstrap() -> None:
    """Bring up every background worker on the automation loop."""
    from services.autonomous_health_service import autonomous_health_service

    _spawn(_run_migrations(), name="startup:migrations")

    # NVIDIA NIM startup validation
    async def _validate_nim_bg():
        try:
            from database import validate_nim_connection
            nim_state = await validate_nim_connection(force=True)
            if nim_state.get("available"):
                logger.info(f"[NIM] {nim_state.get('diagnostic')}")
            else:
                logger.error(f"[NIM] UNAVAILABLE: {nim_state.get('diagnostic')} (HTTP {nim_state.get('http_status')})")
        except Exception as e:
            logger.error(f"[NIM] Startup validation crashed: {e}")

    _spawn(_validate_nim_bg(), name="startup:nim-validation")

    # Warm the connector-status live-check caches (NVIDIA + Serper) so the first
    # real page load does not pay a slow cold-cache probe.
    async def _warm_connector_caches():
        try:
            await asyncio.sleep(1)
            from routers.connectors import verify_serper_key
            serper_key = os.environ.get("SERPER_API_KEY", "")
            if serper_key:
                await verify_serper_key(serper_key)
            from database import is_nim_available
            await is_nim_available()
        except Exception as e:
            logger.debug(f"[Connectors] Cache warm-up note: {e}")

    _spawn(_warm_connector_caches(), name="startup:connector-cache")

    # Seed the knowledge-mirror dedup index (77 MB parse) off the loop.
    try:
        from services.local_store import _kb_dedup_seed
        asyncio.get_running_loop().run_in_executor(None, _kb_dedup_seed)
    except Exception as e:
        logger.debug(f"[local_store] dedup seed note: {e}")

    # Autonomous health service
    try:
        await autonomous_health_service.start()
        logger.info("[HealthService] Master autonomous health engine initialized.")
    except Exception as e:
        logger.error(f"[HealthService] Startup failed: {e}")

    # APScheduler — single scheduling authority (Asia/Kolkata)
    try:
        from agents.scheduler import setup_scheduler, get_scheduler_status, run_pending_daily_jobs

        sched = setup_scheduler()
        if not sched.running:
            sched.start()
        status = get_scheduler_status()
        logger.info(f"[Scheduler] Started ({len(status.get('jobs', []))} jobs registered in Asia/Kolkata):")
        for j in status.get("jobs", []):
            logger.info(f"  {j['name']} -> Next run: {j['next_run']}")

        async def _run_catchup():
            try:
                await asyncio.sleep(2)
                catchup = await run_pending_daily_jobs()
                if catchup.get("ran"):
                    logger.info(f"[Startup] Catch-up executed missed daily jobs: {catchup['ran']}")
            except Exception as e:
                logger.warning(f"[Startup] Daily job catch-up failed: {e}")

        _spawn(_run_catchup(), name="startup:daily-catchup")
        _spawn(_restore_schedules(), name="startup:restore-schedules")
        _spawn(_recover_interrupted_jobs(), name="startup:recover-jobs")
        _spawn(_recover_stale_crawls(), name="startup:recover-crawls")
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start: {e}")

    logger.info("[Startup] Backlink jobs delegated to APScheduler (single authority Asia/Kolkata)")

    # Continuous 24/7 monitoring engine (6 loops)
    try:
        from services.continuous_monitor import start_all_monitors
        start_all_monitors()
        logger.info("[ContinuousMonitor] 6 autonomous monitoring loops started (Rank, SERP, Competitor, Tech, Geo, Structure).")
    except Exception as e:
        logger.error(f"[ContinuousMonitor] Startup failed: {e}")

    # Keep the loop alive until shutdown is requested.
    while not _shutdown_requested.is_set():
        await asyncio.sleep(1)


async def _shutdown() -> None:
    from services.autonomous_health_service import autonomous_health_service

    try:
        from services.continuous_monitor import stop_all_monitors
        stop_all_monitors()
    except Exception as e:
        logger.warning("[Background] Monitor stop failed: %s", e)
    try:
        await autonomous_health_service.stop()
    except Exception as e:
        logger.warning("[Background] Health service stop failed: %s", e)
    try:
        from agents.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning("[Background] Scheduler stop failed: %s", e)
    try:
        from services.local_store import flush_local_store
        flush_local_store()
    except Exception as e:
        logger.warning("[Background] Local store flush failed: %s", e)


def _thread_main() -> None:
    global _loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop
    _loop_ready.set()
    try:
        loop.run_until_complete(_bootstrap())
    except Exception as e:
        logger.error(f"[Background] Runtime crashed: {e}")
    finally:
        try:
            loop.run_until_complete(_shutdown())
        except Exception as e:
            logger.warning(f"[Background] Shutdown error: {e}")
        try:
            loop.close()
        except Exception:
            pass
        _loop = None
        logger.info("[Background] Runtime stopped.")


def start_background_runtime() -> None:
    """Start the automation loop in a daemon thread (idempotent)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    if os.getenv("RANKFORGE_DISABLE_BACKGROUND") == "1":
        logger.warning("[Background] Runtime DISABLED via RANKFORGE_DISABLE_BACKGROUND")
        return
    _shutdown_requested.clear()
    _loop_ready.clear()
    _thread = threading.Thread(target=_thread_main, name="rankforge-background", daemon=True)
    _thread.start()
    # Give the loop a moment to start; not required for correctness, only so the
    # first request does not race the very first scheduled job.
    _loop_ready.wait(timeout=5)
    logger.info("[Background] Dedicated automation loop started (API event loop is isolated).")


def stop_background_runtime(timeout: float = 10.0) -> None:
    """Ask the automation loop to shut down and wait for the thread to exit."""
    global _thread
    _shutdown_requested.set()
    loop = _loop
    if loop is not None and loop.is_running():
        try:
            loop.call_soon_threadsafe(lambda: None)
        except Exception:
            pass
    if _thread is not None:
        _thread.join(timeout=timeout)
    _thread = None
