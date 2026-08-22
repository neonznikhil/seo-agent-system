import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.settings")
router = APIRouter()

# In-memory fallback used until /setup creates the `settings` table.
# Keeps autonomous jobs running (with defaults) instead of crashing.
_MEMORY_SETTINGS: dict = {}


def get_global_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read a global setting; falls back to memory if table missing."""
    try:
        res = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", key)
            .is_("website_id", "null")
            .maybe_single()
            .execute()
        )
        return res.data.get("value") if (res and res.data) else None
    except Exception as e:
        logger.warning(f"settings table unavailable ({e}); using memory fallback")
        return _MEMORY_SETTINGS.get(key, default)


def set_global_setting(key: str, value: str) -> bool:
    """Write a global setting; persists to memory if table missing."""
    _MEMORY_SETTINGS[key] = value
    try:
        supabase = get_supabase()
        existing = (
            supabase.table("settings")
            .select("value")
            .eq("key", key)
            .is_("website_id", "null")
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            supabase.table("settings").update({"value": value}).eq("key", key).is_("website_id", "null").execute()
        else:
            supabase.table("settings").insert({"key": key, "value": value, "website_id": None}).execute()
        return True
    except Exception as e:
        logger.warning(f"settings persist failed ({e}); kept in memory only")
        return False


class SettingIn(BaseModel):
    key: str
    value: str
    website_id: Optional[str] = None


class SettingUpdate(BaseModel):
    value: str


class SettingOut(BaseModel):
    key: str
    value: str
    website_id: Optional[str] = None


@router.get("/settings")
async def list_settings(website_id: Optional[str] = None):
    query = get_supabase().table("settings").select("*")
    if website_id:
        query = query.eq("website_id", website_id)
    res = query.execute()
    return res.data or []


@router.get("/settings/website/{website_id}")
async def get_website_settings(website_id: str):
    website = get_supabase().table("websites").select("*").eq("id", website_id).single().execute().data or {}
    settings = get_supabase().table("settings").select("*").eq("website_id", website_id).execute().data or []
    settings_map = {s["key"]: s["value"] for s in settings}
    return {
        "website_id": website_id,
        "domain": website.get("domain", ""),
        "cms_url": website.get("cms_url", ""),
        "gsc_property": website.get("gsc_property", ""),
        "settings": settings_map,
    }


@router.post("/settings")
async def create_setting(body: SettingIn):
    res = get_supabase().table("settings").insert(body.model_dump()).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create setting")
    return row


@router.get("/settings/{key}")
async def get_setting(key: str, website_id: Optional[str] = None):
    query = get_supabase().table("settings").select("*").eq("key", key)
    if website_id:
        query = query.eq("website_id", website_id)
    res = query.single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Not found")
    return res.data


@router.put("/settings/website/{website_id}")
async def update_website_settings(website_id: str, body: dict):
    website_fields = {k: v for k, v in body.items() if k in ("domain", "cms_url", "cms_user", "app_password", "gsc_property", "status")}
    settings_fields = {k: v for k, v in body.items() if k not in website_fields}
    result = {}
    if website_fields:
        res = get_supabase().table("websites").update(website_fields).eq("id", website_id).execute()
        result["website"] = res.data[0] if res.data else {}
    for key, value in settings_fields.items():
        existing = get_supabase().table("settings").select("*").eq("key", key).eq("website_id", website_id).execute().data
        if existing:
            get_supabase().table("settings").update({"value": value}).eq("key", key).eq("website_id", website_id).execute()
        else:
            get_supabase().table("settings").insert({"key": key, "value": value, "website_id": website_id}).execute()
    return result


@router.put("/settings/{key}")
async def update_setting(key: str, body: SettingUpdate, website_id: Optional[str] = None):
    updates = {"value": body.value}
    query = get_supabase().table("settings").update(updates).eq("key", key)
    if website_id:
        query = query.eq("website_id", website_id)
    res = query.execute()
    return res.data[0] if res.data else {"detail": "updated"}


AUTOMATION_KEYS = {
    "automate_seo": ("on", "Master switch for all autonomous daily jobs"),
    "auto_publish_new_pages": ("off", "Auto-publish new pages (on) or keep as WP drafts (off)"),
    "daily_refresh": ("on", "Daily refresh of old content via ContentRefresherAgent"),
}


class AutomationOut(BaseModel):
    automate_seo: str = "on"
    auto_publish_new_pages: str = "off"
    daily_refresh: str = "on"


def _read_global_setting(key: str) -> Optional[str]:
    return get_global_setting(key)


def _write_global_setting(key: str, value: str) -> None:
    set_global_setting(key, value)


@router.get("/automation")
async def get_automation_settings() -> AutomationOut:
    values = {}
    for key, (default, _desc) in AUTOMATION_KEYS.items():
        stored = _read_global_setting(key)
        values[key] = stored or default
        # Self-heal: persist defaults on first read so setup is zero-touch
        if stored is None:
            try:
                _write_global_setting(key, default)
            except Exception:
                pass
    return AutomationOut(**values)


@router.put("/automation")
async def update_automation_settings(body: dict):
    updated = {}
    for key in AUTOMATION_KEYS:
        if key in body:
            value = "on" if str(body[key]).lower() in ("on", "true", "1") else "off"
            _write_global_setting(key, value)
            updated[key] = value
    if not updated:
        raise HTTPException(status_code=400, detail=f"No valid keys. Valid: {list(AUTOMATION_KEYS)}")
    persisted = all(_read_global_setting(k) == v for k, v in updated.items())
    result = {"updated": updated, "persisted": bool(persisted)}
    if not persisted:
        result["note"] = (
            "Held in memory only - run /setup with DB password to create the "
            "settings table and persist toggles across restarts."
        )
    return result
