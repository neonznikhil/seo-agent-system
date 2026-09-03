import logging
import os
from typing import Optional, Callable
from fastapi import Request, HTTPException, Depends, Header
from database import get_supabase

logger = logging.getLogger("backend.middleware.rbac")

ROLE_HIERARCHY = {
    "owner": 3,
    "editor": 2,
    "viewer": 1
}

DEFAULT_ACCOUNT_ID = "a0000000-0000-0000-0000-000000000001"
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"


def require_role(min_role: str = "viewer"):
    """FastAPI dependency to enforce server-side Role-Based Access Control (RBAC)."""
    min_level = ROLE_HIERARCHY.get(min_role.lower(), 1)

    async def role_checker(
        request: Request,
        x_website_id: Optional[str] = Header(None, alias="X-Website-Id")
    ):
        # Extract server-verified account_id from request state (set by AuthMiddleware)
        account_id = getattr(request.state, "account_id", None)
        if not account_id:
            raw_id = request.headers.get("x-user-id") or request.headers.get("X-User-Id")
            account_id = raw_id.strip() if raw_id else None

        if not account_id:
            if IS_PRODUCTION:
                raise HTTPException(status_code=401, detail="Authentication required for role verification")
            account_id = DEFAULT_ACCOUNT_ID

        user_role = "viewer"
        supabase = get_supabase()

        try:
            # 1. Check if user is the account owner in accounts table
            acc = supabase.table("accounts").select("id").eq("id", account_id).limit(1).execute()
            if acc.data and len(acc.data) > 0:
                user_role = "owner"
            else:
                # 2. Check workspace_members role
                q = supabase.table("workspace_members").select("role").eq("user_id", account_id)
                if x_website_id:
                    q = q.eq("website_id", x_website_id)
                res = q.limit(1).execute()
                if res.data and len(res.data) > 0:
                    user_role = res.data[0].get("role", "viewer")
                else:
                    user_role = "viewer"
        except Exception as e:
            logger.debug(f"[RBAC] Member lookup query note: {e}")
            user_role = "viewer"

        user_level = ROLE_HIERARCHY.get(user_role.lower(), 1)
        if user_level < min_level:
            logger.warning(f"[RBAC] Access denied for account {account_id} with role '{user_role}'. Requires '{min_role}'.")
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Action requires minimum '{min_role}' role. Current role is '{user_role}'."
            )

        return {"user_id": account_id, "role": user_role, "website_id": x_website_id or "default"}

    return role_checker
