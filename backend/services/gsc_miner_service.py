import json
import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import get_supabase, get_embedding
from services.gsc_service import GSCService
from services.reporting_service import report_problem

logger = logging.getLogger("backend.services.gsc_miner_service")


class GSCMinerService:
    """AGENT 1 - Mine keywords from GSC, cluster them with NIM embeddings, and persist to topic_clusters + cluster_articles."""

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id

    async def mine_and_cluster(
        self,
        max_clusters: int = 10,
        row_limit: int = 5000,
    ) -> Dict[str, Any]:
        """Mine live GSC keyword data, cluster via NIM cosine similarity > 0.82, and save results."""
        supabase = get_supabase()

        website_url = None
        if self.website_id:
            website = (
                supabase.table("websites")
                .select("domain,gsc_property")
                .eq("id", self.website_id)
                .single()
                .execute()
                .data
            )
            if website:
                website_url = website.get("gsc_property") or f"https://{website.get('domain', '')}"

        gsc_service = GSCService(website_url=website_url)
        if not gsc_service.is_connected():
            return {"error": "Connect GSC"}

        gsc_data = await gsc_service.get_keyword_performance(row_limit=row_limit)
        if gsc_data.get("error"):
            return {"error": "Connect GSC", "detail": gsc_data.get("error")}

        keywords: List[Dict[str, Any]] = gsc_data.get("keywords", [])
        if not keywords:
            return {"error": "Connect GSC", "detail": "No GSC data returned"}

        high_volume_kws = [k for k in keywords if k.get("impressions", 0) >= 10]
        if not high_volume_kws:
            high_volume_kws = keywords[:200]

        texts = [k.get("keyword", "") for k in high_volume_kws]
        embedding_tasks = [self._safe_embed(t) for t in texts]
        embeddings: List[List[float]] = await asyncio.gather(*embedding_tasks)

        clusters = self._cluster_by_cosine(high_volume_kws, embeddings, threshold=0.82)
        created_clusters: List[Dict[str, Any]] = []
        created_articles: List[Dict[str, Any]] = []

        for cluster_data in clusters[:max_clusters]:
            cluster_id = str(uuid.uuid4())
            pillar_keyword = cluster_data["primary"]

            cluster = {
                "id": cluster_id,
                "website_id": self.website_id,
                "cluster_name": pillar_keyword.title(),
                "pillar_keyword": pillar_keyword,
                "keywords": [kw.get("keyword", "") for kw in cluster_data["keywords"]],
                "coverage": 0,
                "authority_score": 0.0,
                "avg_position": 0.0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            supabase.table("topic_clusters").insert(cluster).execute()
            created_clusters.append(cluster)

            for kw in cluster_data["keywords"]:
                article = {
                    "id": str(uuid.uuid4()),
                    "cluster_id": cluster_id,
                    "website_id": self.website_id,
                    "keyword": kw.get("keyword", ""),
                    "intent": self._classify_intent(kw.get("keyword", "")),
                    "business_potential": 0,
                    "search_volume": kw.get("impressions", 0),
                    "current_position": kw.get("position", 0.0),
                    "priority_score": kw.get("impressions", 0) / max(kw.get("position", 1.0), 1.0),
                    "status": "opportunity",
                    "created_at": datetime.utcnow().isoformat(),
                }

                supabase.table("cluster_articles").insert(article).execute()
                created_articles.append(article)

        for c in created_clusters:
            await self._calculate_authority_score(c["id"], supabase)

        high_priority = [a for a in created_articles if a.get("priority_score", 0) > 100]
        for article in high_priority[:10]:
            await report_problem(
                website_id=self.website_id,
                alert_type="keyword_opportunity",
                severity="high",
                title=f"High-priority keyword opportunity: {article['keyword']}",
                description=(
                    f"Impressions={article['search_volume']}, "
                    f"Position={article['current_position']:.1f}, "
                    f"Priority={article['priority_score']:.1f}"
                ),
                data={
                    "keyword": article["keyword"],
                    "cluster_id": article["cluster_id"],
                    "search_volume": article["search_volume"],
                    "current_position": article["current_position"],
                    "priority_score": article["priority_score"],
                },
                source_monitor="gsc_miner_service",
            )

        return {
            "status": "success",
            "clusters_created": len(created_clusters),
            "articles_created": len(created_articles),
            "total_keywords_analyzed": len(high_volume_kws),
            "high_priority_alerts": len(high_priority),
            "source": "gsc_real",
        }

    async def _safe_embed(self, text: str) -> List[float]:
        try:
            return await get_embedding(text, website_id=self.website_id)
        except Exception:
            return [0.0] * 1024

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def _cluster_by_cosine(
        self,
        keywords: List[Dict[str, Any]],
        embeddings: List[List[float]],
        threshold: float = 0.82,
    ) -> List[Dict[str, Any]]:
        clusters: List[Dict[str, Any]] = []
        assigned = set()

        for i, kw in enumerate(keywords):
            if i in assigned:
                continue

            cluster_kws = [kw]
            assigned.add(i)

            for j, other in enumerate(keywords):
                if j in assigned:
                    continue

                sim = self._cosine_similarity(
                    embeddings[i] if i < len(embeddings) else [0.0] * 1024,
                    embeddings[j] if j < len(embeddings) else [0.0] * 1024,
                )

                if sim > threshold:
                    cluster_kws.append(other)
                    assigned.add(j)

            if cluster_kws:
                primary = max(cluster_kws, key=lambda x: x.get("impressions", 0))
                clusters.append(
                    {
                        "primary": primary.get("keyword", ""),
                        "keywords": cluster_kws,
                        "size": len(cluster_kws),
                    }
                )

        return clusters

    def _classify_intent(self, keyword: str) -> str:
        transactional = ["buy", "price", "cost", "discount", "deal", "offer", "trial", "demo", "pricing"]
        informational = ["what is", "how to", "guide", "tutorial", "explain", "definition", "why", "benefits"]
        kw_lower = keyword.lower()
        for tk in transactional:
            if tk in kw_lower:
                return "transactional"
        for ik in informational:
            if ik in kw_lower:
                return "informational"
        return "commercial"

    async def _calculate_authority_score(self, cluster_id: str, supabase) -> float:
        articles = (
            supabase.table("cluster_articles")
            .select("search_volume,current_position")
            .eq("cluster_id", cluster_id)
            .execute()
            .data
            or []
        )

        total = len(articles)
        avg_impressions = sum(a.get("search_volume", 0) for a in articles) / max(total, 1)
        avg_position = sum(a.get("current_position", 0.0) for a in articles) / max(total, 1)

        position_score = max(0.0, 1.0 - (avg_position / 100.0))
        volume_score = min(1.0, avg_impressions / 10000.0)
        authority = (volume_score * 60.0) + (position_score * 40.0)

        supabase.table("topic_clusters").update(
            {
                "authority_score": authority,
                "avg_position": avg_position,
            }
        ).eq("id", cluster_id).execute()

        return authority


async def mine_gsc_keywords(website_id: str, max_clusters: int = 10, row_limit: int = 5000) -> Dict[str, Any]:
    """Standalone function for AGENT 1."""
    service = GSCMinerService(website_id)
    return await service.mine_and_cluster(max_clusters, row_limit)
