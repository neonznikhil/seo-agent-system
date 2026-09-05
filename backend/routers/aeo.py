import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from database import get_supabase, call_nim_llm
from services.serper_service import serper_search_safe

logger = logging.getLogger("backend.routers.aeo")
router = APIRouter(tags=["aeo"])


class SemanticScoreRequest(BaseModel):
    html_content: str = ""
    target_keyword: str = ""


class RedditOpportunitiesRequest(BaseModel):
    keywords: Optional[list] = None


@router.post("/aeo/semantic-score")
async def get_semantic_score(request: Request, body: SemanticScoreRequest):
    account_id = request.state.account_id if hasattr(request.state, "account_id") else None
    website_id = request.query_params.get("website_id") or (request.headers.get("X-Website-Id") if hasattr(request, "headers") else None)

    article_html = body.html_content
    target_keyword = body.target_keyword

    if not article_html or not target_keyword:
        raise HTTPException(400, "html_content and target_keyword are required")

    from bs4 import BeautifulSoup
    import numpy as np

    soup = BeautifulSoup(article_html, 'html.parser')
    article_text = soup.get_text()[:3000]

    test_queries = [
        f"what is {target_keyword}",
        f"how does {target_keyword} work",
        f"explain {target_keyword}",
        f"{target_keyword} explained simply",
        f"best approach to {target_keyword}",
    ]

    try:
        article_embedding = await _get_embedding(article_text)
    except Exception as e:
        logger.warning(f"[AEO] Article embed failed: {e}")
        article_embedding = []

    scores = []

    for query in test_queries:
        query_embedding = []
        try:
            query_embedding = await _get_embedding(query)
        except Exception:
            pass

        if article_embedding and query_embedding:
            a = np.array(article_embedding)
            b = np.array(query_embedding)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a > 0 and norm_b > 0:
                similarity = float(np.dot(a, b) / (norm_a * norm_b))
            else:
                similarity = 0.0
            scores.append({
                "query": query,
                "similarity_score": round(similarity, 3),
                "grade": (
                    "Excellent" if similarity > 0.85 else
                    "Good" if similarity > 0.75 else
                    "Fair" if similarity > 0.65 else
                    "Poor"
                )
            })

    if not scores:
        return {
            "average_semantic_score": 0.0,
            "overall_grade": "Poor — could not compute embeddings",
            "query_scores": [],
            "recommendation": "Ensure NIM embedding API is configured"
        }

    avg_score = sum(s["similarity_score"] for s in scores) / len(scores)

    return {
        "average_semantic_score": round(avg_score, 3),
        "overall_grade": (
            "Excellent" if avg_score > 0.85 else
            "Good" if avg_score > 0.75 else
            "Fair" if avg_score > 0.65 else
            "Poor — needs semantic expansion"
        ),
        "query_scores": scores,
        "recommendation": (
            "Add more natural language answers to common questions"
            if avg_score < 0.75 else
            "Article is well-optimized for AI search"
        )
    }


async def _get_embedding(text: str) -> list:
    try:
        from services.nim_client import embed
        vecs = await embed(text)
        return vecs if vecs else []
    except Exception:
        return []


@router.get("/aeo/reddit/opportunities")
async def get_reddit_opportunities(request: Request):
    website_id = None
    if hasattr(request.state, "account_id"):
        website_id = request.query_params.get("website_id") or request.headers.get("X-Website-Id")

    if not website_id:
        try:
            from services.website_service import get_default_website_id
            website_id = get_default_website_id()
        except Exception:
            pass

    if not website_id:
        return {"opportunities": [], "message": "No website context found"}

    try:
        supabase = get_supabase()
        blogs = supabase.table("content_log")\
            .select("target_keyword")\
            .eq("website_id", website_id)\
            .order("created_at", desc=True)\
            .limit(10)\
            .execute().data or []

        keywords = [b["target_keyword"] for b in blogs if b.get("target_keyword")]
    except Exception:
        keywords = []

    if not keywords:
        return {"opportunities": [], "message": "No blogs yet"}

    try:
        site_data = get_supabase().table("websites")\
            .select("domain")\
            .eq("id", website_id)\
            .single()\
            .execute().data or {}
        domain = site_data.get("domain", "")
    except Exception:
        domain = ""

    from services.reddit_service import RedditService
    reddit_service = RedditService()
    threads = await reddit_service.search_relevant_threads(keywords)
    opportunities = await reddit_service.identify_opportunity_threads(threads, domain)

    return {
        "opportunities": opportunities,
        "total_found": len(opportunities),
        "keywords_searched": keywords[:5]
    }


@router.post("/aeo/reddit/generate-comment")
async def generate_reddit_comment_endpoint(request: Request, body: dict):
    website_id = request.query_params.get("website_id") or request.headers.get("X-Website-Id")

    thread_title = body.get("thread_title", "")
    thread_snippet = body.get("thread_snippet", "")
    relevant_article_url = body.get("relevant_article_url", "")

    if not thread_title:
        raise HTTPException(400, "thread_title is required")

    website_facts = {}
    if website_id:
        try:
            from services.website_service import get_website_details
            website_facts = get_website_details(website_id) or {}
        except Exception:
            pass

    from services.reddit_service import RedditService
    reddit_service = RedditService()
    comment = await reddit_service.generate_reddit_comment(
        thread_title=thread_title,
        thread_snippet=thread_snippet,
        website_facts=website_facts,
        relevant_article_url=relevant_article_url
    )

    return {"comment": comment}
