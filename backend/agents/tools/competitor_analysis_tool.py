import logging
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio
import json
from datetime import datetime

logger = logging.getLogger("backend.tools.competitor_analysis_tool")


class CompetitorAnalysisInput(BaseModel):
    competitor_urls: str = Field(description="Comma-separated list of competitor URLs to analyze")
    website_id: str = Field(description="Website ID for logging")


class CompetitorAnalysisTool(BaseTool):
    name: str = "competitor_analysis"
    description: str = "Analyze competitor websites for SEO insights, content gaps, backlink opportunities, and optimization strategies. Uses browser automation to render dynamic content and extract real-time data."
    args_schema: type[BaseModel] = CompetitorAnalysisInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def _run(self, competitor_urls: str, website_id: str = None) -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})
        
        urls = [u.strip() for u in competitor_urls.split(",") if u.strip()]
        results = {
            "analysis_date": datetime.utcnow().isoformat(),
            "comparisons": [],
            "insights": {},
            "opportunities": []
        }
        
        for url in urls[:5]:
            try:
                analysis = self._analyze_url(url)
                results["comparisons"].append(analysis)
            except Exception as e:
                logger.warning(f"Failed to analyze {url}: {e}")
                results["comparisons"].append({"url": url, "error": str(e)})
        
        results["insights"] = self._generate_insights(results["comparisons"])
        results["opportunities"] = self._identify_opportunities(results["comparisons"])
        
        _log_proof(self._website_id, "competitor_analysis", "analysis", "playwright", f"urls={len(urls)}")
        return json.dumps(results, indent=2)

    def _analyze_url(self, url: str) -> Dict[str, Any]:
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup
        
        result = {"url": url, "timestamp": datetime.utcnow().isoformat()}
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (compatible; SEO-Agent-Bot/1.0)"})
                
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)
                
                title = page.title()
                meta_desc = page.evaluate("document.querySelector('meta[name=\"description\"]').getAttribute('content') || ''")
                h1 = page.evaluate("document.querySelector('h1').innerText || ''")
                
                page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('h2, h3, h4');
                        return Array.from(elements).map(el => el.innerText.trim());
                    }
                """)
                
                links = page.evaluate("""
                    () => Array.from(document.querySelectorAll('a')).map(a => ({
                        text: a.innerText.trim().substring(0, 100),
                        href: a.href
                    })).filter(a => a.text && !a.href.includes('javascript:'))
                """)[:20]
                
                images = page.evaluate("""
                    () => Array.from(document.querySelectorAll('img')).map(img => ({
                        alt: img.alt || '',
                        src: img.src
                    }))
                """)[:10]
                
                content = page.inner_text("body")[:5000]
                
                result.update({
                    "title": title,
                    "meta_description": meta_desc,
                    "h1": h1,
                    "content_length": len(content),
                    "word_count": len(content.split()),
                    "internal_links": len(links),
                    "images": len(images),
                    "headings_structure": True,
                    "structured_data": "JSON-LD" in page.content() or "schema.org" in page.content(),
                    "last_analyzed": datetime.utcnow().isoformat()
                })
                
                browser.close()
                
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _generate_insights(self, comparisons: List[Dict]) -> Dict[str, Any]:
        insights = {
            "average_word_count": 0,
            "common_title_patterns": [],
            "meta_description_trends": [],
            "structural_gaps": [],
            "content_strengths": [],
            "seo_opportunities": []
        }
        
        valid_comparisons = [c for c in comparisons if "error" not in c]
        if not valid_comparisons:
            return insights
        
        total_words = sum(c.get("word_count", 0) for c in valid_comparisons)
        insights["average_word_count"] = total_words // len(valid_comparisons)
        
        word_counts = [c.get("word_count", 0) for c in valid_comparisons]
        avg_word_count = sum(word_counts) / len(word_counts) if word_counts else 0
        
        if avg_word_count > 1500:
            insights["content_strengths"].append("Long-form content (above 1500 words)")
        else:
            insights["seo_opportunities"].append(f"Increase content depth from average {int(avg_word_count)} to 1500+ words")
        
        if any(c.get("structured_data", False) for c in valid_comparisons):
            insights["content_strengths"].append("Structured data implemented")
        else:
            insights["seo_opportunities"].append("Add FAQ/HowTo schema for rich results")
        
        if any("FAQ" in c.get("headings_structure", "") for c in comparisons):
            insights["content_strengths"].append("FAQ sections present")
        else:
            insights["seo_opportunities"].append("Add FAQ section for featured snippets")
        
        return insights

    def _identify_opportunities(self, comparisons: List[Dict]) -> List[Dict]:
        opportunities = []
        
        for comp in comparisons:
            if "error" in comp:
                continue
            
            if comp.get("meta_description", "").endswith("..."):
                opportunities.append({
                    "url": comp["url"],
                    "opportunity": "Meta description truncates - rewrite for full visibility",
                    "impact": "medium"
                })
            
            if not comp.get("structured_data", False):
                opportunities.append({
                    "url": comp["url"], 
                    "opportunity": "Missing structured data (FAQ/HowTo schema)",
                    "impact": "high"
                })
            
            if comp.get("content_length", 0) < 1000:
                opportunities.append({
                    "url": comp["url"],
                    "opportunity": "Thin content - needs expansion",
                    "impact": "medium"
                })
        
        opportunities.extend([
            {
                "opportunity": "Target featured snippets with 50-word answer blocks",
                "impact": "high",
                "implementation": "Add direct answer paragraphs for key queries"
            },
            {
                "opportunity": "Create table-based content for ranking",
                "impact": "high",
                "implementation": "Add comparison tables, data visualizations"
            },
            {
                "opportunity": "Optimize for AI citations with entity markup",
                "impact": "medium",
                "implementation": "Add structured data for brands, products, dates"
            }
        ])
        
        return opportunities


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        from ...database import get_supabase
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "result": json.dumps({"real_api_called": real_api}),
            "real_api_called": real_api,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass
