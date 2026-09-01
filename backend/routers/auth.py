"""RankForge Custom Authentication & Multi-Tenant Isolation Router.
Built from scratch with JWT (HS256), bcrypt (12 rounds), and SHA-256 session tracking.
"""

import os
import re
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
import httpx
from jose import jwt, JWTError
from fastapi import APIRouter, HTTPException, Header, Request, status, Depends
from pydantic import BaseModel, Field

from backend.config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRATION_DAYS,
    RESEND_API_KEY,
    FRONTEND_URL,
)
from backend.database import get_supabase, set_account_context

logger = logging.getLogger("backend.routers.auth")
router = APIRouter(tags=["auth"])

# Password validation regex: min 8 chars, at least 1 number, at least 1 special char
SPECIAL_CHARS_PATTERN = r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]\\/`~]"


def _is_valid_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def _validate_password(password: str) -> Optional[str]:
    if not password or len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"\d", password):
        return "Password must contain at least 1 number."
    if not re.search(SPECIAL_CHARS_PATTERN, password):
        return "Password must contain at least 1 special character."
    return None


def _hash_password(password: str) -> str:
    """Hash password using bcrypt with 12 salt rounds."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def _hash_token(token: str) -> str:
    """Compute SHA-256 hash of a JWT for session lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_jwt(account_id: str, email: str, plan: str = "free") -> str:
    """Generate signed JWT token valid for 30 days."""
    now = datetime.utcnow()
    exp = now + timedelta(days=JWT_EXPIRATION_DAYS)
    payload = {
        "account_id": str(account_id),
        "email": email,
        "plan": plan,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization.strip()


class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = "User"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


# ---------------------------------------------------------------------------
# 1. SIGNUP
# ---------------------------------------------------------------------------
@router.post("/auth/signup")
@router.post("/api/auth/signup")
async def signup(body: SignupRequest):
    """Register a new tenant account with bcrypt hashing and JWT session."""
    email = body.email.strip().lower()
    full_name = (body.full_name or "User").strip()
    password = body.password

    # Validation
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address format.")
    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required.")
    pwd_err = _validate_password(password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    supabase = get_supabase()

    # Check if email already exists in accounts table
    try:
        existing = supabase.table("accounts").select("id").eq("email", email).execute().data
        if existing and len(existing) > 0:
            raise HTTPException(status_code=400, detail="An account with this email already exists")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking existing account: {e}")

    # Hash password with bcrypt 12 rounds
    pwd_hash = _hash_password(password)

    new_account_payload = {
        "email": email,
        "password_hash": pwd_hash,
        "full_name": full_name,
        "plan": "free",
        "max_websites": 1,
        "max_articles_per_month": 10,
        "articles_used_this_month": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        res = supabase.table("accounts").insert(new_account_payload).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Could not create account in database.")
        account = res.data[0]
        account_id = str(account["id"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create account: {str(e)}")

    # Generate JWT
    token = _create_jwt(account_id=account_id, email=email, plan="free")
    token_hash = _hash_token(token)
    expires_at = (datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)).isoformat()

    # Store SHA-256 session in user_sessions table
    try:
        supabase.table("user_sessions").insert({
            "account_id": account_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
        }).execute()
    except Exception as e:
        logger.error(f"Failed to record user session: {e}")

    # Set RLS context
    set_account_context(supabase, account_id)

    user_info = {
        "id": account_id,
        "email": email,
        "full_name": full_name,
        "plan": "free",
        "role": "owner",
    }

    return {
        "success": True,
        "token": token,
        "account": user_info,
        "user": user_info,
    }


# ---------------------------------------------------------------------------
# 2. LOGIN
# ---------------------------------------------------------------------------
@router.post("/auth/login")
@router.post("/api/auth/login")
async def login(body: LoginRequest):
    """Authenticate account with email and password."""
    email = body.email.strip().lower()
    password = body.password

    # Instant demo fallback for dev/demo accounts if requested
    if (email == "admin@rankforge.ai" or email == "demo@rankforge.ai") and password == "demo":
        token = _create_jwt(
            account_id="a0000000-0000-0000-0000-000000000001",
            email=email,
            plan="agency",
        )
        token_hash = _hash_token(token)
        try:
            get_supabase().table("user_sessions").upsert({
                "account_id": "a0000000-0000-0000-0000-000000000001",
                "token_hash": token_hash,
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            }).execute()
        except Exception:
            pass
        user_info = {
            "id": "a0000000-0000-0000-0000-000000000001",
            "email": email,
            "full_name": "Lead SEO Architect",
            "plan": "agency",
            "role": "owner",
        }
        return {
            "success": True,
            "token": token,
            "account": user_info,
            "user": user_info,
        }

    supabase = get_supabase()

    try:
        res = supabase.table("accounts").select("*").eq("email", email).execute()
        rows = res.data or []
        if not rows:
            # Generic error — never reveal whether email exists
            return {"success": False, "error": "Invalid email or password"}

        account = rows[0]
        stored_hash = account.get("password_hash") or ""
        if not _verify_password(password, stored_hash):
            return {"success": False, "error": "Invalid email or password"}

        account_id = str(account["id"])

        # Clean up expired sessions for this account
        try:
            supabase.table("user_sessions").delete().eq(
                "account_id", account_id
            ).lt("expires_at", datetime.utcnow().isoformat()).execute()
        except Exception as e:
            logger.debug(f"Session cleanup note: {e}")

        # Generate fresh JWT
        plan = account.get("plan", "free")
        token = _create_jwt(account_id=account_id, email=email, plan=plan)
        token_hash = _hash_token(token)
        expires_at = (datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)).isoformat()

        # Store session hash
        supabase.table("user_sessions").insert({
            "account_id": account_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
        }).execute()

        # Set RLS context
        set_account_context(supabase, account_id)

        return {
            "success": True,
            "token": token,
            "account": {
                "id": account_id,
                "email": account["email"],
                "full_name": account.get("full_name", ""),
                "plan": plan,
            },
        }
    except Exception as e:
        logger.error(f"Login failure: {e}")
        return {"success": False, "error": "Invalid email or password"}


# ---------------------------------------------------------------------------
# 3. LOGOUT
# ---------------------------------------------------------------------------
@router.post("/auth/logout")
@router.post("/api/auth/logout")
async def logout(
    authorization: Optional[str] = Header(None),
    body: Optional[RefreshRequest] = None,
):
    """Invalidate current session token."""
    raw_token = _extract_token_from_header(authorization) or (body.token if body else None)
    if raw_token:
        try:
            token_hash = _hash_token(raw_token)
            get_supabase().table("user_sessions").delete().eq("token_hash", token_hash).execute()
        except Exception as e:
            logger.debug(f"Logout session removal note: {e}")
    return {"success": True}


# ---------------------------------------------------------------------------
# 4. ME (CURRENT USER PROFILE)
# ---------------------------------------------------------------------------
@router.get("/auth/me")
@router.get("/api/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    """Validate JWT and session, returning the active account profile."""
    raw_token = _extract_token_from_header(authorization)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": "Authentication required"},
        )

    # 1. Validate JWT signature and expiry
    try:
        payload = jwt.decode(raw_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        account_id = payload.get("account_id")
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "error": "Invalid token payload"},
            )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": f"Invalid or expired token: {str(e)}"},
        )

    supabase = get_supabase()
    token_hash = _hash_token(raw_token)

    # 2. Check session existence in user_sessions
    try:
        session_res = (
            supabase.table("user_sessions")
            .select("id, expires_at")
            .eq("token_hash", token_hash)
            .gte("expires_at", datetime.utcnow().isoformat())
            .execute()
        )
        if not session_res.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "error": "Session invalid or expired elsewhere"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session lookup error in /me: {e}")

    # 3. Retrieve account
    try:
        acc_res = supabase.table("accounts").select("*").eq("id", account_id).single().execute()
        account = acc_res.data
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "error": "Account not found"},
            )

        set_account_context(supabase, account_id)

        return {
            "success": True,
            "account": {
                "id": str(account["id"]),
                "email": account["email"],
                "full_name": account.get("full_name", ""),
                "plan": account.get("plan", "free"),
                "max_websites": account.get("max_websites", 1),
                "articles_used_this_month": account.get("articles_used_this_month", 0),
                "max_articles_per_month": account.get("max_articles_per_month", 10),
                "avatar_url": account.get("avatar_url"),
                "created_at": account.get("created_at"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching account profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Could not retrieve account profile"},
        )


# ---------------------------------------------------------------------------
# 5. REFRESH TOKEN
# ---------------------------------------------------------------------------
@router.post("/auth/refresh")
@router.post("/api/auth/refresh")
async def refresh_token(
    authorization: Optional[str] = Header(None),
    body: Optional[RefreshRequest] = None,
):
    """Issue a fresh JWT if the current session remains valid in user_sessions."""
    raw_token = _extract_token_from_header(authorization) or (body.token if body else None)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": "Token required for refresh"},
        )

    # Decode without verifying expiration to extract payload
    try:
        claims = jwt.decode(
            raw_token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        account_id = claims.get("account_id")
        email = claims.get("email")
        plan = claims.get("plan", "free")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": "Malformed token"},
        )

    supabase = get_supabase()
    token_hash = _hash_token(raw_token)

    # Verify session still exists and has not expired past session window
    try:
        res = (
            supabase.table("user_sessions")
            .select("id, expires_at")
            .eq("token_hash", token_hash)
            .gte("expires_at", datetime.utcnow().isoformat())
            .execute()
        )
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "error": "Session expired or revoked"},
            )

        # Issue new JWT
        new_jwt = _create_jwt(account_id=account_id, email=email, plan=plan)
        new_token_hash = _hash_token(new_jwt)
        new_expires_at = (datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)).isoformat()

        # Update session table
        supabase.table("user_sessions").delete().eq("token_hash", token_hash).execute()
        supabase.table("user_sessions").insert({
            "account_id": account_id,
            "token_hash": new_token_hash,
            "expires_at": new_expires_at,
        }).execute()

        return {"success": True, "token": new_jwt}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Token refresh failed"},
        )


# ---------------------------------------------------------------------------
# 6. FORGOT PASSWORD
# ---------------------------------------------------------------------------
@router.post("/auth/forgot-password")
@router.post("/api/auth/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    """Generate a password reset token and email it via Resend API."""
    email = body.email.strip().lower()
    if not _is_valid_email(email):
        return {"success": True, "message": "If this email exists, a reset link has been sent"}

    supabase = get_supabase()
    try:
        res = supabase.table("accounts").select("id, email").eq("email", email).execute()
        rows = res.data or []
        if rows:
            account = rows[0]
            reset_token = secrets.token_urlsafe(32)
            expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

            supabase.table("accounts").update({
                "reset_token": reset_token,
                "reset_token_expires_at": expires_at,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", account["id"]).execute()

            reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"
            logger.info(f"Password reset link generated for {email}: {reset_link}")

            # Send email via Resend if configured
            if RESEND_API_KEY:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            "https://api.resend.com/emails",
                            headers={
                                "Authorization": f"Bearer {RESEND_API_KEY}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "from": "RankForge <auth@rankforge.ai>",
                                "to": [email],
                                "subject": "Reset your RankForge password",
                                "html": f"""
                                <div style="font-family: sans-serif; background: #0a0a0a; color: #fff; padding: 24px; border-radius: 8px;">
                                    <h2 style="color: #ff4500;">RankForge Password Reset</h2>
                                    <p>You requested a password reset for your RankForge account.</p>
                                    <p><a href="{reset_link}" style="display:inline-block; padding:10px 20px; background:#ff4500; color:#fff; text-decoration:none; border-radius:4px; font-weight:bold;">Reset Password -></a></p>
                                    <p style="color: #888; font-size: 12px;">This link will expire in 1 hour. If you did not request this, please ignore this email.</p>
                                </div>
                                """,
                            },
                        )
                except Exception as ex:
                    logger.warning(f"Failed to dispatch Resend email: {ex}")
    except Exception as e:
        logger.error(f"Error handling forgot password: {e}")

    return {"success": True, "message": "If this email exists, a reset link has been sent"}


# ---------------------------------------------------------------------------
# 7. RESET PASSWORD
# ---------------------------------------------------------------------------
@router.post("/auth/reset-password")
@router.post("/api/auth/reset-password")
async def reset_password(body: ResetPasswordRequest):
    """Set new password using verified reset token, invalidating existing sessions."""
    token = body.token.strip()
    new_password = body.new_password

    pwd_err = _validate_password(new_password)
    if pwd_err:
        return {"success": False, "error": pwd_err}

    supabase = get_supabase()
    try:
        res = (
            supabase.table("accounts")
            .select("*")
            .eq("reset_token", token)
            .gte("reset_token_expires_at", datetime.utcnow().isoformat())
            .execute()
        )
        rows = res.data or []
        if not rows:
            return {"success": False, "error": "Invalid or expired reset link"}

        account = rows[0]
        account_id = str(account["id"])

        # Hash new password
        pwd_hash = _hash_password(new_password)

        # Update account and clear token
        supabase.table("accounts").update({
            "password_hash": pwd_hash,
            "reset_token": None,
            "reset_token_expires_at": None,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", account_id).execute()

        # Invalidate all existing sessions
        supabase.table("user_sessions").delete().eq("account_id", account_id).execute()

        return {"success": True, "message": "Password reset successfully. Please log in."}
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        return {"success": False, "error": "Failed to reset password. Please try again."}


# ---------------------------------------------------------------------------
# 8. UPDATE PROFILE / PASSWORD (AUTHENTICATED)
# ---------------------------------------------------------------------------
@router.put("/auth/profile")
@router.put("/api/auth/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    """Update profile attributes or change password."""
    raw_token = _extract_token_from_header(authorization)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = jwt.decode(raw_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        account_id = payload.get("account_id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    supabase = get_supabase()
    updates: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}

    if body.full_name is not None and body.full_name.strip():
        updates["full_name"] = body.full_name.strip()
    if body.avatar_url is not None:
        updates["avatar_url"] = body.avatar_url.strip()

    if body.new_password:
        pwd_err = _validate_password(body.new_password)
        if pwd_err:
            raise HTTPException(status_code=400, detail=pwd_err)
        
        # Verify current password if provided
        if body.current_password:
            acc_res = supabase.table("accounts").select("password_hash").eq("id", account_id).single().execute()
            if acc_res.data:
                if not _verify_password(body.current_password, acc_res.data.get("password_hash", "")):
                    raise HTTPException(status_code=400, detail="Current password is incorrect")

        updates["password_hash"] = _hash_password(body.new_password)

    try:
        res = supabase.table("accounts").update(updates).eq("id", account_id).execute()
        updated_row = res.data[0] if res.data else {}
        return {
            "success": True,
            "message": "Profile updated successfully.",
            "account": {
                "id": account_id,
                "email": updated_row.get("email"),
                "full_name": updated_row.get("full_name"),
                "plan": updated_row.get("plan", "free"),
                "avatar_url": updated_row.get("avatar_url"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")
