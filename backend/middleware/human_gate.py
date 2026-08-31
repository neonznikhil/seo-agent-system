import logging
from functools import wraps
from fastapi import Request, HTTPException
from ..database import get_supabase
from datetime import datetime

logger = logging.getLogger("backend.middleware.human_gate")


from ..middleware.auth import _validate_user_exists


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
            from ..database import get_supabase
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
        
        if not _validate_user_exists(user_id):
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
    
    if not _validate_user_exists(user_id):
        raise HTTPException(403, f"Forbidden: Invalid X-User-Id '{user_id}' not found in database")
    
    return user_id


def human_approval_required():
    """FastAPI dependency for human approval."""
    async def dependency(request: Request):
        user_id = request.headers.get("X-User-Id")
        ip = request.client.host if request.client else "unknown"
        
        if not user_id:
            from ..database import get_supabase
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
        
        if not _validate_user_exists(user_id):
            raise HTTPException(
                403,
                f"Forbidden: Invalid X-User-Id '{user_id}' not found in database"
            )
        
        return user_id
    
    return dependency