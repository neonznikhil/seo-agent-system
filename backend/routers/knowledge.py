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


class WatchBusinessRequest(BaseModel):
    site_url: Optional[str] = "https://accident.innovatcs.com"
    website_id: Optional[str] = None


# ---------------------------------------------------------
# Knowledge Base List & Search Endpoints
# ---------------------------------------------------------

@router.get("/api/knowledge")
@router.get("/knowledge")
async def get_knowledge(
    type: Optional[str] = None,
    website_id: Optional[str] = None,
    validated: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 50
):
    """List knowledge base documents with entities, credibility, and validation states."""
    supabase = get_supabase()
    try:
        query = supabase.table("knowledge_base").select("*")
        if website_id:
            query = query.eq("website_id", website_id)
        if type and type != "all":
            query = query.eq("type", type)
        if validated is not None:
            query = query.eq("validated", validated)
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
                "source_type": item.get("source_type", "file"),
                "url": item.get("url"),
                "chunk_index": item.get("chunk_index", 0),
                "total_chunks": item.get("total_chunks", 1),
                "freshness_score": float(item.get("freshness_score", 1.0)),
                "credibility_score": float(item.get("credibility_score", 1.0)),
                "validated": bool(item.get("validated", False)),
                "validation_score": float(item.get("validation_score", 0.0)),
                "entities": item.get("entities") or {"people": [], "orgs": [], "locations": [], "laws": [], "services": [], "keywords": []},
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
    """Vector search into knowledge base."""
    service = KnowledgeService(website_id=website_id)
    results = await service.query(keyword=q, top_k=top_k)
    return {
        "query": q,
        "mode": "vector",
        "results_count": len(results),
        "results": results
    }


@router.get("/api/knowledge/search/hybrid")
@router.get("/knowledge/search/hybrid")
async def search_knowledge_hybrid(
    q: str = Query(..., description="Hybrid search query"),
    website_id: Optional[str] = None,
    top_k: int = 5
):
    """True hybrid search (vector cosine 60% + full-text ILIKE 10% + freshness + credibility + validation bonus)."""
    service = KnowledgeService(website_id=website_id)
    results = await service.retrieve_relevant_hybrid(keyword=q, top_k=top_k)
    return {
        "query": q,
        "mode": "hybrid",
        "results_count": len(results),
        "results": results
    }


# ---------------------------------------------------------
# Phase 2: Graph, Validation, Consolidation & Watcher
# ---------------------------------------------------------

@router.get("/api/knowledge/graph")
@router.get("/knowledge/graph")
async def get_knowledge_graph(website_id: Optional[str] = None):
    """Fetch nodes and edges for visual knowledge graph."""
    service = KnowledgeService(website_id=website_id)
    return await service.get_knowledge_graph()


@router.post("/api/knowledge/validate/{item_id}")
@router.post("/knowledge/validate/{item_id}")
async def validate_knowledge_item(item_id: str):
    """Run real LLM fact-checking against a single knowledge chunk."""
    service = KnowledgeService()
    res = await service.validate_knowledge(doc_id=item_id)
    return res


@router.post("/api/knowledge/validate-all")
@router.post("/knowledge/validate-all")
async def validate_all_knowledge():
    """Batch validate all unvalidated knowledge records via NIM LLM."""
    service = KnowledgeService()
    res = await service.validate_all_unvalidated()
    return res


@router.post("/api/knowledge/consolidate")
@router.post("/knowledge/consolidate")
async def consolidate_knowledge():
    """Trigger auto-consolidation of duplicate or overlapping business facts."""
    service = KnowledgeService()
    res = await service.auto_consolidate()
    return res


@router.post("/api/knowledge/watch-business")
@router.post("/knowledge/watch-business")
async def watch_business_endpoint(payload: WatchBusinessRequest):
    """Autonomous watcher: parses sitemap, compares content hashes, auto-ingests new/updated pages."""
    service = KnowledgeService(website_id=payload.website_id)
    res = await service.watch_business_website(target_site=payload.site_url)
    return res


# ---------------------------------------------------------
# Ingestion, Scrape & Delete Endpoints
# ---------------------------------------------------------

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
    """Multipart upload endpoint for PDF documents, scraped URLs, or raw text with entity extraction."""
    service = KnowledgeService(website_id=website_id)
    
    # 1. File Upload (PDF / TXT / DOCX)
    if file:
        file_bytes = await file.read()
        filename = file.filename or "uploaded_doc"
        is_pdf = filename.lower().endswith(".pdf") or (file.content_type and "pdf" in file.content_type)
        
        res = await service.ingest(
            content=None if is_pdf else file_bytes.decode("utf-8", errors="ignore"),
            source_type="pdf" if is_pdf else "file",
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
            source_type="manual",
            title=title or "Business Fact",
            explicit_type=type
        )
        return res
        
    else:
        raise HTTPException(status_code=400, detail="Must provide either file, url, or text")


@router.post("/api/knowledge/reingest")
@router.post("/knowledge/reingest")
async def reingest_url_endpoint(payload: IngestUrlRequest):
    """Manual Re-ingest button: executes the full 11-step ingestion pipeline for a selected URL."""
    service = KnowledgeService(website_id=payload.website_id)
    res = await service.ingest(
        url=payload.url.strip(),
        source_type="url",
        title=payload.title or payload.url,
        explicit_type=payload.type or "business_info"
    )
    return {"success": True, "data": res}


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
