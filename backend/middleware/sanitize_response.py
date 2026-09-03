"""Response sanitization middleware for RankForge.

Automatically sanitizes HTML fields in JSON responses to prevent XSS.
"""

import json
import logging
from typing import Callable, Dict, Any, List, Union

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("backend.middleware.sanitize_response")

HTML_FIELD_NAMES = {
    "html_content",
    "original_html",
    "final_html",
    "writer_html",
    "content",
    "html",
    "body",
    "body_html",
    "post_content",
    "message",
    "description",
    "excerpt",
}


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize HTML strings in data structures."""
    if isinstance(value, str):
        # Only sanitize strings that look like HTML
        if "<" in value and ">" in value and any(tag in value.lower() for tag in ["<p", "<div", "<span", "<h1", "<h2", "<h3", "<table", "<ul", "<ol", "<li", "<a", "<img", "<br", "<b", "<i", "<strong", "<em"]):
            from security import sanitize_html
            return sanitize_html(value)
        return value
    elif isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


class SanitizeResponseMiddleware(BaseHTTPMiddleware):
    """Middleware that sanitizes HTML in JSON responses."""

    def __init__(self, app: Callable):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        path = request.url.path or ""
        
        # Skip streaming endpoints and non-API paths
        if any(path.startswith(prefix) for prefix in ["/docs", "/openapi.json", "/redoc", "/stream", "/sse"]):
            return await call_next(request)
        
        response = await call_next(request)
        
        # Only process regular JSON responses, skip streaming
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response
        
        if response.headers.get("transfer-encoding") == "chunked":
            return response
        
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            if body:
                data = json.loads(body.decode("utf-8"))
                sanitized = _sanitize_value(data)
                new_body = json.dumps(sanitized, default=str).encode("utf-8")
                
                new_response = Response(
                    content=new_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type="application/json",
                )
                return new_response
        except Exception as e:
            logger.warning(f"[Sanitize] Failed to sanitize response: {e}")
        
        return response
