from datetime import datetime
import logging
import re
from typing import Dict, Any, List

logger = logging.getLogger("backend.agents.seo_agent")


class SEOAgent:
    """
    SEOAgent - takes raw HTML and returns optimized SEO metadata:
    - seo_title (<60 chars)
    - meta_description (<160 chars)
    - slug
    - keyword_density
    - internal_links (>=3)
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, raw_html: str, keyword: str = "", target_links: int = 3) -> Dict[str, Any]:
        from ..database import call_nim_llm, get_supabase

        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = re.sub(r"\s+", " ", text).strip()
        words = text.split()
        keyword_lower = keyword.lower()
        keyword_count = sum(1 for w in words if keyword_lower in w.lower())
        density = round((keyword_count / len(words)) * 100, 2) if words else 0.0

        title_prompt = (
            f"Write an SEO title (max 58 chars) for keyword '{keyword}'. "
            "Return ONLY the title string, no quotes."
        )
        desc_prompt = (
            f"Write a meta description (max 155 chars) for keyword '{keyword}'. "
            "Return ONLY the description string, no quotes."
        )
        slug_prompt = (
            f"Generate a URL slug for keyword '{keyword}'. "
            "Return ONLY the slug string (lowercase, hyphens, no quotes)."
        )
        link_prompt = (
            f"Generate {target_links} internal link suggestions for a blog about '{keyword}'. "
            "Return ONLY a JSON array of strings, e.g. [\"/guide\",\"/tips\"]. No quotes around the output."
        )

        try:
            seo_title = await call_nim_llm(title_prompt, website_id=self.website_id)
            seo_title = seo_title.strip().strip('\"').strip("'")
            if len(seo_title) > 60:
                seo_title = seo_title[:57] + "..."
        except Exception:
            seo_title = f"{keyword.title()} - Complete Guide"

        try:
            meta_desc = await call_nim_llm(desc_prompt, website_id=self.website_id)
            meta_desc = meta_desc.strip().strip('\"').strip("'")
            if len(meta_desc) > 160:
                meta_desc = meta_desc[:157] + "..."
        except Exception:
            meta_desc = f"Learn everything about {keyword}. Expert insights, best practices, and actionable tips."

        try:
            slug_raw = await call_nim_llm(slug_prompt, website_id=self.website_id)
            slug = slug_raw.strip().strip('\"').strip("'").lower().replace(" ", "-")
            slug = re.sub(r"[^a-z0-9-]", "", slug)
            slug = re.sub(r"-+", "-", slug).strip("-") or keyword.lower().replace(" ", "-")
        except Exception:
            slug = keyword.lower().replace(" ", "-")

        try:
            links_raw = await call_nim_llm(link_prompt, website_id=self.website_id)
            internal_links = self._parse_json_array(links_raw, target_links, keyword)
        except Exception:
            internal_links = [f"/{keyword.replace(' ', '-')}-guide", f"/{keyword.replace(' ', '-')}-tips", f"/{keyword.replace(' ', '-')}-examples"]

        result = {
            "seo_title": seo_title,
            "meta_description": meta_desc,
            "slug": slug,
            "keyword_density": density,
            "internal_links": internal_links,
        }

        try:
            get_supabase().table("seo_meta").insert({
                "website_id": self.website_id,
                "keyword": keyword,
                "seo_title": seo_title,
                "meta_description": meta_desc,
                "slug": slug,
                "keyword_density": density,
            }).execute()
        except Exception:
            pass

        return result

    def _parse_json_array(self, raw: str, expected: int, keyword: str) -> List[str]:
        import json, re
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data[:expected]]
        except Exception:
            pass
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return [str(x) for x in data[:expected]]
            except Exception:
                pass
        return [f"/{keyword.replace(' ', '-')}-guide", f"/{keyword.replace(' ', '-')}-tips", f"/{keyword.replace(' ', '-')}-examples"]


def create_seo_agent(website_id: str) -> SEOAgent:
    return SEOAgent(website_id)
