import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field

from ..database import get_supabase
from ..services.knowledge_service import KnowledgeService

logger = logging.getLogger("backend.routers.knowledge")
router = APIRouter(tags=["knowledge"])


class IngestTextRequest(BaseModel):
    title: Optional[str] = None
    content: str
    type: Optional[str] = None
    website_id: Optional[str] = None


class IngestUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None
    type: Optional[str] = None
    website_id: Optional[str] = None


class ScrapeCompetitorRequest(BaseModel):
    url: str
    website_id: Optional[str] = None


# ---------------------------------------------------------
# Knowledge Base Endpoints
# ---------------------------------------------------------

@router.get("/api/knowledge")
@router.get("/knowledge")
async def get_knowledge(
    type: Optional[str] = None,
    website_id: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50
):
    """List knowledge base documents filtered by type or text query."""
    supabase = get_supabase()
    try:
        query = supabase.table("knowledge_base").select("*")
        if website_id:
            query = query.eq("website_id", website_id)
        if type and type != "all":
            query = query.eq("type", type)
        if q:
            query = query.ilike("content", f"%{q}%")
            
        res = query.order("created_at", desc=True).limit(limit).execute()
        data = res.data or []
        
        # Format for UI presentation
        formatted = []
        for item in data:
            formatted.append({
                "id": item.get("id"),
                "title": item.get("title") or "Untitled Fact",
                "content": item.get("content") or "",
                "type": item.get("type", "business_info"),
                "source": item.get("source", "text"),
                "url": item.get("url"),
                "chunk_index": item.get("chunk_index", 0),
                "total_chunks": item.get("total_chunks", 1),
                "freshness_score": float(item.get("freshness_score", 1.0)),
                "usage_count": int(item.get("usage_count", 0)),
                "last_used": item.get("last_used"),
                "created_at": item.get("created_at")
            })
        return formatted
    except Exception as e:
        logger.error(f"Error fetching knowledge items: {e}")
        return []


@router.get("/api/knowledge/search")
@router.get("/knowledge/search")
async def search_knowledge(
    q: str = Query(..., description="Semantic search query"),
    website_id: Optional[str] = None,
    top_k: int = 5
):
    """Deep vector search into knowledge base with anti-hallucination threshold."""
    service = KnowledgeService(website_id=website_id)
    results = await service.query(keyword=q, top_k=top_k)
    return {
        "query": q,
        "results_count": len(results),
        "results": results
    }


@router.post("/api/knowledge/upload")
@router.post("/knowledge/upload")
async def upload_knowledge(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    website_id: Optional[str] = Form(None)
):
    """Multipart upload endpoint for PDF documents, scraped URLs, or raw text."""
    service = KnowledgeService(website_id=website_id)
    
    # 1. File Upload (PDF / TXT / DOCX)
    if file:
        file_bytes = await file.read()
        filename = file.filename or "uploaded_doc"
        is_pdf = filename.lower().endswith(".pdf") or (file.content_type and "pdf" in file.content_type)
        
        res = await service.ingest(
            content=None if is_pdf else file_bytes.decode("utf-8", errors="ignore"),
            source_type="pdf" if is_pdf else "text",
            title=title or filename,
            file_bytes=file_bytes if is_pdf else None,
            explicit_type=type,
            user_id=None
        )
        return res
        
    # 2. URL Scrape
    elif url:
        res = await service.ingest(
            url=url.strip(),
            source_type="url",
            title=title or url,
            explicit_type=type
        )
        return res
        
    # 3. Direct Text
    elif text:
        res = await service.ingest(
            content=text.strip(),
            source_type="text",
            title=title or "Business Fact",
            explicit_type=type
        )
        return res
        
    else:
        raise HTTPException(status_code=400, detail="Must provide either file, url, or text")


@router.post("/api/knowledge/scrape-competitor")
@router.post("/knowledge/scrape-competitor")
async def scrape_competitor_endpoint(payload: ScrapeCompetitorRequest):
    """Scrape competitor domain, analyze keyword strategies, and store as competitor type."""
    service = KnowledgeService(website_id=payload.website_id)
    res = await service.scrape_competitor(url=payload.url)
    return res


@router.delete("/api/knowledge/{item_id}")
@router.delete("/knowledge/{item_id}")
async def delete_knowledge_item(item_id: str):
    """Delete a chunk or document from the knowledge base."""
    supabase = get_supabase()
    try:
        supabase.table("knowledge_base").delete().eq("id", item_id).execute()
        return {"success": True, "id": item_id, "message": "Item removed from Knowledge Base"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/knowledge/reindex")
@router.post("/knowledge/reindex")
async def reindex_knowledge():
    """Re-compute embeddings for all knowledge base entries."""
    supabase = get_supabase()
    try:
        items = supabase.table("knowledge_base").select("id, content, title").execute().data or []
        reindexed = 0
        for it in items:
            txt = it.get("content") or it.get("title", "")
            if txt:
                emb = await KnowledgeService.create_embedding(txt)
                supabase.table("knowledge_base").update({"embedding": emb, "freshness_score": 1.0}).eq("id", it["id"]).execute()
                reindexed += 1
        return {"success": True, "reindexed_count": reindexed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
