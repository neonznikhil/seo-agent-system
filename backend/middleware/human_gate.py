import logging
from functools import wraps
from fastapi import Request, HTTPException
from database import get_supabase
from datetime import datetime

logger = logging.getLogger("backend.middleware.human_gate")


from middleware import auth as _auth_module
from utils.errors import is_connectivity_error


def _identity_exists(user_id: str) -> bool:
    """_validate_user_exists that turns an unreachable identity store into a denial.

    _validate_user_exists raises when Supabase is unreachable (it must not guess).
    These gates deny by default, so without this the raise would escape as an
    opaque 500. We resolve the function through the auth module so runtime
    monkeypatching (and tests) of middleware.auth._validate_user_exists still works.
    """
    try:
        return _auth_module._validate_user_exists(user_id)
    except Exception as exc:
        # Fail CLOSED: an identity we cannot verify is not an approved identity.
        logger.error(f"[HumanGate] identity store unavailable, denying {user_id}: {exc}")
        raise HTTPException(
            status_code=403,
            detail="Forbidden: identity could not be verified (account store unavailable). Retry shortly.",
        )


def require_human(func):
    """Decorator to enforce human approval for critical actions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request") or (args[0] if args and hasattr(args[0], "headers") else None)
        
        if not request:
            return await func(*args, **kwargs)
        
        user_id = request.headers.get("X-User-Id")
        ip = request.client.host if request.client else "unknown"
        
        if not user_id:
            from database import get_supabase
            try:
                get_supabase().table("critical_action_logs").insert({
                    "action": request.url.path,
                    "status": "blocked_no_human",
                    "ip": ip,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            except Exception as e:
                logger.error(f"Failed to log blocked action: {e}")
            
            raise HTTPException(
                403, 
                "Human approval required - click 'Approve' button in dashboard which sends X-User-Id header"
            )
        
        if not _identity_exists(user_id):
            raise HTTPException(
                403,
                f"Forbidden: Invalid X-User-Id '{user_id}' not found in database"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper


async def require_human_for_request(request: Request):
    """Check if request has human approval."""
    user_id = request.headers.get("X-User-Id")
    ip = request.client.host if request.client else "unknown"

    if not user_id:
        raise HTTPException(403, "Human approval required - provide X-User-Id header")

    if not _identity_exists(user_id):
        raise HTTPException(403, f"Forbidden: Invalid X-User-Id '{user_id}' not found in database")

    return user_id


# Identities that must never be accepted as a human publisher, even though
# they look like user ids. Compared here — the single canonical publishing
# gate — so no router needs its own fallback-identity blocklist.
_BLOCKED_PUBLISHER_IDENTITIES = frozenset({
    "human-approved",
    "autonomous",
    "system",
    "dashboard",
    "admin",
    "anonymous",
    "a0000000-0000-0000-0000-000000000001",
})


async def require_verified_publisher(request: Request) -> str:
    """Canonical publishing gate: verified human identity or 403.

    Rejects missing/blank/blocked identities AND identities absent from the
    users table. No fallback identity is ever returned — callers must deny
    the request when this raises. Use for every WordPress write path.
    """
    user_id = (request.headers.get("X-User-Id") or "").strip()
    if not user_id or user_id in _BLOCKED_PUBLISHER_IDENTITIES:
        raise HTTPException(
            status_code=403,
            detail="Valid X-User-Id required. Publishing without human identity is not permitted.",
        )
    if not _identity_exists(user_id):
        raise HTTPException(status_code=403, detail="User not found")
    return user_id


def human_approval_required():
    """FastAPI dependency for human approval."""
    async def dependency(request: Request):
        user_id = request.headers.get("X-User-Id")
        ip = request.client.host if request.client else "unknown"
        
        if not user_id:
            from database import get_supabase
            try:
                get_supabase().table("critical_action_logs").insert({
                    "action": request.url.path,
                    "status": "blocked_no_human",
                    "ip": ip,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            except Exception as e:
                logger.error(f"Failed to log blocked action: {e}")
            
            raise HTTPException(
                403, 
                "Human approval required - provide X-User-Id header via dashboard Approve button"
            )
        
        if not _identity_exists(user_id):
            raise HTTPException(
                403,
                f"Forbidden: Invalid X-User-Id '{user_id}' not found in database"
            )
        
        return user_id
    
    return dependency