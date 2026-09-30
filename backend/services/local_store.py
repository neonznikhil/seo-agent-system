"""RankForge Persistent Local Store.
Provides transparent local JSON persistence and multi-tenant fallback
when Supabase RLS policies restrict anon writes in local dev environments.
"""

import os
import json
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("backend.services.local_store")

DATA_DIR = os.getenv(
    "RANKFORGE_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"),
)
os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(filename: str) -> List[Dict[str, Any]]:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read {filename}: {e}")
        return []


def _save_json(filename: str, data: List[Dict[str, Any]]) -> None:
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to write {filename}: {e}")


# ============================================================================
# WEBSITES
# ============================================================================

def save_local_website(site: Dict[str, Any]) -> Dict[str, Any]:
    sites = _load_json("websites.json")
    site_id = site.get("id") or str(uuid.uuid4())
    site["id"] = site_id
    site["updated_at"] = site.get("updated_at") or datetime.utcnow().isoformat()
    if "created_at" not in site:
        site["created_at"] = datetime.utcnow().isoformat()

    updated = False
    for i, s in enumerate(sites):
        if s.get("id") == site_id or (site.get("domain") and s.get("domain") == site.get("domain")):
            site_id = s.get("id")
            site["id"] = site_id
            sites[i] = {**s, **site}
            updated = True
            break
    if not updated:
        sites.append(site)
    
    _save_json("websites.json", sites)
    logger.info(f"[LocalStore] Saved website: {site.get('domain')} ({site_id})")
    return site


