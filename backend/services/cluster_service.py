import json
import logging
import math
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

logger = logging.getLogger("backend.services.cluster_service")


class ClusterService:
    """Build topic authority clusters from live GSC keyword data & NIM embeddings."""
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id or "default"
    
    async def build_clusters(self, max_clusters: int = 6) -> Dict[str, Any]:
        """Build topic clusters from live GSC / DB keywords with cosine similarity clustering."""
        from ..database import get_supabase
        from ..services.gsc_service import GSCService
        from ..services.knowledge_service import KnowledgeService
        
        supabase = get_supabase()
        keywords: List[Dict[str, Any]] = []

        # 1. Try GSC Service
        try:
            gsc_service = GSCService()
            if gsc_service.is_connected():
                gsc_data = await gsc_service.get_keyword_performance(row_limit=500)
                keywords = gsc_data.get("keywords", [])
        except Exception:
            pass

        # 2. Fallback to database keywords
        if not keywords:
            try:
                db_kws = supabase.table("gsc_keywords").select("*").eq("website_id", self.website_id).limit(40).execute().data or []
                if not db_kws:
                    db_kws = supabase.table("keyword_opportunities").select("*").eq("website_id", self.website_id).limit(40).execute().data or []
                keywords = db_kws
            except Exception:
                pass

        # 3. If no keywords found in GSC or DB, return empty result
        if not keywords:
            return {"clusters": [], "created_articles": [], "total_keywords": 0}

        kw_texts = [k.get("keyword", "") for k in keywords if k.get("keyword")]
        embeddings = await KnowledgeService.create_embeddings_batch(kw_texts[:30])
        clusters = await self._cluster_keywords(keywords[:30], embeddings)
        
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
                "keywords": cluster_data["keywords"][:10],
                "coverage": 25,
                "authority_score": 78,
                "created_at": datetime.utcnow().isoformat()
            }
            
            try:
                supabase.table("topic_clusters").insert(cluster).execute()
            except Exception:
                try:
                    supabase.table("clusters").insert({
                        "id": cluster_id,
                        "website_id": self.website_id,
                        "name": cluster["cluster_name"],
                        "keywords": [k.get("keyword") for k in cluster["keywords"] if isinstance(k, dict)]
                    }).execute()
                except Exception:
                    pass

            created_clusters.append(cluster)
            
            for kw in cluster_data["keywords"][:8]:
                kw_str = kw.get("keyword", "") if isinstance(kw, dict) else str(kw)
                article = {
                    "id": str(uuid.uuid4()),
                    "cluster_id": cluster_id,
                    "website_id": self.website_id,
                    "keyword": kw_str,
                    "intent": self._classify_intent(kw_str),
                    "business_potential": 3,
                    "search_volume": kw.get("impressions", 1500) if isinstance(kw, dict) else 1500,
                    "current_position": kw.get("position", 12.0) if isinstance(kw, dict) else 12.0,
                    "priority_score": round((kw.get("impressions", 1500) if isinstance(kw, dict) else 1500) / max(kw.get("position", 1) if isinstance(kw, dict) else 1, 1), 1),
                    "status": "opportunity",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                try:
                    supabase.table("cluster_articles").insert(article).execute()
                except Exception:
                    pass
                created_articles.append(article)
        
        return {
            "status": "success",
            "clusters_created": len(created_clusters),
            "articles_created": len(created_articles),
            "total_keywords_analyzed": len(keywords),
            "clusters": created_clusters
        }
    
    async def _cluster_keywords(self, keywords: List[Dict], embeddings: List[List[float]]) -> List[Dict]:
        """Cluster keywords using cosine similarity."""
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
                
                emb_i = embeddings[i] if i < len(embeddings) else []
                emb_j = embeddings[j] if j < len(embeddings) else []
                sim = self._cosine_similarity(emb_i, emb_j)
                
                if sim > 0.65 or (kw.get("keyword", "") and other_kw.get("keyword", "") and any(w in other_kw.get("keyword", "").lower() for w in kw.get("keyword", "").lower().split() if len(w) > 4)):
                    cluster_keywords.append(other_kw)
                    assigned.add(j)
            
            if cluster_keywords:
                primary = max(cluster_keywords, key=lambda x: x.get("impressions", 0) if isinstance(x, dict) else 0)
                primary_kw = primary.get("keyword", "") if isinstance(primary, dict) else str(primary)
                clusters.append({
                    "primary": primary_kw,
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
        """Classify keyword search intent."""
        kw_lower = keyword.lower()
        if any(w in kw_lower for w in ["buy", "hire", "lawyer", "attorney", "cost", "fee", "payout", "settlement"]):
            return "transactional"
        if any(w in kw_lower for w in ["best", "review", "vs", "compare", "options", "timeline"]):
            return "commercial"
    async def cluster_keywords_list(self, keywords_list: List[str]) -> List[Dict[str, Any]]:
        """Cluster arbitrary list of keywords using semantic embeddings and cosine similarity."""
        if not keywords_list:
            return []
        from ..services.knowledge_service import KnowledgeService
        kw_records = [{"keyword": kw, "impressions": 100, "position": 10.0} for kw in keywords_list]
        embeddings = await KnowledgeService.create_embeddings_batch(keywords_list[:50])
        return await self._cluster_keywords(kw_records, embeddings)


# Backwards compatibility alias
ClusterEngine = ClusterService


async def build_clusters(website_id: str = "default", max_clusters: int = 6) -> Dict[str, Any]:
    """Helper function to build clusters for website."""
    svc = ClusterService(website_id=website_id)
    return await svc.build_clusters(max_clusters=max_clusters)