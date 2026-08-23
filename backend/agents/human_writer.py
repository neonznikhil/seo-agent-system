import logging
from typing import Optional, Dict, List, Any
import json
from datetime import datetime
import asyncio

logger = logging.getLogger("backend.agents.writer_human")


class HumanWriterAgent:
    """
    Professional SEO Content Writer that produces human-quality content.
    No AI tells. No robotic patterns. Pure expert writing style.
    """
    
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.business_info = {}
        self.tone_profile = {}
        self.knowledge_base = []
        self.active_keywords = []
        self.company_name = "Your Business"
        
        self.banned_phrases = [
            "in today's fast-paced world",
            "in today's digital landscape",
            "in conclusion",
            "in summary",
            "delve", "dive into",
            "unlock", "unleash",
            "elevate", "embark",
            "it's important to note",
            "it's worth noting",
            "as we all know",
            "leverage", "utilize",
            "comprehensive guide",
            "plethora", "myriad",
            "cutting-edge", "game-changer"
        ]
        
        self.human_starters = [
            "Here is what actually works",
            "The key insight",
            "What matters most",
            "Your next step",
            "Consider this approach",
            "Based on my experience"
        ]
        
        self.professional_replacements = {
            "utilize": "use",
            "implement": "apply",
            "facilitate": "help",
            "in order to": "to",
            "pursuant to": "according to"
        }
    
    def setup_profile(self) -> Dict[str, Any]:
        """Load website context: business, tone, knowledge, keywords"""
        try:
            from ..database import get_supabase
            
            kb = get_supabase().table("knowledge_base").select("fact").eq("website_id", self.website_id).limit(50).execute().data or []
            self.knowledge_base = [item["fact"] for item in kb]
            
            tone = get_supabase().table("tone_profiles").select("*").eq("website_id", self.website_id).single().execute().data
            if tone:
                self.tone_profile = tone
                self.company_name = tone.get("company_name", "Your Business")
            
            from ..database import get_supabase
            keywords = get_supabase().table("gsc_keywords").select("*").eq("website_id", self.website_id).gte("impressions", 500).order("impressions", desc=True).limit(10).execute().data or []
            self.active_keywords = keywords
            
        except Exception as e:
            logger.warning(f"Setup partial: {e}")
            self.tone_profile = {
                "tone_description": "professional and helpful",
                "example_phrases": ["here's what works", "we built this for customers"],
                "brand_voice": "confident expert"
            }
            self.active_keywords = [{"keyword": "seo", "impressions": 1000}]
        
        return {
            "loaded": len(self.knowledge_base) > 0 or len(self.active_keywords) > 0,
            "company_name": self.company_name,
            "keywords_count": len(self.active_keywords),
            "knowledge_facts": len(self.knowledge_base)
        }
    
    async def write_blog(self, title: str, outline: dict, keywords: list, tone: str = "authoritative and engaging") -> str:
        from ..database import call_nim_llm
        prompt = f"""
        Write a complete 1500-2000 word blog post.
        
        Title: {title}
        Keywords to include naturally: {', '.join(keywords)}
        Tone: {tone}
        Outline: {json.dumps(outline)}
        
        Requirements:
        - Start with a 50-word featured snippet answer
        - Use H2 and H3 headers from the outline
        - Include a data comparison table
        - Add 5 FAQ questions at the end
        - Write naturally, not like AI
        - Include statistics and specific examples
        - Internal link placeholders: [LINK: relevant topic]
        
        Write the complete blog post now:
        """
        return await call_nim_llm(prompt, max_tokens=3000, website_id=self.website_id)
    
    async def generate_blog(self, topic: str, primary_keyword: str, secondary_keywords: List[str] = None) -> Dict[str, Any]:
        """Generate human-quality blog post with real LLM content"""
        from ..database import call_nim_llm
        
        if not secondary_keywords:
            secondary_keywords = []
        
        tone_desc = self.tone_profile.get("tone_description", "authoritative, engaging and SEO-optimized")
        all_keywords = [primary_keyword] + secondary_keywords
        
        outline = {
            "title": topic,
            "h2s": [
                f"Introduction to {primary_keyword}",
                f"Key Strategies for {primary_keyword}",
                "Step-by-Step Implementation Framework",
                "Comparison & Industry Benchmarks",
                "Frequently Asked Questions"
            ]
        }
        
        try:
            content = await self.write_blog(title=topic, outline=outline, keywords=all_keywords, tone=tone_desc)
            humanized_content = self.humanize(content)
            quality_report = self.check_quality(humanized_content, primary_keyword)
            
            return {
                "status": "generated",
                "topic": topic,
                "primary_keyword": primary_keyword,
                "secondary_keywords": secondary_keywords,
                "content": humanized_content,
                "quality_report": quality_report,
                "word_count": len(humanized_content.split()),
            }
        except Exception as e:
            logger.error(f"HumanWriter blog generation error: {e}")
            return {"status": "error", "error": str(e)}
    
    def humanize(self, text: str) -> str:
        """Remove AI patterns from text"""
        result = text
        
        result = result.replace('—', ', ')
        result = result.replace('–', '-')
        
        for pattern in self.banned_phrases[:10]:
            if pattern.lower() in result.lower():
                result = result.replace(pattern, '')
        
        import re
        result = re.sub(r"'([a-zA-Z0-9]{3,20})'", r'\1', result)
        result = re.sub(r'\s{2,}', ' ', result)
        
        return result.strip()
    
    def check_quality(self, text: str, keyword: str) -> Dict[str, Any]:
        """Check if content passes human quality gates"""
        issues = []
        score = 100
        
        if '—' in text:
            score -= 20
            issues.append("Contains em dash —")
        
        banned_found = []
        for phrase in self.banned_phrases:
            if phrase.lower() in text.lower():
                banned_found.append(phrase)
        if banned_found:
            score -= len(banned_found) * 10
            issues.append(f"Banned phrases: {banned_found}")
        
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        avg_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        if avg_len > 30:
            score -= 10
            issues.append(f"Sentences too long: avg {avg_len:.0f} words")
        
        has_kw_title = keyword.lower() in text[:100]
        has_kw_intro = keyword.lower() in text.split('\n\n')[0] if '\n\n' in text else keyword.lower() in text[:300]
        
        if not (has_kw_title or has_kw_intro):
            score -= 15
            issues.append(f"Keyword '{keyword}' missing from title/intro")
        
        fact_matches = 0
        for fact in self.knowledge_base[:5]:
            if fact.lower() in text.lower():
                fact_matches += 1
        if fact_matches < 1:
            score -= 10
            issues.append("No facts from knowledge base included")
        
        human_score = max(score, 0)
        is_human = human_score >= 75
        
        return {
            "human_score": human_score,
            "is_human": is_human,
            "issues": issues,
            "quality": "PASS" if is_human else "REGENERATE",
            "checks": {
                "no_em_dash": "—" not in text,
                "banned_phrases_clear": len(banned_found) == 0,
                "keyword_present": has_kw_title or has_kw_intro,
                "facts_included": fact_matches >= 1,
                "sentence_variation": avg_len < 30
            }
        }


def create_human_writer(website_id: str) -> HumanWriterAgent:
    return HumanWriterAgent(website_id)


HumanWriter = HumanWriterAgent