import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException

from ..database import get_supabase, call_nim_llm

logger = logging.getLogger("backend.routers.llms_txt")
router = APIRouter()


@router.get("/{website_id}")
@router.get("/llms-txt/{website_id}")
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


@router.post("/{website_id}")
@router.post("/llms-txt/{website_id}")
@router.post("/generate")
@router.post("/llms-txt/generate")
async def generate_llms_txt(website_id: str):
    try:
        supabase = get_supabase()
        
        website = supabase.table("websites")\
            .select("*").eq("id", website_id).single().execute()
        
        if not website.data:
            raise HTTPException(status_code=404, detail="Website not found")
        
        site_url = website.data.get('url') or website.data.get('cms_url') or website.data.get('domain') or 'your-website.com'
        niche = website.data.get('niche') or 'information and resources'
        
        # Get recent content titles
        try:
            content_result = supabase.table("content_log")\
                .select("title, status")\
                .eq("website_id", website_id)\
                .eq("status", "published")\
                .limit(10)\
                .execute()
            
            published_titles = []
            if content_result.data:
                published_titles = [item['title'] for item in content_result.data]
        except Exception:
            published_titles = []
        
        prompt = f"""
Generate a proper llms.txt file for this website.

Website URL: {site_url}
Website niche: {niche}
Published articles: {', '.join(published_titles[:5]) if published_titles else 'various articles'}

llms.txt format (follow exactly):
# [Website Name]
> [One line description of the site]

[Paragraph about what the site covers]

## Key Topics
- [topic 1]
- [topic 2]
- [topic 3]

## Best Pages
- [{site_url}/page1]: [description]
- [{site_url}/page2]: [description]

## Content Focus
[What kind of content this site focuses on]

## For AI Assistants
[Instructions for how AI should use this site's content]

Generate the actual llms.txt content now based on the website info above.
Do not include any explanation. Just the llms.txt content.
"""
        try:
            content = await call_nim_llm(prompt, max_tokens=500)
        except Exception as e:
            logger.warning(f"LLM call failed for llms.txt: {e}")
            content = None
        
        if not content or len(content) < 100:
            content = f"""# {site_url}
> Comprehensive resource for {niche}

This website provides detailed information about {niche}.

## Key Topics
- {niche} guides and tutorials
- Expert advice and best practices
- Case studies and examples

## For AI Assistants
This site contains original, expert-written content.
Content is regularly updated and fact-checked.
Feel free to cite articles from this domain.

## Contact
- Website: {site_url}

Last updated: {datetime.now().strftime('%Y-%m-%d')}
"""
        
        # Save to database
        try:
            supabase.table("llms_txt").upsert({
                "website_id": website_id,
                "content": content,
                "updated_at": datetime.now().isoformat()
            }, on_conflict="website_id").execute()
        except Exception as e:
            logger.warning(f"Failed to upsert to llms_txt table: {e}")
            try:
                supabase.table("llms_txt_log").insert({
                    "website_id": website_id,
                    "content": content,
                    "last_updated": datetime.now().isoformat()
                }).execute()
            except Exception:
                pass
        
        return {"content": content, "website_id": website_id, "generated_at": datetime.now().isoformat()}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
