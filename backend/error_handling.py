"""Safe error response helpers for RankForge.

Prevents information leakage by ensuring no internal error details,
stack traces, file paths, or database details are returned to clients.
"""

import logging
import traceback
import uuid
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("backend.error_handling")

# Correlation ID header name
CORRELATION_ID_HEADER = "X-Request-ID"

# Generic error messages for clients
GENERIC_ERROR_MESSAGE = "An internal server error occurred. Please try again later."
GENERIC_DB_ERROR_MESSAGE = "Database operation failed. Please try again later."
GENERIC_EXTERNAL_API_ERROR_MESSAGE = "External service temporarily unavailable. Please try again later."
GENERIC_AUTH_ERROR_MESSAGE = "Authentication failed. Please check your credentials."
GENERIC_NOT_FOUND_MESSAGE = "Resource not found."
GENERIC_VALIDATION_ERROR_MESSAGE = "Invalid request parameters."


def get_correlation_id(request: Optional[Request] = None, existing_id: Optional[str] = None) -> str:
    """Get or generate a correlation ID for request tracking."""
    if existing_id:
        return existing_id
    if request:
        # Try to get from request state (set by logging middleware)
        correlation_id = getattr(request.state, "correlation_id", None)
        if correlation_id:
            return correlation_id
    return str(uuid.uuid4())


def log_server_error(
    exc: Exception,
    request: Request,
    context: str = "unhandled_exception",
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Log full error details server-side and return correlation ID."""
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    
    log_data = {
        "correlation_id": correlation_id,
        "path": str(request.url.path),
        "method": request.method,
        "context": context,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    if extra:
        log_data.update(extra)
    
    logger.error(
        "%s %s %s [%s] %s: %s\n%s",
        request.method,
        request.url.path,
        context,
        correlation_id,
        type(exc).__name__,
        str(exc),
        traceback.format_exc(),
        extra=log_data,
    )
    
    return correlation_id


def safe_error_response(
    request: Request,
    exc: Exception,
    status_code: int = 500,
    message: Optional[str] = None,
    context: str = "unhandled_exception",
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Generate a safe error response without leaking internal details."""
    correlation_id = log_server_error(exc, request, context, extra)
    
    # Use generic message unless a safe custom one is provided
    if message is None:
        if status_code == 401:
            message = GENERIC_AUTH_ERROR_MESSAGE
        elif status_code == 403:
            message = GENERIC_AUTH_ERROR_MESSAGE
        elif status_code == 404:
            message = GENERIC_NOT_FOUND_MESSAGE
        elif status_code == 422:
            message = GENERIC_VALIDATION_ERROR_MESSAGE
        else:
            message = GENERIC_ERROR_MESSAGE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": message,
            "correlation_id": correlation_id,
        },
        headers={CORRELATION_ID_HEADER: correlation_id},
    )
