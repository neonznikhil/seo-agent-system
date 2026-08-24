"""RankForge Open System Middleware.
Provides default account context without blocking requests with auth requirements.
"""

import logging
from typing import Optional, Dict, Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..database import get_supabase, set_account_context

logger = logging.getLogger("backend.middleware.auth")

DEFAULT_ACCOUNT_ID = "a0000000-0000-0000-0000-000000000001"


def get_current_account_id(request: Request) -> str:
    """Helper to safely retrieve account_id with default fallback."""
    account_id = getattr(request.state, "account_id", None)
    if account_id:
        return str(account_id)
    return DEFAULT_ACCOUNT_ID


async def authenticate_request(request: Request) -> Dict[str, Any]:
    """Pass-through request context builder."""
    request.state.account_id = DEFAULT_ACCOUNT_ID
    request.state.account = {
        "id": DEFAULT_ACCOUNT_ID,
        "email": "admin@rankforge.ai",
        "full_name": "Lead SEO Architect",
        "plan": "agency",
    }
    set_account_context(get_supabase(), DEFAULT_ACCOUNT_ID)
    return request.state.account


async def require_auth(request: Request) -> Dict[str, Any]:
    """Dependency helper returning default account."""
    return await authenticate_request(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """Pass-through middleware establishing default tenant context."""

    async def dispatch(self, request: Request, call_next):
        request.state.account_id = DEFAULT_ACCOUNT_ID
        request.state.account = {
            "id": DEFAULT_ACCOUNT_ID,
            "email": "admin@rankforge.ai",
            "full_name": "Lead SEO Architect",
            "plan": "agency",
        }
        try:
            set_account_context(get_supabase(), DEFAULT_ACCOUNT_ID)
        except Exception:
            pass

        return await call_next(request)
