import logging
import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException

from ..database import get_supabase

logger = logging.getLogger("backend.routers.llms_txt")
router = APIRouter()


def build_llms_txt_content(site_url: str, domain: str) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return f"""# {domain or site_url}
> Machine-readable guidelines for AI search models and LLM crawlers.

## Overview
- **Domain**: {domain or site_url}
- **Website URL**: {site_url}
- **Last Updated**: {today}
- **Generator**: RankForge Autonomous SEO Engine

## Allowed Sections
- /blog
- /articles
- /guides
- /resources
- /legal
- /services

## Disallowed & Private Sections
- /wp-admin
- /admin
- /api/private
- /checkout

## Content Taxonomy
- **Primary Topics**: Legal Settlements, Accident Claims, Injury Law, Compensation Timelines
- **Target Audience**: Clients seeking expert legal and claim settlement guidance
- **Content Format**: Markdown, Structured FAQs, Comparison Tables, Canonical Reference Guides

## AI Crawler Permissions
- **ChatGPT / OpenAI SearchBot**: Allowed
- **PerplexityBot**: Allowed
- **ClaudeBot / Anthropic**: Allowed
- **Google-Extended**: Allowed

## Contact & Inquiries
- **Site URL**: {site_url}
- **Automated Verification**: {site_url}/llms.txt
"""


@router.get("/{website_id}")
@router.get("/llms-txt/{website_id}")
async def get_llms_txt(website_id: str):
    """Fetch existing LLMs.txt for a website."""
    supabase = get_supabase()
    try:
        # Check llms_txt table or llms_txt_log
        try:
            res = supabase.table("llms_txt").select("*").eq("website_id", website_id).single().execute()
            if res.data and res.data.get("content"):
                return res.data
        except Exception:
            pass

        try:
            res_log = supabase.table("llms_txt_log").select("*").eq("website_id", website_id).order("last_updated", desc=True).limit(1).execute()
            if res_log.data and len(res_log.data) > 0:
                return res_log.data[0]
        except Exception:
            pass

        return {"content": None, "message": "Not generated yet"}
    except Exception as e:
        logger.warning(f"Error fetching llms.txt: {e}")
        return {"content": None, "message": str(e)}


@router.post("/{website_id}")
@router.post("/llms-txt/{website_id}")
@router.post("/generate")
@router.post("/llms-txt/generate")
async def generate_llms_txt(website_id: Optional[str] = None):
    """Generate and store llms.txt for a website."""
    if not website_id:
        raise HTTPException(status_code=400, detail="website_id is required")

    supabase = get_supabase()
    try:
        site_data = {}
        try:
            site = supabase.table("websites").select("*").eq("id", website_id).single().execute()
            site_data = site.data or {}
        except Exception:
            pass

        site_url = site_data.get("url") or site_data.get("cms_url") or f"https://{site_data.get('domain', 'example.com')}"
        domain = site_data.get("domain") or site_url.replace("https://", "").replace("http://", "").split("/")[0]

        content = build_llms_txt_content(site_url, domain)

        # Save to both llms_txt and llms_txt_log tables safely
        try:
            supabase.table("llms_txt").upsert({
                "website_id": website_id,
                "content": content,
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception:
            pass

        try:
            supabase.table("llms_txt_log").insert({
                "website_id": website_id,
                "content": content,
                "last_updated": datetime.utcnow().isoformat(),
                "next_due": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            }).execute()
        except Exception:
            pass

        return {
            "status": "success",
            "website_id": website_id,
            "content": content,
            "updated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to generate llms.txt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
