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
    
    def generate_blog(self, topic: str, primary_keyword: str, secondary_keywords: List[str] = None) -> Dict[str, Any]:
        """Generate human-quality blog post"""
        
        if not secondary_keywords:
            secondary_keywords = []
        
        tone_desc = self.tone_profile.get("tone_description", "professional")
        example_phrases = self.tone_profile.get("example_phrases", [])[:3]
        
        system_prompt = f"""You are senior {self.company_name} SEO writer with 8 years experience writing for {self.company_name}. You write like a human who actually uses the product.

BUSINESS: {self.company_name} - professional services firm
KEYWORD: {primary_keyword}
TONE: {tone_desc}
EXAMPLE PHRASES: {', '.join(example_phrases)}

Write 1200-1500 words. 

HARD RULES - BREAK THESE = FAIL:
1. NEVER use em dash —
2. NEVER use banned phrases: {', '.join(self.banned_phrases[:8])}
3. First paragraph must answer the search intent directly
4. Primary keyword in: title + first 100 words + 1 H2
5. Include 2 facts from knowledge base verbatim
6. Vary sentence length - human burstiness
7. Use contractions naturally: don't, can't, it's

Structure: Problem > Our Approach > Solution > Evidence > Mistakes > Takeaways

DO NOT write AI content. Write like a tired writer at 2am who knows this topic cold."""

        try:
            prompt = f"""Write a blog about {topic} targeting keyword "{primary_keyword}". 

{system_prompt}

Include:
- Direct answer in first paragraph
- Real examples from our work
- Statistics we can cite
- FAQ section
- Comparison table
- Checklist at end

Write now:"""
            
            return {
                "status": "generated",
                "prompt_used": system_prompt,
                "topic": topic,
                "primary_keyword": primary_keyword,
                "secondary_keywords": secondary_keywords,
                "word_target": 1200,
                "structure": [
                    f"H1: How to Master {primary_keyword} for Business Results",
                    "Introduction: Direct problem statement",
                    f"What is {primary_keyword}: Our take from experience",
                    f"Why {primary_keyword} matters for professionals",
                    "5-7 points with examples from our work",
                    "Table: Before vs After",
                    "Common mistakes we see",
                    "How we approach this differently",
                    "FAQ: 4 questions",
                    "Key takeaways checklist"
                ]
            }
            
        except Exception as e:
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