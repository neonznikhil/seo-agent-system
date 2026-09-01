import os
import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from auto_supabase import connect_and_setup

try:
    from ..database import get_supabase
except ImportError:
    get_supabase = None

logger = logging.getLogger("backend.routers.setup")

router = APIRouter(prefix="/setup", tags=["setup"])


class SupabaseSetupRequest(BaseModel):
    supabase_url: str
    anon_key: str
    service_key: str
    db_password: str


@router.get("/status")
async def setup_status():
    supabase_url = os.environ.get("SUPABASE_URL", "")
    connected = bool(supabase_url) and get_supabase is not None
    tables = []
    error = None

    if connected:
        try:
            supabase = get_supabase()
            response = supabase.table("").select("*").limit(1).execute()
            tables = []
        except Exception as exc:
            connected = False
            error = str(exc)
            logger.exception("Failed to get Supabase status")

    return {
        "connected": connected,
        "supabase_url": supabase_url,
        "tables": tables,
        "error": error,
    }


@router.post("/supabase")
async def setup_supabase(request: Request, body: SupabaseSetupRequest):
    logger.info("Received Supabase setup request")
    result = connect_and_setup(
        body.supabase_url,
        body.anon_key,
        body.service_key,
        body.db_password,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Setup failed"))
    return result
