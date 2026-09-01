import os
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auto_supabase import connect_and_setup

try:
    from .database import get_supabase
except Exception:
    get_supabase = None

logger = logging.getLogger("backend.minimal")

app = FastAPI(title="Minimal Setup Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SupabaseSetupRequest(BaseModel):
    supabase_url: str
    anon_key: str
    service_key: str
    db_password: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/setup/status")
async def setup_status():
    supabase_url = os.getenv("SUPABASE_URL", "")
    if not supabase_url:
        return {
            "connected": False,
            "supabase_url": "",
            "tables": [],
        }

    if get_supabase is None:
        return {
            "connected": False,
            "supabase_url": supabase_url,
            "tables": [],
            "error": "get_supabase not available",
        }

    try:
        get_supabase().table("websites").select("id").limit(1).execute()
        return {
            "connected": True,
            "supabase_url": supabase_url,
            "tables": ["websites"],
        }
    except Exception as e:
        return {
            "connected": False,
            "supabase_url": supabase_url,
            "tables": [],
            "error": str(e),
        }


@app.post("/api/setup/supabase")
async def setup_supabase(body: SupabaseSetupRequest):
    result = connect_and_setup(
        body.supabase_url,
        body.anon_key,
        body.service_key,
        body.db_password,
    )
    return result


@app.get("/api/setup/tables")
async def list_tables():
    return {"tables": []}


@app.on_event("startup")
async def startup():
    logger.info("Minimal setup server running on :8001")
