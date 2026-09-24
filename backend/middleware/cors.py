"""Strict CORS middleware for RankForge.

Uses an explicit allow-list. Security is enforced at the application layer via
X-User-Id, Supabase RLS, and auth checks.
"""

import logging
from typing import List

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config import ALLOWED_CORS_ORIGINS

logger = logging.getLogger("backend.middleware.cors")

# Sourced from config so it honours ALLOWED_CORS_ORIGINS, the localhost defaults
# and FRONTEND_URL. Reading the env var here directly would ignore all three and
# leave the browser blocked whenever the var is unset.
ALLOWED_ORIGINS: List[str] = list(ALLOWED_CORS_ORIGINS)


class StrictCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that only allows origins from ALLOWED_CORS_ORIGINS."""

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        method = request.method or ""

        allowed_origin = origin if origin in ALLOWED_ORIGINS else ""

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
