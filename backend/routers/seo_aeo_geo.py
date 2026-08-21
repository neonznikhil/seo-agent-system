import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import asyncio
import json

from ..database import get_supabase, call_nim_llm
from ..agents.tools.seo_aeo_geo_tool import SEOAEOGEOTool
from ..agents.tools.serp_analyzer_tool import SERPAnalyzerTool
from ..agents.tools.content_optimizer_tool import ContentOptimizerTool

logger = logging.getLogger("backend.routers.seo_aeo_geo")
router = APIRouter()





class SEOTaskIn(BaseModel):
    url: str
    target_keywords: Optional[str] = None


@router.get("/seo-analysis/{website_id}/{url:path}")
async def seo_analysis(website_id: str, url: str):
    seo_tool = SEOAEOGEOTool()
    seo_tool.set_website_id(website_id)
    result = seo_tool._run(url, website_id)
    return json.loads(result)


@router.get("/serp-analysis/{website_id}")
async def serp_analysis(website_id: str, query: str):
    serp_tool = SERPAnalyzerTool()
    serp_tool.set_website_id(website_id)
    result = serp_tool._run(query, website_id)
    return json.loads(result)


@router.post("/optimize-content/{website_id}")
async def optimize_content(website_id: str, task: SEOTaskIn):
    content_tool = ContentOptimizerTool()
    content_tool.set_website_id(website_id)
    result = content_tool._run(task.url, website_id, task.target_keywords or "")
    return json.loads(result)


@router.get("/aeo-score/{website_id}")
async def aeo_score(website_id: str):
    rows = get_supabase().table("knowledge_base").eq("website_id", website_id).limit(50).execute().data or []
    facts_text = "\n".join(r.get("fact", "") for r in rows)
    
    prompt = f"""
    You are an AEO (Answer Engine Optimization) specialist. 
    Analyze the following knowledge facts and calculate an AEO readiness score (0-100).
    
    Facts:
    {facts_text[:5000]}
    
    Return JSON with keys:
    - score: 0-100
    - improvements: list of 5 specific ways to improve AEO optimization
    - featured_snippet_opportunities: list of questions that could trigger featured snippets
    
    Think about: structure, clarity, data points, FAQ potential, snippet eligibility.
    """
    
    raw = await call_nim_llm(prompt, "Output only JSON.")
    try:
        return json.loads(raw)
    except:
        return {"error": "Failed to parse AEO analysis"}


@router.get("/geo-readiness/{website_id}")  
async def geo_readiness(website_id: str):
    rows = get_supabase().table("knowledge_base").eq("website_id", website_id).limit(50).execute().data or []
    facts = [r.get("fact", "") for r in rows]
    
    prompt = f"""
    You are a GEO (Generative Engine Optimization) expert.
    
    Analyze these facts for GEO/LLM training data inclusion potential:
    Facts: {facts[:3000]}
    
    Return JSON with:
    - score: 0-100
    - ai_citation_potential: how likely these facts are to be cited by AI (high/medium/low)
    - citation_ready: true/false if ready for AI training datasets
    - improvements: 5 ways to make more AI-citable
    
    Consider: source attribution, data verifiability, entity references, citation format.
    """
    
    raw = await call_nim_llm(prompt, "Output only JSON.")
    try:
        return json.loads(raw)
    except:
        return {"error": "Failed to parse GEO analysis"}


class AEOOptimizationIn(BaseModel):
    content: str
    target_query: str


@router.post("/content-aeo-optimize/{website_id}")
async def content_aeo_optimize(website_id: str, task: AEOOptimizationIn):
    """Optimize existing content for Answer Engine Optimization"""
    prompt = f"""
    You are an AEO (Answer Engine Optimization) specialist.
    
    Analyze this content for featured snippet and AI answer box optimization:
    
    Content:
    {task.content[:3000]}
    
    Target query: {task.target_query}
    
    Return JSON with:
    - snippet_optimized: modified content starting with direct answer
    - aeo_elements: {{"has_direct_answer": bool, "has_table": bool, "stat_in_content": bool, "faq_count": int}}
    - recommendations: 5 specific AEO improvements
    - featured_snippet_type: paragraph/list/video/table (most likely)
    """
    
    raw = await call_nim_llm(prompt, "Output valid JSON only.")
    try:
        return json.loads(raw)
    except:
        return {"error": "Failed to parse AEO optimization"}


class GEOContentIn(BaseModel):
    content: str
    topics: str


@router.post("/content-geo-optimize/{website_id}")
async def content_geo_optimize(website_id: str, task: GEOContentIn):
    """Optimize content for Generative Engine Optimization (AI training data)"""
    prompt = f"""
    You are a GEO (Generative Engine Optimization) specialist.
    
    Optimize this content for AI/LLM summarization and citation:
    
    Content:
    {task.content[:3000]}
    
    Key topics: {task.topics}
    
    Return JSON with:
    - geo_optimized: content optimized for AI summarization
    - entities: list of entities that should be marked up
    - citation_points: 3-5 verifiable data points
    - ai_summarization_score: 0-100
    - improvements: 5 GEO-specific recommendations
    
    Focus on: entity recognition, data verifiability, clear conclusions, citation readiness.
    """
    
    raw = await call_nim_llm(prompt, "Output valid JSON only.")
    try:
        return json.loads(raw)
    except:
        return {"error": "Failed to parse GEO optimization"}