def list_local_websites(account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sites = _load_json("websites.json")
    if account_id and account_id not in ("all", "default"):
        return [s for s in sites if not s.get("account_id") or s.get("account_id") == account_id]
    return sites


def get_local_website(website_id: str) -> Optional[Dict[str, Any]]:
    sites = _load_json("websites.json")
    for s in sites:
        if s.get("id") == website_id or s.get("domain") == website_id:
            return s
    return None


def delete_local_website(website_id: str) -> bool:
    sites = _load_json("websites.json")
    initial_len = len(sites)
    sites = [s for s in sites if s.get("id") != website_id]
    if len(sites) != initial_len:
        _save_json("websites.json", sites)
        return True
    return False


# ============================================================================
# KNOWLEDGE BASE
# ============================================================================

def save_local_knowledge(item: Dict[str, Any]) -> Dict[str, Any]:
    kb = _load_json("knowledge_base.json")
    item_id = item.get("id") or str(uuid.uuid4())
    item["id"] = item_id
    item["created_at"] = item.get("created_at") or datetime.utcnow().isoformat()
    kb.append(item)
    _save_json("knowledge_base.json", kb)
    return item


def list_local_knowledge(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
    kb = _load_json("knowledge_base.json")
    if website_id and website_id not in ("all", "default", "00000000-0000-0000-0000-000000000001"):
        return [k for k in kb if not k.get("website_id") or k.get("website_id") == website_id]
    return kb


# ============================================================================
# BRAIN MEMORY
# ============================================================================

def save_local_brain_memory(item: Dict[str, Any]) -> Dict[str, Any]:
    memories = _load_json("brain_memory.json")
    mem_id = item.get("id") or str(uuid.uuid4())
    item["id"] = mem_id
    item["created_at"] = item.get("created_at") or datetime.utcnow().isoformat()
    memories.append(item)
    _save_json("brain_memory.json", memories)
    return item


def list_local_brain_memory(website_id: Optional[str] = None, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
    memories = _load_json("brain_memory.json")
    results = memories
    if website_id and website_id not in ("all", "default", "00000000-0000-0000-0000-000000000001"):
        results = [m for m in results if not m.get("website_id") or m.get("website_id") == website_id]
    if memory_type and memory_type != "all":
        results = [m for m in results if m.get("memory_type") == memory_type]
    return results


# ============================================================================
# CONTENT & APPROVALS
# ============================================================================

def save_local_content(item: Dict[str, Any]) -> Dict[str, Any]:
    content = _load_json("content_log.json")
    item_id = item.get("id") or str(uuid.uuid4())
    item["id"] = item_id
    # Upsert by id: generation writes a placeholder row up-front and later the
    # finished article under the same id. Appending unconditionally produced two
    # rows per blog (one empty "in_progress", one filled), and status lookups
    # could return the empty one.
    for i, existing in enumerate(content):
        if existing.get("id") == item_id:
            item["created_at"] = item.get("created_at") or existing.get("created_at")
            content[i] = {**existing, **item}
            _save_json("content_log.json", content)
            return content[i]
    item["created_at"] = item.get("created_at") or datetime.utcnow().isoformat()
    content.append(item)
    _save_json("content_log.json", content)
    return item


def list_local_content(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
    content = _load_json("content_log.json")
    if website_id and website_id not in ("all", "default"):
        return [c for c in content if not c.get("website_id") or c.get("website_id") == website_id]
    return content


def get_local_content(content_id: str) -> Optional[Dict[str, Any]]:
    content = _load_json("content_log.json")
    for c in content:
        if c.get("id") == content_id:
            return c
    return None


# ---------------------------------------------------------------------------
# In-flight generation liveness
#
# A generation run can legitimately take far longer than any fixed timeout when
# the LLM is cold or under load (observed: ~46 minutes on shared NIM). Guessing
# staleness from a timestamp alone is wrong in both directions — it hides a
# genuinely still-running job, or falsely fails one. These helpers track which
# runs this process is actually executing, so "still generating" is decided by
# liveness, not by clock arithmetic.
# ---------------------------------------------------------------------------
_ACTIVE_RUNS: Dict[str, float] = {}


def mark_run_active(content_id: str) -> None:
    _ACTIVE_RUNS[str(content_id)] = time.time()


def mark_run_finished(content_id: str) -> None:
    _ACTIVE_RUNS.pop(str(content_id), None)


def is_run_active(content_id: str, grace_seconds: float = 300.0) -> bool:
    """True if this process is running (or very recently ran) the generation.

    The grace window covers the brief moment after a run finishes but before the
    finished row is written, and the handoff between task scheduling and the
    task body starting.
    """
    started = _ACTIVE_RUNS.get(str(content_id))
    if started is None:
        return False
    return (time.time() - started) < grace_seconds


def save_local_approval(item: Dict[str, Any]) -> Dict[str, Any]:
    approvals = _load_json("blog_approvals.json")
    item_id = item.get("id") or str(uuid.uuid4())
    item["id"] = item_id
    item["created_at"] = item.get("created_at") or datetime.utcnow().isoformat()
    
    updated = False
    for i, a in enumerate(approvals):
        if a.get("id") == item_id:
            approvals[i] = {**a, **item}
            updated = True
            break
    if not updated:
        approvals.append(item)

    _save_json("blog_approvals.json", approvals)
    return item


def list_local_approvals(website_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    approvals = _load_json("blog_approvals.json")
    results = approvals
    if website_id and website_id not in ("all", "default"):
        results = [a for a in results if not a.get("website_id") or a.get("website_id") == website_id]
    if status and status != "all":
        results = [a for a in results if a.get("status") == status]
    return results


def get_local_approval(approval_id: str) -> Optional[Dict[str, Any]]:
    approvals = _load_json("blog_approvals.json")
    for a in approvals:
        if a.get("id") == approval_id:
            return a
    return None


# ============================================================================
# RANK TRACKING
# ============================================================================

def save_local_rank_tracking(item: Dict[str, Any]) -> Dict[str, Any]:
    records = _load_json("rank_tracking.json")
    item_id = item.get("id") or str(uuid.uuid4())
    item["id"] = item_id
    if "published_at" not in item:
        item["published_at"] = datetime.utcnow().isoformat()

    updated = False
    for i, r in enumerate(records):
        if r.get("id") == item_id or (item.get("website_id") == r.get("website_id") and item.get("target_keyword") == r.get("target_keyword")):
            item_id = r.get("id")
            item["id"] = item_id
            records[i] = {**r, **item}
            updated = True
            break
    if not updated:
        records.append(item)

    _save_json("rank_tracking.json", records)
    return item


def list_local_rank_tracking(website_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    records = _load_json("rank_tracking.json")
    if website_id and website_id not in ("all", "default"):
        records = [r for r in records if not r.get("website_id") or r.get("website_id") == website_id]
    if status and status != "all":
        records = [r for r in records if r.get("status") == status]
    return records


def get_local_rank_tracking(track_id: str) -> Optional[Dict[str, Any]]:
    records = _load_json("rank_tracking.json")
    for r in records:
        if r.get("id") == track_id:
            return r
    return None


# ============================================================================
# INTERNAL LINK INDEX
# ============================================================================

def save_local_internal_link(item: Dict[str, Any]) -> Dict[str, Any]:
    records = _load_json("internal_link_index.json")
    item_id = item.get("id") or str(uuid.uuid4())
    item["id"] = item_id
    if "published_at" not in item:
        item["published_at"] = datetime.utcnow().isoformat()

    updated = False
    for i, r in enumerate(records):
        if r.get("id") == item_id or (item.get("website_id") == r.get("website_id") and item.get("url") == r.get("url")):
            item_id = r.get("id")
            item["id"] = item_id
            records[i] = {**r, **item}
            updated = True
            break
    if not updated:
        records.append(item)

    _save_json("internal_link_index.json", records)
    return item


def list_local_internal_links(website_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    records = _load_json("internal_link_index.json")
    if website_id and website_id not in ("all", "default"):
        records = [r for r in records if not r.get("website_id") or r.get("website_id") == website_id]
    records.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return records[:limit]


# ============================================================================
# CONTENT REFRESH QUEUE
# ============================================================================

def save_local_refresh_queue(item: Dict[str, Any]) -> Dict[str, Any]:
    queue = _load_json("content_refresh_queue.json")
    item_id = item.get("id") or str(uuid.uuid4())
    item["id"] = item_id
    if "queued_at" not in item:
        item["queued_at"] = datetime.utcnow().isoformat()

    updated = False
    for i, q in enumerate(queue):
        if q.get("id") == item_id or (item.get("website_id") == q.get("website_id") and item.get("target_keyword") == q.get("target_keyword") and q.get("status") == "pending"):
            item_id = q.get("id")
            item["id"] = item_id
            queue[i] = {**q, **item}
            updated = True
            break
    if not updated:
        queue.append(item)

    _save_json("content_refresh_queue.json", queue)
    return item


def list_local_refresh_queue(website_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    queue = _load_json("content_refresh_queue.json")
    if website_id and website_id not in ("all", "default"):
        queue = [q for q in queue if not q.get("website_id") or q.get("website_id") == website_id]
    if status and status != "all":
        queue = [q for q in queue if q.get("status") == status]
    return queue


# ============================================================================
# WORDPRESS CONNECTIONS
# ============================================================================

def save_local_wp_connection(item: Dict[str, Any]) -> Dict[str, Any]:
    conns = _load_json("wordpress_connections.json")
    item_id = item.get("id") or str(uuid.uuid4())
    item["id"] = item_id
    item["created_at"] = item.get("created_at") or datetime.utcnow().isoformat()
    item["updated_at"] = datetime.utcnow().isoformat()

    updated = False
    for i, c in enumerate(conns):
        if c.get("id") == item_id or (item.get("site_url") and c.get("site_url") == item.get("site_url")):
            item_id = c.get("id")
            item["id"] = item_id
            conns[i] = {**c, **item}
            updated = True
            break
    if not updated:
        conns.append(item)

    _save_json("wordpress_connections.json", conns)
    return item


def get_local_wp_connection(website_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conns = _load_json("wordpress_connections.json")
    if not conns:
        return None
    if website_id and website_id not in ("all", "default"):
        for c in conns:
            if c.get("website_id") == website_id or c.get("id") == website_id:
                return c
        return None
    # Return latest active or latest connection only when no specific website_id requested
    for c in reversed(conns):
        if c.get("is_active", True):
            return c
    return conns[-1]


# ============================================================================
# DAILY COSTS & AUTONOMOUS SETTINGS
# ============================================================================

def save_local_cost(cost_item: Dict[str, Any]) -> Dict[str, Any]:
    costs = _load_json("daily_costs.json")
    item_id = cost_item.get("id") or str(uuid.uuid4())
    cost_item["id"] = item_id
    if "date" not in cost_item:
        cost_item["date"] = datetime.utcnow().strftime("%Y-%m-%d")
    if "created_at" not in cost_item:
        cost_item["created_at"] = datetime.utcnow().isoformat()
    costs.append(cost_item)
    _save_json("daily_costs.json", costs)
    return cost_item


def list_local_costs(website_id: Optional[str] = None, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
    costs = _load_json("daily_costs.json")
    filtered = []
    for c in costs:
        if website_id and c.get("website_id") and c.get("website_id") != website_id:
            continue
        if date_str and c.get("date") != date_str:
            continue
        filtered.append(c)
    return filtered


def save_local_autonomous_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    current = _load_json("autonomous_settings.json")
    if current and isinstance(current, list):
        current_dict = current[0] if len(current) > 0 else {}
    else:
        current_dict = {}
    updated = {**current_dict, **settings, "updated_at": datetime.utcnow().isoformat()}
    _save_json("autonomous_settings.json", [updated])
    return updated


def get_local_autonomous_settings() -> Dict[str, Any]:
    current = _load_json("autonomous_settings.json")
    if current and isinstance(current, list) and len(current) > 0:
        return current[0]
    return {
        "daily_limit": 10,
        "daily_blog_target": 5,
        "generation_interval": 288,
        "auto_topic_selection": True,
        # Drafts only by default: publishing requires explicit opt-in.
        "auto_publish": False,
    }


# ============================================================================
# LEAD ATTRIBUTION SETTINGS
# ============================================================================

def save_local_lead_settings(website_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    all_settings = _load_json("lead_settings.json")
    record = {**settings, "website_id": website_id, "updated_at": datetime.utcnow().isoformat()}
    updated = False
    for i, s in enumerate(all_settings):
        if s.get("website_id") == website_id:
            all_settings[i] = record
            updated = True
            break
    if not updated:
        all_settings.append(record)
    _save_json("lead_settings.json", all_settings)
    return record


def get_local_lead_settings(website_id: str) -> Dict[str, Any]:
    all_settings = _load_json("lead_settings.json")
    for s in all_settings:
        if s.get("website_id") == website_id:
            return s
    return {
        "website_id": website_id,
        "monthly_seo_spend": 2500.0,
        "target_cpl": 75.0,
        "lead_value": 350.0,
        "conversion_goals": ["form_submission", "booking", "contact", "purchase"],
    }


# ============================================================================
# INDEXATION CHECKS
# ============================================================================

def save_local_indexation_check(check: Dict[str, Any]) -> Dict[str, Any]:
    checks = _load_json("indexation_checks.json")
    check_id = check.get("id") or str(uuid.uuid4())
    check["id"] = check_id
    if "checked_at" not in check:
        check["checked_at"] = datetime.utcnow().isoformat()
    checks.insert(0, check)
    # Keep last 100 checks
    _save_json("indexation_checks.json", checks[:100])
    return check


def list_local_indexation_checks(website_id: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    checks = _load_json("indexation_checks.json")
    if website_id and website_id not in ("all", "default"):
        checks = [c for c in checks if not c.get("website_id") or c.get("website_id") == website_id]
    return checks[:limit]


# ============================================================================
# BRAND VOICE GUIDES
# ============================================================================

def save_local_brand_voice(website_id: str, guide: Dict[str, Any]) -> Dict[str, Any]:
    guides = _load_json("brand_voice_guides.json")
    existing = [g for g in guides if g.get("website_id") == website_id]
    version = max([g.get("version", 0) for g in existing], default=0) + 1
    record = {**guide, "website_id": website_id, "version": version, "updated_at": datetime.utcnow().isoformat()}
    guides.append(record)
    _save_json("brand_voice_guides.json", guides)
    return record


def get_local_brand_voice(website_id: str) -> Optional[Dict[str, Any]]:
    guides = _load_json("brand_voice_guides.json")
    matching = [g for g in guides if g.get("website_id") == website_id]
    if not matching:
        return None
    matching.sort(key=lambda g: g.get("version", 0), reverse=True)
    return matching[0]


# ============================================================================
# GUARDRAIL AUDIT CHANGES & ROLLBACK
# ============================================================================

def save_local_guardrail_change(change: Dict[str, Any]) -> Dict[str, Any]:
    changes = _load_json("guardrail_changes.json")
    change_id = change.get("id") or str(uuid.uuid4())
    change["id"] = change_id
    if "created_at" not in change:
        change["created_at"] = datetime.utcnow().isoformat()
    changes.insert(0, change)
    _save_json("guardrail_changes.json", changes)
    return change


def list_local_guardrail_changes(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
    changes = _load_json("guardrail_changes.json")
    if website_id and website_id not in ("all", "default"):
        return [c for c in changes if c.get("website_id") == website_id]
    return changes


def get_local_guardrail_change(change_id: str) -> Optional[Dict[str, Any]]:
    changes = _load_json("guardrail_changes.json")
    for c in changes:
        if c.get("id") == change_id:
            return c
    return None


def update_local_guardrail_change(change_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    changes = _load_json("guardrail_changes.json")
    for i, c in enumerate(changes):
        if c.get("id") == change_id:
            updated_record = {**c, **updates, "updated_at": datetime.utcnow().isoformat()}
            changes[i] = updated_record
            _save_json("guardrail_changes.json", changes)
            return updated_record
    return None


# ============================================================================
# COMPETITORS
# ============================================================================

def save_local_competitor(website_id_or_comp: Any, competitor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    competitors = _load_json("competitors.json")
    if isinstance(website_id_or_comp, dict) and competitor is None:
        comp_dict = website_id_or_comp
        site_id = comp_dict.get("website_id") or "default"
    else:
        site_id = str(website_id_or_comp)
        comp_dict = competitor or {}

    comp_id = comp_dict.get("id") or str(uuid.uuid4())
    record = {
        **comp_dict,
        "id": comp_id,
        "website_id": site_id,
        "created_at": comp_dict.get("created_at") or datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    updated = False
    for i, c in enumerate(competitors):
        if (c.get("website_id") == site_id or not site_id) and (c.get("id") == comp_id or c.get("domain") == comp_dict.get("domain")):
            competitors[i] = record
            updated = True
            break
    if not updated:
        competitors.append(record)
    _save_json("competitors.json", competitors)
    return record


def list_local_competitors(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
    competitors = _load_json("competitors.json")
    if website_id and website_id not in ("all", "default"):
        return [c for c in competitors if c.get("website_id") == website_id]
    return competitors


def delete_local_competitor(website_id_or_id: str, competitor_id: Optional[str] = None) -> bool:
    competitors = _load_json("competitors.json")
    initial_len = len(competitors)
    if competitor_id is not None:
        filtered = [c for c in competitors if not (c.get("website_id") == website_id_or_id and c.get("id") == competitor_id)]
    else:
        filtered = [c for c in competitors if c.get("id") != website_id_or_id]
    if len(filtered) < initial_len:
        _save_json("competitors.json", filtered)
        return True
    return False


def save_local_competitor_pages(website_id: str, pages: List[Dict[str, Any]]) -> None:
    all_pages = _load_json("competitor_pages.json")
    existing_urls = {p.get("url") for p in all_pages if p.get("website_id") == website_id}
    for p in pages:
        if p.get("url") not in existing_urls:
            all_pages.insert(0, {**p, "website_id": website_id, "discovered_at": datetime.utcnow().isoformat()})
    _save_json("competitor_pages.json", all_pages[:200])


def list_local_competitor_pages(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
    all_pages = _load_json("competitor_pages.json")
    if website_id and website_id not in ("all", "default"):
        return [p for p in all_pages if p.get("website_id") == website_id]
    return all_pages


# ============================================================================
# ROI POST-FIX TRACKER (28-DAY EVIDENCE OF ROI)
# ============================================================================

def save_local_roi_tracked_fix(fix: Dict[str, Any]) -> Dict[str, Any]:
    fixes = _load_json("roi_tracked_fixes.json")
    fix_id = fix.get("id") or str(uuid.uuid4())
    record = {
        **fix,
        "id": fix_id,
        "created_at": fix.get("created_at") or datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    updated = False
    for i, item in enumerate(fixes):
        if item.get("id") == fix_id:
            fixes[i] = record
            updated = True
            break
    if not updated:
        fixes.insert(0, record)
    _save_json("roi_tracked_fixes.json", fixes)
    return record


def list_local_roi_tracked_fixes(website_id: Optional[str] = None) -> List[Dict[str, Any]]:
    fixes = _load_json("roi_tracked_fixes.json")
    if website_id and website_id not in ("all", "default"):
        return [f for f in fixes if f.get("website_id") == website_id]
    return fixes


def get_local_roi_tracked_fix(fix_id: str) -> Optional[Dict[str, Any]]:
    fixes = _load_json("roi_tracked_fixes.json")
    for f in fixes:
        if f.get("id") == fix_id:
            return f
    return None


def update_local_roi_tracked_fix(fix_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fixes = _load_json("roi_tracked_fixes.json")
    for i, f in enumerate(fixes):
        if f.get("id") == fix_id:
            updated_record = {**f, **updates, "updated_at": datetime.utcnow().isoformat()}
            fixes[i] = updated_record
            _save_json("roi_tracked_fixes.json", fixes)
            return updated_record
    return None


# Backward-compatibility aliases for ROI fix tracking
save_local_roi_fix = save_local_roi_tracked_fix
list_local_roi_fixes = list_local_roi_tracked_fixes
get_local_roi_fix = get_local_roi_tracked_fix
update_local_roi_fix = update_local_roi_tracked_fix


# ============================================================================
# AUDITS & KEYWORD RESEARCH
# ============================================================================

def save_local_audit(audit: Dict[str, Any]) -> Dict[str, Any]:
    audits = _load_json("audits.json")
    audit_id = audit.get("id") or str(uuid.uuid4())
    audit["id"] = audit_id
    # Ensure website scoping: without it a stored audit leaks into every other
    # website's health/indexation view.
    if "website_id" not in audit:
        audit["website_id"] = audit.get("site_id") or audit.get("url") or "default"
    audit["created_at"] = audit.get("created_at") or datetime.utcnow().isoformat()
    audits.insert(0, audit)
    _save_json("audits.json", audits)
    return audit


def list_local_audits(website_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    audits = _load_json("audits.json")
    if website_id and website_id not in ("all", "default"):
        audits = [a for a in audits if a.get("website_id") == website_id]
    return audits[:limit]


def save_local_keyword_research(research: Dict[str, Any]) -> Dict[str, Any]:
    items = _load_json("keyword_research.json")
    r_id = research.get("id") or str(uuid.uuid4())
    research["id"] = r_id
    research["created_at"] = research.get("created_at") or datetime.utcnow().isoformat()
    items.insert(0, research)
    _save_json("keyword_research.json", items)
    return research


def list_local_keyword_research(website_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    items = _load_json("keyword_research.json")
    if website_id and website_id not in ("all", "default"):
        items = [i for i in items if i.get("website_id") == website_id]
    return items[:limit]


def save_local_keyword(keyword: Dict[str, Any]) -> Dict[str, Any]:
    items = _load_json("keywords.json")
    k_id = keyword.get("id") or str(uuid.uuid4())
    keyword["id"] = k_id
    keyword["created_at"] = keyword.get("created_at") or datetime.utcnow().isoformat()
    items.insert(0, keyword)
    _save_json("keywords.json", items)
    return keyword


def list_local_keywords(website_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    items = _load_json("keywords.json")
    if website_id and website_id not in ("all", "default"):
        items = [i for i in items if i.get("website_id") == website_id]
    return items[:limit]


# ============================================================================
# CONNECTOR SETTINGS (non-secret durable fallback: GSC/GA4/Slack/auto-publish)
# ============================================================================

def set_local_connector_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Merge connector settings into a durable local JSON file.

    Used so that saving GSC/GA4/Slack configuration survives even when Supabase
    writes are unavailable. Values that are None are ignored so a partial save
    never erases a previously stored setting.
    """
    current = _load_json("connector_settings.json")
    current_dict = current[0] if current and isinstance(current, list) and current else {}
    incoming = {k: v for k, v in (settings or {}).items() if v is not None}
    updated = {**current_dict, **incoming, "updated_at": datetime.utcnow().isoformat()}
    _save_json("connector_settings.json", [updated])
    return updated


def get_local_connector_settings() -> Dict[str, Any]:
    current = _load_json("connector_settings.json")
    if current and isinstance(current, list) and current:
        return current[0]
    return {}


# ============================================================================
# SLACK MESSAGE LOG (durable fallback when the slack_message_log table is absent)
# ============================================================================

def save_local_slack_message_log(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append a Slack dispatch record to a durable local JSON file.

    Mirrors the `slack_message_log` table so observability survives when the
    table has not been provisioned on the connected Supabase project. The insert
    used to fail silently and the dispatch history was simply lost.
    """
    logs = _load_json("slack_message_log.json")
    record = {
        "id": entry.get("id") or str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        **entry,
    }
    logs.append(record)
    _save_json("slack_message_log.json", logs[-500:])
    return record


def list_local_slack_message_log(website_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    logs = _load_json("slack_message_log.json")
    if website_id:
        logs = [x for x in logs if x.get("website_id") == website_id]
    return logs[-limit:][::-1]




