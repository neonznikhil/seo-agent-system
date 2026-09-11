"""Cannibalization detection: two or more pages competing for one keyword.

A keyword is cannibalized when >=2 distinct URLs target it (tracked
positions or site content). Each issue carries an actionable recommendation
— rewrite, merge, redirect, differentiate, or internal-link consolidation —
never just an alert. Findings become pending_fixes TASKS via
create_cannibalization_tasks(), so decay/cannibalization turn into work.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("backend.services.cannibalization")

try:
    from database import get_supabase
except (ImportError, ValueError):
    from backend.database import get_supabase

TRACKED_POSITION_CAP = 20
CONSOLIDATE_GAP = 5


def normalize_keyword(keyword: str) -> str:
    """Canonical form so 'Houston Car-Accident Lawyer!' matches its variants."""
    text = (keyword or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_cannibalization(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pure detector: group rows by normalized keyword, flag multi-URL groups.

    Row shape: {"keyword": str, "url": str|None, "title": str|None,
    "position": int|None}. Position None means unmeasured (content-only).
    Returns issues sorted by severity then best position.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows or []:
        key = normalize_keyword(r.get("keyword") or "")
        if not key:
            continue
        url = (r.get("url") or "").strip() or f"untracked:{(r.get('title') or key)[:60]}"
        groups.setdefault(key, []).append({
            "keyword": r.get("keyword") or key,
            "url": url,
            "title": r.get("title") or "",
            "position": r.get("position"),
        })

    issues = []
    for key, pages in groups.items():
        urls = {p["url"] for p in pages}
        if len(urls) < 2:
            continue
        measured = sorted(
            [p for p in pages if isinstance(p.get("position"), (int, float))],
            key=lambda p: p["position"],
        )
        unmeasured = len(pages) - len(measured)
        display_kw = pages[0]["keyword"]
        if measured:
            best = measured[0]
            worst = measured[-1]
            gap = worst["position"] - best["position"]
            if gap >= CONSOLIDATE_GAP:
                action = "consolidate"
                recommendation = (
                    f"Page '{best['title'] or best['url']}' ranks #{best['position']} while "
                    f"'{worst['title'] or worst['url']}' sits at #{worst['position']} for the same "
                    f"keyword. Merge the weaker page's unique content into the stronger page, "
                    f"301-redirect the weaker URL, and point internal links at the survivor."
                )
                severity = "high"
            else:
                action = "differentiate"
                recommendation = (
                    f"{len(urls)} pages rank #{best['position']}–#{worst['position']} for '{display_kw}'. "
                    f"Split search intent: keep one page per intent angle, retarget secondary keywords, "
                    f"rewrite overlapping sections, and consolidate internal-link anchors to one canonical page."
                )
                severity = "high" if best["position"] <= 10 else "medium"
            best_pos, worst_pos = best["position"], worst["position"]
        else:
            action = "differentiate"
            recommendation = (
                f"{len(urls)} site pages target '{display_kw}' with no measured positions. "
                f"Verify which ranks in GSC, then differentiate intent or merge duplicates. "
                f"Positions unmeasured — treat as medium priority until confirmed."
            )
            severity = "medium"
            best_pos, worst_pos = None, None
        issues.append({
            "keyword": display_kw,
            "normalized_keyword": key,
            "urls": [{"url": p["url"], "title": p["title"], "position": p["position"]}
                     for p in (measured + [p for p in pages if p.get("position") is None])],
            "page_count": len(urls),
            "unmeasured_count": unmeasured,
            "best_position": best_pos,
            "worst_position": worst_pos,
            "action": action,
            "recommendation": recommendation,
            "severity": severity,
        })
    rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: (rank.get(i["severity"], 3),
                               i["best_position"] if i["best_position"] is not None else 999))
    return issues


def _rows_from_rank_tracking(supabase, website_id: str) -> List[Dict[str, Any]]:
    try:
        tracked = supabase.table("rank_tracking").select(
            "target_keyword, wp_url, title, current_position"
        ).eq("website_id", website_id).execute().data or []
    except Exception as e:
        logger.debug(f"[Cannibalization] rank_tracking note: {e}")
        return []
    rows = []
    for r in tracked:
        kw = r.get("target_keyword")
        if not kw:
            continue
        rows.append({"keyword": kw, "url": r.get("wp_url") or "",
                     "title": r.get("title") or "",
                     "position": r.get("current_position")})
    return rows


def _rows_from_content(supabase, website_id: str) -> List[Dict[str, Any]]:
    """Site content keyword map (unmeasured): catches duplication that rank
    tracking never sees because only published/tracked posts are monitored."""
    rows = []
    for table, kw_col in (("content_log", "keyword"), ("blogs", "primary_keyword")):
        try:
            items = supabase.table(table).select(
                f"{kw_col}, title, published_url"
            ).eq("website_id", website_id).limit(200).execute().data or []
        except Exception:
            continue
        for it in items:
            kw = it.get(kw_col)
            if not kw:
                continue
            rows.append({"keyword": kw, "url": it.get("published_url") or "",
                         "title": it.get("title") or "", "position": None})
    return rows


async def scan_website(website_id: str) -> Dict[str, Any]:
    """Detect cannibalization for a site. Read-only: creates no tasks."""
    supabase = get_supabase()
    rows = _rows_from_rank_tracking(supabase, website_id)
    rows += _rows_from_content(supabase, website_id)
    issues = detect_cannibalization(rows)
    return {"website_id": website_id, "issue_count": len(issues),
            "issues": issues,
            "sources": {"tracked_rows": len([r for r in rows if r.get("position") is not None]),
                        "content_rows": len([r for r in rows if r.get("position") is None])}}


async def create_cannibalization_tasks(website_id: str,
                                       issues: Optional[List[Dict[str, Any]]] = None) -> int:
    """Turn issues into pending_fixes tasks. Idempotent: an open task with
    the same title is never duplicated."""
    supabase = get_supabase()
    if issues is None:
        issues = (await scan_website(website_id)).get("issues", [])
    try:
        open_rows = supabase.table("pending_fixes").select("fix_payload").eq(
            "website_id", website_id).eq("status", "pending_approval").execute().data or []
    except Exception:
        open_rows = []
    open_titles = {((r.get("fix_payload") or {}).get("title") or "").lower()
                   for r in open_rows}
    created = 0
    now = datetime.now(timezone.utc).isoformat()
    action_labels = {
        "consolidate": "Merge + 301-redirect weaker page into stronger page",
        "differentiate": "Split intent / rewrite overlapping sections",
        "rewrite": "Rewrite to a distinct angle",
        "merge": "Merge duplicate pages",
        "redirect": "Redirect duplicate URL",
        "internal_links": "Consolidate internal-link anchors to one canonical page",
    }
    for issue in issues:
        title = f"Cannibalization: {issue['page_count']} pages target '{issue['keyword']}'"
        if title.lower() in open_titles:
            continue
        body = (f"{issue['recommendation']}\n\nPages:\n" + "\n".join(
            f"- {u['title'] or u['url']} ({u['url'] or 'no URL'}, "
            f"position {u['position'] if u['position'] is not None else 'unmeasured'})"
            for u in issue["urls"][:8]
        ) + f"\n\nRecommended action: {action_labels.get(issue['action'], issue['action'])}")
        try:
            supabase.table("pending_fixes").insert({
                "website_id": website_id,
                "fix_type": f"cannibalization_{issue['action']}",
                "fix_payload": {"title": title, "description": body,
                                "keyword": issue["keyword"],
                                "action": issue["action"],
                                "severity": issue["severity"],
                                "urls": issue["urls"][:8]},
                "status": "pending_approval",
                "proposed_by": "cannibalization_service",
                "created_at": now,
            }).execute()
            created += 1
            open_titles.add(title.lower())
        except Exception as e:
            logger.debug(f"[Cannibalization] task insert note: {e}")
    return created
