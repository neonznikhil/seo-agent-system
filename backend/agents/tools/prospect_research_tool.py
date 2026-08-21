import logging
from typing import Optional, List, Dict, Any
import json
import re

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase

logger = logging.getLogger("backend.tools.prospect_research")


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "error": json.dumps({"real_api_called": real_api}),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


class ProspectResearchInput(BaseModel):
    keyword: str = Field(description="Target keyword for backlink prospect research")
    website_id: str = Field(description="Website ID for context")


class ProspectResearchTool(BaseTool):
    name: str = "prospect_research"
    description: str = "Finds relevant websites, blogs, and directories for backlink outreach based on target keywords"
    args_schema: type[BaseModel] = ProspectResearchInput
    _website_id: Optional[str] = None
    _agent_name: str = "backlink_agent"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, keyword: str, website_id: str) -> str:
        if not keyword:
            return "# Error: No keyword provided"

        try:
            from ...database import call_nim_llm

            website = get_supabase().table("websites").select("*").eq("id", website_id).single().execute().data
            if not website:
                return "# Error: Website not found"

            domain = website.get("domain", "")
            prompt = f"""You are an expert link building researcher. Find high-quality backlink prospects for a website about "{keyword}" targeting domain "{domain}".

            Find 10 relevant prospects in these categories:
            1. Guest post opportunities (blogs accepting guest posts in this niche)
            2. Resource pages (pages listing useful resources)
            3. Industry directories (niche-specific directories)
            4. Forum communities (active forums in this niche)
            5. Social bookmarking sites (high DA social sites)

            For each prospect, provide:
            - name: Website name
            - url: Full URL
            - type: guest_post, resource_page, directory, forum, or social
            - domain_authority: Estimated DA (1-100)
            - contact_email: If known, or outreach page URL
            - relevance_score: 1-10 how relevant to keyword
            - notes: Specific page to target or contact info

            Return JSON array format:
            [
              {{
                "name": "Example Blog",
                "url": "https://example.com/guest-post",
                "type": "guest_post",
                "domain_authority": 45,
                "contact_email": "editor@example.com",
                "relevance_score": 8,
                "notes": "Target /guest-post guidelines page"
              }}
            ]

            Only include real, relevant prospects. No generic directories."""

            result = call_nim_llm(prompt, "You are a professional link building researcher. Provide only valid JSON.")
            _log_proof(website_id, self._agent_name, "prospect_research", "nim", f"research:{keyword}")

            prospects = json.loads(result)
            saved = 0
            for prospect in prospects:
                try:
                    get_supabase().table("backlink_prospects").insert({
                        "website_id": website_id,
                        "name": prospect.get("name", ""),
                        "url": prospect.get("url", ""),
                        "type": prospect.get("type", "unknown"),
                        "domain_authority": prospect.get("domain_authority", 0),
                        "contact_email": prospect.get("contact_email"),
                        "relevance_score": prospect.get("relevance_score", 5),
                        "notes": prospect.get("notes", ""),
                        "status": "new",
                        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
                    }).execute()
                    saved += 1
                except Exception as e:
                    logger.error("Failed to save prospect: %s", e)

            return json.dumps({
                "keyword": keyword,
                "prospects_found": len(prospects),
                "prospects_saved": saved,
                "prospects": prospects,
            })

        except Exception as e:
            logger.error("Prospect research failed: %s", e)
            _log_proof(website_id, self._agent_name, "prospect_research", "error", str(e))
            return f"# Error: Prospect research failed: {str(e)[:200]}"
