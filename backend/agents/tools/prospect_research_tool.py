import logging
from typing import Optional, List, Dict, Any
import json
import re

try:
    from crewai.tools import BaseTool
except ImportError:
    try:
        from crewai_tools import BaseTool  # type: ignore
    except ImportError:
        class BaseTool:  # fallback stub for py_compile without crewai
            name: str = ""
            description: str = ""
            def _run(self, *a, **kw):
                raise NotImplementedError("crewai not installed")
from pydantic import BaseModel, Field

from database import get_supabase

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
    keyword: str = Field(description="Target keyword for technical backlink acquisition opportunity research")
    website_id: str = Field(description="Website ID for context")


class ProspectResearchTool(BaseTool):
    name: str = "prospect_research"
    description: str = "Discovers high-DR resource hubs, data citation targets, and competitor link gaps for technical asset engineering"
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
            prompt = f"""You are an expert technical backlink authority researcher. Find high-quality backlink asset targets for "{keyword}" targeting domain "{domain}".

            Find 10 relevant linking targets in these categories:
            1. Resource pages (pages curating useful external guides & tools)
            2. Statistics citation pages (pages citing industry research & data points)
            3. Industry glossaries & directories (authoritative niche indexes)
            4. Interactive tool & calculator hubs
            5. Competitor backlink gaps (pages linking to multiple competitor domains)

            For each prospect, provide:
            - name: Website name
            - url: Full URL
            - type: resource_page, statistics_citation, directory, tool_hub, or competitor_gap
            - domain_authority: Estimated DA (1-100)
            - relevance_score: 1-10 how relevant to keyword
            - placement_context: Specific section of page where a linkable asset naturally fits

            Return JSON array format:
            [
              {{
                "name": "Legal Resource Hub",
                "url": "https://example.com/legal-resources",
                "type": "resource_page",
                "domain_authority": 52,
                "relevance_score": 9,
                "placement_context": "Recommended Statutory Reference & Calculator section"
              }}
            ]

            Only include real, relevant targets. Provide valid JSON only."""

            result = call_nim_llm(prompt, "You are a professional link acquisition researcher. Provide only valid JSON.")
            _log_proof(website_id, self._agent_name, "prospect_research", "nim", f"research:{keyword}")

            # Parse JSON safely
            match = re.search(r'\[.*\]', result, re.DOTALL)
            json_str = match.group(0) if match else result
            prospects = json.loads(json_str)

            saved = 0
            for prospect in prospects:
                try:
                    get_supabase().table("backlink_opportunities").insert({
                        "website_id": website_id,
                        "url": prospect.get("url", ""),
                        "domain_rating": prospect.get("domain_authority", 40),
                        "opportunity_type": prospect.get("type", "resource_page"),
                        "topic_relevance_score": float(prospect.get("relevance_score", 8)) / 10.0,
                        "placement_context": prospect.get("placement_context", ""),
                        "acquisition_difficulty": "medium",
                        "priority_score": prospect.get("domain_authority", 40) * (float(prospect.get("relevance_score", 8)) / 10.0),
                        "status": "discovered",
                    }).execute()
                    saved += 1
                except Exception as e:
                    logger.debug("Failed saving backlink opportunity: %s", e)

            return f"Found and saved {saved} backlink asset targets for '{keyword}'."
        except Exception as e:
            logger.error("Prospect research failed: %s", e)
            _log_proof(website_id, self._agent_name, "prospect_research", "error", str(e))
            return f"# Error: {str(e)[:200]}"
