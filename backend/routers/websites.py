import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..database import get_supabase
from ..security import encrypt_secret, decrypt_secret, sanitize_website_row
from ..agents.knowledge_agent import run_knowledge_agent

logger = logging.getLogger("backend.routers.websites")
router = APIRouter()

# Columns that hold secrets. They are encrypted at rest and NEVER returned.
_SECRET_COLUMNS = {"app_password", "wordpress_password", "serper_api_key"}

# Public column list used for every SELECT on the websites table.
_WEBSITE_SAFE_COLUMNS = (
    "id, domain, url, cms_url, cms_user, wordpress_url, wordpress_user, "
    "gsc_property, niche, name, status, created_at, updated_at, "
    "last_audit_score, last_audit_date"
)


class WebsiteIn(BaseModel):
    id: Optional[str] = None
    domain: Optional[str] = None
    url: Optional[str] = None
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = "active"


class WebsiteUpdate(BaseModel):
    domain: Optional[str] = None
    url: Optional[str] = None
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    gsc_property: Optional[str] = None
    status: Optional[str] = None


def extract_domain(raw_url: Optional[str], default_domain: Optional[str] = None) -> str:
    if default_domain and default_domain.strip():
        return default_domain.strip().replace("https://", "").replace("http://", "").split("/")[0]
    if raw_url and raw_url.strip():
        clean = raw_url.strip().replace("https://", "").replace("http://", "").split("/")[0]
        if clean:
            return clean
    return ""


def _resolve_app_password(row: dict) -> str:
    """Decrypt the stored application password for outbound API calls only."""
    raw = (
        row.get("wordpress_password_encrypted")
        or row.get("app_password")
        or row.get("wordpress_password")
        or ""
    )
    if not raw:
        return ""
    # Legacy rows may hold plaintext; encrypt-on-read migrates them lazily.
    decrypted = decrypt_secret(raw)
    return decrypted


@router.get("/websites")
async def list_websites():
    try:
        supabase = get_supabase()
        res = supabase.table("websites").select("*").execute()
        return [sanitize_website_row(r) for r in (res.data or [])]
    except Exception as e:
        logger.error(f"Error fetching websites: {e}")
        return []


@router.post("/websites")
async def create_or_update_website(website: WebsiteIn, background_tasks: BackgroundTasks):
    supabase = get_supabase()

    cms_url = website.cms_url or website.url
    resolved_domain = extract_domain(cms_url, website.domain)
    if not resolved_domain:
        raise HTTPException(status_code=400, detail="A valid domain or CMS URL is required")

    payload: dict = {
        "domain": resolved_domain,
        "status": website.status or "active",
        "updated_at": datetime.utcnow().isoformat(),
    }
    if cms_url:
        payload["cms_url"] = cms_url
        payload["url"] = cms_url
    if website.cms_user:
        payload["cms_user"] = website.cms_user
        payload.setdefault("wordpress_user", website.cms_user)
    if website.gsc_property:
        payload["gsc_property"] = website.gsc_property
    if website.app_password:
        # Encrypt before storage. The plaintext is never persisted anywhere.
        try:
            payload["app_password"] = encrypt_secret(website.app_password)
            payload["wordpress_password"] = payload["app_password"]
        except Exception as e:
            logger.error(f"Failed to encrypt WordPress credentials: {e}")
            raise HTTPException(status_code=500, detail="Failed to secure credentials")

    # 1. If an explicit ID is provided, update that website
    if website.id:
        try:
            res = supabase.table("websites").update(payload).eq("id", website.id).execute()
            if res.data:
                return sanitize_website_row(res.data[0])
        except Exception as e:
            logger.warning(f"Failed to update website by id {website.id}: {e}")

    # 2. Check if a website with this domain exists
    existing = None
    try:
        existing = supabase.table("websites").select("*").eq("domain", resolved_domain).limit(1).execute().data
    except Exception:
        pass

    if existing and len(existing) > 0:
        wid = existing[0]["id"]
        res = supabase.table("websites").update(payload).eq("id", wid).execute()
        return sanitize_website_row(res.data[0]) if res.data else sanitize_website_row(existing[0])

    # 3. Create new website
    payload["created_at"] = datetime.utcnow().isoformat()
    res = supabase.table("websites").insert(payload).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create website")

    from ..agents.setup_pipeline import run_first_time_setup_bg
    background_tasks.add_task(run_first_time_setup_bg, row["id"], row.get("cms_url") or f"https://{row['domain']}")
    return sanitize_website_row(row)


