"""Schema-resilient Supabase writes for the `websites` table.

PostgREST is all-or-nothing: if a payload contains one column the target
project does not have, the whole INSERT/UPDATE is rejected with PGRST204 and
nothing is written. A deployment that never applied every optional column (for
example `wordpress_password_encrypted`, which DDL migrations add only when a
direct Postgres URL is configured) therefore silently lost WordPress
credentials: the API fell back to the local mirror and still reported success.

`write_website` retries without the offending column so the real credentials
land in Supabase on projects with a reduced schema, and returns the written
rows so callers can tell a durable write from a fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("backend.services.supabase_write")

# "Could not find the 'wordpress_password_encrypted' column of 'websites' in the schema cache"
_UNKNOWN_COLUMN_RE = re.compile(r"Could not find the '([^']+)' column")
# Raw Postgres phrasing: column "wp_verified" of relation "websites" does not exist
_PG_UNKNOWN_COLUMN_RE = re.compile(r'column "([^"]+)" of relation "[^"]+" does not exist')
# Cap retries so a pathological error cannot loop forever. Six covers every
# optional column we ship today with headroom for one more.
_MAX_STRIP_RETRIES = 6

_OPTIONAL_COLUMNS = (
    "wordpress_password_encrypted",
    "wp_verified_at",
    "wp_verified_role",
    "wp_last_error",
    "wp_verified",
)


def _unknown_column(exc: Exception) -> Optional[str]:
    message = str(getattr(exc, "message", "") or exc)
    match = _UNKNOWN_COLUMN_RE.search(message) or _PG_UNKNOWN_COLUMN_RE.search(message)
    if match:
        return match.group(1)
    # Older PostgREST builds omit the quoted column; treat any PGRST204 as a
    # schema rejection and fall back to stripping optional columns below.
    if "PGRST204" in message:
        return ""
    return None


def write_website(
    supabase,
    payload: Dict[str, Any],
    website_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Insert or update a `websites` row, tolerating unknown columns.

    Pass `website_id` to update an existing row, or omit it to insert. When
    `account_id` is given on an update, the row must belong to that tenant.
    Returns the rows Supabase actually wrote (empty list when nothing was
    persisted).
    """
    data = dict(payload)

    for _ in range(_MAX_STRIP_RETRIES):
        try:
            if website_id:
                query = supabase.table("websites").update(data).eq("id", website_id)
                if account_id:
                    query = query.eq("account_id", account_id)
                res = query.execute()
            else:
                res = supabase.table("websites").insert(data).execute()
            return res.data or []
        except Exception as exc:  # noqa: BLE001 - we inspect the provider error
            column = _unknown_column(exc)
            if column is None:
                raise
            if column and column in data:
                logger.warning("[Supabase] websites.%s absent; retrying write without it", column)
                data.pop(column, None)
                if column in _OPTIONAL_COLUMNS:
                    # The optional columns ship in the same migration set, so a
                    # project missing one is missing them all. Drop the set in a
                    # single retry instead of one round trip per column.
                    for optional in _OPTIONAL_COLUMNS:
                        data.pop(optional, None)
                continue
            # Unknown column name (or a generic PGRST204): drop known-optional
            # columns one at a time until the write is accepted.
            stripped = False
            for optional in _OPTIONAL_COLUMNS:
                if optional in data:
                    data.pop(optional)
                    stripped = True
                    break
            if not stripped:
                raise
    logger.error("[Supabase] websites write kept failing after stripping optional columns")
    return []
