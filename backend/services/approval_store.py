"""Approval store with graceful degradation.

Tries Supabase first (table must exist). If the table is missing (service
key/DB password never provided via /setup), rows are kept in per-process
memory so the feature still works; a later setup run persists everything.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database import get_supabase

logger = logging.getLogger("backend.services.approval_store")

_TABLE_MISSING = "blog_approvals not found in Supabase - run /setup with " \
    "service key (or DB password) to persist approvals."
_memory: Dict[str, Dict[str, Any]] = {}
_table_checked = False
_table_exists = False


def _table_available(supabase=None) -> bool:
    global _table_checked, _table_exists
    try:
        sb = supabase or get_supabase()
        sb.table("blog_approvals").select("id").limit(1).execute()
        _table_checked = True
        _table_exists = True
    except Exception:
        _table_checked = True
        _table_exists = False
    return _table_exists


def insert(row: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(row)
    row.setdefault("id", str(uuid.uuid4()))
    row.setdefault("created_at", datetime.utcnow().isoformat())
    row.setdefault("status", "pending")
    row.setdefault("auto_generated", True)
    try:
        supabase = get_supabase()
        if _table_checked and not _table_exists:
            raise RuntimeError(_TABLE_MISSING)
        res = supabase.table("blog_approvals").insert(row).execute()
        _table_checked = _table_exists = True
        return res.data[0] if res.data else row
    except Exception as e:
        logger.warning(f"{_TABLE_MISSING} - using memory store ({e})")
        _memory[row["id"]] = row
        return row


def list_rows(
    status: Optional[str] = None,
    website_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    try:
        supabase = get_supabase()
        if _table_checked and not _table_exists:
            raise RuntimeError(_TABLE_MISSING)
        q = supabase.table("blog_approvals").select("*").order("created_at", desc=True).limit(limit)
        if status:
            q = q.eq("status", status)
        if website_id:
            q = q.eq("website_id", website_id)
        _table_checked = _table_exists = True
        return q.execute().data or []
    except Exception:
        rows = list(_memory.values())
        if status:
            rows = [r for r in rows if r.get("status") == status]
        if website_id:
            rows = [r for r in rows if str(r.get("website_id")) == website_id]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows[:limit]


def get(approval_id: str) -> Optional[Dict[str, Any]]:
    try:
        if _table_checked and not _table_exists:
            raise RuntimeError(_TABLE_MISSING)
        res = (
            get_supabase()
            .table("blog_approvals")
            .select("*")
            .eq("id", approval_id)
            .maybe_single()
            .execute()
        )
        if res and res.data:
            return res.data
        return _memory.get(approval_id)
    except Exception:
        return _memory.get(approval_id)


def update(approval_id: str, updates: Dict[str, Any]) -> bool:
    ok = False
    try:
        if _table_checked and not _table_exists:
            raise RuntimeError(_TABLE_MISSING)
        get_supabase().table("blog_approvals").update(updates).eq("id", approval_id).execute()
        ok = True
    except Exception:
        ok = False
    if approval_id in _memory:
        _memory[approval_id].update(updates)
        ok = True
    return ok


def count(status: str, website_id: Optional[str] = None) -> int:
    try:
        supabase = get_supabase()
        if _table_checked and not _table_exists:
            raise RuntimeError(_TABLE_MISSING)
        q = supabase.table("blog_approvals").select("id", count="exact").eq("status", status)
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.execute()
        return getattr(res, "count", None) or len(res.data or [])
    except Exception:
        return sum(1 for r in _memory.values() if r.get("status") == status)


def storage_backend() -> str:
    try:
        return "supabase" if _table_available() else "memory"
    except Exception:
        return "memory"
