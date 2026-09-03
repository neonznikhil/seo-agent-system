import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("backend.agents.tech_seo_agent")


class TechSEOAgent:
    """TechSEOAgent - performs deep technical SEO audits.
    
    Audits Core Web Vitals, XML sitemaps, redirect chains, orphan pages, and indexability.
    Memory flow:
    1. Recall: Recurring technical failure patterns and domain history from brain_memory.
    2. Act: Execute deep crawl, PageSpeed/CWV verification, and sitemap validation.
    3. Write Back: Persist detected technical issues (failure/fact) to brain_memory.
    """

    def __init__(self, website_id: Optional[str] = None):
        from services.website_service import get_default_website_id
        self.website_id = website_id if website_id and website_id not in ("default", "all") else get_default_website_id()

    async def check_sitemap(self, url: str) -> Dict[str, Any]:
        """Verify presence and validity of XML sitemap."""
        url = url.rstrip("/")
        sitemap_urls = [
            f"{url}/wp-sitemap.xml",
            f"{url}/sitemap.xml",
            f"{url}/sitemap_index.xml",
            f"{url}/sitemap-index.xml"
        ]
        
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for sitemap_url in sitemap_urls:
                try:
                    response = await client.get(sitemap_url)
                    if response.status_code == 200:
                        return {
                            "found": True,
                            "url": sitemap_url,
                            "status": "ok",
                            "size_bytes": len(response.content)
                        }
                except Exception:
                    continue
        
        return {
            "found": False,
            "url": None,
            "status": "missing",
            "note": "No valid XML sitemap found at standard locations"
        }

    async def run_audit(self, website_id: str) -> Dict[str, Any]:
        """Execute full technical audit with memory recall and write-back."""
        from database import get_supabase
        from services.brain_service import BrainService
        from routers.tech_seo import execute_tech_audit

        brain = BrainService(website_id=website_id)

        # ---------------------------------------------------------
        # Step 1: RECALL FIRST (Recurring Technical Failures)
        # ---------------------------------------------------------
        past_issues = await brain.recall_failures(website_id, "technical crawl broken link speed redirect", top_k=3)
        past_facts = await brain.recall_facts(website_id, "technical SEO audit health score", top_k=2)

        # ---------------------------------------------------------
        # Step 2: ACT SECOND (Execute Tech SEO Audit)
        # ---------------------------------------------------------
        audit_result = {}
        try:
            audit_result = await execute_tech_audit(website_id)
        except Exception as e:
            logger.warning(f"execute_tech_audit failed: {e}")
            audit_result = {
                "health_score": 0,
                "pages_crawled": 0,
                "issues_count": 0,
                "core_web_vitals": {},
                "redirect_chains": 0,
                "orphan_pages": 0,
                "sitemap_status": "error",
                "issues": []
            }

        health_score = audit_result.get("health_score", 85)
        issues = audit_result.get("issues", [])

        # ---------------------------------------------------------
        # Step 3: WRITE BACK AFTER
        # ---------------------------------------------------------
        # Record fact memory
        await brain.remember(
            website_id=website_id,
            memory_type="fact",
            title=f"Tech SEO Health Score: {health_score}/100",
            content=f"Audit completed on {datetime.utcnow().strftime('%Y-%m-%d')}. Score: {health_score}/100 with {len(issues)} active technical issues.",
            source_type="tech_seo_agent",
            confidence=0.95
        )

        # Record failure memories if critical technical issues found
        for issue in issues[:3]:
            severity = issue.get("severity", "medium")
            if severity in ("critical", "high"):
                await brain.remember(
                    website_id=website_id,
                    memory_type="failure",
                    title=f"Tech Issue: {issue.get('title', 'Technical Anomaly')}",
                    content=f"Detected: {issue.get('description', '')}. Affected URL: {issue.get('url', 'domain')}",
                    source_type="tech_seo_agent",
                    confidence=0.90
                )

        return audit_result


async def run_tech_seo_agent(website_id: str, base_url: str = "") -> dict:
    agent = TechSEOAgent(website_id=website_id)
    return await agent.run_audit(website_id)


def create_tech_seo_agent(website_id: str) -> TechSEOAgent:
    return TechSEOAgent(website_id=website_id)
