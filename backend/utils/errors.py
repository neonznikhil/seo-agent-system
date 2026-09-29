"""Classify exceptions so an unreachable dependency is reported honestly.

A database or upstream API being down is transient and retryable, not a bug in
the request. Route handlers must surface that as 503 (with Retry-After) rather
than a generic 500, so the UI can tell the user to retry instead of showing a
hard failure.
"""

import logging

logger = logging.getLogger("backend.utils.errors")

_CONNECTIVITY_EXC_NAMES = {
    "ConnectError",
    "ConnectTimeout",
    "ReadTimeout",
    "ReadError",
    "PoolTimeout",
    "RemoteProtocolError",
    "NetworkError",
    "ConnectionError",
    "ConnectionRefusedError",
    "ConnectionResetError",
    "gaierror",
}

_CONNECTIVITY_MARKERS = (
    "name or service not known",
    "temporary failure in name resolution",
    "connection refused",
    "connection reset",
    "getaddrinfo failed",
    "nodename nor servname",
    "timed out",
    "timeout",
)


def is_connectivity_error(exc: Exception) -> bool:
    """True when `exc` is an unreachable-dependency/network failure."""
    name = type(exc).__name__
    if name in _CONNECTIVITY_EXC_NAMES:
        return True
    text = f"{name}: {exc}".lower()
    return any(marker in text for marker in _CONNECTIVITY_MARKERS)


def service_unavailable_detail() -> str:
    return (
        "A required backend service (database or upstream API) is temporarily "
        "unavailable. Please retry shortly."
    )


def raise_db_or_500(exc: Exception, fallback_detail: str) -> None:
    """Re-raise `exc` as HTTPException: 503 when the dependency is unreachable
    (retryable), otherwise 500 with `fallback_detail`."""
    from fastapi import HTTPException

    if is_connectivity_error(exc):
        raise HTTPException(
            status_code=503,
            detail=service_unavailable_detail(),
            headers={"Retry-After": "5"},
        )
    raise HTTPException(status_code=500, detail=fallback_detail)
