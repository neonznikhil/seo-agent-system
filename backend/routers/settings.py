import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.settings")
router = APIRouter()


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
    res = get_supabase().table("settings").insert(body.dict()).execute()
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
