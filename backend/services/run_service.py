"""Run envelopes: every major job reads its previous run and reports diffs.

Contract:
  run = await start_run(website_id, job_name)   # links previous_run_id
  ... do the work, build a snapshot dict ...
  out = await complete_run(run_id, snapshot, run["prev_snapshot"])
  # out = {"summary": str, "changes": {fixed,new,still_open,regressed}, ...}

Snapshots are plain JSON with an optional "issue_ids" list plus numeric
signals ("health_score", "indexation_rate"). Diffs classify:
  fixed      = in previous, absent now
  new        = absent before, present now
  still_open = in both
  regressed  = a tracked numeric signal dropped >10% (or an issue id
               explicitly marked worse by the caller via "worsened_ids").
Failed runs record status=failed + error and never invent a summary.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("backend.services.run_service")

try:
    from database import get_supabase
except (ImportError, ValueError):
    from backend.database import get_supabase

REGRESSED_DROP_FRACTION = 0.10
TRACKED_SIGNALS = ("health_score", "indexation_rate")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def start_run(website_id: str, job_name: str) -> Dict[str, Any]:
    """Open a run envelope linked to the previous completed run."""
    supabase = get_supabase()
    prev_run_id = None
    prev_snapshot = None
    try:
        prev = supabase.table("runs").select("id, snapshot").eq(
            "website_id", website_id).eq("job_name", job_name).eq(
            "status", "completed").order("completed_at", desc=True).limit(1).execute()
        rows = prev.data or []
        if rows:
            prev_run_id = rows[0].get("id")
            prev_snapshot = rows[0].get("snapshot")
    except Exception as e:
        logger.debug(f"[Runs] previous-run lookup note: {e}")

    try:
        ins = supabase.table("runs").insert({
            "website_id": website_id,
            "job_name": job_name,
            "previous_run_id": prev_run_id,
            "status": "running",
            "started_at": _utcnow(),
        }).execute()
        run_id = (ins.data or [{}])[0].get("id")
    except Exception as e:
        logger.warning(f"[Runs] start_run insert failed: {e}")
        run_id = None
    return {"run_id": run_id, "prev_run_id": prev_run_id, "prev_snapshot": prev_snapshot}


def compute_diff(snapshot: Optional[Dict[str, Any]],
                 prev_snapshot: Optional[Dict[str, Any]]) -> Dict[str, List[Any]]:
    """Pure diff: safe to unit-test without a database."""
    changes: Dict[str, List[Any]] = {"fixed": [], "new": [], "still_open": [], "regressed": []}
    if not prev_snapshot or not snapshot:
        return changes
    prev_issues = set(prev_snapshot.get("issue_ids", []) or [])
    curr_issues = set(snapshot.get("issue_ids", []) or [])
    changes["fixed"] = sorted(prev_issues - curr_issues)
    changes["new"] = sorted(curr_issues - prev_issues)
    changes["still_open"] = sorted(prev_issues & curr_issues)
    for key in TRACKED_SIGNALS:
        prev_val = prev_snapshot.get(key)
        curr_val = snapshot.get(key)
        try:
            if prev_val is not None and curr_val is not None:
                prev_f, curr_f = float(prev_val), float(curr_val)
                if prev_f > 0 and curr_f < prev_f * (1 - REGRESSED_DROP_FRACTION):
                    changes["regressed"].append(f"{key}: {prev_f:.2f} -> {curr_f:.2f}")
        except (TypeError, ValueError):
            continue
    for wid in snapshot.get("worsened_ids", []) or []:
        if wid in prev_issues and wid not in changes["regressed"]:
            changes["regressed"].append(wid)
    return changes


def build_summary(changes: Dict[str, List[Any]], job_name: str = "") -> str:
    parts = []
    if changes.get("fixed"):
        parts.append(f"{len(changes['fixed'])} issue(s) fixed")
    if changes.get("new"):
        parts.append(f"{len(changes['new'])} new issue(s) found")
    if changes.get("still_open"):
        parts.append(f"{len(changes['still_open'])} still open")
    if changes.get("regressed"):
        parts.append(f"{len(changes['regressed'])} regressed")
    body = ". ".join(parts) if parts else "No changes from previous run."
    prefix = f"{job_name}: " if job_name else ""
    return prefix + body + "."


def build_next_actions(changes: Dict[str, List[Any]]) -> List[str]:
    actions = []
    if changes.get("new"):
        actions.append(f"Investigate {len(changes['new'])} new issue(s)")
    if changes.get("regressed"):
        actions.append("Review regressed metric(s) urgently")
    if not changes.get("fixed") and changes.get("still_open"):
        actions.append(f"{len(changes['still_open'])} issue(s) remain unresolved from last run")
    return actions


async def complete_run(run_id: Optional[str], snapshot: Dict[str, Any],
                       prev_snapshot: Optional[Dict[str, Any]] = None,
                       job_name: str = "") -> Dict[str, Any]:
    """Close a run: diff, summarize, persist. run_id None = DB-less dry run."""
    changes = compute_diff(snapshot, prev_snapshot)
    summary = build_summary(changes, job_name)
    next_actions = build_next_actions(changes)
    if run_id:
        try:
            get_supabase().table("runs").update({
                "status": "completed",
                "completed_at": _utcnow(),
                "snapshot": snapshot,
                "summary": summary,
                "changes": changes,
                "fixed_count": len(changes["fixed"]),
                "new_count": len(changes["new"]),
                "still_open_count": len(changes["still_open"]),
                "regressed_count": len(changes["regressed"]),
                "next_actions": next_actions,
            }).eq("id", run_id).execute()
        except Exception as e:
            logger.warning(f"[Runs] complete_run update note: {e}")
    return {"run_id": run_id, "summary": summary, "changes": changes,
            "next_actions": next_actions}


async def fail_run(run_id: Optional[str], error: str) -> Dict[str, Any]:
    """Mark a run failed with the real error. Never invents a summary."""
    if run_id:
        try:
            get_supabase().table("runs").update({
                "status": "failed",
                "error": str(error)[:1000],
                "completed_at": _utcnow(),
            }).eq("id", run_id).execute()
        except Exception as e:
            logger.warning(f"[Runs] fail_run update note: {e}")
    return {"run_id": run_id, "status": "failed", "error": str(error)[:1000]}


async def generate_job_summary(run_id: str) -> str:
    """Written run summary for dashboards: what changed and what is next."""
    supabase = get_supabase()
    try:
        rows = supabase.table("runs").select("*").eq("id", run_id).limit(1).execute().data or []
    except Exception as e:
        return f"Run summary unavailable: {e}"
    if not rows:
        return "Run not found."
    r = rows[0]
    if r.get("status") == "failed":
        return f"Run: {r.get('job_name')} — failed. Error: {r.get('error') or 'unknown'}."
    parts = [f"Run: {r.get('job_name')} — {r.get('status')}"]
    if (r.get("fixed_count") or 0) > 0:
        parts.append(f"Fixed: {r['fixed_count']} issue(s) resolved since last run.")
    if (r.get("new_count") or 0) > 0:
        parts.append(f"New: {r['new_count']} new issue(s) found.")
    if (r.get("still_open_count") or 0) > 0:
        parts.append(f"Still open: {r['still_open_count']} unresolved.")
    if (r.get("regressed_count") or 0) > 0:
        parts.append(f"Regressed: {r['regressed_count']} metric(s) got worse.")
    if r.get("summary") and r["summary"] not in (" ".join(parts),):
        parts.append(r["summary"])
    if r.get("next_actions"):
        parts.append("Next: " + "; ".join(r["next_actions"]) + ".")
    return " ".join(parts)


async def get_last_run_summary(website_id: str, job_name: Optional[str] = None) -> Dict[str, Any]:
    """Latest run (optionally per job) shaped for the dashboard."""
    supabase = get_supabase()
    try:
        q = supabase.table("runs").select(
            "job_name, status, summary, fixed_count, new_count, still_open_count, "
            "regressed_count, next_actions, completed_at, error"
        ).eq("website_id", website_id).order("completed_at", desc=True).limit(1)
        if job_name:
            q = q.eq("job_name", job_name)
        rows = q.execute().data or []
    except Exception:
        rows = []
    if not rows:
        return {"summary": "No runs yet", "job_name": job_name, "status": None,
                "fixed": 0, "new": 0, "still_open": 0, "regressed": 0,
                "next_actions": [], "completed_at": None}
    r = rows[0]
    return {"summary": r.get("summary") or "No summary recorded",
            "job_name": r.get("job_name"), "status": r.get("status"),
            "fixed": r.get("fixed_count") or 0, "new": r.get("new_count") or 0,
            "still_open": r.get("still_open_count") or 0,
            "regressed": r.get("regressed_count") or 0,
            "next_actions": r.get("next_actions") or [],
            "completed_at": r.get("completed_at"),
            "error": r.get("error")}


async def get_recent_runs(website_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Last N runs for the dashboard history strip."""
    supabase = get_supabase()
    try:
        rows = supabase.table("runs").select(
            "job_name, status, summary, fixed_count, new_count, still_open_count, "
            "regressed_count, completed_at"
        ).eq("website_id", website_id).order("completed_at", desc=True).limit(
            max(1, min(limit, 20))).execute().data or []
    except Exception:
        rows = []
    return rows


