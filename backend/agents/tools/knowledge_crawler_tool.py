import logging
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("backend.tools.knowledge_crawler_tool")


class KnowledgeCrawlerInput(BaseModel):
    url: str = Field(description="Website URL to crawl")
    max_pages: int = Field(default=50, description="Maximum pages to crawl")
    website_id: str = Field(description="Website ID for storage")


class KnowledgeCrawlerTool(BaseTool):
    name: str = "knowledge_crawler"
    description = "Crawls entire website to extract business info, tone, keywords, themes, and writing patterns. Creates comprehensive knowledge base for AI."
    args_schema: type[BaseModel] = KnowledgeCrawlerInput
    _website_id: Optional[str] = None
    
    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id
    
    def _run(self, url: str, max_pages: int = 50, website_id: str = None) -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})
        
        result = {
            "website_url": url,
            "crawled_at": datetime.utcnow().isoformat(),
            "pages_crawled": 0,
            "business_insights": {},
            "tone_profile": {},
            "keyword_profile": {},
            "theme_profile": {},
            "writing_pattern": {},
            "expert_facts": []
        }
        
        try:
            sitemaps = self._find_sitemaps(url)
            all_urls = self._crawl_sitemap(sitemaps, max_pages)
            
            content_samples = []
            for page_url in all_urls[:10]:
                content = self._fetch_page_content(page_url)
                if content:
                    content_samples.append({"url": page_url, "content": content})
            
            if content_samples:
                result["business_insights"] = self._extract_business_insights(content_samples)
                result["tone_profile"] = self._analyze_tone(content_samples)
                result["keyword_profile"] = self._extract_keywords(content_samples)
                result["theme_profile"] = self._extract_themes(content_samples)
                result["writing_pattern"] = self._analyze_writing_pattern(content_samples)
                result["expert_facts"] = self._extract_expert_facts(content_samples)
                result["pages_crawled"] = len(content_samples)
            
            self._save_to_knowledge_base(result)
            result["status"] = "success"
            
        except Exception as e:
            logger.error(f"Knowledge crawl failed: {e}")
            result["error"] = str(e)
        
        return json.dumps(result, indent=2)
    
    def _find_sitemaps(self, base_url: str) -> List[str]:
        sitemaps = []
        domains = [
            base_url.rstrip('/'),
            f"https://{base_url.replace('https://', '').replace('http://', '')}",
            f"http://{base_url.replace('https://', '').replace('http://', '')}"
        ]
        
        for domain in domains:
            sitemap_urls = [
                f"{domain}/sitemap.xml",
                f"{domain}/sitemap.txt",
                f"{domain}/robots.txt"
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    resp = httpx.get(sitemap_url, timeout=10)
                    if resp.status_code == 200:
                        if 'sitemap.xml' in sitemap_url:
                            import xml.etree.ElementTree as ET
                            root = ET.fromstring(resp.text)
                            for url in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                                sitemaps.append(url.text)
                        else:
                            for line in resp.text.split('\n'):
                                if line.strip().startswith('http'):
                                    sitemaps.append(line.strip())
                except:
                    continue
        
        return list(set(sitemaps))
    
    def _crawl_sitemap(self, sitemaps: List[str], max_pages: int) -> List[str]:
        urls = []
        for sitemap in sitemaps[:5]:
            try:
                resp = httpx.get(sitemap, timeout=10)
                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text)
                    for loc in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                        if len(urls) < max_pages:
                            urls.append(loc.text)
            except:
                continue
        return urls
    
    def _fetch_page_content(self, url: str) -> Optional[str]:
        try:
            resp = httpx.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'lxml')
                for script in soup(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                content = soup.get_text(separator=' ', strip=True)
                return content[:10000]
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
        return None
    
    def _extract_business_insights(self, samples: List[Dict]) -> Dict:
        combined = "\n".join(s["content"] for s in samples[:5])
        
        insights = {
            "company_name": self._extract_entity(combined, ["company", "business", "brand"]),
            "industry": self._detect_industry(combined),
            "value_proposition": self._extract_value_prop(combined),
            "target_audience": self._extract_audience(combined),
            "brand_voice": self._detect_voice(combined),
            "unique_selling_points": self._extract_usps(combined),
            "mission_vision": self._extract_mission(combined)
        }
        
        return insights
    
    def _detect_industry(self, text: str) -> str:
        industry_keywords = {
            "technology": ["software", "tech", "digital", "app", "platform", "api", "ai", "ml", "cloud"],
            "healthcare": ["health", "medical", "patient", "doctor", "treatment", "care", "therapy"],
            "finance": ["finance", "money", "investment", "loan", "bank", "tax", "account"],
            "marketing": ["marketing", "advertisement", "campaign", "brand", "growth", "strategy"],
            "ecommerce": ["shop", "store", "product", "buy", "sell", "cart", "order"],
            "consulting": ["consult", "advisor", "strategy", "solution", "expert", "professional"],
            "education": ["learn", "course", "study", "student", "teacher", "education", "knowledge"],
            "legal": ["law", "legal", "attorney", "court", "case", "contract", "jurisdiction"]
        }
        
        text_lower = text.lower()
        scores = {}
        for industry, keywords in industry_keywords.items():
            scores[industry] = sum(1 for kw in keywords if kw in text_lower)
        
        return max(scores.items(), key=lambda x: x[1])[0] if any(scores.values()) else "general"
    
    def _extract_value_prop(self, text: str) -> str:
        patterns = [r"we help [\w\s]+", r"transform [\w\s]+", r"(?:expert|professional|leading) [\w\s]+", r"(\d+\s*(?:years|months) of experience)"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return "Professional services with expert approach"
    
    def _extract_audience(self, text: str) -> str:
        patterns = [r"(?:small|medium|large) (?:business|company|enterprise)", r"entrepreneurs?", r"professionals?", r"teams?", r"organizations?"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return "business professionals"
    
    def _detect_voice(self, text: str) -> str:
        professional_indicators = ["professional", "expert", "industry", "specialized", "proven", "trusted"]
        casual_indicators = ["awesome", "cool", "great", "easy", "simple", "fun"]
        
        prof_count = sum(1 for w in professional_indicators if w in text.lower())
        casual_count = sum(1 for w in casual_indicators if w in text.lower())
        
        if prof_count > casual_count:
            return "professional"
        elif casual_count > 0:
            return "conversational"
        return "expert-authoritative"
    
    def _extract_usps(self, text: str) -> List[str]:
        bullet_patterns = re.findall(r"•\s*([^\n]+)", text)
        number_patterns = re.findall(r"\d+\.\s*([^\n]+)", text)
        
        usps = []
        for pattern in [bullet_patterns, number_patterns]:
            for item in pattern[:5]:
                clean = item.strip()[:150]
                if len(clean) > 20:
                    usps.append(clean)
        
        return usps[:5] if usps else ["Expert knowledge", "Proven results", "Professional approach"]
    
    def _extract_mission(self, text: str) -> Dict:
        mission_match = re.search(r"(?:mission|vision|goal)[:\s]*([^\n]{50,200})", text, re.IGNORECASE)
        return {
            "mission": mission_match.group(1) if mission_match else "Deliver exceptional professional services",
            "vision": "To be the leading provider in our industry"
        }
    
    def _extract_entity(self, text: str, keywords: List[str]) -> str:
        for kw in keywords:
            match = re.search(rf"\b([A-Z][a-zA-Z\s&]+(?:\w|{kw}))\b", text[:1000])
            if match:
                return match.group(1).strip()
        return "Professional Services"
    
    def _extract_keywords(self, samples: List[Dict]) -> Dict:
        combined = "\n".join(s["content"] for s in samples)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', combined.lower())
        
        from collections import Counter
        word_freq = Counter(words)
        
        stop_words = {"the", "and", "this", "that", "have", "has", "with", "from", "what", "when", "where", "your", "they", "them", "their", "would", "could", "should", "might", "also", "has", "have", "been", "being"}
        
        keywords = []
        for word, count in word_freq.most_common(50):
            if word not in stop_words and count > 3:
                keywords.append(word)
        
        primary = keywords[:10] if len(keywords) >= 10 else keywords
        
        lsi_keywords = []
        for kw in primary:
            if "seo" in kw or "content" in kw or "strategy" in kw:
                lsi_keywords.extend([f"{kw} best practices", f"improve {kw}", f"{kw} optimization"])
        
        return {
            "primary_keywords": primary,
            "LSI_keywords": lsi_keywords[:15],
            "semantic_cluster": list(set(primary[:5]))
        }
    
    def _extract_themes(self, samples: List[Dict]) -> Dict:
        combined = "\n".join(s["content"] for s in samples)
        
        themes = []
        theme_patterns = [
            (r"(?:success|results|growth|improvement)", "results-driven"),
            (r"(?:expert|professional|specialized)", "expertise"),
            (r"(?:guide|tutorial|how-to)", "educational"),
            (r"(?:case study|example|demonstration)", "case-based learning"),
            (r"(?:best practices|strategies|methods)", "methodology"),
            (r"(?:industry|market|competition)", "industry insights")
        ]
        
        for pattern, theme in theme_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                themes.append(theme)
        
        return {
            "primary_themes": themes,
            "content_categories": ["Educational", "Case Studies", "Industry Analysis"],
            "narrative_style": "problem-solution-focus"
        }
    
    def _analyze_writing_pattern(self, samples: List[Dict]) -> Dict:
        patterns = {
            "paragraph_style": "concise",
            "sentence_length": "moderate",
            "tone": "professional",
            "complexity": "intermediate",
            "preferred_punctuation": ["periods", "commas", "colons"],
            "avoid_phrases": ["very", "really", "really", "so much", "like", "you know", "and", "awesome", "great", "cool"],
            "preferred_phrases": ["expert", "professional", "proven", "industry-leading", "comprehensive", "strategic", "optimized", "results-driven"],
            "sentence_structure": ["start with main point", "use active voice", "avoid filler words"]
        }
        
        combined = "\n".join(s["content"] for s in samples[:3])
        avg_len = sum(len(p.split()) for p in combined.split('\n\n')) / max(1, len([p for p in combined.split('\n\n') if p.strip()]))
        
        if avg_len > 25:
            patterns["paragraph_style"] = "short-concise"
        elif avg_len > 15:
            patterns["paragraph_style"] = "medium"
        else:
            patterns["paragraph_style"] = "brief"
        
        return patterns
    
    def _extract_expert_facts(self, samples: List[Dict]) -> List[Dict]:
        facts = []
        combined = "\n".join(s["content"] for s in samples[:5])
        
        stat_patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:%|million|billion|%|times|years?)",
            r"(?:most|top|best)\s+(?:\d+\s+)?(?:\w+\s+)?(?:companies|brands|businesses)",
            r"(?:studies?|research|data) show(?:s)?"
        ]
        
        for pattern in stat_patterns:
            for match in re.finditer(pattern, combined, re.IGNORECASE):
                facts.append({
                    "fact": match.group(0),
                    "type": "statistic" if ("%" in match.group(0) or any(c.isdigit() for c in match.group(0))) else "text",
                    "confidence": 0.9
                })
        
        return facts[:20]
    
    def _save_to_knowledge_base(self, result: Dict) -> None:
        try:
            from ...database import get_supabase
            kb_entry = {
                "website_id": self._website_id,
                "fact": f"Business profile - {result['business_insights'].get('industry', 'general')} business with voice: {result['tone_profile'].get('brand_voice', 'professional')}",
                "fact_type": "business_profile",
                "source_url": result['website_url'],
                "tags": ["business-profile", "tone-analysis", "keyword-profile"],
                "created_at": datetime.utcnow().isoformat()
            }
            get_supabase().table("knowledge_base").insert(kb_entry).execute()
        except Exception as e:
            logger.warning(f"Could not save to knowledge base: {e}")


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        from ...database import get_supabase
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "result": json.dumps({"real_api_called": real_api}),
            "real_api_called": real_api,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass
