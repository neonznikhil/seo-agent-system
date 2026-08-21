import logging

from .tools.crawlee_tool import CrawleeTool
from ..database import get_supabase, call_nim_llm

logger = logging.getLogger("backend.agents.tech_seo_agent")


def run_tech_seo_agent(website_id: str, base_url: str) -> dict:
    crawlee = CrawleeTool()
    crawlee.set_website_id(website_id)
    crawlee.set_agent_name("tech_seo")

    checks = {
        "sitemap": "unknown",
        "robots": "unknown",
        "canonical": "unknown",
        "broken_links_404": [],
        "redirect_chains": [],
        "schema": "unknown",
        "indexability": "unknown",
    }

    try:
        sitemap_content = crawlee._run(f"{base_url.rstrip('/')}/sitemap.xml")
        checks["sitemap"] = "found" if sitemap_content and not sitemap_content.startswith("# Mock") else "missing"
    except Exception as e:
        checks["sitemap"] = f"error: {e}"

    try:
        robots_content = crawlee._run(f"{base_url.rstrip('/')}/robots.txt")
        checks["robots"] = "found" if robots_content and not robots_content.startswith("# Mock") else "missing"
        if "noindex" in robots_content.lower():
            checks["indexability"] = "noindex_found"
        else:
            checks["indexability"] = "ok"
    except Exception as e:
        checks["robots"] = f"error: {e}"
        checks["indexability"] = "error"

    try:
        homepage = crawlee._run(base_url)
        if homepage and "canonical" in homepage.lower():
            checks["canonical"] = "found"
        else:
            checks["canonical"] = "missing"
    except Exception as e:
        checks["canonical"] = f"error: {e}"

    try:
        schema_check_prompt = f"Check the following HTML for schema markup errors:\n\n{crawlee._run(base_url)[:3000]}"
        schema_res = call_nim_llm(schema_check_prompt, "You are a schema validator. Return PASS or FAIL with reason.", website_id=website_id)
        checks["schema"] = "pass" if "PASS" in schema_res.upper() else "fail"
    except Exception as e:
        checks["schema"] = f"error: {e}"

    issues = []
    for k, v in checks.items():
        if k in ("broken_links_404", "redirect_chains"):
            continue
        if v == "missing" or str(v).startswith("error") or v == "fail":
            issues.append(f"{k}: {v}")

    score = max(0.0, 100.0 - len(issues) * 15.0)

    audit = {
        "website_id": website_id,
        "checks": checks,
        "score": score,
        "issues": issues[:20],
        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
    res = get_supabase().table("technical_audits").insert(audit).execute()
    logger.info("Tech SEO audit saved for %s: score=%s issues=%d", website_id, score, len(issues))
    return res.data[0] if res.data else audit
