"""Indexation tracking: how much of the site Google actually indexes.

Data flow: GSC sitemaps API (submitted/valid counts) when credentials
exist, else sitemap URL count only (submitted known, indexed unknown).
Every check persists to indexation_checks. The gate (indexation_gate_check)
is consulted BEFORE content generation: below-threshold sites pause new
drafts and get internal-link / crawl-fix tasks instead.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("backend.services.indexation")

try:
    from seo_constants import INDEXATION_GATE_THRESHOLD
except (ImportError, ValueError):
    try:
        from backend.seo_constants import INDEXATION_GATE_THRESHOLD
    except (ImportError, ValueError):
        INDEXATION_GATE_THRESHOLD = 0.80

try:
    from database import get_supabase
except (ImportError, ValueError):
    from backend.database import get_supabase


SITEMAP_CANDIDATES = [
    "/wp-sitemap.xml",
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
]


async def get_site_indexation_threshold(website_id: str) -> float:
    """Per-site threshold override, else the global default (0.80).

    Accepts both `indexation_threshold` and `indexation_min_rate` column
    names (plus either key inside goals JSON): schema revisions have used
    both, and a silently-ignored override would be worse than supporting
    both spellings.
    """
    try:
        supabase = get_supabase()
        # select("*"): schema revisions created different threshold column
        # spellings; naming a missing column would fail the whole query.
        rows = supabase.table("autonomous_settings").select(
            "*"
        ).eq("website_id", website_id).limit(1).execute().data or []
        if rows:
            row = rows[0]
            for key in ("indexation_threshold", "indexation_min_rate"):
                direct = row.get(key)
                if direct is not None:
                    return max(0.0, min(1.0, float(direct)))
            goals = row.get("goals") or {}
            for key in ("indexation_threshold", "indexation_min_rate"):
                if goals.get(key) is not None:
                    return max(0.0, min(1.0, float(goals[key])))
    except Exception as e:
        logger.debug(f"[Indexation] threshold lookup note: {e}")
    return INDEXATION_GATE_THRESHOLD


async def crawl_sitemap_urls(site_url: str, cap: int = 5000) -> List[str]:
    """Parse the site's sitemap (following index nesting) and return page URLs."""
    import httpx
    import xml.etree.ElementTree as ET

    base = (site_url or "").rstrip("/")
    if not base:
        return []
    if not base.startswith("http"):
        base = f"https://{base}"

    timeout = httpx.Timeout(20.0, connect=10.0)
    urls: List[str] = []
    seen_sitemaps: set = set()

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                 headers={"User-Agent": "RankForge-Indexation/1.0"}) as client:
        async def fetch_text(url: str) -> Optional[str]:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.text:
                    return resp.text
            except Exception as e:
                logger.debug(f"[Indexation] sitemap fetch note {url}: {e}")
            return None

        queue: List[str] = [base + c for c in SITEMAP_CANDIDATES]
        sitemap_url = None
        root_text = None
        for candidate in queue:
            root_text = await fetch_text(candidate)
            if root_text and ("<url" in root_text or "<sitemap" in root_text):
                sitemap_url = candidate
                break
        if not root_text:
            return []

        def local(tag: str) -> str:
            return tag.split("}", 1)[-1] if "}" in tag else tag

        pending_docs = [root_text]
        while pending_docs and len(urls) < cap:
            doc = pending_docs.pop(0)
            try:
                root = ET.fromstring(doc)
            except Exception:
                continue
            for child in root:
                name = local(child.tag).lower()
                if name == "sitemap":
                    for sub in child:
                        if local(sub.tag).lower() == "loc" and sub.text:
                            loc = sub.text.strip()
                            if loc and loc not in seen_sitemaps and len(seen_sitemaps) < 50:
                                seen_sitemaps.add(loc)
                                sub_text = await fetch_text(loc)
                                if sub_text:
                                    pending_docs.append(sub_text)
                elif name == "url":
                    for sub in child:
                        if local(sub.tag).lower() == "loc" and sub.text:
                            urls.append(sub.text.strip())
                            if len(urls) >= cap:
                                break
    return urls


def _site_base_url(site_row: Dict[str, Any]) -> str:
    raw = (site_row.get("url") or site_row.get("domain") or site_row.get("wordpress_url") or "").strip()
    raw = raw.rstrip("/")
    if raw and not raw.startswith("http"):
        raw = f"https://{raw}"
    return raw


