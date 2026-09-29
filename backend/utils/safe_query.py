"""Safe Supabase read helpers.

The database is an external dependency: it can be unreachable (DNS/network
failure) or a table can be missing. Route handlers must never turn that into a
500. `safe_rows` runs a builder callback and returns [] instead of raising, so a
page still renders with whatever durable local data exists.
"""

import logging
from typing import Any, Callable, List

logger = logging.getLogger("backend.utils.safe_query")


def safe_rows(builder: Callable[[Any], Any], label: str = "query") -> List[dict]:
    """Execute `builder(supabase)` and return a list of rows, never raising."""
    try:
        from database import get_supabase

        res = builder(get_supabase())
        data = getattr(res, "data", None)
        if data is None and isinstance(res, dict):
            data = res.get("data")
        return data or []
    except Exception as exc:
        logger.warning("[safe_query] %s failed, returning []: %s", label, exc)
        return []


def safe_value(builder: Callable[[Any], Any], fallback: Any = None, label: str = "query") -> Any:
    """Execute `builder(supabase)` and return `fallback` on any failure."""
    try:
        from database import get_supabase

        return builder(get_supabase())
    except Exception as exc:
        logger.warning("[safe_query] %s failed, using fallback: %s", label, exc)
        return fallback
