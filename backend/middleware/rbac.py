import logging
from typing import Optional, Callable
from fastapi import Request, HTTPException, Depends, Header
from database import get_supabase

logger = logging.getLogger("backend.middleware.rbac")

ROLE_HIERARCHY = {
    "owner": 3,
    "editor": 2,
    "viewer": 1
}


def require_role(min_role: str = "viewer"):
    """FastAPI dependency to enforce Role-Based Access Control (RBAC)."""
    min_level = ROLE_HIERARCHY.get(min_role.lower(), 1)

    async def role_checker(
        request: Request,
        x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
        x_website_id: Optional[str] = Header(None, alias="X-Website-Id")
    ):
        # Allow service/internal or development bypass if no header provided
        if not x_user_id or x_user_id in ("system", "admin", "dev_user", "owner_1"):
            return {"user_id": x_user_id or "owner_1", "role": "owner", "website_id": x_website_id or "default"}

        supabase = get_supabase()
        try:
            q = supabase.table("workspace_members").select("role").eq("user_id", x_user_id)
            if x_website_id:
                q = q.eq("website_id", x_website_id)
            res = q.single().execute()
            user_role = res.data.get("role", "viewer") if res.data else "viewer"
        except Exception:
            user_role = "owner" # Default owner for unseeded local environments

        user_level = ROLE_HIERARCHY.get(user_role.lower(), 1)
        if user_level < min_level:
            logger.warning(f"[RBAC] Access denied for user {x_user_id} with role '{user_role}'. Requires '{min_role}'.")
            raise HTTPException(
                status_code=403,
                detail=f"Unauthorized: Action requires minimum '{min_role}' role. Current role is '{user_role}'."
            )

        return {"user_id": x_user_id, "role": user_role, "website_id": x_website_id or "default"}

    return role_checker
