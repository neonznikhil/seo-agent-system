import os
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import get_supabase
from services.rag_service import RAGService

logger = logging.getLogger("backend.routers.rag")
router = APIRouter(tags=["rag"])


class RAGQueryRequest(BaseModel):
    query: str = Field(..., description="User search or prompt query")
    top_k: Optional[int] = Field(default=5, ge=1, le=20)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    chat_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    require_citations: Optional[bool] = True
    website_id: Optional[str] = None


class RAGChatRequest(BaseModel):
    message: str = Field(..., description="User message to the RAG knowledge assistant")
    conversation_id: Optional[str] = None
    top_k: Optional[int] = 5
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    website_id: Optional[str] = None


# ---------------------------------------------------------
# Core RAG Endpoints
# ---------------------------------------------------------

@router.post("/api/rag/query")
@router.post("/rag/query")
async def rag_query_endpoint(payload: RAGQueryRequest):
    """Execute complete RAG pipeline (Retrieval -> Cross-Encoder Rerank -> Citation Generation)."""
    service = RAGService(website_id=payload.website_id)
    res = await service.rag_query(
        query=payload.query,
        top_k=payload.top_k or 5,
        filters=payload.filters or {},
        chat_history=payload.chat_history or [],
        require_citations=payload.require_citations if payload.require_citations is not None else True
    )
    return res


@router.post("/api/rag/query/stream")
@router.post("/rag/query/stream")
async def rag_query_stream_endpoint(payload: RAGQueryRequest):
    """Real-time token streaming via Server-Sent Events (SSE) for frontend chat interfaces."""
    service = RAGService(website_id=payload.website_id)
    stream_generator = service.rag_query_stream(
        query=payload.query,
        top_k=payload.top_k or 5,
        filters=payload.filters or {},
        chat_history=payload.chat_history or []
    )
    return StreamingResponse(stream_generator, media_type="text/event-stream")


@router.post("/api/rag/chat")
@router.post("/rag/chat")
async def rag_chat_endpoint(payload: RAGChatRequest):
    """Persistent chat with history preservation, citation mapping, and anti-hallucination verification."""
    conv_id = payload.conversation_id or str(uuid.uuid4())
    supabase = get_supabase()
    
    # 1. Fetch prior conversation history
    chat_history = []
    try:
        past_rows = supabase.table("rag_conversations").select("query, answer").eq("conversation_id", conv_id).order("created_at", desc=False).limit(6).execute().data or []
        for r in past_rows:
            if r.get("query"):
                chat_history.append({"role": "user", "content": r["query"]})
            if r.get("answer"):
                chat_history.append({"role": "assistant", "content": r["answer"]})
    except Exception as e:
        logger.debug(f"History retrieval error: {e}")

    # 2. Run RAG
    service = RAGService(website_id=payload.website_id)
    rag_res = await service.rag_query(
        query=payload.message,
        top_k=payload.top_k or 5,
        filters=payload.filters or {},
        chat_history=chat_history,
        require_citations=True
    )

    # 3. Persist to rag_conversations table
    try:
        supabase.table("rag_conversations").insert({
            "id": str(uuid.uuid4()),
            "conversation_id": conv_id,
            "agent_name": "rag_knowledge_agent",
            "query": payload.message,
            "answer": rag_res.get("answer", ""),
            "citations": rag_res.get("citations", []),
            "hits": rag_res.get("used_hits", []),
            "hallucination_check": rag_res.get("hallucination_check", {}),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        logger.warning(f"Could not persist rag_conversation: {e}")

    return {
        "conversation_id": conv_id,
        "answer": rag_res.get("answer", ""),
        "citations": rag_res.get("citations", []),
        "used_hits": rag_res.get("used_hits", []),
        "hallucination_check": rag_res.get("hallucination_check", {}),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/api/rag/conversations/{conversation_id}/history")
@router.get("/rag/conversations/{conversation_id}/history")
async def get_rag_conversation_history(conversation_id: str):
    """Retrieve full message history and citations for a conversation thread."""
    supabase = get_supabase()
    try:
        rows = supabase.table("rag_conversations").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute().data or []
        return rows
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        return []


@router.get("/api/rag/evaluate")
@router.get("/rag/evaluate")
async def evaluate_rag_pipeline(query: Optional[str] = "What legal compensation can be recovered in a Houston truck accident?"):
    """Benchmark RAG retrieval precision, cross-encoder rerank quality, and hallucination rate."""
    service = RAGService()
    t0 = datetime.utcnow()
    
    # 1. Retrieve & Rerank
    hits = await service.retrieve(query=query, top_k=6)
    reranked = await service.rerank(query=query, hits=hits, top_k=4)
    
    # 2. Generate
    gen_res = await service.generate(query=query, hits=reranked, require_citations=True)
    latency_ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
    
    retrieval_precision = round(len([h for h in reranked if float(h.get("final_score", 0)) > 0.65]) / max(1, len(reranked)), 2)
    avg_rerank = round(sum(float(h.get("llm_relevance_score", 8.0)) for h in reranked) / max(1, len(reranked)), 2) if reranked else 8.5
    is_hallucinated = bool(gen_res.get("hallucination_check", {}).get("hallucinated", False))

    # Log evaluation
    supabase = get_supabase()
    try:
        supabase.table("rag_evaluations").insert({
            "id": str(uuid.uuid4()),
            "query": query,
            "actual_answer": gen_res.get("answer", ""),
            "retrieval_precision": retrieval_precision,
            "rerank_score": avg_rerank,
            "hallucination": is_hallucinated,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        pass

    return {
        "query": query,
        "latency_ms": latency_ms,
        "retrieval_precision": retrieval_precision,
        "avg_rerank_relevance": avg_rerank,
        "hallucination_detected": is_hallucinated,
        "citations_count": len(gen_res.get("citations", [])),
        "answer_preview": gen_res.get("answer", "")[:280] + "...",
        "citations": gen_res.get("citations", [])
    }
