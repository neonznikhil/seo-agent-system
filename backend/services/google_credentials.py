"""Resolve Google service-account credentials from a path, raw JSON, or dict.

The Connectors UI lets a user paste the service-account JSON. The save endpoints
persist that payload as `GA4_CREDENTIALS_JSON` / `GSC_SERVICE_ACCOUNT_JSON`, but
the Google client libraries only accept a *file path*
(`from_service_account_file`). The services read only `*_CREDENTIALS_PATH`, so
pasted credentials were stored and then never used — GA4/GSC always reported
"not configured" even after a successful save. Accepting either form fixes that.

A pasted JSON blob also commonly carries the PEM private key with escaped `\\n`
instead of real newlines; `service_account` rejects that with an opaque error, so
the key is un-escaped here.
"""

import json
import os
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger("backend.services.google_credentials")


class GoogleCredentialsError(ValueError):
    """Raised when no usable Google service-account credential can be found."""


def _as_info(source: Any) -> Optional[Dict[str, Any]]:
    """Return a service-account info dict when `source` is JSON content."""
    if isinstance(source, dict):
        info = dict(source)
    elif isinstance(source, str):
        text = source.strip()
        if not text or not text.startswith("{"):
            return None
        try:
            info = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(info, dict):
            return None
    else:
        return None

    # A JSON file on disk contains real newlines; a value pasted into a form
    # usually contains the escaped form ("-----BEGIN PRIVATE KEY-----\nMIIE...").
    key = info.get("private_key")
    if isinstance(key, str) and "\\n" in key:
        info["private_key"] = key.replace("\\n", "\n")
    return info


def _as_existing_path(source: Any) -> Optional[str]:
    """Return `source` when it is a path to an existing credentials file."""
    if isinstance(source, str) and source and not source.strip().startswith("{") and os.path.isfile(source):
        return source
    return None


def _iter_sources(
    candidates: Iterable[Any],
    json_env_keys: Sequence[str],
    path_env_keys: Sequence[str],
) -> Iterable[Any]:
    """Yield explicit candidates first, then env values (JSON before path)."""
    for candidate in candidates:
        if candidate:
            yield candidate
    for key in json_env_keys:
        value = os.getenv(key)
        if value:
            yield value
    for key in path_env_keys:
        value = os.getenv(key)
        if value:
            yield value


def has_service_account_credentials(
    candidates: Iterable[Any] = (),
    json_env_keys: Sequence[str] = (),
    path_env_keys: Sequence[str] = (),
) -> bool:
    """True when any candidate resolves to usable credential content.

    Only inspects shape (parseable JSON or an existing file) — it never performs
    a network call, so callers can report "configured" without pretending the
    credentials are valid.
    """
    for source in _iter_sources(candidates, json_env_keys, path_env_keys):
        if _as_info(source) is not None or _as_existing_path(source) is not None:
            return True
    return False


def load_service_account_credentials(
    scopes: Sequence[str],
    candidates: Iterable[Any] = (),
    json_env_keys: Sequence[str] = (),
    path_env_keys: Sequence[str] = (),
):
    """Build google service_account.Credentials from the first usable source.

    Raises GoogleCredentialsError with an actionable message when nothing usable
    is found, rather than letting the client library raise an opaque error.
    """
    from google.oauth2 import service_account

    tried: List[str] = []
    for source in _iter_sources(candidates, json_env_keys, path_env_keys):
        info = _as_info(source)
        if info is not None:
            try:
                return service_account.Credentials.from_service_account_info(info, scopes=list(scopes))
            except Exception as e:
                tried.append(f"JSON payload rejected ({str(e)[:80]})")
                continue
        path = _as_existing_path(source)
        if path:
            try:
                return service_account.Credentials.from_service_account_file(path, scopes=list(scopes))
            except Exception as e:
                tried.append(f"file {path} rejected ({str(e)[:80]})")
                continue

    detail = f" ({'; '.join(tried)})" if tried else ""
    raise GoogleCredentialsError(
        "No Google service-account credentials found. Paste the service-account "
        "JSON in Connectors (or set GA4_CREDENTIALS_JSON / GSC_SERVICE_ACCOUNT_JSON, "
        "or point *_CREDENTIALS_PATH at the file)." + detail
    )
