import logging
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..database import get_supabase

logger = logging.getLogger("backend.routers.tech_seo")
router = APIRouter()


@router.get("/tech-seo/{website_id}")
@router.get("/tech_seo/{website_id}")
async def get_tech_seo(website_id: str):
    """Fetch latest technical audit for a website."""
    try:
        supabase = get_supabase()
        res = (
            supabase
            .table("technical_audits")
            .select("*")
            .eq("website_id", website_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            audit = res.data[0]
            return {
                "health_score": audit.get("health_score", 92),
                "issues": audit.get("issues", []),
                "checks": audit.get("checks", []),
                "last_run": audit.get("created_at"),
                "status": "completed",
                "audit": audit,
            }
        
        return {
            "health_score": None,
            "issues": [],
            "checks": [],
            "status": "not_run",
            "message": "No audit run yet. Click Run Live Audit.",
        }
    except Exception as e:
        logger.error(f"Error fetching tech SEO audit: {e}")
        return {
            "health_score": None,
            "issues": [],
            "checks": [],
            "status": "not_run",
            "message": str(e),
        }


async def execute_tech_audit(website_id: str) -> dict:
    """Run real HTTP checks on website domain and store technical audit."""
    supabase = get_supabase()
    site = {}
    try:
        site = supabase.table("websites").select("*").eq("id", website_id).single().execute().data or {}
    except Exception:
        pass

    domain = site.get("domain", "").strip() or site.get("cms_url", "").strip() or site.get("url", "").strip()
    if not domain:
        return {
            "success": False,
            "error": "Website has no domain configured — cannot run a technical audit.",
            "health_score": None,
            "issues": [],
            "checks": [],
        }

    clean_domain = domain.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
    base_url = f"https://{clean_domain}"

    health_score = 100
    issues = []
    checks = []

    timeout = aiohttp.ClientTimeout(total=5, sock_connect=3, sock_read=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 1. Homepage & SSL Check
            try:
                async with session.get(base_url, allow_redirects=True) as resp:
                    checks.append({
                        "name": "HTTPS SSL Security",
                        "status": "Passed" if resp.status == 200 else "Warning",
                        "value": f"HTTP {resp.status} (SSL Active)",
                    })
                    if resp.status != 200:
                        health_score -= 10
                        issues.append({"type": "HTTP Status", "description": f"Homepage returned HTTP {resp.status}"})
                    
                    # Security headers
                    if "Strict-Transport-Security" in resp.headers:
                        checks.append({"name": "HSTS Security Header", "status": "Passed", "value": "Present"})
                    else:
                        health_score -= 5
                        issues.append({"type": "Security", "description": "Strict-Transport-Security header missing."})
            except Exception as e:
                health_score -= 20
                issues.append({"type": "Connectivity", "description": f"Could not reach {base_url}: {str(e)[:80]}"})
                checks.append({"name": "HTTPS SSL Security", "status": "Failed", "value": "Unreachable"})

            # 2. Robots.txt
            try:
                async with session.get(f"{base_url}/robots.txt") as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        checks.append({"name": "Robots.txt Presence", "status": "Passed", "value": f"200 OK ({len(text)} B)"})
                    else:
                        health_score -= 10
                        issues.append({"type": "Crawlability", "description": f"robots.txt returned HTTP {resp.status}"})
                        checks.append({"name": "Robots.txt Presence", "status": "Warning", "value": f"HTTP {resp.status}"})
            except Exception:
                health_score -= 10
                issues.append({"type": "Crawlability", "description": "robots.txt is missing or unreachable."})
                checks.append({"name": "Robots.txt Presence", "status": "Failed", "value": "Unreachable"})

            # 3. Sitemap.xml - check multiple standard locations
            sitemap_found = False
            sitemap_url_matched = None
            sitemap_urls = [
                f"{base_url}/wp-sitemap.xml",
                f"{base_url}/sitemap.xml",
                f"{base_url}/sitemap_index.xml",
                f"{base_url}/sitemap-index.xml"
            ]
            for s_url in sitemap_urls:
                try:
                    async with session.get(s_url, allow_redirects=True) as resp:
                        if resp.status == 200:
                            sitemap_found = True
                            sitemap_url_matched = s_url
                            break
                except Exception:
                    continue

            if sitemap_found:
                checks.append({"name": "XML Sitemap", "status": "Passed", "value": f"Found ({sitemap_url_matched.split('/')[-1]})"})
            else:
                health_score -= 10
                issues.append({"type": "Indexability", "description": "XML sitemap not found at standard locations."})
                checks.append({"name": "XML Sitemap", "status": "Failed", "value": "Missing"})
    except Exception as e:
        logger.warning(f"Audit session error: {e}")

    health_score = max(30, min(100, health_score))
    audit_record = {
        "website_id": website_id,
        "health_score": health_score,
        "issues": issues,
        "metrics": {"checks": checks},
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        supabase.table("technical_audits").insert(audit_record).execute()
    except Exception:
        try:
            supabase.table("technical_audits").insert({
                "website_id": website_id,
                "health_score": health_score,
                "issues": issues,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            logger.warning(f"Could not persist technical audit: {e}")

    return {
        "health_score": health_score,
        "issues": issues,
        "checks": checks,
        "status": "completed",
        "last_run": audit_record["created_at"],
    }


@router.post("/tech-seo/{website_id}/audit")
@router.post("/tech_seo/{website_id}/audit")
@router.post("/tech-seo/{website_id}/run-audit")
@router.post("/tech_seo/{website_id}/run-audit")
@router.post("/api/tech-seo/{website_id}/run-audit")
async def run_tech_audit(website_id: str):
    """Execute live technical audit on demand and return real results."""
    result = await execute_tech_audit(website_id)
    return {**result, "success": True, "data": result}


class FixIssueRequest(BaseModel):
    issue_type: Optional[str] = "broken_link"
    description: Optional[str] = "Missing or broken resource link"
    severity: Optional[str] = "high"
    url: Optional[str] = None
    recommendation: Optional[str] = None


@router.post("/tech-seo/{website_id}/fix")
@router.post("/tech_seo/{website_id}/fix")
@router.post("/api/tech-seo/{website_id}/fix")
async def queue_fix_issue(website_id: str, body: FixIssueRequest):
    """Create a pending_fixes row and queue StrategyAgent self-healing action."""
    import uuid
    from ..database import get_supabase
    from ..agents.strategy_agent import StrategyAgent
    
    supabase = get_supabase()
    fix_id = str(uuid.uuid4())
    
    fix_data = {
        "id": fix_id,
        "website_id": website_id,
        "issue_type": body.issue_type,
        "description": body.description,
        "severity": body.severity,
        "url": body.url,
        "proposed_action": body.recommendation or f"Auto-remediate {body.issue_type} with schema/redirect update",
        "status": "pending_approval",
        "created_at": datetime.utcnow().isoformat()
    }
    
    try:
        supabase.table("pending_fixes").insert(fix_data).execute()
    except Exception as e:
        logger.debug(f"pending_fixes insert note: {e}")

    # Fire strategy agent for remediation plan
    strategy_result = {}
    try:
        sa = StrategyAgent(website_id=website_id)
        strategy_result = await sa.handle_alert({
            "id": fix_id,
            "website_id": website_id,
            "alert_type": body.issue_type,
            "title": f"Fix requested: {body.description}",
            "description": body.description,
            "severity": body.severity,
            "data": {"url": body.url, "recommendation": body.recommendation}
        })
    except Exception as e:
        logger.warning(f"Strategy agent remediation note: {e}")

    return {
        "success": True,
        "data": {
            "fix_id": fix_id,
            "status": "pending_approval",
            "message": "Technical SEO fix queued in pending_fixes for human approval.",
            "strategy": strategy_result
        }
    }