async def check_indexation(website_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Run one indexation check for a site and persist it.

    Uses the GSC sitemaps API when credentials exist (submitted_count /
    valid_count per sitemap — the real GSCService.get_sitemaps shape).
    Falls back to sitemap URL counting (submitted known, indexed unknown).
    gate_passed is None (not False) when the rate is unknown.
    """
    supabase = get_supabase()
    result: Dict[str, Any] = {
        "website_id": website_id,
        "run_id": run_id,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "submitted_pages": 0,
        "indexed_pages": 0,
        "indexation_rate": None,
        "gsc_connected": False,
        "method": "unavailable",
    }

    try:
        site_rows = supabase.table("websites").select(
            "id, url, domain, wordpress_url"
        ).eq("id", website_id).limit(1).execute().data or []
    except Exception as e:
        logger.warning(f"[Indexation] site lookup failed: {e}")
        return {"error": f"Site lookup failed: {e}", **result}
    if not site_rows:
        return {"error": "Site not found", **result}
    site_url = _site_base_url(site_rows[0])
    if not site_url:
        return {"error": "Site has no URL/domain configured", **result}

    # Path 1: GSC sitemaps API (real submitted/valid counts).
    sitemap_url = None
    try:
        try:
            from services.gsc_service import GSCService
        except (ImportError, ValueError):
            from backend.services.gsc_service import GSCService
        gsc = GSCService(website_url=site_url)
        if gsc.is_connected():
            sm = await gsc.get_sitemaps()
            sitemaps = sm.get("sitemaps", []) if isinstance(sm, dict) else []
            if sitemaps:
                result["gsc_connected"] = True
                result["method"] = "gsc_sitemap_api"
                total_submitted = sum(int(s.get("submitted_count") or 0) for s in sitemaps)
                total_indexed = sum(int(s.get("valid_count") or 0) for s in sitemaps)
                result["submitted_pages"] = total_submitted
                result["indexed_pages"] = total_indexed
                result["sitemap_url"] = sitemaps[0].get("url")
                if total_submitted > 0:
                    result["indexation_rate"] = round(total_indexed / total_submitted, 4)
    except Exception as e:
        logger.warning(f"[Indexation] GSC sitemaps note: {e}. Falling back to sitemap parse.")

    # Path 2: sitemap URL count (submitted known, indexed unknown).
    if result["indexation_rate"] is None:
        try:
            pages = await crawl_sitemap_urls(site_url)
            if pages:
                result["submitted_pages"] = len(pages)
                result["method"] = "sitemap_count_only" if not result["gsc_connected"] else result["method"]
                result["note"] = ("GSC not connected. Submitted count from sitemap only. "
                                  "Connect GSC for indexed count.")
            elif not result["gsc_connected"]:
                result["method"] = "unavailable"
                result["note"] = "No sitemap found and GSC not connected. Nothing to measure."
        except Exception as e:
            logger.warning(f"[Indexation] sitemap parse note: {e}")

    threshold = await get_site_indexation_threshold(website_id)
    result["threshold"] = threshold
    if result["indexation_rate"] is not None:
        result["gate_passed"] = bool(result["indexation_rate"] >= threshold)
    else:
        result["gate_passed"] = None  # Unknown — must not be treated as False.

    # Run envelope: consecutive checks diff the rate (regressed on >10% drop).
    try:
        from services.run_service import start_run, complete_run
    except (ImportError, ValueError):
        from backend.services.run_service import start_run, complete_run
    _run = None
    _prev_snapshot = None
    if not run_id:
        try:
            _run = await start_run(website_id, "indexation_check")
            run_id = _run["run_id"]
            _prev_snapshot = _run["prev_snapshot"]
            result["run_id"] = run_id
        except Exception as e:
            logger.debug(f"[Indexation] run envelope note: {e}")
    if run_id:
        try:
            _snap = {}
            if result["indexation_rate"] is not None:
                _snap["indexation_rate"] = float(result["indexation_rate"])
            _done = await complete_run(run_id, _snap, _prev_snapshot, "indexation_check")
            result["_run"] = {"run_id": run_id, "summary": _done["summary"],
                              "changes": _done["changes"],
                              "next_actions": _done["next_actions"]}
        except Exception as e:
            logger.debug(f"[Indexation] run complete note: {e}")

    try:
        insertable = {k: v for k, v in result.items()
                      if k in ("website_id", "run_id", "checked_at", "submitted_pages",
                               "indexed_pages", "indexation_rate", "not_indexed_urls",
                               "sitemap_url", "gsc_connected", "method", "threshold",
                               "gate_passed", "action_taken")}
        supabase.table("indexation_checks").insert(insertable).execute()
    except Exception as e:
        logger.warning(f"[Indexation] persist note: {e}")

    try:
        from services.local_store import save_local_indexation_check
        save_local_indexation_check(result)
    except Exception:
        pass

    return result


async def create_indexation_fix_tasks(website_id: str, check: Dict[str, Any]) -> int:
    """Create internal-link / crawl-fix tasks instead of new content tasks."""
    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    tasks = [
        {"website_id": website_id, "title": "Add internal links to unindexed pages",
         "description": ("Indexation below threshold. Build contextual internal links from "
                         "high-traffic pages to pages missing from the index before creating new content."),
         "task_type": "internal_linking", "status": "pending", "created_at": now},
        {"website_id": website_id, "title": "Fix crawl errors and resubmit sitemap",
         "description": ("Check GSC Coverage for excluded/error URLs, fix canonicals, "
                         "redirects and noindex leaks, then resubmit the sitemap."),
         "task_type": "technical_fix", "status": "pending", "created_at": now},
    ]
    created = 0
    for task in tasks:
        try:
            supabase.table("pending_fixes").insert({
                "website_id": website_id,
                "fix_type": task["task_type"],
                "fix_payload": {"title": task["title"],
                                "description": task["description"]},
                "status": "pending_approval",
                "proposed_by": "indexation_service",
                "created_at": now,
            }).execute()
            created += 1
        except Exception as e:
            logger.warning(f"[Indexation] fix-task insert failed: {e}")
    return created


async def indexation_gate_check(website_id: str) -> Dict[str, Any]:
    """Decide whether a site may generate new content right now.

    Returns gate pass|blocked|warn|unknown. blocked also creates
    internal-link / fix tasks and records the action on the check row.
    warn/unknown allow generation (data missing is not proof of failure)
    but tell the caller to connect GSC.
    """
    supabase = get_supabase()
    try:
        rows = supabase.table("indexation_checks").select("*").eq(
            "website_id", website_id).order("checked_at", desc=True).limit(1).execute().data or []
    except Exception as e:
        logger.warning(f"[Indexation] gate lookup note: {e}")
        rows = []
    if not rows:
        try:
            from services.local_store import list_local_indexation_checks
            rows = list_local_indexation_checks(website_id, limit=1)
        except Exception:
            rows = []
    if not rows:
        return {"gate": "unknown",
                "reason": "No indexation check run yet. Run indexation check first."}
    check = rows[0]
    rate = check.get("indexation_rate")
    try:
        threshold = float(check.get("threshold") or await get_site_indexation_threshold(website_id))
    except Exception:
        threshold = INDEXATION_GATE_THRESHOLD
    if rate is None:
        return {"gate": "warn",
                "reason": "Indexation rate unknown — GSC not connected.",
                "action": "Connect GSC to enable indexation gating."}
    rate = float(rate)
    if rate < threshold:
        created = await create_indexation_fix_tasks(website_id, check)
        action = (f"Paused new content at {rate:.0%} < {threshold:.0%}; "
                  f"created {created} internal-link/fix task(s).")
        try:
            supabase.table("indexation_checks").update(
                {"action_taken": action}).eq("id", check.get("id")).execute()
        except Exception:
            pass
        return {"gate": "blocked", "indexation_rate": rate, "threshold": threshold,
                "reason": f"Indexation rate {rate:.0%} is below {threshold:.0%} threshold.",
                "action": "Pausing new content. Focus: internal linking, fix crawl errors, submit sitemap."}
    return {"gate": "pass", "indexation_rate": rate, "threshold": threshold}


async def get_indexation_summary(website_id: str) -> Dict[str, Any]:
    """Latest check shaped for the dashboard. Nulls mean 'no data', never 0%."""
    supabase = get_supabase()
    try:
        rows = supabase.table("indexation_checks").select("*").eq(
            "website_id", website_id).order("checked_at", desc=True).limit(1).execute().data or []
    except Exception:
        rows = []
    if not rows:
        try:
            from services.local_store import list_local_indexation_checks
            rows = list_local_indexation_checks(website_id, limit=1)
        except Exception:
            rows = []
    if not rows:
        return {"rate": None, "label": "No check yet", "submitted": None,
                "indexed": None, "checked_at": None, "gate_passed": None}
    c = rows[0]
    rate = c.get("indexation_rate")
    return {"rate": float(rate) if rate is not None else None,
            "label": ("Indexed" if c.get("gate_passed") else
                      "Below threshold" if c.get("gate_passed") is False else "Rate unknown"),
            "submitted": c.get("submitted_pages"),
            "indexed": c.get("indexed_pages"),
            "checked_at": c.get("checked_at"),
            "gate_passed": c.get("gate_passed")}


async def run_indexation_check_job(website_id: str) -> Dict[str, Any]:
    """Single-site check plus gate verdict (used by workflow envelopes)."""
    check = await check_indexation(website_id)
    try:
        gate = await indexation_gate_check(website_id)
    except Exception as e:
        gate = {"gate": "unknown", "reason": str(e)[:200]}
    return {**check, "gate": gate.get("gate"), "gate_reason": gate.get("reason")}


async def run_indexation_check_all_sites() -> Dict[str, Any]:
    """Scheduled daily fan-out: one check per active website."""
    supabase = get_supabase()
    try:
        sites = supabase.table("websites").select("id").execute().data or []
    except Exception as e:
        return {"ran": 0, "error": str(e)}
    results = []
    for site in sites:
        wid = site.get("id")
        if not wid:
            continue
        try:
            res = await check_indexation(wid)
            results.append({"website_id": wid, "rate": res.get("indexation_rate"),
                            "gate_passed": res.get("gate_passed")})
        except Exception as e:
            results.append({"website_id": wid, "error": str(e)[:200]})
    return {"ran": len(results), "results": results}
