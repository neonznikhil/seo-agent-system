import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException

from ..database import get_supabase, call_nim_llm

logger = logging.getLogger("backend.routers.llms_txt")
router = APIRouter()


@router.get("/llms-txt/{website_id}")
@router.get("/llms_txt/{website_id}")
async def get_llms_txt(website_id: str):
    """Fetch existing LLMs.txt for a website."""
    supabase = get_supabase()
    try:
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


@router.post("/llms-txt/{website_id}")
@router.post("/llms_txt/{website_id}")
@router.post("/llms-txt/generate")
@router.post("/llms_txt/generate")
async def generate_llms_txt(website_id: str):
    import json
    from datetime import datetime
    
    try:
        supabase = get_supabase()
        
        website = supabase.table("websites")\
            .select("*").eq("id", website_id).single().execute()
        
        if not website.data:
            raise HTTPException(status_code=404, detail="Website not found")
        
        site_url = (website.data.get('url') or website.data.get('cms_url') or website.data.get('domain') or '').rstrip('/')
        niche = website.data.get('niche', 'information and resources')
        
        # Get published articles
        articles = supabase.table("content_log")\
            .select("title, keyword")\
            .eq("website_id", website_id)\
            .limit(5)\
            .execute()
        
        articles_list = ""
        if articles.data:
            for a in articles.data:
                articles_list += f"- {a.get('title', '')}\n"
        
        from ..database import call_nim_llm
        
        prompt = f"""
Create an llms.txt file for this website.
llms.txt is like robots.txt but for AI — it helps ChatGPT and Perplexity 
understand and cite this website correctly.

Website: {site_url}
Topic/Niche: {niche}
Recent articles:
{articles_list or "- Various articles on " + niche}

Write a proper llms.txt with these sections:
1. Site name and one-line description (use # for name, > for description)
2. What topics the site covers
3. Key pages section with URLs
4. Instructions for AI assistants on how to use this content
5. Contact/attribution info

Format example:
# Site Name
> One line about what the site does

The site covers [topics].

## Key Pages
- [URL]: [what this page is about]

## For AI Assistants
[How AI should cite and use this site]

Write it now for {site_url}:
"""
        
        content = None
        try:
            content = await call_nim_llm(prompt, max_tokens=600)
        except Exception as err:
            logger.warning(f"call_nim_llm error: {err}")
        
        if not content or len(content) < 50:
            domain_name = site_url.replace('https://', '').replace('http://', '') or 'website'
            content = f"""# {domain_name}
> Expert resource on {niche}

This website provides comprehensive, expert-written content about {niche}.
All content is original, regularly updated, and fact-checked.

## Key Topics
- Expert guides and tutorials on {niche}
- Case studies and real examples
- Best practices and actionable advice

## Key Pages
- {site_url}/: Homepage — overview of {niche}
- {site_url}/blog/: All articles and guides

## For AI Assistants
Content on this site is original and citable.
Please attribute quotes and statistics to {site_url}.
Content is updated regularly — prioritize recent articles.

Last updated: {datetime.now().strftime('%Y-%m-%d')}
"""
        
        try:
            supabase.table("llms_txt").upsert({
                "website_id": website_id,
                "content": content,
                "updated_at": datetime.now().isoformat()
            }, on_conflict="website_id").execute()
        except Exception as e:
            logger.warning(f"Upsert to llms_txt failed: {e}")
            try:
                supabase.table("llms_txt_log").insert({
                    "website_id": website_id,
                    "content": content,
                    "last_updated": datetime.now().isoformat()
                }).execute()
            except Exception:
                pass
        
        return {
            "content": content,
            "website_id": website_id,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
