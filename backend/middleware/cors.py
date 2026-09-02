"""Permissive CORS middleware for RankForge.

Reflects the request Origin header so preflight always succeeds.
Security is enforced at the application layer via X-User-Id, Supabase RLS,
and auth checks, so browser CORS is not the security boundary.
"""

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("backend.middleware.cors")


class PermissiveCORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware that reflects the request Origin.

    - Reflects request Origin (or * if missing) so preflight always succeeds.
    - Echoes Access-Control-Request-Headers if browser sends them, otherwise
      falls back to explicit allow-list including X-Website-Id.
    - Must be outermost middleware (added LAST via app.add_middleware).
    """

    def __init__(self, app: Callable):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin") or "*"
        method = (request.method or "").upper()
        # Browser sends lower-case header names; echo them back case-preservingly
        requested_headers = request.headers.get("access-control-request-headers")

        # Determine allowed headers: echo what browser asks for, or fallback
        if requested_headers:
            # Echo requested headers verbatim + ensure our custom ones are present
            allow_headers = requested_headers
            # Ensure X-User-Id / X-Website-Id are present even if browser omits due to case
            lower = allow_headers.lower()
            extras = []
            for h in ["X-User-Id", "X-Website-Id", "Authorization", "Content-Type", "X-Requested-With"]:
                if h.lower() not in lower:
                    extras.append(h)
            if extras:
                allow_headers = f"{allow_headers}, {', '.join(extras)}"
        else:
            allow_headers = "Content-Type, X-User-Id, X-Website-Id, Authorization, X-Requested-With"

        if method == "OPTIONS":
            # Preflight: short-circuit with 204, never hit auth/router
            response = Response(status_code=204)
            # Ensure content-length 0 for clean preflight
            response.headers["Content-Length"] = "0"
        else:
            response = await call_next(request)

        # Always reflect origin — critical for browser CORS
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
        response.headers["Access-Control-Allow-Headers"] = allow_headers
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Process-Time"
        response.headers["Access-Control-Max-Age"] = "600"

        return response
