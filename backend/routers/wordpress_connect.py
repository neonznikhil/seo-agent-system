import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from wordpress_oauth import (
    generate_authorize_url,
    store_state,
    validate_and_consume_state,
    save_connection,
    get_connection,
    disconnect,
    test_wp_connection,
    decrypt,
    publish_post,
)
from config import FRONTEND_URL, WORDPRESS_URL

logger = logging.getLogger("backend.routers.wordpress_connect")

router = APIRouter(prefix="/wordpress", tags=["wordpress-connect"])


class AuthorizeUrlResponse(BaseModel):
    authorize_url: str


class SaveConnectionRequest(BaseModel):
    username: str
    app_password: str
    site_url: str
    state: str


class SaveConnectionResponse(BaseModel):
    connected: bool
    site_url: str
    username: str
    wp_user_id: Optional[int] = None
    wp_name: Optional[str] = None


class StatusResponse(BaseModel):
    connected: bool
    site_url: Optional[str] = None
    username: Optional[str] = None
    created_at: Optional[str] = None


class TestResponse(BaseModel):
    ok: bool
    user_info: Optional[dict] = None
    error: Optional[str] = None


class PublishRequest(BaseModel):
    title: str
    content: str
    status: str = "draft"


def _get_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-Id")
    if not user_id or user_id == "anonymous":
        raise HTTPException(status_code=403, detail="X-User-Id header required")
    return user_id


@router.get("/authorize-url", response_model=AuthorizeUrlResponse)
async def get_authorize_url(request: Request, redirect_uri: Optional[str] = None):
    user_id = _get_user_id(request)
    state = str(uuid.uuid4())
    await store_state(state, user_id, WORDPRESS_URL)
    success_url = redirect_uri or f"{FRONTEND_URL}/auth/wordpress/callback"
    authorize_url = generate_authorize_url(state, success_url)
    return AuthorizeUrlResponse(authorize_url=authorize_url)


@router.post("/save-connection", response_model=SaveConnectionResponse)
async def save_wp_connection(request: Request, body: SaveConnectionRequest):
    user_id = _get_user_id(request)
    site_url = validate_and_consume_state(body.state, user_id)
    if not site_url or site_url != body.site_url:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    result = await save_connection(user_id, body.site_url, body.username, body.app_password)
    return SaveConnectionResponse(**result)


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request):
    user_id = _get_user_id(request)
    connection = get_connection(user_id)
    if not connection:
        return StatusResponse(connected=False)
    return StatusResponse(
        connected=True,
        site_url=connection.get("site_url"),
        username=connection.get("wp_username"),
        created_at=connection.get("created_at"),
    )


@router.delete("/disconnect")
async def disconnect_wp(request: Request):
    user_id = _get_user_id(request)
    await disconnect(user_id)
    return {"disconnected": True}


@router.get("/test", response_model=TestResponse)
async def test_connection(request: Request):
    user_id = _get_user_id(request)
    connection = get_connection(user_id)
    if not connection:
        return TestResponse(ok=False, error="Not connected")
    try:
        site_url = connection.get("site_url")
        username = connection.get("wp_username")
        encrypted_password = connection.get("encrypted_password")
        password = decrypt(encrypted_password)
        user_info = test_wp_connection(site_url, username, password)
        return TestResponse(ok=True, user_info=user_info)
    except Exception as e:
        return TestResponse(ok=False, error=str(e))


@router.post("/publish")
async def publish_wp_post(request: Request, body: PublishRequest):
    user_id = _get_user_id(request)
    result = await publish_post(user_id, body.title, body.content, body.status)
    return result
