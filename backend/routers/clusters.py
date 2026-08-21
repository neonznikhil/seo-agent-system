import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.clusters")
router = APIRouter()


class ClusterIn(BaseModel):
    website_id: str
    name: str
    description: Optional[str] = None
    keywords: Optional[List[str]] = None


class ClusterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None


class ClusterOut(BaseModel):
    id: str
    website_id: str
    name: str
    description: Optional[str] = None
    keywords: Optional[List[str]] = None


@router.get("/clusters")
async def list_clusters(website_id: Optional[str] = None):
    query = get_supabase().table("clusters").select("*")
    if website_id:
        query = query.eq("website_id", website_id)
    res = query.execute()
    return res.data or []


@router.post("/clusters")
async def create_cluster(body: ClusterIn):
    res = get_supabase().table("clusters").insert(body.dict()).execute()
    row = res.data[0] if res.data else None
    if not row:
        raise HTTPException(status_code=400, detail="Failed to create cluster")
    return row


@router.get("/clusters/{cluster_id}")
async def get_cluster(cluster_id: str):
    res = get_supabase().table("clusters").select("*").eq("id", cluster_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Not found")
    return res.data


@router.put("/clusters/{cluster_id}")
async def update_cluster(cluster_id: str, body: ClusterUpdate):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        return {"detail": "no changes"}
    res = get_supabase().table("clusters").update(updates).eq("id", cluster_id).execute()
    return res.data[0] if res.data else {"detail": "updated"}
