# AI Web Browsing Workflow

This document shows how to integrate web browsing and real-time data collection into AI agents for SEO, AEO, and GEO optimization.

## Core Browsing Tools

### 1. Web Browser Tool

```python
from backend.agents.tools.web_browser_tool import WebBrowserTool

browser = WebBrowserTool()
browser.set_website_id("website-123")

# Extract full content with JavaScript rendering
result = browser._run(
    url="https://example.com/article",
    wait_time=5,  # Wait for JS to load
    extract="content"  # Options: content, links, images, tables, seo_data
)
```

### 2. Real-Time Data Tool

```python
from backend.agents.tools.real_time_data_tool import RealTimeDataTool

data = RealTimeDataTool()
data.set_website_id("website-123")

# Fetch trending news
news = data._run("SEO AI trends 2024", source="news", count=5)

# Fetch social media sentiment
social = data._run("content marketing", source="social", count=10)

# Fetch API data (crypto, stocks, weather)
api_data = data._run("bitcoin", source="api", count=3)
```

### 3. Competitor Analysis Tool

```python
from backend.agents.tools.competitor_analysis_tool import CompetitorAnalysisTool

comp = CompetitorAnalysisTool()
comp.set_website_id("website-123")

# Analyze multiple competitors at once
result = comp._run(
    "competitor1.com,competitor2.com,competitor3.com",
    "website-123"
)
```

## Integrated Agent Workflow

### Market Research Phase

```python
async def market_research_phase(website_id: str, topic: str):
    from backend.agents.tools.real_time_data_tool import RealTimeDataTool
    
    data_tool = RealTimeDataTool()
    data_tool.set_website_id(website_id)
    
    # Get trending topics
    trends = data_tool._run(topic, source="news", count=10)
    
    # Get social sentiment
    social = data_tool._run(topic, source="social", count=20)
    
    # Get API statistics
    if topic.lower() in ["ai", "seo", "marketing"]:
        stats = data_tool._run(topic, source="api", count=5)
    
    return {
        "trends": trends,
        "social_signals": social,
        "statistics": stats if "topic" in dir() else None
    }
```

### Competitor Gap Analysis

```python
async def competitor_gap_analysis(website_id: str, competitors: List[str]):
    from backend.agents.tools.competitor_analysis_tool import CompetitorAnalysisTool
    from backend.agents.tools.web_browser_tool import WebBrowserTool
    
    # Analyze competitors
    comp = CompetitorAnalysisTool()
    comp.set_website_id(website_id)
    analysis = comp._run(",".join(competitors), website_id)
    
    # Get detailed content for top opportunities
    browser = WebBrowserTool()
    browser.set_website_id(website_id)
    
    top_opportunity = analysis["opportunities"][0]
    if top_opportunity:
        detailed = browser._run(top_opportunity["url"], extract="content")
    
    return {
        "gaps": analysis["opportunities"],
        "insights": analysis["insights"],
        "detailed_analysis": detailed if "detailed" in dir() else None
    }
```

### Real-Time Content Optimization

```python
async def real_time_content_optimization(website_id: str, url: str):
    from backend.agents.tools.web_browser_tool import WebBrowserTool
    from backend.agents.tools.real_time_data_tool import RealTimeDataTool
    import json
    
    # Get current page analysis
    browser = WebBrowserTool()
    browser.set_website_id(website_id)
    
    current_analysis = browser._run(url, 5, "seo_data")
    current_data = json.loads(current_analysis)
    
    # Get trending related queries
    data_tool = RealTimeDataTool()
    data_tool.set_website_id(website_id)
    
    base_topic = url.split("/")[-1].replace("-", " ")
    trending = data_tool._run(f"{base_topic} 2024 trends", source="news", count=5)
    
    return {
        "current_seo": current_data.get("data", {}),
        "trending_topics": json.loads(trending),
        "optimization_recommendations": {
            "add_trending_keywords": True,
            "update_statistics": True,
            "add_faq_section": True,
            "optimize_for_ai_citation": True
        }
    }
```

## Sequential Workflow Example

```python
async def full_seo_ai_workflow(website_id: str, topic: str, competitors: List[str]):
    """
    Complete workflow: research -> analyze -> optimize -> verify
    """
    from backend.agents.crew_manager import run_full_site_optimization
    
    # Phase 1: Market Research
    print("Phase 1: Market Research")
    trends = await market_research_phase(website_id, topic)
    
    # Phase 2: Competitor Analysis
    print("Phase 2: Competitor Analysis")
    gaps = await competitor_gap_analysis(website_id, competitors)
    
    # Phase 3: Run Autonomous Crew
    print("Phase 3: Autonomous Optimization")
    crew_result = run_full_site_optimization(website_id)
    
    # Phase 4: Generate Reports
    print("Phase 4: Final Reports")
    return {
        "market_research": trends,
        "competitor_gaps": gaps,
        "crew_results": crew_result,
        "ai_visibility_score": crew_result.get("seo_score", 0),
        "next_steps": [
            "Implement competitor gap solutions",
            "Update content with trending data",
            "Optimize for featured snippets"
        ]
    }
```

## AI Integration Tips

1. **Always set website_id** for audit logging
2. **Use appropriate extract types** to minimize bandwidth
3. **Cache results** for repeated analysis
4. **Respect rate limits** - max 10 URLs per session
5. **Combine tools** for deeper insights

## Error Handling

```python
try:
    result = browser._run(url, wait_time=5, extract="content")
    data = json.loads(result)
    if "error" in data:
        print(f"Browser error: {data.get('error')}")
    # Process data...
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Browser Configuration

The tools use Playwright with:
- Chromium headless browser
- 30-second page load timeout
- Desktop user agent
- Network idle wait

For custom configurations, modify the launch parameters in the tool files.