async def run_with_envelope(website_id: str, job_name: str, work_fn,
                            snapshot_fn=None) -> Dict[str, Any]:
    """Retrofit helper: run async work_fn() inside a run envelope.

    work_fn: async callable returning the job's result dict.
    snapshot_fn: optional callable(result) -> snapshot dict. Defaults to
      {"issue_ids": result.get("issue_ids", [])} passthrough.
    On exception the run is marked failed and the error re-raised.
    The returned dict is the work result plus _run {run_id, summary, changes}.
    """
    run = await start_run(website_id, job_name)
    run_id = run["run_id"]
    try:
        result = await work_fn()
        if not isinstance(result, dict):
            result = {"result": result}
        try:
            snapshot = snapshot_fn(result) if snapshot_fn else {
                "issue_ids": list(result.get("issue_ids", []) or [])}
        except Exception:
            snapshot = {"issue_ids": []}
        # Carry tracked numeric signals through when the job reports them.
        for key in TRACKED_SIGNALS:
            if key in result and key not in snapshot:
                try:
                    snapshot[key] = float(result[key])
                except (TypeError, ValueError):
                    pass
        done = await complete_run(run_id, snapshot, run["prev_snapshot"], job_name)
        summary = done["summary"]
        # Honest no-data runs: an error result with no issues must not
        # report "No changes" as if a comparison happened.
        if result.get("error") and not snapshot.get("issue_ids"):
            summary = f"{job_name}: no data — {str(result['error'])[:200]}."
            if run_id:
                try:
                    get_supabase().table("runs").update(
                        {"summary": summary}).eq("id", run_id).execute()
                except Exception:
                    pass
        result["_run"] = {"run_id": run_id, "summary": summary,
                          "changes": done["changes"],
                          "next_actions": done["next_actions"]}
        return result
    except Exception as e:
        await fail_run(run_id, str(e))
        raise
