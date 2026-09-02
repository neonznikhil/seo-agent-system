"""Permissive CORS middleware for RankForge.

Allows all origins, methods, and headers. Security is enforced at the
application layer via X-User-Id, Supabase RLS, and auth checks, so browser
CORS is not a security boundary here.
"""

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("backend.middleware.cors")


class PermissiveCORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware that allows all origins."""

    def __init__(self, app: Callable):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin", "*")
        method = request.method or ""

        if method == "OPTIONS":
            response = Response(status_code=204)
        else:
            response = await call_next(request)

        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "600"

        return response
