import json
import logging
import math
from datetime import datetime
from typing import Dict, List, Any
import uuid

logger = logging.getLogger("backend.services.cluster_service")


class ClusterService:
    """Build topic authority clusters from live GSC keyword data."""
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id
    
    async def build_clusters(self, max_clusters: int = 10) -> Dict[str, Any]:
        """Build topic clusters from live GSC keywords."""
        from ..database import get_supabase
        from ..services.gsc_service import GSCService
        from ..services.knowledge_service import KnowledgeService
        
        supabase = get_supabase()
        
        gsc_service = GSCService()
        if not gsc_service.is_connected():
            return {"error": "GSC not connected", "clusters_created": 0}
        
        gsc_data = await gsc_service.get_keyword_performance(row_limit=2000)
        keywords = gsc_data.get("keywords", [])
        
        high_volume_kw = [k for k in keywords if k.get("impressions", 0) > 100]
        
        knowledge_service = KnowledgeService(self.website_id)
        
        embeddings = await self._get_embeddings([k.get("keyword", "") for k in high_volume_kw[:50]])
        
        clusters = await self._cluster_keywords(high_volume_kw[:50], embeddings)
        
        created_clusters = []
        created_articles = []
        
        for cluster_data in clusters[:max_clusters]:
            cluster_id = str(uuid.uuid4())
            pillar_keyword = cluster_data["primary"]
            
            cluster = {
                "id": cluster_id,
                "website_id": self.website_id,
                "cluster_name": pillar_keyword.title(),
                "pillar_keyword": pillar_keyword,
                "keywords": cluster_data["keywords"][:15],
                "coverage": 0,
                "authority_score": 0,
                "created_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("topic_clusters").insert(cluster).execute()
            created_clusters.append(cluster)
            
            for kw in cluster_data["keywords"][:15]:
                article = {
                    "id": str(uuid.uuid4()),
                    "cluster_id": cluster_id,
                    "website_id": self.website_id,
                    "keyword": kw.get("keyword", ""),
                    "intent": await self._classify_intent(kw.get("keyword", "")),
                    "business_potential": await self._score_business_potential(kw.get("keyword", "")),
                    "search_volume": kw.get("impressions", 0),
                    "current_position": kw.get("position", 0),
                    "priority_score": kw.get("impressions", 0) / max(kw.get("position", 1), 1),
                    "status": "opportunity",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                supabase.table("cluster_articles").insert(article).execute()
                created_articles.append(article)
        
        for c in created_clusters:
            self._calculate_authority_score(c["id"], supabase)
        
        return {
            "status": "success",
            "clusters_created": len(created_clusters),
            "articles_created": len(created_articles),
            "total_keywords_analyzed": len(high_volume_kw),
            "source": "gsc_real"
        }
    
    async def _get_embeddings(self, keywords: List[str]) -> List[List[float]]:
        """Get embeddings for keywords."""
        from ..database import call_nim_llm
        
        embeddings = []
        for kw in keywords[:10]:
            try:
                prompt = f"Generate a 8-dimensional embedding vector for: {kw}"
                embedding = await call_nim_llm(prompt)
                embeddings.append([float(x) for x in embedding.strip().split() if x.replace('.','').replace('-','').isdigit()][:8] or [0.0] * 8)
            except:
                embeddings.append([0.0] * 8)
        
        return embeddings
    
    async def _cluster_keywords(self, keywords: List[Dict], embeddings: List[List[float]]) -> List[Dict]:
        """Cluster keywords using simple cosine similarity."""
        from collections import Counter
        import math
        
        if not keywords:
            return []
        
        clusters = []
        assigned = set()
        
        for i, kw in enumerate(keywords):
            if i in assigned:
                continue
            
            cluster_keywords = [kw]
            assigned.add(i)
            
            for j, other_kw in enumerate(keywords):
                if j in assigned:
                    continue
                
                sim = self._cosine_similarity(embeddings[i] if i < len(embeddings) else [0]*8, 
                                             embeddings[j] if j < len(embeddings) else [0]*8)
                
                if sim > 0.7:
                    cluster_keywords.append(other_kw)
                    assigned.add(j)
            
            if cluster_keywords:
                primary = max(cluster_keywords, key=lambda x: x.get("impressions", 0))
                clusters.append({
                    "primary": primary.get("keyword", ""),
                    "keywords": cluster_keywords,
                    "size": len(cluster_keywords)
                })
        
        return clusters
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
        
        return dot_product / (mag_a * mag_b)
    
    def _classify_intent(self, keyword: str) -> str:
        """Classify keyword intent."""
        transactional_keywords = ["buy", "price", "cost", "discount", "deal", "offer", "trial", "demo"]
        informational_keywords = ["what is", "how to", "guide", "tutorial", "explain", "definition"]
        
        kw_lower = keyword.lower()
        
        for tk in transactional_keywords:
            if tk in kw_lower:
                return "transactional"
        
        for ik in informational_keywords:
            if ik in kw_lower:
                return "informational"
        
        return "commercial"
    
    async def _score_business_potential(self, keyword: str) -> int:
        """Score business potential 0-3."""
        business_keywords = ["crm", "saas", "startup", "ecommerce", "marketing", "sales", "productivity"]
        
        kw_lower = keyword.lower()
        
        for bk in business_keywords:
            if bk in kw_lower:
                return 3 if "best" in kw_lower or "startup" in kw_lower else 2
        
        return 1
    
    async def _calculate_authority_score(self, cluster_id: str, supabase) -> float:
        """Calculate authority score for cluster."""
        articles = supabase.table("cluster_articles").select("status,search_volume,current_position").eq("cluster_id", cluster_id).execute().data or []
        
        published = len([a for a in articles if a.get("status") == "published"])
        total = len(articles)
        
        avg_impressions = sum(a.get("search_volume", 0) for a in articles) / max(total, 1)
        avg_position = sum(a.get("current_position", 0) for a in articles) / max(total, 1)
        
        coverage = published / max(total, 1) if total > 0 else 0
        position_score = max(0, 1 - (avg_position / 100))
        volume_score = min(1, avg_impressions / 10000)
        
        authority = (coverage * 40) + (position_score * 30) + (volume_score * 30)
        
        supabase.table("topic_clusters").update({"authority_score": authority}).eq("id", cluster_id).execute()
        
        return authority


async def build_clusters(website_id: str, max_clusters: int = 10) -> Dict:
    """Standalone function."""
    service = ClusterService(website_id)
    return await service.build_clusters(max_clusters)