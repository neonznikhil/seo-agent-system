"""Dual-backend persistence for RankForge intelligence tables.

Every read/write goes to Supabase when it is configured. When it is not, the
record is kept in a local JSON store so the software remains runnable without
credentials. Neither path ever fabricates values: a missing record returns an
empty result and the caller reports ``unconfigured``, never a placeholder.
"""

import json
import logging
import os
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("backend.services.intelligence_store")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_STORE_PATH = os.path.join(_ROOT, "data", "intelligence_store.json")

# Tables owned by this module. Kept explicit so an unknown name fails loudly
# instead of silently creating a phantom collection.
MANAGED_TABLES = {
    "site_metrics_daily",
    "action_items",
    "conversions",
    "keyword_lead_attribution",
    "change_events",
    "competitor_rankings",
    "competitor_new_pages",
    "sov_snapshots",
    "measurement_windows",
    "measurement_snapshots",
    "effort_costs",
    "ymyl_classifications",
}


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _load() -> Dict[str, List[Dict[str, Any]]]:
    if not os.path.exists(_STORE_PATH):
        return {}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("[intelligence_store] could not read store: %s", exc)
        return {}


def _save(data: Dict[str, List[Dict[str, Any]]]) -> None:
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
    tmp = f"{_STORE_PATH}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=_json_default)
        os.replace(tmp, _STORE_PATH)
    except OSError as exc:
        logger.error("[intelligence_store] could not write store: %s", exc)


def _check_table(table: str) -> None:
    if table not in MANAGED_TABLES:
        raise ValueError(f"unmanaged table: {table}")


def supabase_configured() -> bool:
    return bool(
        (os.getenv("SUPABASE_URL") or "")
        and (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_KEY")
            or ""
        )
    )


def _client():
    """Return a Supabase client, or None when credentials are absent."""
    if not supabase_configured():
        return None
    try:
        from database import get_supabase

        return get_supabase()
    except Exception as exc:  # noqa: BLE001 - degrade to local store
        logger.warning("[intelligence_store] supabase unavailable: %s", exc)
        return None


def _matches(row: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    for key, expected in filters.items():
        if expected is None:
            continue
        if str(row.get(key)) != str(expected):
            return False
    return True


def insert(table: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Insert one record. Returns the stored row including its id."""
    _check_table(table)
    row = dict(record)
    row.setdefault("id", str(uuid.uuid4()))
    row.setdefault("created_at", datetime.utcnow().isoformat())

    client = _client()
    if client is not None:
        try:
            res = client.table(table).insert(row).execute()
            if res.data:
                return res.data[0]
            return row
        except Exception as exc:  # noqa: BLE001
            logger.warning("[intelligence_store] insert %s fell back to local: %s", table, exc)

    data = _load()
    data.setdefault(table, []).append(row)
    _save(data)
    return row


def select(
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None,
    desc: bool = True,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Select records, newest-first by default."""
    _check_table(table)
    filters = filters or {}

    client = _client()
    if client is not None:
        try:
            query = client.table(table).select("*")
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
            if order_by:
                query = query.order(order_by, desc=desc)
            if limit:
                query = query.limit(limit)
            res = query.execute()
            return res.data or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("[intelligence_store] select %s fell back to local: %s", table, exc)

    rows = [r for r in _load().get(table, []) if _matches(r, filters)]
    if order_by:
        rows.sort(key=lambda r: str(r.get(order_by) or ""), reverse=desc)
    if limit:
        rows = rows[:limit]
    return rows


def update(
    table: str, record_id: str, patch: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Patch a record by id. Returns the updated row, or None if absent."""
    _check_table(table)
    client = _client()
    if client is not None:
        try:
            res = client.table(table).update(patch).eq("id", record_id).execute()
            if res.data:
                return res.data[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[intelligence_store] update %s fell back to local: %s", table, exc)

    data = _load()
    for row in data.get(table, []):
        if str(row.get("id")) == str(record_id):
            row.update(patch)
            _save(data)
            return row
    return None


def get(table: str, record_id: str) -> Optional[Dict[str, Any]]:
    _check_table(table)
    rows = select(table, {"id": record_id}, limit=1)
    return rows[0] if rows else None


def upsert(
    table: str,
    record: Dict[str, Any],
    keys: List[str],
) -> Tuple[Dict[str, Any], bool]:
    """Insert or update by natural key. Returns (row, created).

    Ingestion runs repeatedly, so writing the same observation twice must not
    create a second row or double-count it downstream. Supabase enforces this
    with unique constraints; the local store enforces it here.
    """
    _check_table(table)
    filters = {k: record.get(k) for k in keys}
    existing = select(table, filters, limit=1)
    if existing:
        updated = update(table, str(existing[0].get("id")), record) or existing[0]
        return updated, False
    return insert(table, record), True


def storage_backend() -> str:
    return "supabase" if supabase_configured() else "local_json"