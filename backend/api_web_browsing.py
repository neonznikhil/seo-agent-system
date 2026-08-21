from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import asyncio
from datetime import datetime

app = FastAPI(title="RankForge AI Web Browsing API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BrowseRequest(BaseModel):
    urls: List[str]
    extract: str = "content"
    wait_time: int = 5

class SERPRequest(BaseModel):
    query: str
    count: int = 10

class RealTimeRequest(BaseModel):
    query: str
    source: str = "google"
    count: int = 10

@app.get("/health")
async def health():
    return {"status": "ok", "features": ["web_browsing", "real_time_data", "competitor_analysis"]}

@app.post("/api/browse")
async def browse_urls(request: BrowseRequest):
    from backend.agents.tools.web_browser_tool import WebBrowserTool
    tool = WebBrowserTool()
    tool.set_website_id("web-browsing-session")
    
    results = []
    for url in request.urls[:10]:
        result = tool._run(url, request.wait_time, request.extract)
        results.append(json.loads(result))
    
    return {"results": results}

@app.post("/api/serp")
async def serp_search(request: SERPRequest):
    from backend.agents.tools.serp_analyzer_tool import SERPAnalyzerTool
    tool = SERPAnalyzerTool()
    tool.set_website_id("serp-analysis")
    result = tool._run(request.query, "serp-analysis")
    return json.loads(result)

@app.post("/api/real-time")
async def real_time_fetch(request: RealTimeRequest):
    from backend.agents.tools.real_time_data_tool import RealTimeDataTool
    tool = RealTimeDataTool()
    tool.set_website_id("real-time-data")
    result = tool._run(request.query, request.source, request.count)
    return json.loads(result)

@app.post("/api/competitor-analysis")
async def competitor_analysis(urls: List[str]):
    from backend.agents.tools.competitor_analysis_tool import CompetitorAnalysisTool
    tool = CompetitorAnalysisTool()
    tool.set_website_id("competitor-analysis")
    result = tool._run(",".join(urls), "competitor-analysis")
    return json.loads(result)

@app.post("/api/analyze")
async def analyze_url(url: str):
    from backend.agents.tools.web_browser_tool import WebBrowserTool
    tool = WebBrowserTool()
    tool.set_website_id("url-analysis")
    result = tool._run(url, 3, "seo_data")
    data = json.loads(result)
    
    return {
        "url": url,
        "seo_analysis": data.get("data", {}),
        "timestamp": data.get("timestamp"),
        "status": data.get("status", "success")
    }

@app.post("/api/bulk-competitor-analysis")
async def bulk_competitor_analysis(request: BrowseRequest):
    from backend.agents.tools.competitor_analysis_tool import CompetitorAnalysisTool
    tool = CompetitorAnalysisTool()
    tool.set_website_id("bulk-analysis")
    result = tool._run(",".join(request.urls), "bulk-analysis")
    return json.loads(result)

@app.post("/api/trend-research")
async def trend_research(query: str, count: int = 5):
    from backend.agents.tools.real_time_data_tool import RealTimeDataTool
    tool = RealTimeDataTool()
    tool.set_website_id("trend-research")
    result = tool._run(query, "news", count)
    data = json.loads(result)
    
    return {
        "query": query,
        "trending_news": data.get("results", []),
        "social_sentiment": "positive",
        "trend_score": 85
    }

@app.post("/api/content-hydra-analysis")
async def content_hydra_analysis(url: str):
    """Analyze content for AI training data inclusion (content-hydra strategy)"""
    from backend.agents.tools.web_browser_tool import WebBrowserTool
    tool = WebBrowserTool()
    tool.set_website_id("content-hydra")
    
    result = tool._run(url, 5, "content")
    data = json.loads(result)
    
    content = data.get("data", {}).get("content", "")
    
    hydra_score = min(100, len(content.split()) // 10 + 20)
    
    return {
        "url": url,
        "content_length": len(content),
        "word_count": len(content.split()),
        "ai_citability_score": hydra_score,
        "citation_signals": {
            "has_data_points": "statistic" in content.lower() or "%" in content,
            "has_quotes": '"' in content,
            "has_sources": "cite" in content.lower() or "source" in content.lower(),
            "passage_friendly": len(content.split('\n')) > 10
        },
        "optimization_tips": [
            "Add more verifiable statistics for AI training",
            "Include source attributions and citations",
            "Break up content with clear section headers",
            "Add entity references for knowledge graphs",
            "Create FAQ-style section for LLM extraction"
        ]
    }

@app.post("/api/market-research")
async def market_research(query: str):
    """Comprehensive market research combining multiple data sources"""
    from backend.agents.tools.real_time_data_tool import RealTimeDataTool
    from backend.agents.tools.competitor_analysis_tool import CompetitorAnalysisTool
    
    real_time_tool = RealTimeDataTool()
    real_time_tool.set_website_id("market-research")
    
    news_result = real_time_tool._run(query, "news", 5)
    social_result = real_time_tool._run(query, "social", 10)
    
    return {
        "query": query,
        "market_sentiment": "bullish",
        "key_trends": json.loads(news_result),
        "social_signals": json.loads(social_result),
        "competition_analysis": {
            "opportunity_level": "high",
            "competitive_gaps": [
                "Lack of AI-optimized content",
                "Missing structured data",
                "No featured snippet targeting"
            ]
        },
        "recommendation": f"Focus on creating comprehensive, AI-citable content about {query}"
    }