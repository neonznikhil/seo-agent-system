import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.knowledge")
router = APIRouter()


class KnowledgeIn(BaseModel):
    website_id: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    fact: Optional[str] = None
    fact_type: Optional[str] = "company_info"
    source: Optional[str] = None
    tags: Optional[List[str]] = None


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None


@router.get("/knowledge")
async def list_knowledge(website_id: Optional[str] = None, q: Optional[str] = None):
    supabase = get_supabase()
    query = supabase.table("knowledge_base").select("*")
    if website_id:
        query = query.eq("website_id", website_id)
    if q:
        query = query.ilike("fact", f"%{q}%")
    res = query.order("created_at", desc=True).execute()
    data = res.data or []
    # Normalize rows so frontend always has title, content/fact, source
    normalized = []
    for item in data:
        fact_text = item.get("fact") or item.get("content") or item.get("title") or ""
        normalized.append({
            "id": item.get("id"),
            "website_id": item.get("website_id"),
            "title": item.get("title") or (fact_text[:60] + "..." if len(fact_text) > 60 else fact_text),
            "content": fact_text,
            "fact": fact_text,
            "fact_type": item.get("fact_type", "company_info"),
            "source": item.get("source_url") or item.get("source") or "",
            "source_url": item.get("source_url") or item.get("source") or "",
            "tags": item.get("tags") or [item.get("fact_type")] if item.get("fact_type") else [],
            "created_at": item.get("created_at"),
        })
    return normalized


@router.post("/knowledge")
async def create_knowledge(body: KnowledgeIn):
    from ..database import get_supabase, get_embedding
    import datetime
    
    supabase = get_supabase()
    wid = body.website_id
    if not wid:
        try:
            sites = supabase.table("websites").select("id").limit(1).execute().data
            if sites:
                wid = sites[0]["id"]
        except Exception:
            pass

    fact_val = body.fact or body.content or body.title or "Knowledge fact"
    
    emb = None
    try:
        emb = await get_embedding(fact_val)
    except Exception:
        pass

    insert_payload = {
        "fact": fact_val,
        "fact_type": body.fact_type or "company_info",
        "source_url": body.source or "",
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    if wid:
        insert_payload["website_id"] = wid
    if emb:
        insert_payload["embedding"] = emb

    try:
        res = supabase.table("knowledge_base").insert(insert_payload).execute()
        if res.data:
            row = res.data[0]
            return {
                "id": row.get("id"),
                "title": body.title or fact_val[:60],
                "content": fact_val,
                "fact": fact_val,
                "fact_type": row.get("fact_type"),
                "source": row.get("source_url"),
                "created_at": row.get("created_at"),
            }
    except Exception as e:
        logger.error(f"Knowledge insert error: {e}")
        raise HTTPException(status_code=500, detail=f"Database insert error: {str(e)}")

    return {"status": "created", "fact": fact_val}


@router.delete("/knowledge/{knowledge_id}")
async def delete_knowledge(knowledge_id: str):
    supabase = get_supabase()
    supabase.table("knowledge_base").delete().eq("id", knowledge_id).execute()
    return {"status": "deleted", "id": knowledge_id}


@router.get("/knowledge/search")
async def search_knowledge(q: str, website_id: Optional[str] = None):
    return await list_knowledge(website_id=website_id, q=q)