@router.get("/websites/{website_id}")
async def get_website(website_id: str):
    supabase = get_supabase()
    res = supabase.table("websites").select("*").eq("id", website_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Website not found")
    return sanitize_website_row(res.data)


@router.get("/websites/{website_id}/connector-status")
async def get_website_connector_status(website_id: str):
    """Booleans-only connector status for the Connectors page.

    Never returns any credential value — only whether each one is saved.
    """
    supabase = get_supabase()
    try:
        res = (
            supabase.table("websites")
            .select(
                "id, domain, cms_url, cms_user, wordpress_user, app_password, "
                "wordpress_password, gsc_property"
            )
            .eq("id", website_id)
            .single()
            .execute()
        )
        row = res.data or {}
    except Exception as e:
        logger.warning(f"connector-status lookup failed: {e}")
        row = {}

    wp_saved = bool(row.get("app_password") or row.get("wordpress_password"))
    serper_saved = bool(os.getenv("SERPER_API_KEY"))
    slack_webhook_configured = bool(os.getenv("SLACK_WEBHOOK_URL") or os.getenv("SLACK_BOT_TOKEN"))

    return {
        "success": True,
        "website_id": website_id,
        "wordpress": {
            "is_configured": wp_saved,
            "site_url": row.get("cms_url") or "",
            "username": row.get("cms_user") or row.get("wordpress_user") or "",
        },
        "serper": {"is_configured": serper_saved},
        "gsc": {"property": row.get("gsc_property") or "", "is_configured": bool(row.get("gsc_property"))},
        "slack": {
            "connected": slack_connected,
            "workspace_name": slack_creds.get("workspace_name") if isinstance(slack_creds, dict) else None,
        },
    }


def get_decrypted_wordpress_credentials(website_id: str) -> tuple:
    """Internal helper for services that need to CALL the WordPress API.

    Returns (base_url, username, password). The password never leaves the
    backend process — callers use it directly in an Authorization header.
    """
    supabase = get_supabase()
    try:
        res = (
            supabase.table("websites")
            .select("*")
            .eq("id", website_id)
            .single()
            .execute()
        )
        row = res.data or {}
    except Exception:
        row = {}
    base_url = row.get("wordpress_url") or row.get("cms_url") or row.get("url") or ""
    user = row.get("cms_user") or row.get("wordpress_user") or ""
    password = _resolve_app_password(row)
    return base_url, user, password


@router.put("/websites/{website_id}")
@router.patch("/websites/{website_id}")
async def update_website(website_id: str, website: WebsiteUpdate):
    supabase = get_supabase()
    updates = {k: v for k, v in website.model_dump().items() if v is not None}
    if not updates:
        return {"detail": "no changes"}

    if "app_password" in updates:
        try:
            encrypted = encrypt_secret(updates.pop("app_password"))
            updates["app_password"] = encrypted
            updates["wordpress_password"] = encrypted
        except Exception as e:
            logger.error(f"Failed to encrypt credentials: {e}")
            raise HTTPException(status_code=500, detail="Failed to secure credentials")

    if "cms_url" in updates and "url" not in updates:
        updates["url"] = updates["cms_url"]
    if "cms_user" in updates:
        updates.setdefault("wordpress_user", updates["cms_user"])
    updates["updated_at"] = datetime.utcnow().isoformat()

    try:
        res = supabase.table("websites").update(updates).eq("id", website_id).execute()
        return sanitize_website_row(res.data[0]) if res.data else {"detail": "updated"}
    except Exception as e:
        logger.error(f"Failed to update website {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/websites/{website_id}")
async def delete_website(website_id: str):
    supabase = get_supabase()
    res = supabase.table("websites").delete().eq("id", website_id).execute()
    return {"detail": "deleted", "rows_affected": len(res.data or [])}
