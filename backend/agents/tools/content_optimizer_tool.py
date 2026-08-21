import logging
from typing import Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase
import asyncio
import json
import re

logger = logging.getLogger("backend.tools.content_optimizer_tool")


class ContentOptimizerInput(BaseModel):
    content: str = Field(description="Content to optimize for SEO, AEO, GEO")
    website_id: str = Field(description="Website ID for logging")
    target_keywords: str = Field(description="Comma-separated target keywords")


class ContentOptimizerTool(BaseTool):
    name: str = "content_optimizer"
    description: str = "Analyzes and suggests SEO/AEO/GEO optimizations for existing content: keyword density, semantic relevance, E-E-A-T signals, and LLM rendering potential"
    args_schema: type[BaseModel] = ContentOptimizerInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def _run(self, content: str, website_id: str, target_keywords: str) -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})
        
        keywords = [k.strip().lower() for k in target_keywords.split(",") if k.strip()]
        content_lower = content.lower()
        
        analysis = {
            "keyword_analysis": {},
            "seo_suggestions": [],
            "aeo_suggestions": [],
            "geo_suggestions": [],
            "eeat_score": 0,
            "semantic_depth": 0
        }
        
        for kw in keywords:
            count = len(re.findall(re.escape(kw), content_lower))
            density = (count / len(content)) * 100 if content else 0
            analysis["keyword_analysis"][kw] = {
                "mentions": count,
                "density_pct": round(density, 2),
                "recommendation": "optimal" if 0.5 <= density <= 2.5 else ("increase" if density < 0.5 else "reduce")
            }
        
        analysis["seo_suggestions"].extend(self._analyze_seo(content_lower, keywords))
        analysis["aeo_suggestions"].extend(self._analyze_aeo(content))
        analysis["geo_suggestions"].extend(self._analyze_geo(content_lower))
        analysis["eeat_score"] = self._calculate_eeat_score(content)
        analysis["semantic_depth"] = self._calculate_semantic_depth(content_lower, keywords)
        
        _log_proof(self._website_id, "content_optimizer", "analysis", "supabase", f"keywords={len(keywords)}")
        return json.dumps(analysis, indent=2)

    def _analyze_seo(self, content: str, keywords: list) -> list:
        suggestions = []
        
        if len(content.split("\n")) < 5:
            suggestions.append("Add more section headings (H2/H3) for better crawlability")
        
        if not re.search(r"\[.*?\]\(.*?\)", content):
            suggestions.append("Add internal links with descriptive anchor text")
        
        if re.search(r"image|img|picture", content):
            suggestions.append("Add alt text with keywords for all images")
        
        if "title" not in content or "meta" not in content:
            suggestions.append("Optimize title tag and meta description")
        
        return suggestions

    def _analyze_aeo(self, content: str) -> list:
        suggestions = []
        
        paragraphs = content.split("\n\n")
        if paragraphs and len(paragraphs[0].split()) > 30:
            suggestions.append("Write a concise direct answer paragraph (30-50 words) for featured snippets")
        
        faq_matches = len(re.findall(r"[?]\s*$", content, re.MULTILINE))
        if faq_matches < 4:
            suggestions.append(f"Add {4 - faq_matches} more FAQ questions with answers")
        
        if not re.search(r"\|.+\|", content):
            suggestions.append("Add a comparison or data table for rich snippet eligibility")
        
        first_100 = content[:100].lower()
        if "how to" not in first_100 and "what is" not in first_100:
            suggestions.append("Start with clear topic definition for passage indexing")
        
        return suggestions

    def _analyze_geo(self, content: str) -> list:
        suggestions = []
        
        entity_matches = len(re.findall(r"[@#$%]?&*(?:\{\|\^\}\[]", content))
        if entity_matches < 3:
            suggestions.append("Add entity markup (brands, products, locations) with structured references")
        
        if "citation" not in content and "source" not in content:
            suggestions.append("Add data citations from authoritative sources")
        
        word_count = len(content.split())
        if word_count < 2000:
            suggestions.append(f"Increase content depth: add {2000 - word_count} words for competitive topics")
        
        if not re.search(r"first|latest|recent|updated", content, re.IGNORECASE):
            suggestions.append('Add publication date or "Last Updated" indicator for freshness signals')
        
        return suggestions

    def _calculate_eeat_score(self, content: str) -> int:
        score = 0
        
        if re.search(r"certified|certification|accredited", content):
            score += 2
        if re.search(r"years?\s+experience|expertise|specialized", content):
            score += 2
        
        cited_sources = len(re.findall(r"\[\d+\]|\[source\]|\[citation\]", content))
        score += min(cited_sources, 3)
        
        if re.search(r"author:|by line|about the author", content):
            score += 2
        
        if re.search(r"case study|real|example|example", content):
            score += 1
        
        return min(score, 10)

    def _calculate_semantic_depth(self, content: str, keywords: list) -> int:
        lsi_keywords = ["related", "similar", "comparison", "benefit", "feature", "result"]
        found_lsi = sum(1 for k in lsi_keywords if k in content)
        keyword_context = sum(1 for kw in keywords if kw in content)
        
        return min(found_lsi + keyword_context, 10)


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
