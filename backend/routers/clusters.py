import logging
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from backend.database import get_supabase
from services.cluster_service import ClusterService
from agents.writer_agent import WriterPipeline

logger = logging.getLogger("backend.routers.clusters")
router = APIRouter()


class ClusterIn(BaseModel):
    website_id: str
    name: str
    description: Optional[str] = None
    keywords: Optional[List[str]] = None


class GenerateClustersRequest(BaseModel):
    website_id: Optional[str] = "default"
    max_clusters: Optional[int] = 6


class GenerateClusterArticleRequest(BaseModel):
    website_id: str
    cluster_id: Optional[str] = None
    keyword: str
    topic: Optional[str] = None


@router.get("/clusters")
@router.get("/api/clusters")
async def list_clusters(website_id: Optional[str] = None):
    supabase = get_supabase()
    data = []
    
    # 1. Try topic_clusters table
    try:
        q = supabase.table("topic_clusters").select("*")
        if website_id:
            q = q.eq("website_id", website_id)
        res = q.execute()
        if res.data:
            data = res.data
    except Exception:
        pass

    # 2. Fallback to clusters table
    if not data:
        try:
            q2 = supabase.table("clusters").select("*")
            if website_id:
                q2 = q2.eq("website_id", website_id)
            res2 = q2.execute()
            data = res2.data or []
        except Exception:
            pass

    # 3. If still empty, auto-generate initial clusters
    if not data and website_id:
        svc = ClusterService(website_id=website_id)
        gen_res = await svc.build_clusters(max_clusters=4)
        data = gen_res.get("clusters", [])

    return {"success": True, "data": data} if isinstance(data, list) else data


@router.post("/clusters/generate")
@router.post("/api/clusters/generate")
async def generate_topic_clusters(body: GenerateClustersRequest):
    """Trigger AI embedding & cosine similarity clustering from live keywords."""
    svc = ClusterService(website_id=body.website_id)
    res = await svc.build_clusters(max_clusters=body.max_clusters or 6)
    return {"success": True, "data": res}


@router.post("/clusters/generate-article")
@router.post("/api/clusters/generate-article")
async def generate_article_from_cluster(body: GenerateClusterArticleRequest, background_tasks: BackgroundTasks):
    """Queue cluster keyword in brain_auto_pages_queue and trigger 10-phase generation."""
    supabase = get_supabase()
    queue_id = str(uuid.uuid4())
    topic = body.topic or f"Complete 2026 Strategy: {body.keyword.title()}"
    
    queue_row = {
        "id": queue_id,
        "website_id": body.website_id,
        "cluster_id": body.cluster_id,
        "primary_keyword": body.keyword,
        "suggested_topic": topic,
        "priority_score": 95,
        "status": "queued_for_writing",
        "created_at": datetime.utcnow().isoformat()
    }
    
    try:
        supabase.table("brain_auto_pages_queue").insert(queue_row).execute()
    except Exception as e:
        logger.debug(f"brain_auto_pages_queue insert note: {e}")

    async def _run_writer_task(wid: str, top: str, kw: str, qid: str):
        try:
            writer = WriterPipeline(website_id=wid)
            await writer.generate(topic=top, primary_keyword=kw)
            supabase.table("brain_auto_pages_queue").update({"status": "draft_ready"}).eq("id", qid).execute()
        except Exception as ex:
            logger.error(f"Background cluster article generation failed: {ex}")
            supabase.table("brain_auto_pages_queue").update({"status": "failed"}).eq("id", qid).execute()

    background_tasks.add_task(_run_writer_task, body.website_id, topic, body.keyword, queue_id)

    return {
        "success": True,
        "data": {
            "queue_id": queue_id,
            "topic": topic,
            "keyword": body.keyword,
            "status": "queued_for_writing",
            "message": f"Article '{topic}' queued in brain_auto_pages_queue and generation started."
        }
    }


@router.get("/clusters/{cluster_id}")
@router.get("/api/clusters/{cluster_id}")
async def get_cluster(cluster_id: str):
    res = get_supabase().table("topic_clusters").select("*").eq("id", cluster_id).maybe_single().execute()
    if not (res and res.data):
        res = get_supabase().table("clusters").select("*").eq("id", cluster_id).maybe_single().execute()
    if not (res and res.data):
        raise HTTPException(status_code=404, detail="Cluster not found")
    return {"success": True, "data": res.data}
