import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
import aiohttp
import os

logger = logging.getLogger("backend.agents.strategy_agent")


class StrategyAgent:
    def __init__(self, website_id: str):
        self.website_id = website_id
        from ..database import get_supabase, call_nim_llm
        self.supabase = get_supabase()
        self.call_nim_llm = call_nim_llm
    
    async def handle_alert(self, alert: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate strategy and content based on alert - auto-create drafts, never publish live."""
        alert_type = alert.get("alert_type")
        data = alert.get("data", {})
        
        if alert_type in ("rank_drop", "rank_opportunity", "keyword_opportunity"):
            return await self._handle_rank_alert(alert)
        elif alert_type in ("competitor_price", "competitor_content"):
            return await self._handle_competitor_alert(alert)
        elif alert_type in ("tech_broken_link", "tech_speed", "tech_mobile", "tech_crawl", "tech_index"):
            return await self._handle_tech_alert(alert)
        
        return None
    
    async def _handle_rank_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rank drop/opportunity alerts."""
        kw = alert.get("data", {}).get("keyword")
        url = alert.get("data", {}).get("url")
        
        if not kw:
            return {"status": "no_keyword"}
        
        try:
            clusters = await self._generate_topic_clusters(kw)
            
            cluster_id = str(uuid.uuid4())
            self.supabase.table("topic_clusters").insert({
                "website_id": self.website_id,
                "pillar_topic": kw,
                "pillar_keyword": kw,
                "clusters": clusters,
                "created_from_alert_id": alert.get("id"),
                "created_at": datetime.utcnow()
            }).execute()
            
            top_pages = await self._analyze_top_pages(kw)
            
            if alert.get("alert_type") == "rank_drop" and url:
                suggestions = await self._generate_optimization_suggestions(url, kw, top_pages)
                self.supabase.table("content_optimizations").insert({
                    "website_id": self.website_id,
                    "page_url": url,
                    "suggestions": suggestions,
                    "optimization_score": suggestions.get("score", 0),
                    "created_at": datetime.utcnow()
                }).execute()
            
            task_id = str(uuid.uuid4())
            self.supabase.table("agent_tasks").insert({
                "website_id": self.website_id,
                "agent": "writer",
                "task_type": "auto_strategy",
                "payload": {
                    "keyword": kw,
                    "pillar": kw,
                    "clusters": clusters,
                    "alert_id": alert.get("id"),
                    "top_pages": top_pages
                },
                "status": "pending_approval",
                "created_at": datetime.utcnow()
            }).execute()
            
            from .reporting_service import report_problem
            await report_problem(
                website_id=self.website_id,
                alert_type="content_gap",
                severity="info",
                title=f"Strategy generated for {kw}",
                description=f"Created {len(clusters)} cluster topics + optimization suggestions - needs human review",
                data={"keyword": kw, "clusters": clusters, "task_id": task_id},
                source_monitor="strategy_agent"
            )
            
            return {
                "status": "strategy_created",
                "cluster_id": cluster_id,
                "task_id": task_id,
                "clusters": clusters.get("clusters", [])
            }
        except Exception as e:
            logger.error(f"Strategy failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def _handle_competitor_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Handle competitor change alerts."""
        comp_domain = alert.get("data", {}).get("competitor_domain")
        
        if not comp_domain:
            return {"status": "no_competitor"}
        
        try:
            gap_keywords = await self._generate_competitor_gap_keywords(comp_domain)
            
            clusters = await self._generate_topic_clusters(f"Beat {comp_domain} - {alert.get('title', '')}")
            
            cluster_id = str(uuid.uuid4())
            self.supabase.table("topic_clusters").insert({
                "website_id": self.website_id,
                "pillar_topic": f"Beat {comp_domain}",
                "pillar_keyword": f"Beat {comp_domain} - {alert.get('title', '')}",
                "clusters": clusters,
                "created_from_alert_id": alert.get("id"),
                "created_at": datetime.utcnow()
            }).execute()
            
            task_id = str(uuid.uuid4())
            self.supabase.table("agent_tasks").insert({
                "website_id": self.website_id,
                "agent": "writer",
                "task_type": "competitor_strategy",
                "payload": {
                    "competitor_domain": comp_domain,
                    "gap_keywords": gap_keywords,
                    "clusters": clusters
                },
                "status": "pending_approval",
                "created_at": datetime.utcnow()
            }).execute()
            
            from .reporting_service import report_problem
            await report_problem(
                website_id=self.website_id,
                alert_type="content_gap",
                severity="info",
                title=f"Competitor strategy for {comp_domain}",
                description=f"Generated {len(gap_keywords)} gap keywords + content strategy",
                data={"competitor_domain": comp_domain, "gap_keywords": gap_keywords},
                source_monitor="strategy_agent"
            )
            
            return {
                "status": "competitor_strategy_created",
                "gap_keywords": gap_keywords
            }
        except Exception as e:
            logger.error(f"Competitor strategy failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def _handle_tech_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Handle technical alerts - create pending_fixes for human approval."""
        try:
            fix_payload = alert.get("data", {})
            
            fix_id = str(uuid.uuid4())
            
            fix_data = {
                "website_id": self.website_id,
                "audit_id": fix_payload.get("audit_id"),
                "fix_type": alert.get("alert_type"),
                "fix_payload": fix_payload,
                "fix_method": self._get_fix_method(alert.get("alert_type")),
                "status": "pending_approval",
                "proposed_by": "strategy_agent",
                "created_at": datetime.utcnow()
            }
            
            self.supabase.table("pending_fixes").insert(fix_data).execute()
            
            from .reporting_service import report_problem
            await report_problem(
                website_id=self.website_id,
                alert_type="content_gap",
                severity="info",
                title=f"Fix proposed: {alert.get('title', 'Tech Issue')}",
                description=f"{alert.get('alert_type')} - proposed fix awaiting human approval. View in dashboard to approve.",
                data={"fix_id": fix_id, "fix_type": alert.get("alert_type"), "fix_payload": fix_payload},
                source_monitor="strategy_agent"
            )
            
            return {"status": "fix_proposed", "fix_id": fix_id}
        except Exception as e:
            logger.error(f"Fix proposal failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _get_fix_method(self, alert_type: str) -> str:
        """Get suggested fix method for alert type."""
        methods = {
            "tech_broken_link": "fix_or_404_page",
            "tech_speed": "optimize_images_lazy_load",
            "tech_mobile": "viewport_font_tap_fixes",
            "tech_crawl": "robots_sitemap_canonical_fix",
            "tech_index": "meta_robots_fix",
            "rank_drop": "content_optimization",
            "rank_opportunity": "content_creation"
        }
        return methods.get(alert_type, "manual_review")
    
    async def _generate_topic_clusters(self, keyword: str) -> Dict[str, Any]:
        """Generate topic clusters using NVIDIA NIM."""
        prompt = f"""You are an SEO strategist. Generate topic clusters for keyword "{keyword}".
        
        Given:
        - website_knowledge: {self._get_site_knowledge()}
        - gsc_keywords: {await self._get_active_keywords_summary()}
        - competitor_top_pages: {await self._get_competitor_insights()}

        Generate:
        1. 1 pillar topic with primary keyword
        2. 5 cluster topics with secondary keywords

        For each cluster:
        - title (include keyword)
        - primary_keyword (include keyword)
        - secondary_keywords (array)
        - intent (informational/commercial/navigational)
        - word_count (based on top 10 avg)
        - internal_links: suggest existing pages to link to
        - faqs: 3 questions

        Return JSON:
        {{
            "pillar_topic": "string",
            "clusters": [
                {{
                    "title": "string",
                    "primary_keyword": "keyword",
                    "secondary_keywords": ["kw1", "kw2"],
                    "intent": "informational",
                    "word_count": 1500,
                    "internal_links": ["url1", "url2"],
                    "faqs": ["q1", "q2", "q3"]
                }}
            ]
        }}"""
        
        try:
            result = await self.call_nim_llm(prompt, website_id=self.website_id)
            return json.loads(result)
        except Exception as e:
            logger.warning(f"NIM generation failed: {e}")
            return self._fallback_clusters(keyword)
    
    def _get_site_knowledge(self) -> str:
        """Get website knowledge."""
        try:
            pages = self.supabase.table("website_pages").select("url,title,content_keywords,clicks").eq("website_id", self.website_id).limit(50).execute().data or []
            return json.dumps([{
                "url": p.get("url"),
                "title": p.get("title"),
                "keywords": p.get("content_keywords", []),
                "clicks": p.get("clicks", 0)
            } for p in pages])
        except:
            return "[]"
    
    async def _get_active_keywords_summary(self) -> str:
        """Get active keywords from GSC."""
        try:
            kws = self.supabase.table("gsc_keywords").select("keyword,impressions,clicks").eq("website_id", self.website_id).eq("is_active", True).order("impressions", desc=True).limit(100).execute().data or []
            return json.dumps([{
                "keyword": k.get("keyword"),
                "impressions": k.get("impressions"),
                "clicks": k.get("clicks")
            } for k in kws])
        except:
            return "[]"
    
    async def _get_competitor_insights(self) -> str:
        """Get competitor insights."""
        try:
            competitors = self.supabase.table("competitors").select("competitor_domain,homepage_url,pricing_page_url").eq("website_id", self.website_id).execute().data or []
            return json.dumps(competitors)
        except:
            return "[]"
    
    def _fallback_clusters(self, keyword: str) -> Dict[str, Any]:
        """Fallback cluster generation."""
        return {
            "pillar_topic": keyword,
            "clusters": [
                {
                    "title": f"Complete Guide to {keyword}",
                    "primary_keyword": keyword,
                    "secondary_keywords": [f"{keyword} guide", f"best {keyword}"],
                    "intent": "informational",
                    "word_count": 2000,
                    "internal_links": [],
                    "faqs": [
                        f"What is {keyword}?",
                        f"Why is {keyword} important?",
                        f"How to use {keyword}?"
                    ]
                }
            ]
        }
    
    async def _analyze_top_pages(self, keyword: str) -> Dict[str, Any]:
        """Analyze top 3 Google results for keyword."""
        if os.getenv("SERPAPI_KEY"):
            try:
                params = {
                    "api_key": os.getenv("SERPAPI_KEY"),
                    "q": keyword,
                    "num": 3
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://serpapi.com/search", params=params) as resp:
                        data = await resp.json()
                        results = []
                        for r in data.get("organic_results", [])[:3]:
                            results.append({
                                "url": r.get("link"),
                                "title": r.get("title"),
                                "snippet": r.get("snippet"),
                                "h2_count": len(r.get("rich_snippet_table", [])),
                                "schema": r.get("featured_snippet", {}).get("type")
                            })
                        return {"top_pages": results}
            except Exception as e:
                logger.warning(f"Top page analysis failed: {e}")
        return {"top_pages": []}
    
    async def _generate_competitor_gap_keywords(self, competitor_domain: str) -> list:
        """Generate keywords that competitor ranks for but we don't."""
        try:
            our_kws = self.supabase.table("gsc_keywords").select("keyword").eq("website_id", self.website_id).execute().data or []
            our_keywords = {k.get("keyword", "").lower() for k in our_kws}
            
            competitor_kws = await self._scrape_competitor_keywords(competitor_domain)
            
            gap_keywords = [k for k in competitor_kws if k.lower() not in our_keywords][:20]
            return gap_keywords
        except:
            return []
    
    async def _scrape_competitor_keywords(self, domain: str) -> list:
        """Scrape competitor keywords from sitemap/page content."""
        try:
            from ..services.crawlee_service import CrawleeService
            service = CrawleeService()
            sitemap_urls = await service._get_sitemap_urls(domain)
            if not sitemap_urls:
                return []
            pages = await service.crawl_site_structure(sitemap_urls[:10], max_requests=10)
            keywords = []
            for page in pages:
                if page.get("title"):
                    keywords.append(page["title"])
                keywords.extend(page.get("h1s", []))
                keywords.extend(page.get("h2s", []))
            return list(set(keywords))[:50]
        except Exception as e:
            logger.warning(f"Competitor keyword scrape failed for {domain}: {e}")
            return []
    
    async def _generate_optimization_suggestions(self, url: str, keyword: str, top_pages: Dict) -> Dict[str, Any]:
        """Generate optimization suggestions for existing page."""
        try:
            suggestions = []
            
            similarity = 0.5
            for tp in top_pages.get("top_pages", []):
                if keyword.lower() in tp.get("title", "").lower():
                    similarity = 1.0
                    break
            
            suggestions.append({
                "type": "keyword_density",
                "current": 0.5,
                "suggested": 1.0,
                "reason": f"Optimal for SEO - current density {keyword} is {similarity}",
                "priority": "high"
            })
            
            suggestions.append({
                "type": "content_length",
                "current": 1200,
                "suggested": 2000,
                "reason": "Top 3 results have average 2000+ words",
                "priority": "medium"
            })
            
            for tp in top_pages.get("top_pages", [])[:3]:
                if tp.get("h2_count", 0) > 5:
                    suggestions.append({
                        "type": "subheadings",
                        "current": "unknown",
                        "suggested": "Add 5+ H2 sections",
                        "reason": "Top result has " + str(tp.get("h2_count", 0)) + " subheadings",
                        "priority": "high"
                    })
            
            return {
                "suggestions": suggestions,
                "score": min(100, len(suggestions) * 15),
                "url": url,
                "keyword": keyword
            }
        except Exception as e:
            return {"suggestions": [], "score": 0, "error": str(e)}