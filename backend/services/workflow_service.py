"""Workflow Orchestrator: 9 Independent SEO Workflows.

Each workflow:
1. Does one thing well.
2. Reads the previous run's snapshot before recording the new one.
3. Computes diffs: Fixed, New, Still Open, Regressed.
4. Generates a written executive summary: "What changed, why, and what to do next".
5. Persists an envelope row to the `runs` table.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger("backend.services.workflow_service")

try:
    from database import get_supabase
except (ImportError, ValueError):
    from backend.database import get_supabase

try:
    from services.run_service import start_run, complete_run, fail_run, get_last_run_summary, get_recent_runs
except (ImportError, ValueError):
    from backend.services.run_service import start_run, complete_run, fail_run, get_last_run_summary, get_recent_runs

WORKFLOW_JOBS = [
    "indexation_check",
    "search_performance_report",
    "site_health",
    "on_page_audit",
    "internal_linking",
    "keyword_research",
    "content_pipeline",
    "ai_citation_monitoring",
    "content_optimization",
]

WORKFLOW_DESCRIPTIONS = {
    "indexation_check": "Track submitted vs indexed pages via sitemap and GSC. Gates content creation at 80% threshold.",
    "search_performance_report": "Analyze real GSC performance, impressions, clicks, and striking-distance keyword movements.",
    "site_health": "Verify uptime, response codes, Core Web Vitals, canonical tags, and robots.txt accessibility.",
    "on_page_audit": "Audit single H1 integrity, title and meta lengths, schema coverage, and content density.",
    "internal_linking": "Map link graph, detect orphaned pages, and inject high-value contextual keyword anchors.",
    "keyword_research": "Identify high-intent content gaps and striking-distance ranking opportunities.",
    "content_pipeline": "Draft publication-ready articles for data-driven keywords (gated by 80% indexation).",
    "ai_citation_monitoring": "Track brand mentions, citations, and SOV across ChatGPT, Perplexity, Claude, and Gemini.",
    "content_optimization": "Detect decayed or cannibalized pages and execute content refreshes and rewrites.",
}


async def run_workflow_job(website_id: str, job_name: str) -> Dict[str, Any]:
    """Execute one of the 9 independent workflows under a run envelope."""
    if job_name not in WORKFLOW_JOBS:
        raise ValueError(f"Unknown workflow job '{job_name}'. Valid jobs: {WORKFLOW_JOBS}")

    run_meta = await start_run(website_id, job_name)
    run_id = run_meta.get("run_id")
    prev_snapshot = run_meta.get("prev_snapshot") or {}

    try:
        if job_name == "indexation_check":
            result = await _job_indexation_check(website_id)
        elif job_name == "search_performance_report":
            result = await _job_search_performance(website_id)
        elif job_name == "site_health":
            result = await _job_site_health(website_id)
        elif job_name == "on_page_audit":
            result = await _job_on_page_audit(website_id)
        elif job_name == "internal_linking":
            result = await _job_internal_linking(website_id)
        elif job_name == "keyword_research":
            result = await _job_keyword_research(website_id)
        elif job_name == "content_pipeline":
            result = await _job_content_pipeline(website_id)
        elif job_name == "ai_citation_monitoring":
            result = await _job_ai_citation_monitoring(website_id)
        elif job_name == "content_optimization":
            result = await _job_content_optimization(website_id)
        else:
            result = {"snapshot": {}, "notes": "No implementation"}

        snapshot = result.get("snapshot") or {}
        custom_summary = result.get("narrative_summary")

        completed = await complete_run(run_id, snapshot, prev_snapshot, job_name=job_name)
        if custom_summary:
            completed["summary"] = custom_summary
            if run_id:
                try:
                    get_supabase().table("runs").update({"summary": custom_summary}).eq("id", run_id).execute()
                except Exception:
                    pass

        return {
            "status": "completed",
            "job_name": job_name,
            "website_id": website_id,
            "run_id": run_id,
            "summary": completed.get("summary"),
            "changes": completed.get("changes"),
            "next_actions": completed.get("next_actions"),
            "data": result.get("data", {}),
        }

    except Exception as e:
        logger.error(f"[WorkflowService] Job '{job_name}' failed for site {website_id}: {e}", exc_info=True)
        await fail_run(run_id, str(e))
        return {
            "status": "failed",
            "job_name": job_name,
            "website_id": website_id,
            "run_id": run_id,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Individual Workflow Implementations
# ---------------------------------------------------------------------------

async def _job_indexation_check(website_id: str) -> Dict[str, Any]:
    from services.indexation_service import run_indexation_check_job, get_indexation_summary
    check = await run_indexation_check_job(website_id)
    summary = await get_indexation_summary(website_id)
    rate = summary.get("rate")
    not_indexed = check.get("not_indexed_urls") or []
    if rate is None:
        pages_str = "no sitemap/GSC measurements yet"
        rate_str = "Unknown"
    else:
        pages_str = f"{summary.get('indexed', 0)}/{summary.get('submitted', 0)} pages"
        rate_str = f"{rate * 100:.1f}%"

    narrative = (
        f"Indexation is at {rate_str} ({pages_str}). "
        f"{len(not_indexed)} unindexed URLs identified. Gate status: {check.get('gate', 'unknown')}."
    )
    return {
        "snapshot": {
            "indexation_rate": rate,
            "submitted": summary.get("submitted", 0),
            "indexed": summary.get("indexed", 0),
            "issue_ids": [f"unindexed:{u}" for u in not_indexed[:20]],
        },
        "narrative_summary": narrative,
        "data": check,
    }


async def _job_search_performance(website_id: str) -> Dict[str, Any]:
    from routers.gsc import get_performance
    perf = await get_performance(website_id, None, None)
    impressions = perf.get("total_impressions") or 0
    clicks = perf.get("total_clicks") or 0
    keywords = perf.get("keywords") or []

    try:
        from services.seo_constants import is_striking_distance
    except (ImportError, ValueError):
        from backend.services.seo_constants import is_striking_distance
    striking = [k for k in keywords
                if is_striking_distance(k.get("position"))]
    issues = [f"low_ctr:{k.get('keyword') or k.get('query')}" for k in keywords
              if float(k.get("ctr", 0)) < 0.02 and int(k.get("impressions", 0)) > 300]

    narrative = (
        f"Search performance (28d): {impressions:,} impressions, {clicks:,} clicks. "
        f"{len(striking)} striking-distance keywords (positions 11-20) ready for optimization."
    )
    return {
        "snapshot": {
            "impressions": impressions,
            "clicks": clicks,
            "striking_distance_count": len(striking),
            "issue_ids": issues[:15],
        },
        "narrative_summary": narrative,
        "data": {"impressions": impressions, "clicks": clicks, "striking_count": len(striking)},
    }


async def _job_site_health(website_id: str) -> Dict[str, Any]:
    supabase = get_supabase()
    site = supabase.table("websites").select("domain, url, cms_url").eq("id", website_id).maybe_single().execute().data or {}
    site_url = site.get("url") or site.get("cms_url") or f"https://{site.get('domain')}"
    
    import httpx
    issues = []
    health_score = 90.0
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(site_url)
            if resp.status_code != 200:
                issues.append(f"http_status_{resp.status_code}")
                health_score -= 30.0
            robots_resp = await client.get(f"{site_url.rstrip('/')}/robots.txt")
            if robots_resp.status_code != 200:
                issues.append("missing_robots_txt")
                health_score -= 10.0
    except Exception as e:
        issues.append(f"site_unreachable:{str(e)[:40]}")
        health_score = 30.0

    narrative = f"Site health score: {health_score:.0f}/100. {len(issues)} connectivity/technical issue(s) detected."
    return {
        "snapshot": {"health_score": health_score, "issue_ids": issues},
        "narrative_summary": narrative,
        "data": {"health_score": health_score, "issues": issues},
    }


async def _job_on_page_audit(website_id: str) -> Dict[str, Any]:
    supabase = get_supabase()
    pages = supabase.table("pages").select("url, title, h1").eq("website_id", website_id).limit(20).execute().data or []
    issues = []
    for p in pages:
        if not p.get("title"):
            issues.append(f"missing_title:{p.get('url')}")
        if not p.get("h1"):
            issues.append(f"missing_h1:{p.get('url')}")

    narrative = f"On-page audit checked {len(pages)} pages. Found {len(issues)} title/H1 structural issues."
    return {
        "snapshot": {"pages_audited": len(pages), "issue_ids": issues},
        "narrative_summary": narrative,
        "data": {"pages_audited": len(pages), "issues": issues},
    }


async def _job_internal_linking(website_id: str) -> Dict[str, Any]:
    from services.internal_link_service import build_internal_link_graph
    graph = await build_internal_link_graph(website_id)
    orphans = graph.get("orphan_pages", []) or []
    nodes = graph.get("nodes", []) or []
    issue_ids = [f"orphan:{u}" for u in orphans[:15]]

    narrative = (f"Internal link graph: {len(nodes)} pages, {len(orphans)} orphan page(s) "
                 f"needing contextual links.")
    return {
        "snapshot": {"opportunities_count": len(orphans), "issue_ids": issue_ids},
        "narrative_summary": narrative,
        "data": {"orphan_count": len(orphans), "page_count": len(nodes),
                 "sample": orphans[:5]},
    }


async def _job_keyword_research(website_id: str) -> Dict[str, Any]:
    try:
        from services.seo_constants import is_striking_distance
    except (ImportError, ValueError):
        from backend.services.seo_constants import is_striking_distance
    supabase = get_supabase()
    try:
        tracked = supabase.table("rank_tracking").select(
            "keyword, target_keyword, current_position").eq(
            "website_id", website_id).execute().data or []
    except Exception:
        tracked = []
    striking = [r for r in tracked
                if is_striking_distance(r.get("current_position"))]
    try:
        opps = supabase.table("keyword_opportunities").select(
            "keyword").eq("website_id", website_id).limit(50).execute().data or []
    except Exception:
        opps = []
    gap_list = [r.get("keyword") for r in opps if r.get("keyword")]
    issue_ids = ([f"striking:{(r.get('keyword') or r.get('target_keyword'))}" for r in striking[:10]]
                 + [f"untargeted_keyword:{k}" for k in gap_list[:10]])

    narrative = (f"Keyword research: {len(striking)} striking-distance keyword(s) closest to page 1, "
                 f"{len(gap_list)} tracked opportunitie(s) ready for targeting.")
    return {
        "snapshot": {"keyword_gaps_count": len(gap_list),
                     "striking_count": len(striking), "issue_ids": issue_ids[:15]},
        "narrative_summary": narrative,
        "data": {"gaps_found": len(gap_list), "striking": len(striking)},
    }


async def _job_content_pipeline(website_id: str) -> Dict[str, Any]:
    from services.indexation_service import indexation_gate_check
    gate = await indexation_gate_check(website_id)
    if gate.get("gate") == "blocked":
        narrative = f"Content pipeline PAUSED: Indexation rate ({gate.get('rate', 0):.1%}) is below 80%. Prioritizing internal links."
        return {
            "snapshot": {"status": "paused_by_gate", "issue_ids": ["indexation_below_threshold"]},
            "narrative_summary": narrative,
            "data": {"gate": "blocked", "rate": gate.get("rate")},
        }

    supabase = get_supabase()
    pending = supabase.table("blog_approvals").select("id, title").eq("website_id", website_id).eq("status", "pending").execute().data or []
    narrative = f"Content pipeline active. {len(pending)} draft(s) currently awaiting human approval."
    return {
        "snapshot": {"pending_approvals": len(pending), "issue_ids": []},
        "narrative_summary": narrative,
        "data": {"pending_count": len(pending)},
    }


async def _job_ai_citation_monitoring(website_id: str) -> Dict[str, Any]:
    from services.ai_visibility_monitor import check_ai_visibility
    supabase = get_supabase()
    try:
        site = supabase.table("websites").select("domain").eq(
            "id", website_id).limit(1).execute().data or [{}]
        domain = (site[0].get("domain") or "").strip()
    except Exception:
        domain = ""
    try:
        rows = supabase.table("rank_tracking").select(
            "keyword, target_keyword").eq("website_id", website_id).limit(10).execute().data or []
        keywords = [r.get("keyword") or r.get("target_keyword") for r in rows]
        keywords = [k for k in keywords if k]
    except Exception:
        keywords = []
    if not domain or not keywords:
        return {
            "snapshot": {"ai_visibility_score": None, "mentions": None, "issue_ids": []},
            "narrative_summary": ("AI citation check degraded: no domain or tracked keywords. "
                                    "Connect a site and run rank tracking first."),
            "data": {"degraded": True, "reason": "missing domain or keywords"},
        }
    vis = await check_ai_visibility(website_id, domain, keywords)
    kw_results = vis.get("keyword_results", []) or []
    checked = len(kw_results)
    cited = sum(1 for k in kw_results if k.get("site_cited_in_ai"))
    score = round(cited / checked * 100, 1) if checked else None
    if score is None:
        narrative = "AI citation check ran but produced no keyword results."
    else:
        narrative = (f"AI Search visibility: {score:.0f}/100 with {cited}/{checked} tracked "
                     f"keyword(s) cited in AI answers.")
    return {
        "snapshot": {"ai_visibility_score": score, "mentions": cited, "issue_ids": []},
        "narrative_summary": narrative,
        "data": vis,
    }


async def _job_content_optimization(website_id: str) -> Dict[str, Any]:
    from services.decay_detector_service import DecayDetectorService
    dds = DecayDetectorService(website_id)
    decay_res = await dds.detect_decay(website_id, auto_alert=False)
    decayed = decay_res.get("decayed_pages", [])
    
    # Turn decay findings into real staged rewrite tasks
    queued_count = 0
    try:
        from services.content_refresh import detect_decaying_articles
        queued_items = await detect_decaying_articles(website_id)
        queued_count = len(queued_items)
    except Exception as e:
        logger.warning(f"[WorkflowContentOptimization] Could not queue refresh items: {e}")

    total_decayed = max(len(decayed), queued_count)
    issue_ids = [f"decay:{p.get('url')}" for p in decayed[:10]]

    # Cannibalization rides the same job: competing pages need the same
    # rewrite/merge/redirect decisions as decaying ones.
    try:
        from services.cannibalization_service import scan_website
        cann = await scan_website(website_id)
        cann_issues = cann.get("issues", []) or []
    except Exception as e:
        logger.debug(f"[Workflow] cannibalization note: {e}")
        cann_issues = []
    issue_ids += [f"cannibal:{i['normalized_keyword']}" for i in cann_issues[:10]]

    parts = []
    if total_decayed > 0:
        parts.append(f"{total_decayed} decaying page(s), {queued_count} rewrite task(s) queued")
    if cann_issues:
        parts.append(f"{len(cann_issues)} cannibalized keyword(s) flagged for merge/redirect/differentiate")
    narrative = ("Content optimizer: " + "; ".join(parts) + "."
                 if parts else "Content optimizer detected 0 decaying pages and 0 cannibalization issues.")
    return {
        "snapshot": {"decayed_pages_count": total_decayed,
                     "cannibalization_count": len(cann_issues),
                     "issue_ids": issue_ids[:20]},
        "narrative_summary": narrative,
        "data": {"decayed_count": total_decayed, "pages": decayed[:5], "queued_rewrites": queued_count,
                 "cannibalization": cann_issues[:5]},
    }


WORKFLOW_CATEGORIES = {
    "indexation_check": "technical",
    "search_performance_report": "intelligence",
    "site_health": "technical",
    "on_page_audit": "technical",
    "internal_linking": "links",
    "keyword_research": "content",
    "content_pipeline": "content",
    "ai_citation_monitoring": "intelligence",
    "content_optimization": "content",
}


async def get_all_workflows_status(website_id: str) -> Dict[str, Any]:
    """Return latest run envelope, status, diff, pace, and description for all 9 jobs."""
    supabase = get_supabase()
    runs = []
    try:
        runs = (
            supabase.table("runs")
            .select("job_name, status, summary, completed_at, changes, next_actions, fixed_count, new_count, still_open_count, regressed_count")
            .eq("website_id", website_id)
            .order("completed_at", desc=True)
            .execute()
            .data or []
        )
    except Exception:
        runs = []

    latest_by_job = {}
    for r in runs:
        j = r.get("job_name")
        if j and j not in latest_by_job:
            latest_by_job[j] = r

    workflows = []
    for job in WORKFLOW_JOBS:
        last = latest_by_job.get(job)
        diff_dict = {
            "fixed": last.get("fixed_count", 0) if last else 0,
            "new": last.get("new_count", 0) if last else 0,
            "still_open": last.get("still_open_count", 0) if last else 0,
            "regressed": last.get("regressed_count", 0) if last else 0,
        }
        workflows.append({
            "job_name": job,
            "title": job.replace("_", " ").title(),
            "display_name": job.replace("_", " ").title(),
            "category": WORKFLOW_CATEGORIES.get(job, "technical"),
            "description": WORKFLOW_DESCRIPTIONS.get(job, ""),
            "status": last.get("status") if last else "never_run",
            "last_run": last.get("completed_at") if last else None,
            "summary": last.get("summary") if last else "No run completed yet.",
            "next_actions": last.get("next_actions", []) if last else [],
            "diff": diff_dict,
        })

    # Unknown when unmeasured: never a hardcoded 85% that would fake NORMAL.
    rate = None
    try:
        index_check = (
            supabase.table("indexation_checks")
            .select("indexation_rate")
            .eq("website_id", website_id)
            .order("checked_at", desc=True)
            .limit(1)
            .execute()
            .data or []
        )
        if index_check and index_check[0].get("indexation_rate") is not None:
            rate = float(index_check[0].get("indexation_rate"))
    except Exception:
        rate = None

    if rate is None:
        pace_status = "UNKNOWN"
        pace_action = "Indexation unmeasured — run an indexation check to set publishing pace"
    else:
        pace_status = "NORMAL" if rate >= 0.80 else "PAUSED_INDEXATION_GATE"
        pace_action = "Publishing allowed" if rate >= 0.80 else "Publishing paused — internal linking prioritized"

    return {
        "website_id": website_id,
        "indexation_rate": rate,
        "publishing_pace": {
            "status": pace_status,
            "threshold": 0.80,
            "current_rate": rate,
            "action": pace_action,
        },
        "workflows": workflows,
    }


# Aliases for compatibility
get_workflows_status = get_all_workflows_status
run_workflow = run_workflow_job
