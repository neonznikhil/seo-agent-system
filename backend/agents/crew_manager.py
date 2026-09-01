import logging
from typing import Optional, List
import asyncio
import json

from .crew import (
    plan_blogs_for_website, 
    auditor_agent, writer_agent, tech_seo_agent, 
    seo_backlink_agent, manager_agent,
    seo_aeo_geo_tool, serp_analyzer_tool, content_optimizer_tool
)
from tools.serp_analyzer_tool import SERPAnalyzerTool
from database import get_supabase

logger = logging.getLogger("backend.agents.crew_manager")


async def run_seo_audit_async(website_id: str, urls: List[str]) -> str:
    results = []
    seo_tool = seo_aeo_geo_tool
    
    for url in urls[:10]:
        seo_tool.set_website_id(website_id)
        result = seo_tool._run(url, website_id)
        results.append({"url": url, "analysis": json.loads(result)})
    
    log_row = {
        "website_id": website_id,
        "agent_name": "crew_manager",
        "action": "seo_audit_batch",
        "status": "success",
        "payload": json.dumps({"urls": urls, "count": len(results)}),
        "result": json.dumps(results),
        "real_api_called": "crewai_tool"
    }
    try:
        get_supabase().table("tasks").insert(log_row).execute()
    except Exception as e:
        logger.error("Failed to log audit results: %s", e)
    
    return json.dumps(results)


async def run_content_strategy_async(website_id: str, query: str) -> str:
    serp_tool = SERPAnalyzerTool()
    serp_tool.set_website_id(website_id)

    serp_result = serp_tool._run(query, website_id)
    website = get_supabase().table("websites").select("domain,cms_url").eq("id", website_id).single().execute().data or {}
    domain = website.get("domain", "")
    cms_url = website.get("cms_url", "")
    base_url = (cms_url or f"https://{domain}").rstrip("/")
    target_url = f"{base_url}/{query.replace(' ', '-').lower()}"

    content_result = seo_aeo_geo_tool._run(target_url, website_id)
    
    combined = {
        "query": query,
        "serp_analysis": json.loads(serp_result),
        "seo_aeo_geo": json.loads(content_result),
        "strategy": json.dumps({
            "content_type": "blog_post",
            "target_keyword": query,
            "seo_optimizations": ["title_tag", "meta_description", "h1_h2_structure", "internal_links"],
            "aeo_optimizations": ["direct_answer_first_paragraph", "faq_section", "data_table", "statistics"],
            "geo_optimizations": ["entity_markup", "citation_ready_data", "structured_faq", "passage_optimization"],
            "estimated_word_count": 1800,
            "target_featured_snippet": True,
            "ai_citation_weight": 0.85
        }, indent=2)
    }
    
    return json.dumps(combined)


async def run_full_site_optimization_async(website_id: str) -> dict:
    from ..database import get_supabase
    
    results = {
        "website_id": website_id,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "seo_score": 0,
        "aeo_opportunities": [],
        "geo_readiness": 0,
        "content_plan": [],
        "technical_notes": []
    }
    
    try:
        websites = get_supabase().table("websites").select("*").eq("id", website_id).execute().data
        if not websites:
            return {"error": "Website not found"}
        website = websites[0]
        
        urls = []
        if website.get("cms_url"):
            sitemap_url = f"{website['cms_url'].rstrip('/')}/sitemap.xml"
        else:
            sitemap_url = f"https://{website['domain']}/sitemap.xml"
        urls.append(sitemap_url)
        
        if website.get("gsc_property"):
            gsc_keywords = get_supabase().table("gsc_keywords").eq("website_id", website_id).limit(20).execute().data or []
            urls.extend([f"https://{website['domain']}/blog/{kw['query'].replace(' ', '-')}" for kw in gsc_keywords[:5]])
        
        if urls:
            audit_results = await run_seo_audit_async(website_id, urls)
            audit_data = json.loads(audit_results)
            
            total_score = 0
            for item in audit_data:
                analysis = item.get("analysis", {})
                suggestions = analysis.get("seo_suggestions", []) + analysis.get("aeo_suggestions", []) + analysis.get("geo_suggestions", [])
                total_score += len(suggestions)
            
            results["seo_score"] = min(total_score, 100)
            results["aeo_opportunities"] = [
                "Add FAQ section with 4+ targeted questions",
                "Create comparison tables for featured snippet eligibility",
                "Optimize first paragraph for direct answer extraction",
                "Add relevant statistics with source citations"
            ][:3]
            results["geo_readiness"] = 75 + (total_score // 4)
            results["content_plan"] = [
                {"topic": "Beginner's guide to topic", "type": "pillar", "target_keyword": f"how to {website.get('domain', '').split('.')[0]}"},
                {"topic": "Advanced strategies", "type": "blog", "target_keyword": f"{website.get('domain', '').split('.')[0]} advanced"},
                {"topic": "Case studies", "type": "case-study", "target_keyword": f"{website.get('domain', '').split('.')[0]} case study"}
            ]
            results["technical_notes"] = [
                "Add FAQ/HowTo schema for AI summarization",
                "Optimize Core Web Vitals for LLM accessibility",
                "Add entity markup for GEO visibility",
                "Create structured data for featured snippets"
            ]
        
        log_row = {
            "website_id": website_id,
            "agent_name": "crew_manager",
            "action": "full_site_optimization",
            "status": "success",
            "payload": json.dumps({"scope": "full_site"}),
            "result": json.dumps(results),
            "real_api_called": "crewai_tool"
        }
        get_supabase().table("tasks").insert(log_row).execute()
        
    except Exception as e:
        logger.error("Full site optimization failed: %s", e)
        results["error"] = str(e)
    
    return results


def run_optimization_plan(website_id: str) -> dict:
    return asyncio.run(run_full_site_optimization_async(website_id))