"""Strict CORS middleware for RankForge.

Uses an explicit allow-list from ALLOWED_CORS_ORIGINS env var.
Security is enforced at the application layer via X-User-Id, Supabase RLS,
and auth checks.
"""

import fnmatch
import logging
import os
from typing import List

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("backend.middleware.cors")

try:
    from config import ALLOWED_CORS_ORIGINS
except ImportError:
    try:
        from backend.config import ALLOWED_CORS_ORIGINS
    except ImportError:
        _default_origins = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000,https://*.onrender.com"
        _raw = os.getenv("ALLOWED_CORS_ORIGINS") or os.getenv("CORS_ORIGINS") or _default_origins
        ALLOWED_CORS_ORIGINS = [
            origin.strip().rstrip("/")
            for origin in _raw.split(",")
            if origin.strip() and origin.strip() != "*"
        ]

ALLOWED_ORIGINS: List[str] = ALLOWED_CORS_ORIGINS


def is_origin_allowed(origin: str, allowed_patterns: List[str]) -> bool:
    """Check if origin matches any allowed origin or wildcard pattern."""
    if not origin:
        return False
    norm_origin = origin.strip().rstrip("/")
    for pattern in allowed_patterns:
        pat = pattern.strip().rstrip("/")
        if not pat or pat == "*":
            continue
        if norm_origin.lower() == pat.lower() or fnmatch.fnmatch(norm_origin.lower(), pat.lower()):
            return True
    return False


class StrictCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that allows origins matching ALLOWED_CORS_ORIGINS (including wildcards)."""

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        method = request.method or ""

        allowed_origin = origin if is_origin_allowed(origin, ALLOWED_ORIGINS) else ""

        if method == "OPTIONS":
            response = Response(status_code=204)
            if allowed_origin:
                response.headers["Access-Control-Allow-Origin"] = allowed_origin
                response.headers["Vary"] = "Origin"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-User-Id, Authorization, X-Requested-With, X-Website-Id"
                response.headers["Access-Control-Max-Age"] = "600"
            return response

        response = await call_next(request)

        if allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-User-Id, Authorization, X-Requested-With, X-Website-Id"
            response.headers["Access-Control-Max-Age"] = "600"

        return response
