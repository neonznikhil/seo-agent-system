import logging
import re
from typing import Optional, List, Dict, Any
import asyncio
import json
from datetime import datetime

logger = logging.getLogger("backend.agents.setup_agent")


class SetupAgent:
    """
    Professional SEO Content Writer Agent (10+ years experience simulation)
    Specializes in creating human-like, AI-free content that ranks and converts
    """
    
    def __init__(self, website_id: str):
        self.website_id = website_id
        self.knowledge_base = {}
        self.tone_profile = {}
        self.keyword_profile = {}
        self.theme_profile = {}
        self.industry = "professional services"
        self.company_name = "Our Organization"
        
    async def setup_website_profile(self, url: str) -> Dict[str, Any]:
        """
        Main method: Crawl website and create comprehensive business understanding
        """
        from .tools.knowledge_crawler_tool import KnowledgeCrawlerTool
        from .tools.anti_ai_pen_tool import AntiAIPenTool
        
        knowledge_tool = KnowledgeCrawlerTool()
        knowledge_tool.set_website_id(self.website_id)
        
        crawl_result = knowledge_tool._run(url, max_pages=50, website_id=self.website_id)
        self.knowledge_base = json.loads(crawl_result)
        
        self.tone_profile = self.knowledge_base.get("tone_profile", {})
        self.keyword_profile = self.knowledge_base.get("keyword_profile", {})
        self.theme_profile = self.knowledge_base.get("theme_profile", {})
        self.industry = self.knowledge_base.get("business_insights", {}).get("industry", "professional services")
        self.company_name = self.knowledge_base.get("business_insights", {}).get("company_name", "Our Organization")
        
        anti_ai_tool = AntiAIPenTool()
        anti_ai_tool.set_website_id(self.website_id)
        
        return {
            "status": "setup_complete",
            "website_url": url,
            "business_profile": self.knowledge_base.get("business_insights", {}),
            "tone_analysis": self.tone_profile,
            "keyword_opportunities": self.keyword_profile,
            "themes_identified": self.theme_profile,
            "expert_facts_extracted": len(self.knowledge_base.get("expert_facts", [])),
            "pages_analyzed": self.knowledge_base.get("pages_crawled", 0)
        }
    
    def generate_blog_outline(self, topic: str, target_keyword: str) -> Dict[str, Any]:
        """
        Generate professional blog outline based on website profile
        Avoids AI-sounding structure
        """
        outline = {
            "title": f"How to Master {topic}: A Complete Guide for {self.industry.title()} Professionals",
            "meta_description": f"Expert insights on {topic} from {self.company_name}. Learn proven strategies used by top professionals in {self.industry}.",
            "target_keyword": target_keyword,
            "focus_keyword": target_keyword,
            "lsi_keywords": self.keyword_profile.get("LSI_keywords", [topic, f"{topic} strategies", f"improve {topic}"])[:4],
            "sections": [
                {
                    "heading": f"The Challenge: Common {topic.title()} Problems We See",
                    "type": "problem_statement",
                    "words": 150,
                    "purpose": "Establish authority by acknowledging real business challenges"
                },
                {
                    "heading": f"Our {self.industry.title()} Approach to {topic.title()}",
                    "type": "methodology",
                    "words": 200,
                    "purpose": "Showcase expertise through structured approach"
                },
                {
                    "heading": f"Step-by-Step: How to {topic.title()}",
                    "type": "how_to",
                    "words": 400,
                    "purpose": "Deliver actionable content with numbered steps",
                    "subsections": [
                        "Preparation Phase",
                        "Implementation Strategy",
                        "Quality Assurance",
                        "Scaling Results"
                    ]
                },
                {
                    "heading": f"Real Results: {self.industry.title()} Case Example",
                    "type": "case_study",
                    "words": 250,
                    "purpose": "Build trust with concrete proof"
                },
                {
                    "heading": "Common Mistakes to Avoid",
                    "type": "mistakes",
                    "words": 150,
                    "purpose": "Position as trusted advisor"
                },
                {
                    "heading": "Key Takeaways",
                    "type": "summary",
                    "words": 100,
                    "purpose": "Quick reference for busy professionals"
                }
            ],
            "seo_structure": {
                "h1": f"Mastering {topic}: Expert Guide for {self.industry.title()} Professionals",
                "h2_count": 4,
                "h3_count": 8,
                "internal_link_opportunities": 2,
                "external_citation_opportunities": 3
            },
            "anti_ai_modifications": {
                "avoid_patterns": ["utilize", "facilitate", "in order to", "pursuant to", "endeavor"],
                "preferred_terms": ["use", "help", "to", "according to", "effort"],
                "sentence_starters": ["The key insight", "What matters most", "Your next step", "Consider this approach"]
            }
        }
        
        return outline
    
    def generate_content(self, outline: Dict[str, Any], context: str = "") -> str:
        """
        Generate human-like content that does not sound AI-written
        """
        sections_output = []
        
        for section in outline.get("sections", []):
            content = self._generate_section_content(section, context)
            sections_output.append(content)
        
        full_content = "\n\n".join(sections_output)
        
        processed = self._apply_professional_tone(full_content)
        processed = self._remove_ai_patterns(processed)
        
        return processed
    
    def _generate_section_content(self, section: Dict, context: str) -> str:
        heading = section.get("heading", "")
        section_type = section.get("type", "general")
        subsection_count = section.get("subsections", 0)
        words = section.get("words", 200)
        
        templates = {
            "problem_statement": f"""{heading}

The most common issue we encounter in {self.industry} is approaches that do not match reality. I have watched countless {self.industry} professionals struggle with exactly this challenge.

The root cause is not lack of effort - it is using outdated methods for current problems. In {self.industry} environments, what worked five years ago simply does not cut it anymore.""",
            
            "methodology": f"""{heading}

What we have learned from years of working with {self.industry} clients is that successful outcomes come from systematic execution, not random experimentation.

Here is the framework we use:

1. **Assessment Phase**: We start by measuring exactly where you stand today.
2. **Strategy Development**: Based on the assessment, we craft a targeted approach.
3. **Implementation**: We execute with precision and documented processes.
4. **Review and Refine**: We measure impact and adjust continuously.""",
            
            "how_to": f"""{heading}

Based on my experience working with {self.industry} teams on this exact challenge, here is what actually works:

**Preparation Phase**
Do not skip this. I have seen too many projects fail because they jumped straight to implementation without proper groundwork. Take time to understand your current position.""",
            
            "case_study": f"""{heading}

Last quarter, we worked with a {self.industry} company facing similar challenges. They started with manual processes and were getting inconsistent results.

Our approach was systematic: we mapped their existing workflow, identified three critical bottlenecks that no one had noticed, then implemented targeted solutions. The result? 40% faster delivery times and significantly improved quality scores.""",
            
            "mistakes": f"""{heading}

In my {self.industry} career, I have seen these mistakes cost clients time and money:

1. **Trying to do everything at once**: Prioritization is not optional - it is essential.
2. **Ignoring data**: Gut feelings are valuable, but they need data to guide action.
3. **Over-engineering**: The best solution is often the simplest one that works."""
            
            }
        
        return templates.get(section_type, f"\n{heading}\n\nBased on extensive experience in {self.industry}, here is what you need to know about {heading.lower()}...")
    
    def _apply_professional_tone(self, content: str) -> str:
        replacements = [
            (r"\bI have been there[,\.]?", "In my experience"),
            (r"\bI have seen[,\.]?", "I have observed"),  
            (r"\bwe have worked with\b", "we have collaborated with"),
            (r"\byou know\b", ""),
            (r"\blike\b(?=\s+(?:this|that|these|those|how|what))", "such as"),
            (r"\bso much\b", "significantly"),
            (r"\bvery good\b", "excellent"),
            (r"\bvery important\b", "critical"),
            (r"\breally big\b", "substantial"),
            (r"\ba lot of\b", "numerous"),
        ]
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
        return content
    
    def _remove_ai_patterns(self, content: str) -> str:
        from .tools.anti_ai_pen_tool import AntiAIPenTool
        
        tool = AntiAIPenTool()
        result = tool._run(content, self.website_id)
        data = json.loads(result)
        
        return data.get("fixed_content", content)
    
    def save_to_knowledge_base(self, content_id: str, content: str) -> Dict:
        """Save generated content and learnings to knowledge base"""
        entry = {
            "website_id": self.website_id,
            "fact": content[:500] if len(content) > 500 else content,
            "fact_type": "generated_content",
            "source_url": content_id,
            "tags": ["blog_post", "seo_optimized", "ai_clean"],
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            from database import get_supabase
            get_supabase().table("knowledge_base").insert(entry).execute()
            entry["status"] = "saved"
        except Exception as e:
            entry["status"] = f"error: {str(e)}"
        
        return entry


def create_setup_agent(website_id: str) -> SetupAgent:
    """Factory function to create a fresh setup agent for a website"""
    return SetupAgent(website_id)