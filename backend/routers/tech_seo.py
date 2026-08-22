import logging
import aiohttp
from datetime import datetime
from fastapi import APIRouter

from ..database import get_supabase

logger = logging.getLogger("backend.routers.tech_seo")
router = APIRouter()


@router.get("/tech-seo/{website_id}")
async def get_tech_seo(website_id: str):
    res = (
        get_supabase()
        .table("technical_audits")
        .select("*")
        .eq("website_id", website_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return {"health_score": None, "issues": [], "audit": None}
    audit = res.data[0]
    issues = audit.get("issues", []) or []
    health_score = audit.get("health_score")
    return {
        "health_score": health_score,
        "issues": issues,
        "audit": audit,
    }


@router.post("/tech-seo/{website_id}/run-audit")
async def run_tech_seo_audit(website_id: str):
    supabase = get_supabase()
    
    # Retrieve website domain
    site = supabase.table("websites").select("*").eq("id", website_id).single().execute().data or {}
    domain = site.get("domain", "").strip()
    if not domain:
        domain = "example.com"
    
    clean_domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    base_url = f"https://{clean_domain}"
    
    health_score = 100.0
    issues = []
    checks = []
    
    sitemap_status = "missing"
    robots_status = "missing"
    ssl_grade = "Unknown"
    
    timeout = aiohttp.ClientTimeout(total=4, sock_connect=2, sock_read=2)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 1. Check Homepage & HTTPS
        try:
            async with session.get(base_url, allow_redirects=True) as resp:
                ssl_grade = "A+" if str(resp.url).startswith("https://") else "B"
                checks.append({"name": "HTTPS SSL Verification", "status": "Passed", "value": f"Status {resp.status} (SSL Active)"})
                
                # Check security headers
                headers = resp.headers
                if "Strict-Transport-Security" in headers:
                    checks.append({"name": "HSTS Security Header", "status": "Passed", "value": "Present"})
                else:
                    score -= 5
                    issues.append({"type": "info", "message": "Strict-Transport-Security header not configured."})
        except Exception as e:
            ssl_grade = "F"
            score -= 25
            issues.append({"type": "error", "message": f"Could not reach {base_url} over HTTPS: {str(e)[:100]}"})
            checks.append({"name": "HTTPS SSL Verification", "status": "Failed", "value": "Connection Failed"})

        # 2. Check Robots.txt
        try:
            async with session.get(f"{base_url}/robots.txt") as resp:
                if resp.status == 200:
                    robots_status = "ok"
                    text = await resp.text()
                    checks.append({"name": "Robots.txt Configuration", "status": "Passed", "value": f"200 OK ({len(text)} bytes)"})
                else:
                    score -= 15
                    robots_status = "missing"
                    issues.append({"type": "warning", "message": f"robots.txt returned HTTP {resp.status}"})
                    checks.append({"name": "Robots.txt Configuration", "status": "Warning", "value": f"HTTP {resp.status}"})
        except Exception:
            score -= 15
            robots_status = "missing"
            issues.append({"type": "warning", "message": "robots.txt not found or unreachable"})
            checks.append({"name": "Robots.txt Configuration", "status": "Failed", "value": "Unreachable"})

        # 3. Check Sitemap.xml
        try:
            async with session.get(f"{base_url}/sitemap.xml") as resp:
                if resp.status == 200:
                    sitemap_status = "ok"
                    checks.append({"name": "Sitemap.xml Presence", "status": "Passed", "value": "200 OK"})
                else:
                    score -= 15
                    sitemap_status = "missing"
                    issues.append({"type": "warning", "message": f"sitemap.xml returned HTTP {resp.status}"})
                    checks.append({"name": "Sitemap.xml Presence", "status": "Warning", "value": f"HTTP {resp.status}"})
        except Exception:
            score -= 15
            sitemap_status = "missing"
            issues.append({"type": "warning", "message": "sitemap.xml not found or unreachable"})
            checks.append({"name": "Sitemap.xml Presence", "status": "Failed", "value": "Unreachable"})

    health_score = max(0, min(100, score))
    
    audit_record = {
        "website_id": website_id,
        "health_score": float(health_score),
        "sitemap_status": sitemap_status,
        "robots_status": robots_status,
        "ssl_grade": ssl_grade,
        "issues": issues,
        "created_at": datetime.utcnow().isoformat()
    }
    
    try:
        res = supabase.table("technical_audits").insert(audit_record).execute()
        return {"status": "completed", "health_score": health_score, "audit": res.data[0] if res.data else audit_record, "checks": checks}
    except Exception as e:
        logger.error(f"Audit insert failed: {e}")
        return {"status": "completed", "health_score": health_score, "audit": audit_record, "checks": checks}


