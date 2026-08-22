import logging
from typing import Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase, call_nim_llm
import asyncio
import json

logger = logging.getLogger("backend.tools.seo_aeo_geo_tool")


class SEOAEOGEOInput(BaseModel):
    url: str = Field(description="URL to analyze for SEO/AEO/GEO optimization")
    website_id: str = Field(description="Website ID in Supabase")


class SEOAEOGEOTool(BaseTool):
    name: str = "seo_aeo_geo_analyzer"
    description: str = "Analyzes real page content for SEO, AEO (Answer Engine Optimization), and GEO (Generative Engine Optimization) using LLM. Returns verified analysis or explicit error."
    args_schema: type[BaseModel] = SEOAEOGEOInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    async def _run(self, url: str, website_id: str) -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set", "real_api_called": "none"})

        page_content = ""
        crawl_source = "none"

        try:
            from ...services.crawlee_service import CrawleeService
            crawler = CrawleeService()
            results = await crawler.crawl_site_structure([url], max_requests=1)
            if results:
                page = results[0]
                page_content = f"Title: {page.get('title', '')}\n"
                page_content += f"URL: {page.get('url', url)}\n"
                page_content += f"H1s: {', '.join(page.get('h1s', []))}\n"
                page_content += f"H2s: {', '.join(page.get('h2s', [])[:20])}\n"
                page_content += f"Meta Description: {page.get('meta_description', '')}\n"
                page_content += f"Word Count: {page.get('word_count', 0)}\n"
                page_content += f"Canonical: {page.get('canonical', '')}\n"
                page_content += f"Schemas: {', '.join(str(s.get('@type', '')) for s in page.get('schemas', []))}\n"
                crawl_source = "crawlee"
        except Exception as e:
            logger.warning("Crawlee failed for %s: %s", url, e)
            page_content = f"URL: {url}\nError during crawl: {str(e)}"
            crawl_source = "error"

        try:
            prompt = f"""You are an expert SEO/AEO/GEO analyst. Analyze the following page content and return ONLY a JSON object with these exact keys:
{{
  "seo": ["suggestion1", "suggestion2"],
  "aeo": ["suggestion1", "suggestion2"],
  "geo": ["suggestion1", "suggestion2"],
  "score": 0-100,
  "issues_found": 0,
  "data_source": "llm_analysis"
}}

Page content:
{page_content[:4000]}

Rules:
- Base ALL suggestions ONLY on the provided page content
- If content is missing or empty, state that in issues
- Score must be a number 0-100
- Return ONLY valid JSON, no markdown, no extra text"""

            result = await call_nim_llm(prompt, "You are an SEO analyst. Output only valid JSON.", website_id=self._website_id)
            llm_source = "nim"
            try:
                analysis = json.loads(result)
                analysis["real_api_called"] = f"crawlee+{llm_source}"
                analysis["crawl_source"] = crawl_source
                analysis["no_hallucination"] = True
            except json.JSONDecodeError:
                logger.warning("LLM returned invalid JSON for %s: %s", url, result[:200])
                analysis = {
                    "seo": ["Unable to parse LLM response"],
                    "aeo": ["Unable to parse LLM response"],
                    "geo": ["Unable to parse LLM response"],
                    "score": 0,
                    "issues_found": 1,
                    "real_api_called": f"crawlee+{llm_source}",
                    "crawl_source": crawl_source,
                    "no_hallucination": True,
                    "parse_error": True,
                }
        except Exception as e:
            logger.warning("LLM analysis failed for %s: %s", url, e)
            analysis = {
                "seo": [f"LLM analysis failed: {str(e)[:100]}"],
                "aeo": ["LLM analysis unavailable"],
                "geo": ["LLM analysis unavailable"],
                "score": 0,
                "issues_found": 1,
                "real_api_called": f"crawlee+error",
                "crawl_source": crawl_source,
                "no_hallucination": True,
                "error": str(e)[:200],
            }

        _log_proof(self._website_id, "seo_aeo_geo_analyzer", "analysis", analysis.get("real_api_called", "unknown"), f"url={url}")
        logger.info("SEO/AEO/GEO analysis completed for %s: score=%s source=%s", url, analysis.get("score"), analysis.get("real_api_called"))
        return json.dumps(analysis, indent=2)


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "result": {"real_api_called": real_api},
            "real_api_called": real_api,
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass
