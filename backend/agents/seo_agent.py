from datetime import datetime
import logging
import re
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger("backend.agents.seo_agent")


class SEOAgent:
    """SEOAgent - takes raw content and returns optimized SEO metadata.
    
    Memory flow:
    1. Recall: Meta patterns that previously passed the quality gate from brain_memory.
    2. Act: Generate SEO title (<60 chars), meta description (<160 chars), slug, density, and internal links.
    3. Write Back: Persist successful meta configurations to brain_memory.
    """

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, raw_html: str, keyword: str = "", target_links: int = 3) -> Dict[str, Any]:
        from ..database import call_nim_llm, get_supabase
        from ..services.brain_service import BrainService

        brain = BrainService(website_id=self.website_id)

        # ---------------------------------------------------------
        # Step 1: RECALL FIRST (Quality Gate Passing Meta Patterns)
        # ---------------------------------------------------------
        meta_prefs = await brain.recall_preferences(self.website_id, "meta title description quality gate pattern", top_k=2)
        past_experiences = await brain.recall_experiences(self.website_id, f"meta optimization {keyword}", top_k=2)

        meta_guidance = (
            meta_prefs[0].get("content", "")
            if meta_prefs
            else "Ensure keyword is at beginning of title (<58 chars) and action-driven meta description (<155 chars)."
        )

        # Content stats
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = re.sub(r"\s+", " ", text).strip()
        words = text.split()
        keyword_lower = keyword.lower()
        keyword_count = sum(1 for w in words if keyword_lower in w.lower())
        density = round((keyword_count / max(1, len(words))) * 100, 2) if words else 0.0

        # ---------------------------------------------------------
        # Step 2: ACT SECOND (Metadata Generation with NIM LLM)
        # ---------------------------------------------------------
        prompt = (
            f"You are an Elite Technical SEO Specialist. Generate optimized metadata for '{keyword}'.\n\n"
            f"RECALLED BEST PRACTICES:\n{meta_guidance}\n\n"
            "Return ONLY a JSON object with keys:\n"
            "- seo_title (compelling title under 58 characters with primary keyword)\n"
            "- meta_description (action-driven summary under 155 characters with clear CTA)\n"
            "- slug (lowercase hyphenated URL slug, no symbols)\n"
            "- internal_links (array of 3 suggested relative path links)\n"
            "- schema_types (array of recommended schema types e.g. ['Article', 'FAQPage'])\n"
            "Example: {\"seo_title\":\"...\", \"meta_description\":\"...\", \"slug\":\"...\", \"internal_links\":[\"/link1\", \"/link2\"], \"schema_types\":[\"Article\"]}"
        )

        try:
            raw = await call_nim_llm(prompt, system="You are an SEO metadata optimizer. Return ONLY valid JSON.", website_id=self.website_id)
            data = self._parse_json(raw)
        except Exception as e:
            logger.warning(f"SEO metadata NIM generation error: {e}")
            data = {}

        # Fallback normalizations
        seo_title = (data.get("seo_title") or f"{keyword.title()} - Complete 2026 Guide").strip()
        if len(seo_title) > 60:
            seo_title = seo_title[:57] + "..."

        meta_desc = (data.get("meta_description") or f"Learn everything about {keyword}. Expert insights, legal statutory guidelines, and actionable settlement steps.").strip()
        if len(meta_desc) > 160:
            meta_desc = meta_desc[:157] + "..."

        slug = data.get("slug") or keyword.lower().replace(" ", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        slug = re.sub(r"-+", "-", slug).strip("-") or keyword.lower().replace(" ", "-")

        internal_links = data.get("internal_links") or [
            f"/{keyword.replace(' ', '-')}-guide",
            f"/{keyword.replace(' ', '-')}-statutes",
            f"/{keyword.replace(' ', '-')}-faq"
        ]

        result = {
            "seo_title": seo_title,
            "meta_description": meta_desc,
            "slug": slug,
            "keyword_density": density,
            "internal_links": internal_links[:target_links],
            "schema_types": data.get("schema_types", ["Article", "FAQPage"])
        }

        # ---------------------------------------------------------
        # Step 3: WRITE BACK AFTER
        # ---------------------------------------------------------
        try:
            get_supabase().table("seo_meta").insert({
                "website_id": self.website_id,
                "keyword": keyword,
                "seo_title": seo_title,
                "meta_description": meta_desc,
                "slug": slug,
                "keyword_density": density,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception:
            pass

        await brain.remember(
            website_id=self.website_id,
            memory_type="experience",
            title=f"SEO Metadata: {keyword}",
            content=f"Title: '{seo_title}' ({len(seo_title)} chars) | Slug: '{slug}' | Density: {density}%",
            source_type="seo_agent",
            confidence=0.95
        )

        return result

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except Exception:
            pass
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {}


def create_seo_agent(website_id: str) -> SEOAgent:
    return SEOAgent(website_id)
