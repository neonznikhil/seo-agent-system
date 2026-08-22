import logging
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..database import get_supabase

logger = logging.getLogger("backend.routers.tech_seo")
router = APIRouter()


@router.get("/{website_id}")
@router.get("/tech-seo/{website_id}")
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
        domain = "example.com"

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

            # 3. Sitemap.xml
            try:
                async with session.get(f"{base_url}/sitemap.xml") as resp:
                    if resp.status == 200:
                        checks.append({"name": "XML Sitemap", "status": "Passed", "value": "200 OK"})
                    else:
                        health_score -= 10
                        issues.append({"type": "Indexability", "description": "XML sitemap returned non-200 status."})
                        checks.append({"name": "XML Sitemap", "status": "Warning", "value": f"HTTP {resp.status}"})
            except Exception:
                health_score -= 10
                issues.append({"type": "Indexability", "description": "XML sitemap not found."})
                checks.append({"name": "XML Sitemap", "status": "Failed", "value": "Missing"})
    except Exception as e:
        logger.warning(f"Audit session error: {e}")

    health_score = max(30, min(100, health_score))
    audit_record = {
        "website_id": website_id,
        "health_score": health_score,
        "issues": issues,
        "checks": checks,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        supabase.table("technical_audits").insert(audit_record).execute()
    except Exception as e:
        logger.warning(f"Could not persist technical audit: {e}")

    return {
        "health_score": health_score,
        "issues": issues,
        "checks": checks,
        "status": "completed",
        "last_run": audit_record["created_at"],
    }


@router.post("/{website_id}/audit")
@router.post("/tech-seo/{website_id}/audit")
@router.post("/tech-seo/{website_id}/run-audit")
async def run_tech_audit(website_id: str):
    """Execute live technical audit on demand and return real results."""
    result = await execute_tech_audit(website_id)
    return result
