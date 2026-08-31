"""RankForge Persistent Local Store.
Provides transparent local JSON persistence and multi-tenant fallback
when Supabase RLS policies restrict anon writes in local dev environments.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("backend.services.local_store")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
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
    # Return latest active or latest connection
    for c in reversed(conns):
        if c.get("is_active", True):
            return c
    return conns[-1]


